import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .connection_manager import connection_manager

# Import the necessary models
from django.apps import apps

logger = logging.getLogger(__name__)

class MoveXConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection"""
        # Accept the connection
        await self.accept()
        self.client_id = None
        logger.info("New WebSocket connection accepted")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self.client_id:
            # Unregister the connection when client disconnects
            connection_manager.unregister_connection(self.client_id)
            logger.info(f"WebSocket disconnected (code: {close_code}): {self.client_id}")

    @database_sync_to_async
    def update_driver_status_in_db(self, driver_id, new_status):
        """Update the driver's status in the database"""
        try:
            # Get the Motorista model dynamically
            Motorista = apps.get_model('usuarios', 'Motorista')
            
            # Find the driver by CPF
            driver = Motorista.objects.filter(cpf=driver_id).first()
            
            if not driver:
                logger.error(f"Driver with CPF {driver_id} not found in database")
                return False, "Motorista não encontrado"
            
            # Map the status from the app to the database status
            status_mapping = {
                'DISPONIVEL': 'DISPONIVEL',
                'ONLINE': 'DISPONIVEL',
                'OFFLINE': 'OFFLINE'
            }
            
            db_status = status_mapping.get(new_status, new_status)
            
            # Record the current status before updating
            old_status = driver.status
            old_disponivel = driver.disponivel
            
            logger.info(f"Updating driver status from {old_status} to {db_status}, disponivel from {old_disponivel} to {db_status == 'DISPONIVEL'}")
            
            # Update the driver's status
            driver.status = db_status
            
            # Set disponível field based on status
            driver.disponivel = (db_status == 'DISPONIVEL')
            
            # Force save - use update method directly to ensure update
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE usuarios_motorista SET status = %s, disponivel = %s WHERE cpf = %s", 
                [db_status, (db_status == 'DISPONIVEL'), driver_id]
            )
            
            # Also save with the model API
            driver.save(update_fields=['status', 'disponivel'])
            
            # Verify changes were applied by refreshing from DB
            driver.refresh_from_db()
            
            logger.info(f"After database update: Status now {driver.status}, disponivel now {driver.disponivel}")
            
            if driver.status != db_status or driver.disponivel != (db_status == 'DISPONIVEL'):
                logger.error("Database update did not apply correctly!")
                return False, "Falha ao atualizar o status no banco de dados"
                
            return True, None
            
        except Exception as e:
            logger.exception(f"Error updating driver status: {str(e)}")
            return False, str(e)

    @database_sync_to_async
    def get_driver_status(self, driver_id):
        """Get the driver's current status from the database"""
        try:
            # Get the Motorista model dynamically
            Motorista = apps.get_model('usuarios', 'Motorista')
            
            # Find the driver by CPF
            driver = Motorista.objects.filter(cpf=driver_id).first()
            
            if not driver:
                logger.error(f"Driver with CPF {driver_id} not found in database")
                return None
            
            # Map DB status to app status format if needed
            return driver.status
            
        except Exception as e:
            logger.exception(f"Error fetching driver status: {str(e)}")
            return None

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # Log incoming message
            if message_type != 'ping':
                logger.debug(f"Received {message_type} message: {text_data}")

            if message_type == 'ping':
                # Handle ping messages with minimal processing
                await self.send(json.dumps({
                    'type': 'pong'
                }))
                return

            if message_type == 'motorista_conectado':
                # Extract client ID (CPF) from connection message
                self.client_id = data.get('cpf')
                if self.client_id:
                    # Register this connection
                    connection_manager.register_connection(self.client_id, self.channel_name)
                    
                    # If client requested current status, fetch it
                    response = {
                        'type': 'connection_success',
                        'message': 'Connected successfully'
                    }
                    
                    # Add current driver status to response if requested
                    if data.get('requestStatus', False):
                        current_status = await self.get_driver_status(self.client_id)
                        if (current_status):
                            response['driverStatus'] = current_status
                            logger.debug(f"Sending current status with connection response: {current_status}")
                    
                    await self.send(json.dumps(response))
                    logger.info(f"Motorista connected with ID: {self.client_id}")
                else:
                    logger.warning("Motorista connection attempt without CPF")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF não fornecido'
                    }))

            elif message_type == 'alterar_status_motorista':
                driver_id = data.get('motoristaId')
                new_status = data.get('status')
                
                logger.info(f"🔄 Status update requested for {driver_id}: {new_status}")
                
                if not self.client_id:
                    self.client_id = driver_id
                    connection_manager.register_connection(self.client_id, self.channel_name)

                # Process status update regardless of throttling
                success, error_message = await self.update_driver_status_in_db(driver_id, new_status)
                
                if success:
                    # Send confirmation with details
                    await self.send(json.dumps({
                        'type': 'status_alterado',
                        'status': new_status,
                        'success': True,
                        'message': f'Status alterado para {new_status}'
                    }))
                    logger.info(f"✅ Driver {driver_id} status changed to {new_status}")
                else:
                    logger.error(f"❌ Failed to update driver status: {error_message}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao atualizar status: {error_message}'
                    }))

            # Handle other message types as needed
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send(json.dumps({
                'type': 'erro',
                'message': 'Formato de mensagem inválido'
            }))
        except Exception as e:
            logger.exception(f"Error in receive: {str(e)}")
            await self.send(json.dumps({
                'type': 'erro',
                'message': f'Erro interno: {str(e)}'
            }))
