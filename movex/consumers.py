import json
import logging
import requests
import time
from collections import defaultdict
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from asgiref.sync import sync_to_async
import datetime

# Importando funções de utils
from .utils import (
    calcular_distancia, 
    is_horario_pico, 
    calcular_valor_corrida, 
    buscar_rota_openroute,
    TARIFA_BASE,
    TARIFA_KM,
    TARIFA_MINUTO,
    TARIFA_MINIMA,
    MULTIPLICADOR_HORARIO_PICO,
    HORARIO_PICO_MANHA_INICIO,
    HORARIO_PICO_MANHA_FIM,
    HORARIO_PICO_TARDE_INICIO,
    HORARIO_PICO_TARDE_FIM,
    calcular_rota_simplificada_melhorada,
    debug_websocket_message
)

# Importando funções de database_services
from .database_services import (
    verificar_corridas_em_andamento,
    buscar_motoristas_disponiveis,
    registrar_corrida,
    aceitar_corrida,
    atualizar_status_motorista,
    buscar_dados_motorista,
    atualizar_localizacao_motorista,
    obter_corrida_em_andamento,
    finalizar_corrida,
    cancelar_corrida,
    registrar_chegada_motorista,
    cancelar_corrida_sem_motoristas,
    iniciar_corrida,
    verificar_corrida_em_andamento_motorista,
    verificar_corrida_em_andamento_passageiro,
    avaliar_motorista,
    avaliar_passageiro,
    obter_dados_avaliacao_corrida,
    atualizar_status_corrida,
    registrar_mensagem_chat,
    obter_mensagens_chat,
    limpar_corrida_da_memoria
)

logger = logging.getLogger(__name__)

# Definindo eventos de alta frequência que não precisam ser logados
FREQUENT_EVENTS = ['ping', 'pong', 'heartbeat', 'atualizar_localizacao', 'app_background']

# Dicionário para rastrear conexões ativas por usuário (CPF)
# Formato: {cpf: {connection_id: timestamp}}
active_connections = defaultdict(dict)

# Dicionário para limitar frequência de solicitações
# Formato: {(cpf, request_type, parameter): last_request_timestamp}
request_rate_limiter = {}

# Configurações de limitação de taxa
RATE_LIMIT_SECONDS = {
    'default': 1,  # 1 segundo entre solicitações padrão
    'solicitar_historico_chat': 5,  # 5 segundos entre solicitações de histórico de chat
    'ping': 0.5,  # 0.5 segundos entre pings
}

# Número máximo de conexões permitidas por usuário
MAX_CONNECTIONS_PER_USER = 3

# Cache para históricos de chat recentemente enviados
# Formato: {(cpf, corrida_id): {'timestamp': time, 'mensagens': data}}
historico_chat_cache = {}
CHAT_CACHE_TTL = 10  # Tempo de vida do cache em segundos

class MoveXConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.user_info = None
        self.room_group_name = 'movex_general'
        self.connection_id = f"{id(self)}"  # ID único para esta conexão
        
        # Adicionar ao grupo geral
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Enviar confirmação de conexão
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Conexão WebSocket estabelecida',
            'connection_id': self.connection_id
        }))
        
        # Log simplificado de conexão
        logger.info(f"Nova conexão WebSocket: {self.connection_id}")
    
    async def disconnect(self, close_code):
        # Remover do grupo geral
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Log simplificado de desconexão com informações de usuário
        user_info = ""
        if self.user_info and 'cpf' in self.user_info:
            cpf = self.user_info['cpf']
            tipo = self.user_info.get('tipo', 'Unknown')
            user_info = f" - {tipo}: {cpf}"
            
            # Remover esta conexão dos registros de conexão ativa
            if cpf in active_connections and self.connection_id in active_connections[cpf]:
                del active_connections[cpf][self.connection_id]
                # Se não houver mais conexões para este usuário, limpe a entrada
                if not active_connections[cpf]:
                    del active_connections[cpf]
        
        logger.info(f"Cliente desconectado{user_info}: código {close_code}")
        
        # Se for um motorista, atualizar status para offline e verificar corridas
        if self.user_info and self.user_info.get('tipo') == 'MOTORISTA':
            await database_sync_to_async(atualizar_status_motorista)(
                self.user_info.get('cpf'), 'OFFLINE', False
            )
            
            # Verificar corridas em andamento deste motorista
            sucesso, passageiros_cpfs = await database_sync_to_async(verificar_corridas_em_andamento)(
                self.user_info.get('cpf')
            )
            
            # Notificar passageiros sobre a desconexão do motorista se necessário
            if sucesso and passageiros_cpfs:
                for passageiro_cpf in passageiros_cpfs:
                    passageiro_group = f'passageiro_{passageiro_cpf}'
                    await self.channel_layer.group_send(
                        passageiro_group,
                        {
                            'type': 'motorista_desconectado',
                            'message': 'O motorista se desconectou temporariamente.'
                        }
                    )
    
    def _check_rate_limit(self, event_type, parameter=None):
        """
        Verifica se uma solicitação está dentro dos limites de taxa
        Retorna True se permitido, False se deve ser limitado
        """
        if not self.user_info or 'cpf' not in self.user_info:
            return True  # Não limitar se não estiver autenticado
        
        cpf = self.user_info['cpf']
        now = time.time()
        
        # Chave única para esta combinação de usuário, tipo de evento e parâmetro
        key = (cpf, event_type, str(parameter) if parameter else None)
        
        # Obter tempo mínimo entre solicitações para este tipo de evento
        min_interval = RATE_LIMIT_SECONDS.get(event_type, RATE_LIMIT_SECONDS['default'])
        
        # Verificar se já existe um registro recente para esta solicitação
        if key in request_rate_limiter:
            last_request = request_rate_limiter[key]
            if now - last_request < min_interval:
                return False  # Muito cedo para outra solicitação
        
        # Atualizar o timestamp da última solicitação
        request_rate_limiter[key] = now
        return True
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            # Log seletivo - evitar logar eventos de alta frequência
            if event_type not in FREQUENT_EVENTS:
                # Identificar o usuário no log caso esteja autenticado
                user_id = f" ({self.user_info['cpf']})" if self.user_info and 'cpf' in self.user_info else ""
                logger.debug(f"Evento{user_id}: {event_type}")
            
            # EVENTOS FREQUENTES - sem logs
            if event_type == 'ping' or event_type == 'heartbeat':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': str(timezone.now())
                }))
                return
                
            # ===== EVENTOS DE MOTORISTA ENVIADOS PELO APP =====
            # Evento quando o motorista avisa que chegou ao local de embarque
            elif event_type == 'aviso_chegada':
                corrida_id = data.get('corridaId') or data.get('corrida_id')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                
                if not corrida_id:
                    logger.error("ID da corrida não fornecido no aviso_chegada")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida é obrigatório'
                    }))
                    return
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem avisar chegada'
                    }))
                    return
                
                logger.info(f"Motorista {motorista_cpf} chegou ao local de embarque da corrida {corrida_id}")
                
                # Registrar chegada no banco de dados
                sucesso = await database_sync_to_async(registrar_chegada_motorista)(
                    corrida_id, motorista_cpf
                )
                
                if not sucesso:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Não foi possível registrar a chegada. Verifique o ID da corrida.'
                    }))
                    return
                
                # Obter o CPF do passageiro para notificação
                try:
                    from corridas.models import Corrida
                    corrida = await database_sync_to_async(Corrida.objects.get)(id=corrida_id)
                    
                    passageiro_cpf = await database_sync_to_async(
                        lambda: corrida.passageiro.usuario.cpf if corrida.passageiro and corrida.passageiro.usuario else None
                    )()
                    
                    if passageiro_cpf:
                        # Confirmar ao motorista
                        await self.send(json.dumps({
                            'type': 'chegada_confirmada',
                            'corridaId': corrida_id,
                            'message': 'Sua chegada foi registrada com sucesso. O passageiro foi notificado.'
                        }))
                        
                        # Notificar o passageiro
                        passageiro_group = f'passageiro_{passageiro_cpf}'
                        await self.channel_layer.group_send(
                            passageiro_group,
                            {
                                'type': 'motorista_chegou',
                                'corridaId': corrida_id
                            }
                        )
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível identificar o passageiro da corrida'
                        }))
                
                except Exception as e:
                    logger.error(f"Erro ao processar aviso de chegada: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao processar aviso de chegada: {str(e)}'
                    }))
                
                return
            
            # Evento quando o motorista se conecta e fica online
            elif event_type == 'motorista_conectado':
                cpf = data.get('cpf')
                if not cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF do motorista é obrigatório'
                    }))
                    return
                
                # Registrar as informações do usuário
                self.user_info = {
                    'cpf': cpf,
                    'tipo': 'MOTORISTA'
                }
                
                logger.info(f"Motorista conectado: {cpf}")
                
                # Verificar e gerenciar conexões para este usuário
                if not self._manage_connections():
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Muitas conexões ativas para este motorista. Esta conexão será encerrada.',
                        'code': 'TOO_MANY_CONNECTIONS'
                    }))
                    await self.close(code=4001)
                    return
                
                # Atualizar status do motorista para DISPONÍVEL
                try:
                    # Verificar status atual para diagnóstico usando operação assíncrona
                    # Função auxiliar assíncrona para verificar status
                    @database_sync_to_async
                    def check_driver_status(driver_cpf):
                        from django.db import connection
                        cursor = connection.cursor()
                        cursor.execute("SELECT status, esta_disponivel FROM usuarios_motorista WHERE cpf = %s", [driver_cpf])
                        return cursor.fetchone()
                    
                    # Função auxiliar para atualização do status
                    @database_sync_to_async
                    def update_driver_status(driver_cpf):
                        from movex.database_services import atualizar_status_motorista
                        return atualizar_status_motorista(driver_cpf, 'DISPONIVEL', True)
                    
                    # Verificar status antes da atualização
                    status_antes = await check_driver_status(cpf)
                    if status_antes:
                        logger.info(f"Status antes da atualização: {status_antes[0]}, disponível: {status_antes[1]}")
                    
                    # Atualizar para DISPONÍVEL
                    success = await update_driver_status(cpf)
                    
                    if success:
                        logger.info(f"Motorista {cpf} definido como DISPONÍVEL após evento motorista_conectado")
                        
                        # Verificar novamente o status após a atualização
                        status_depois = await check_driver_status(cpf)
                        if status_depois:
                            logger.info(f"Status após atualização: {status_depois[0]}, disponível: {status_depois[1]}")
                    else:
                        logger.error(f"Falha ao definir motorista {cpf} como disponível")
                        
                except Exception as e:
                    logger.error(f"Erro ao atualizar status do motorista: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                # Adicionar motorista ao grupo específico para receber notificações
                motorista_group = f'motorista_{cpf}'
                await self.channel_layer.group_add(
                    motorista_group,
                    self.channel_name
                )
                
                # Confirmar ao motorista que ele está conectado e disponível
                await self.send(text_data=json.dumps({
                    'type': 'status_atualizado',
                    'status': 'DISPONIVEL',
                    'disponivel': True,
                    'message': 'Você está online e disponível para receber corridas.'
                }))
                
                # Verificar se há corridas em andamento para este motorista (se solicitado)
                if data.get('verificar_corrida_ativa', False):
                    corrida_em_andamento = await database_sync_to_async(verificar_corrida_em_andamento_motorista)(cpf)
                    if corrida_em_andamento:
                        await self.send(text_data=json.dumps({
                            'type': 'corrida_em_andamento',
                            'corridaId': str(corrida_em_andamento.get('id')),
                            'passageiro': corrida_em_andamento.get('passageiro'),
                            'origem': corrida_em_andamento.get('origem'),
                            'destino': corrida_em_andamento.get('destino'),
                            'status': corrida_em_andamento.get('status'),
                            'valor': corrida_em_andamento.get('valor')
                        }))
                
                return
            
            # Evento periódico de status do motorista
            elif event_type == 'motorista_status':
                cpf = data.get('cpf')
                status = data.get('status')
                disponivel = data.get('disponivel')
                em_corrida = data.get('em_corrida')
                
                if not cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF do motorista é obrigatório'
                    }))
                    return
                
                # Se não tiver informação de usuário ainda, registrar
                if not self.user_info:
                    self.user_info = {
                        'cpf': cpf,
                        'tipo': 'MOTORISTA'
                    }
                    
                    # Adicionar motorista ao grupo apropriado
                    motorista_group = f'motorista_{cpf}'
                    await self.channel_layer.group_add(
                        motorista_group,
                        self.channel_name
                    )
                
                # Determinar o status no banco de dados com base nas informações enviadas
                db_status = 'DISPONIVEL'
                if status == 'offline':
                    db_status = 'OFFLINE'
                elif em_corrida:
                    db_status = 'EM_CORRIDA'
                
                # Atualizar status no banco de dados (sem logs extensivos para este evento periódico)
                await database_sync_to_async(atualizar_status_motorista)(
                    cpf, db_status, disponivel
                )
                
                # Responder com sucesso (sem logs para não sobrecarregar)
                await self.send(json.dumps({
                    'type': 'status_atualizado',
                    'status': db_status,
                    'disponivel': disponivel,
                    'timestamp': str(timezone.now())
                }))
                
                return
            
            # Evento quando o motorista fica disponível após finalizar uma corrida
            elif event_type == 'motorista_disponivel':
                cpf = data.get('cpf')
                
                if not cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF do motorista é obrigatório'
                    }))
                    return
                
                logger.info(f"Motorista {cpf} sinalizou disponibilidade")
                
                # Função auxiliar assíncrona para verificar status
                @database_sync_to_async
                def check_driver_status(driver_cpf):
                    from django.db import connection
                    cursor = connection.cursor()
                    cursor.execute("SELECT status, esta_disponivel FROM usuarios_motorista WHERE cpf = %s", [driver_cpf])
                    return cursor.fetchone()
                
                # Função auxiliar para atualização do status
                @database_sync_to_async
                def update_driver_status(driver_cpf):
                    from movex.database_services import atualizar_status_motorista
                    return atualizar_status_motorista(driver_cpf, 'DISPONIVEL', True)
                
                # Atualizar status para DISPONÍVEL
                success = await update_driver_status(cpf)
                
                # Verificar status atual
                status_atual = await check_driver_status(cpf)
                
                if status_atual:
                    logger.info(f"Status atual do motorista {cpf}: {status_atual[0]}, disponível: {status_atual[1]}")
                
                # Confirmar que o motorista está disponível
                await self.send(text_data=json.dumps({
                    'type': 'status_atualizado',
                    'status': 'DISPONIVEL',
                    'disponivel': True,
                    'message': 'Você agora está disponível para receber novas corridas.'
                }))
                
                return
            
            # EVENTOS DE LOGIN E AUTENTICAÇÃO
            elif event_type == 'login':
                cpf = data.get('cpf')
                tipo_usuario = data.get('tipo')
                
                if not cpf or not tipo_usuario:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF e tipo de usuário são obrigatórios para o login'
                    }))
                    return
                
                # Registrar as informações do usuário
                self.user_info = {
                    'cpf': cpf,
                    'tipo': tipo_usuario
                }
                
                # Log simplificado de login
                logger.info(f"Login WebSocket: {tipo_usuario} {cpf}")
                
                # Verificar e gerenciar conexões para este usuário
                if not self._manage_connections():
                    # Enviar mensagem de aviso e fechar conexão
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Muitas conexões ativas para este usuário. Esta conexão será encerrada.',
                        'code': 'TOO_MANY_CONNECTIONS'
                    }))
                    await self.close(code=4001)  # Código personalizado
                    return
                
                if tipo_usuario == 'MOTORISTA':
                    # AQUI É O LOCAL CORRETO para atualizar o status do motorista para DISPONÍVEL
                    # pois a conexão WebSocket já foi estabelecida
                    try:
                        # Primeiro, obtenha o status atual para diagnóstico
                        from django.db import connection
                        cursor = connection.cursor()
                        cursor.execute("SELECT status, esta_disponivel FROM usuarios_motorista WHERE cpf = %s", [cpf])
                        status_antes = cursor.fetchone()
                        if status_antes:
                            logger.info(f"Status antes da atualização: {status_antes[0]}, disponível: {status_antes[1]}")
                        
                        # Agora atualize para DISPONÍVEL
                        success = await database_sync_to_async(atualizar_status_motorista)(
                            cpf, 'DISPONIVEL', True
                        )
                        
                        if success:
                            logger.info(f"Motorista {cpf} ficou DISPONÍVEL com sucesso após conexão WebSocket")
                            
                            # Verificar novamente o status após a atualização
                            cursor = connection.cursor()
                            cursor.execute("SELECT status, esta_disponivel FROM usuarios_motorista WHERE cpf = %s", [cpf])
                            status_depois = cursor.fetchone()
                            if status_depois:
                                logger.info(f"Status após atualização: {status_depois[0]}, disponível: {status_depois[1]}")
                        else:
                            logger.error(f"FALHA ao definir motorista {cpf} como disponível")
                            
                    except Exception as e:
                        logger.error(f"Erro ao atualizar status do motorista: {str(e)}")
                        import traceback
                        logger.error(traceback.format_exc())
                    
                    # Adicionar motorista ao grupo específico para receber notificações
                    motorista_group = f'motorista_{cpf}'
                    await self.channel_layer.group_add(
                        motorista_group,
                        self.channel_name
                    )
                    
                    # Notificar o motorista sobre seu status atual
                    await self.send(text_data=json.dumps({
                        'type': 'status_atualizado',
                        'status': 'DISPONIVEL',
                        'disponivel': True,
                        'message': 'Você está online e disponível para receber corridas.'
                    }))
                
                elif tipo_usuario == 'PASSAGEIRO':
                    # Adicionar passageiro ao grupo específico
                    passageiro_group = f'passageiro_{cpf}'
                    await self.channel_layer.group_add(
                        passageiro_group,
                        self.channel_name
                    )
                
                # Confirmar login bem-sucedido
                await self.send(text_data=json.dumps({
                    'type': 'login_success',
                    'message': f'Login WebSocket bem-sucedido como {tipo_usuario}',
                    'connection_id': self.connection_id
                }))
                return
            
            # EVENTO PARA CÁLCULO DE ROTA
            elif event_type == 'calcular_rota':
                if not self._check_rate_limit('calcular_rota'):
                    await self.send(json.dumps({
                        'type': 'rate_limited',
                        'message': 'Muitas solicitações recentes. Por favor, aguarde alguns segundos.',
                        'request_type': 'calcular_rota'
                    }))
                    return
                
                # Log simplificado - coordenadas resumidas
                try:
                    start_lat = float(data.get('start_lat'))
                    start_lng = float(data.get('start_lng'))
                    end_lat = float(data.get('end_lat'))
                    end_lng = float(data.get('end_lng'))
                    
                    # Apenas um log resumido e uma vez
                    logger.info(f"Calculando rota: [{start_lat:.6f},{start_lng:.6f}] → [{end_lat:.6f},{end_lng:.6f}]")
                    
                    # Usar a função buscar_rota_openroute
                    resultado_rota = await buscar_rota_openroute(
                        start_lat, start_lng, end_lat, end_lng
                    )
                    
                    if resultado_rota and resultado_rota['success']:
                        if len(resultado_rota['coordinates']) < 2:
                            resultado_rota = calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)
                        
                        # Enviar resultado ao cliente
                        await self.send(json.dumps({
                            'type': 'rota_calculada',
                            'distancia': resultado_rota['distancia'],
                            'tempo_estimado': resultado_rota['tempo_estimado'],
                            'valor': resultado_rota['valor'],
                            'coordinates': resultado_rota['coordinates'],
                            'horario_pico': is_horario_pico(),
                            'origem': {'latitude': start_lat, 'longitude': start_lng},
                            'destino': {'latitude': end_lat, 'longitude': end_lng}
                        }))
                    else:
                        # Método alternativo
                        resultado_rota = calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)
                        
                        await self.send(json.dumps({
                            'type': 'rota_calculada',
                            'distancia': resultado_rota['distancia'],
                            'tempo_estimado': resultado_rota['tempo_estimado'],
                            'valor': resultado_rota['valor'],
                            'coordinates': resultado_rota['coordinates'],
                            'horario_pico': is_horario_pico(),
                            'modo_calculo': 'simplificado_melhorado',
                            'origem': {'latitude': start_lat, 'longitude': start_lng},
                            'destino': {'latitude': end_lat, 'longitude': end_lng}
                        }))
                except Exception as e:
                    logger.error(f"Erro ao calcular rota: {str(e)}")
                    
                    # Tentar método alternativo em caso de erro
                    try:
                        resultado_rota = calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)
                        
                        await self.send(json.dumps({
                            'type': 'rota_calculada',
                            'distancia': resultado_rota['distancia'],
                            'tempo_estimado': resultado_rota['tempo_estimado'],
                            'valor': resultado_rota['valor'],
                            'coordinates': resultado_rota['coordinates'],
                            'horario_pico': is_horario_pico(),
                            'modo_calculo': 'emergencia',
                            'origem': {'latitude': start_lat, 'longitude': start_lng},
                            'destino': {'latitude': end_lat, 'longitude': end_lng}
                        }))
                    except Exception as e2:
                        # Informar o cliente sobre o erro
                        await self.send(json.dumps({
                            'type': 'erro_rota',
                            'message': f'Erro ao calcular rota: {str(e)}'
                        }))
                
                return
            
            # EVENTO PARA SOLICITAR CORRIDA
            elif event_type == 'solicitar_corrida':
                # Log simplificado com informações essenciais
                passageiro_data = data.get('passageiro', {})
                origem = data.get('origem', {})
                destino = data.get('destino', {})
                
                # Um único log com informações resumidas
                logger.info(f"Nova corrida: {passageiro_data.get('nome')} {passageiro_data.get('sobrenome')}, " +
                           f"Distância: {data.get('distancia', 0):.2f}km, Valor: R${data.get('valor', 0)}")
                
                # Verificar campos obrigatórios
                campos_obrigatorios = ['passageiro', 'origem', 'destino', 'valor', 'distancia', 'tempo_estimado']
                campos_faltantes = [campo for campo in campos_obrigatorios if campo not in data]
                
                if campos_faltantes:
                    logger.error(f"Campos obrigatórios faltando: {', '.join(campos_faltantes)}")
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': f'Campos obrigatórios faltando: {", ".join(campos_faltantes)}'
                    }))
                    return
                
                # Verificar dados do passageiro
                campos_passageiro_obrigatorios = ['cpf', 'nome', 'sobrenome', 'telefone']
                campos_passageiro_faltantes = [campo for campo in campos_passageiro_obrigatorios 
                                              if campo not in passageiro_data or not passageiro_data.get(campo)]
                
                if campos_passageiro_faltantes:
                    logger.error(f"Campos do passageiro faltando: {', '.join(campos_passageiro_faltantes)}")
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': f'Dados do passageiro incompletos: {", ".join(campos_passageiro_faltantes)}'
                    }))
                    return
                
                # Verificar coordenadas
                origem = data.get('origem', {})
                destino = data.get('destino', {})
                
                if not origem.get('latitude') or not origem.get('longitude') or not destino.get('latitude') or not destino.get('longitude'):
                    logger.error("Coordenadas inválidas ou ausentes")
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Coordenadas de origem ou destino inválidas'
                    }))
                    return
                
                # Preparar dados para registro
                origem_descricao = data.get('origem_descricao', 'Local de origem')
                destino_descricao = data.get('destino_descricao', 'Local de destino')
                passageiro_cpf = passageiro_data.get('cpf')
                data['passageiro_cpf'] = passageiro_cpf
                
                # Registrar corrida no banco de dados
                corrida_id = await database_sync_to_async(registrar_corrida)(data)
                
                if not corrida_id:
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Erro ao registrar a corrida.'
                    }))
                    return
                
                logger.info(f"Corrida registrada: ID {corrida_id}")
                
                # Buscar motoristas disponíveis
                motoristas_disponiveis = await database_sync_to_async(buscar_motoristas_disponiveis)(
                    lat=data.get('origem', {}).get('latitude'),
                    lng=data.get('origem', {}).get('longitude')
                )
                
                if not motoristas_disponiveis:
                    # Cancelar corrida automaticamente se não houver motoristas
                    await database_sync_to_async(cancelar_corrida_sem_motoristas)(corrida_id)
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Não há motoristas disponíveis no momento.'
                    }))
                    return
                
                # Confirmar registro ao passageiro
                await self.send(json.dumps({
                    'type': 'corrida_registrada',
                    'corridaId': str(corrida_id),
                    'message': 'Corrida registrada com sucesso, buscando motorista...'
                }))
                
                # Log resumido dos motoristas disponíveis
                logger.info(f"Notificando {len(motoristas_disponiveis)} motoristas disponíveis sobre nova corrida")
                
                # Notificar motoristas disponíveis
                for motorista in motoristas_disponiveis:
                    motorista_group = f'motorista_{motorista["cpf"]}'
                    
                    await self.channel_layer.group_send(
                        motorista_group,
                        {
                            'type': 'nova_solicitacao_corrida',
                            'corridaId': str(corrida_id),
                            'passageiro': data.get('passageiro'),
                            'origem': data.get('origem'),
                            'destino': data.get('destino'),
                            'origem_descricao': origem_descricao,
                            'destino_descricao': destino_descricao,
                            'valor': data.get('valor'),
                            'distancia': data.get('distancia'),
                            'tempo_estimado': data.get('tempo_estimado')
                        }
                    )
                
                return

            # EVENTO PARA ACEITAR CORRIDA
            elif event_type == 'aceitar_corrida':
                # Aceitar tanto corridaId quanto corrida_id
                corrida_id = data.get('corridaId') or data.get('corrida_id')
                motorista_data = data.get('motorista', {})
                status = data.get('status', 'ACEITA')
                
                # Verificar se o ID da corrida foi fornecido
                if not corrida_id:
                    logger.error("ID da corrida não fornecido")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido'
                    }))
                    return
                
                # Obter CPF do motorista do payload ou das informações de usuário
                motorista_cpf = motorista_data.get('cpf') or motorista_data.get('id')
                
                # Se não houver CPF no payload, usar o CPF do usuário autenticado
                if not motorista_cpf:
                    motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                
                logger.info(f"Motorista {motorista_cpf} aceitando corrida {corrida_id}")

                if not motorista_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Motorista não identificado'
                    }))
                    return

                # Atualizar corrida com o motorista que aceitou
                sucesso, passageiro_cpf, outros_motoristas = await database_sync_to_async(aceitar_corrida)(
                    corrida_id, motorista_cpf, status
                )

                if sucesso:
                    # Notificar o motorista que aceitou
                    await self.send(json.dumps({
                        'type': 'corrida_aceita',
                        'corridaId': corrida_id,
                        'message': 'Você aceitou a corrida com sucesso!'
                    }))

                    # Notificar o passageiro sobre a aceitação
                    if passageiro_cpf:
                        passageiro_group = f'passageiro_{passageiro_cpf}'

                        # Se temos os dados do motorista no payload, usá-los
                        if motorista_data and motorista_data.get('nome'):
                            motorista_dados = {
                                'cpf': motorista_data.get('cpf', ''),
                                'nome': motorista_data.get('nome', 'Motorista'),  # Garantir um valor padrão
                                'sobrenome': motorista_data.get('sobrenome', ''),
                                'telefone': motorista_data.get('telefone', ''),
                                'veiculo': {
                                    'modelo': motorista_data.get('modeloCarro', ''),
                                    'cor': motorista_data.get('corCarro', ''),
                                    'placa': motorista_data.get('placaCarro', '')
                                },
                                'avaliacao': motorista_data.get('avaliacao', 0),
                                'foto': motorista_data.get('foto', '')
                            }
                        else:
                            # Caso contrário, buscar do banco de dados
                            motorista_dados = await database_sync_to_async(buscar_dados_motorista)(motorista_cpf)
                            # Garantir que nome esteja presente
                            if not motorista_dados.get('nome'):
                                motorista_dados['nome'] = 'Motorista'

                        await self.channel_layer.group_send(
                            passageiro_group,
                            {
                                'type': 'corrida_aceita',
                                'corridaId': corrida_id,
                                'motorista': motorista_dados
                            }
                        )

                    # Notificar outros motoristas que a corrida foi aceita
                    for outro_cpf in outros_motoristas:
                        motorista_group = f'motorista_{outro_cpf}'
                        await self.channel_layer.group_send(
                            motorista_group,
                            {
                                'type': 'corrida_aceita_por_outro',
                                'corridaId': corrida_id,
                                'message': 'A corrida foi aceita por outro motorista.'
                            }
                        )
                else:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Não foi possível aceitar a corrida. Ela pode já ter sido aceita por outro motorista.'
                    }))
                
                return
            
            # EVENTO PARA INICIAR CORRIDA
            elif event_type == 'iniciar_corrida':
                corrida_id = data.get('corridaId')
                motorista_cpf = data.get('motoristaCpf') or (self.user_info.get('cpf') if self.user_info else None)

                if not corrida_id or not motorista_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'corridaId e motoristaCpf são obrigatórios'
                    }))
                    return

                try:
                    sucesso, passageiro_cpf = await database_sync_to_async(iniciar_corrida)(corrida_id, motorista_cpf)
                    if sucesso:
                        await self.send(json.dumps({
                            'type': 'corrida_iniciada',
                            'corridaId': corrida_id,
                            'message': 'Corrida iniciada com sucesso'
                        }))
                        if passageiro_cpf:
                            passageiro_group = f'passageiro_{passageiro_cpf}'
                            await self.channel_layer.group_send(
                                passageiro_group,
                                {
                                    'type': 'corrida_iniciada',
                                    'corridaId': corrida_id,
                                    'message': 'Sua corrida foi iniciada!'
                                }
                            )
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível iniciar a corrida'
                        }))
                except Exception as e:
                    logger.error(f"Erro ao iniciar corrida: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao iniciar corrida: {str(e)}'
                    }))
                return

            # EVENTO PARA FINALIZAR CORRIDA
            elif event_type == 'finalizar_corrida':
                corrida_id = data.get('corridaId')
                motorista_cpf = data.get('motoristaId') or (self.user_info.get('cpf') if self.user_info else None)

                if not corrida_id or not motorista_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'corridaId e motoristaId são obrigatórios'
                    }))
                    return

                try:
                    sucesso, passageiro_cpf = await database_sync_to_async(finalizar_corrida)(corrida_id, motorista_cpf)
                    if sucesso:
                        await self.send(json.dumps({
                            'type': 'corrida_finalizada',
                            'corridaId': corrida_id,
                            'message': 'Corrida finalizada com sucesso'
                        }))
                        if passageiro_cpf:
                            passageiro_group = f'passageiro_{passageiro_cpf}'
                            await self.channel_layer.group_send(
                                passageiro_group,
                                {
                                    'type': 'corrida_finalizada_por_motorista',
                                    'corridaId': corrida_id,
                                    'message': 'O motorista finalizou a corrida.'
                                }
                            )
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível finalizar a corrida'
                        }))
                except Exception as e:
                    logger.error(f"Erro ao finalizar corrida: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao finalizar corrida: {str(e)}'
                    }))
                return

            # EVENTOS PARA ATUALIZAÇÕES DE LOCALIZAÇÃO - Reduzir logs
            elif event_type == 'atualizar_localizacao':
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem atualizar localização'
                    }))
                    return
                
                # Verificar múltiplos formatos de localização
                latitude_str = data.get('latitude')
                longitude_str = data.get('longitude')
                
                if not latitude_str or not longitude_str:
                    location = data.get('location', {})
                    if isinstance(location, dict):
                        latitude_str = location.get('latitude')
                        longitude_str = location.get('longitude')
                
                if not latitude_str or not longitude_str:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Latitude e longitude são obrigatórios'
                    }))
                    return
                
                try:
                    latitude = float(latitude_str)
                    longitude = float(longitude_str)
                except ValueError:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Latitude e longitude devem ser numéricos'
                    }))
                    return
                
                # Atualizar localização no banco sem logs
                await database_sync_to_async(atualizar_localizacao_motorista)(
                    motorista_cpf, latitude, longitude
                )
                
                # Verificar corridas em andamento para notificação
                corrida_atual = await database_sync_to_async(obter_corrida_em_andamento)(motorista_cpf)
                
                # Notificar passageiro se existir corrida em andamento
                if corrida_atual and corrida_atual.get('passageiro_cpf'):
                    passageiro_group = f'passageiro_{corrida_atual["passageiro_cpf"]}'
                    
                    await self.channel_layer.group_send(
                        passageiro_group,
                        {
                            'type': 'localizacao_atualizada',
                            'corridaId': corrida_atual.get('corrida_id'),
                            'latitude': latitude,
                            'longitude': longitude
                        }
                    )
                
                # Responder com sucesso (sem logs)
                await self.send(json.dumps({
                    'type': 'localizacao_atualizada',
                    'message': 'Localização atualizada com sucesso'
                }))
                
            # EVENTOS DE CHAT - Otimizar logs
            elif event_type == 'mensagem_chat':
                corrida_id = data.get('corridaId')
                remetente_tipo = data.get('remetente')  # 'PASSAGEIRO' ou 'MOTORISTA'
                conteudo = data.get('conteudo')

                # Validar dados
                if not corrida_id or not remetente_tipo or not conteudo:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Dados incompletos para envio de mensagem'
                    }))
                    return

                # Validar tipo de remetente
                if remetente_tipo not in ['PASSAGEIRO', 'MOTORISTA']:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Tipo de remetente inválido'
                    }))
                    return

                # Registrar a mensagem no banco de dados
                mensagem = await database_sync_to_async(registrar_mensagem_chat)(
                    corrida_id, remetente_tipo, conteudo
                )

                if not mensagem:
                    logger.error(f"Erro ao registrar mensagem para corrida {corrida_id}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Erro ao registrar mensagem'
                    }))
                    return

                # Log simplificado da mensagem
                logger.info(f"Mensagem chat: corrida {corrida_id}, de {remetente_tipo[:3]}")
                
                # Determinar o destinatário da mensagem
                try:
                    from corridas.models import Corrida
                    corrida = await database_sync_to_async(Corrida.objects.get)(id=corrida_id)

                    # Obter CPFs do motorista e passageiro
                    motorista_cpf = await database_sync_to_async(
                        lambda: corrida.motorista.usuario.cpf if corrida.motorista and corrida.motorista.usuario else None
                    )()
                    
                    passageiro_cpf = await database_sync_to_async(
                        lambda: corrida.passageiro.usuario.cpf if corrida.passageiro and corrida.passageiro.usuario else None
                    )()

                    # Enviar mensagem para o destinatário apropriado
                    if remetente_tipo == 'PASSAGEIRO' and motorista_cpf:
                        destinatario_grupo = f'motorista_{motorista_cpf}'
                        destinatario_tipo = 'MOTORISTA'
                    elif remetente_tipo == 'MOTORISTA' and passageiro_cpf:
                        destinatario_grupo = f'passageiro_{passageiro_cpf}'
                        destinatario_tipo = 'PASSAGEIRO'
                    else:
                        logger.error(f"Não foi possível determinar o destinatário da mensagem")
                        destinatario_grupo = None
                        destinatario_tipo = None

                    # Confirmar o envio ao remetente
                    await self.send(json.dumps({
                        'type': 'mensagem_enviada',
                        'corridaId': corrida_id,
                        'id': str(mensagem.id),
                        'conteudo': conteudo,
                        'data': mensagem.data_envio.isoformat(),
                        'remetente': remetente_tipo
                    }))

                    # Encaminhar a mensagem ao destinatário
                    if destinatario_grupo:
                        await self.channel_layer.group_send(
                            destinatario_grupo,
                            {
                                'type': 'nova_mensagem_chat',
                                'corridaId': corrida_id,
                                'id': str(mensagem.id),
                                'conteudo': conteudo,
                                'data': mensagem.data_envio.isoformat(),
                                'remetente': remetente_tipo
                            }
                        )

                except Exception as e:
                    logger.error(f"Erro ao encaminhar mensagem de chat: {str(e)}")
            
            # EVENTO PARA AVALIAR MOTORISTA
            elif event_type == 'avaliar_motorista':
                corrida_id = data.get('corridaId')
                avaliacao = data.get('avaliacao')
                comentario = data.get('comentario')
                passageiro_cpf = data.get('passageiroCpf') or (self.user_info.get('cpf') if self.user_info else None)

                if not corrida_id or not avaliacao or not passageiro_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'corridaId, avaliacao e passageiroCpf são obrigatórios'
                    }))
                    return

                try:
                    sucesso, motorista_cpf = await database_sync_to_async(avaliar_motorista)(corrida_id, passageiro_cpf, avaliacao, comentario)
                    if sucesso:
                        await self.send(json.dumps({
                            'type': 'avaliacao_motorista_sucesso',
                            'corridaId': corrida_id,
                            'message': 'Avaliação do motorista registrada com sucesso.'
                        }))
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível registrar a avaliação do motorista.'
                        }))
                except Exception as e:
                    logger.error(f"Erro ao avaliar motorista: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao avaliar motorista: {str(e)}'
                    }))
                return

            # ... outros manipuladores de eventos ...
                
        except json.JSONDecodeError:
            logger.error("Erro ao decodificar JSON da mensagem recebida")
            await self.send(json.dumps({
                'type': 'erro',
                'message': 'Formato de mensagem inválido'
            }))
        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {str(e)}")
            await self.send(json.dumps({
                'type': 'erro',
                'message': f'Erro ao processar solicitação: {str(e)}'
            }))

    # Métodos para enviar mensagens específicas entre grupos
    async def nova_solicitacao_corrida(self, event):
        try:
            # Log simplificado da nova solicitação
            logger.info(f"Enviando solicitação de corrida para motorista")
            
            # Criar mensagem simplificada
            mensagem = {
                'type': 'nova_corrida',  # Para compatibilidade com app motorista
                'corridaId': event.get('corridaId', ''),
                'passageiro': event.get('passageiro', {}),
                'origem': event.get('origem', {}),
                'destino': event.get('destino', {}),
                'origem_descricao': event.get('origem_descricao', 'Local de origem'),
                'destino_descricao': event.get('destino_descricao', 'Local de destino'),
                'valor': event.get('valor', 0),
                'distancia': event.get('distancia', 0),
                'tempo_estimado': event.get('tempo_estimado', '0 min')
            }
            
            # Enviar a mensagem
            await self.send(json.dumps(mensagem))
            
        except Exception as e:
            logger.error(f"Erro ao enviar nova solicitação de corrida: {str(e)}")
            # Tentar enviar versão mínima como fallback
            try:
                mensagem_minima = {
                    'type': 'nova_corrida',
                    'corridaId': event.get('corridaId', ''),
                    'passageiro': {
                        'nome': event.get('passageiro', {}).get('nome', 'Passageiro')
                    },
                    'origem': {
                        'latitude': event.get('origem', {}).get('latitude', 0),
                        'longitude': event.get('origem', {}).get('longitude', 0)
                    },
                    'destino': {
                        'latitude': event.get('destino', {}).get('latitude', 0),
                        'longitude': event.get('destino', {}).get('longitude', 0)
                    },
                    'valor': event.get('valor', 0),
                    'distancia': event.get('distancia', 0),
                    'tempo_estimado': event.get('tempo_estimado', '0 min')
                }
                await self.send(json.dumps(mensagem_minima))
                logger.warning("Enviada mensagem mínima como fallback")
            except Exception as fallback_error:
                logger.error(f"Erro ao enviar mensagem mínima: {str(fallback_error)}")

    # Função utilitária para gerenciar conexões
    def _manage_connections(self):
        """
        Gerencia as conexões ativas para este usuário
        Retorna True se a conexão atual é permitida, False se deve ser encerrada
        """
        if not self.user_info or 'cpf' not in self.user_info:
            return True  # Não gerenciar se não estiver autenticado
        
        cpf = self.user_info['cpf']
        now = time.time()
        
        # Registrar esta conexão
        active_connections[cpf][self.connection_id] = now
        
        # Log simplificado de conexões
        total_connections = len(active_connections[cpf])
        if total_connections > 1:
            logger.info(f"Usuário {cpf} tem {total_connections} conexões ativas")
        
        # Se o usuário tem muitas conexões, manter apenas as mais recentes
        if total_connections > MAX_CONNECTIONS_PER_USER:
            # Ordenar conexões por timestamp (mais antigas primeiro)
            sorted_connections = sorted(
                active_connections[cpf].items(), 
                key=lambda x: x[1]
            )
            
            # Verificar se esta conexão está entre as mais recentes
            # Se não estiver nas N conexões mais recentes, encerrar
            recent_connections = dict(sorted_connections[-MAX_CONNECTIONS_PER_USER:])
            if self.connection_id not in recent_connections:
                logger.warning(f"Excesso de conexões para {cpf}. Esta conexão será encerrada.")
                return False
            
            # Limpar conexões antigas
            active_connections[cpf] = recent_connections
            logger.info(f"Mantidas apenas {len(recent_connections)} conexões recentes para {cpf}")
        
        return True

    # Handler para a notificação de desconexão do motorista (enviado a passageiros)
    async def motorista_desconectado(self, event):
        await self.send(text_data=json.dumps({
            'type': 'motorista_desconectado',
            'message': event.get('message', 'O motorista se desconectou temporariamente.'),
            'timestamp': str(timezone.now())
        }))
        
    # Handler para corrida aceita pelo motorista (enviado ao passageiro)
    async def corrida_aceita_por_motorista(self, event):
        # Obter os dados do motorista do evento
        motorista_dados = event.get('motorista', {})
        
        # Reformatar os dados do motorista para o formato esperado pelo app do passageiro
        motorista_reformatado = {}
        
        # Verificar se há dados do motorista
        if motorista_dados:
            # Dados básicos do motorista
            motorista_reformatado = {
                'cpf': motorista_dados.get('cpf', ''),
                'nome': motorista_dados.get('nome', ''),
                'sobrenome': motorista_dados.get('sobrenome', ''),
                'telefone': motorista_dados.get('telefone', ''),
            }
            
            # Adicionar dados do veículo diretamente no objeto do motorista
            # Se estiverem em um subobjeto veiculo, extraí-los
            if 'veiculo' in motorista_dados and isinstance(motorista_dados['veiculo'], dict):
                veiculo = motorista_dados['veiculo']
                motorista_reformatado['modeloCarro'] = veiculo.get('modelo', '')
                motorista_reformatado['corCarro'] = veiculo.get('cor', '')
                motorista_reformatado['placaCarro'] = veiculo.get('placa', '')
            else:
                # Se não estiverem em um subobjeto, procurar diretamente ou usar valores padrão
                motorista_reformatado['modeloCarro'] = motorista_dados.get('modeloCarro', '')
                motorista_reformatado['corCarro'] = motorista_dados.get('corCarro', '')
                motorista_reformatado['placaCarro'] = motorista_dados.get('placaCarro', '')
            
            # Adicionar avaliação e foto se disponíveis
            if 'avaliacao' in motorista_dados:
                motorista_reformatado['avaliacao'] = motorista_dados.get('avaliacao')
            if 'foto' in motorista_dados:
                motorista_reformatado['foto'] = motorista_dados.get('foto')
        
        # Enviar a mensagem no formato esperado pelo cliente
        await self.send(text_data=json.dumps({
            'type': 'corrida_aceita',
            'corridaId': event.get('corridaId'),
            'motorista': motorista_reformatado,
            'message': 'Um motorista aceitou sua solicitação de corrida.'
        }))
    
    # Handler para corrida aceita por outro motorista (enviado a outros motoristas)
    async def corrida_aceita_por_outro(self, event):
        await self.send(text_data=json.dumps({
            'type': 'corrida_indisponivel',
            'corridaId': event.get('corridaId'),
            'message': event.get('message', 'A corrida foi aceita por outro motorista.')
        }))
    
    # Handler para atualização de localização (enviado ao passageiro)
    async def localizacao_atualizada(self, event):
        await self.send(text_data=json.dumps({
            'type': 'localizacao_motorista_atualizada',
            'corridaId': event.get('corridaId'),
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude')
        }))
    
    # Handler para nova mensagem de chat
    async def nova_mensagem_chat(self, event):
        await self.send(text_data=json.dumps({
            'type': 'nova_mensagem',
            'corridaId': event.get('corridaId'),
            'id': event.get('id'),
            'conteudo': event.get('conteudo'),
            'data': event.get('data'),
            'remetente': event.get('remetente')
        }))
    
    # Handler para notificação de chegada do motorista (enviado ao passageiro)
    async def motorista_chegou(self, event):
        # Garantir que o objeto enviado ao passageiro tenha todas as informações necessárias
        corridaId = event.get('corridaId')
        
        # Preparar um objeto completo e consistente
        mensagem_chegada = {
            'type': 'motorista_chegou',
            'corridaId': corridaId,
            'message': 'O motorista chegou ao local de embarque.',
            'timestamp': str(timezone.now())
        }
        
        # Adicionar informações do motorista se disponíveis
        if event.get('motorista'):
            motorista_dados = event.get('motorista', {})
            
            # Inicializar o objeto motorista com valores padrão
            motorista_info = {
                'cpf': '',
                'nome': 'Motorista',  # Valor padrão para nome
                'sobrenome': '',
                'telefone': '',
                'modeloCarro': '',
                'corCarro': '',
                'placaCarro': '',
                'avaliacao': 0,
                'foto': ''
            }
            
            # Atualizar com os dados disponíveis
            if motorista_dados:
                motorista_info.update({
                    'cpf': motorista_dados.get('cpf', ''),
                    'telefone': motorista_dados.get('telefone', '')
                })
                
                # Nome e sobrenome com tratamento especial
                if motorista_dados.get('nome'):
                    motorista_info['nome'] = motorista_dados.get('nome')
                if motorista_dados.get('sobrenome'):
                    motorista_info['sobrenome'] = motorista_dados.get('sobrenome')
                
                # Veículo
                if 'veiculo' in motorista_dados and isinstance(motorista_dados['veiculo'], dict):
                    veiculo = motorista_dados['veiculo']
                    motorista_info.update({
                        'modeloCarro': veiculo.get('modelo', ''),
                        'corCarro': veiculo.get('cor', ''),
                        'placaCarro': veiculo.get('placa', '')
                    })
                else:
                    motorista_info.update({
                        'modeloCarro': motorista_dados.get('modeloCarro', ''),
                        'corCarro': motorista_dados.get('corCarro', ''),
                        'placaCarro': motorista_dados.get('placaCarro', '')
                    })
                
                # Outros detalhes
                if 'avaliacao' in motorista_dados:
                    motorista_info['avaliacao'] = motorista_dados.get('avaliacao')
                if 'foto' in motorista_dados:
                    motorista_info['foto'] = motorista_dados.get('foto')
            
            # Adicionar informações do motorista à mensagem
            mensagem_chegada['motorista'] = motorista_info
            logger.info(f"Enviando aviso de chegada do motorista para passageiro: nome={motorista_info['nome']}, corridaId={corridaId}")
        else:
            logger.info(f"Enviando aviso de chegada do motorista para passageiro - corridaId={corridaId}")
        
        # Enviar a mensagem ao cliente
        await self.send(text_data=json.dumps(mensagem_chegada))

    # Handler para corrida aceita (enviado ao passageiro)
    async def corrida_aceita(self, event):
        # Obter os dados do motorista do evento
        motorista_dados = event.get('motorista', {})
        
        # Inicializar o objeto motorista com valores padrão para TODAS as propriedades necessárias
        motorista_reformatado = {
            'cpf': '',
            'nome': 'Motorista',  # Valor padrão para nome é obrigatório
            'sobrenome': '',
            'telefone': '',
            'modeloCarro': '',
            'corCarro': '',
            'placaCarro': '',
            'avaliacao': 0,
            'foto': ''
        }
        
        # Verificar se há dados do motorista e atualizar com os dados disponíveis
        if motorista_dados:
            # Dados básicos do motorista - sempre garantindo valores válidos
            motorista_reformatado.update({
                'cpf': motorista_dados.get('cpf', ''),
                'telefone': motorista_dados.get('telefone', '')
            })
            
            # Nome e sobrenome com tratamento especial para garantir que nunca sejam vazios
            if motorista_dados.get('nome'):
                motorista_reformatado['nome'] = motorista_dados.get('nome')
            if motorista_dados.get('sobrenome'):
                motorista_reformatado['sobrenome'] = motorista_dados.get('sobrenome')
            
            # Adicionar dados do veículo diretamente no objeto do motorista
            # Se estiverem em um subobjeto veiculo, extraí-los
            if 'veiculo' in motorista_dados and isinstance(motorista_dados['veiculo'], dict):
                veiculo = motorista_dados['veiculo']
                motorista_reformatado.update({
                    'modeloCarro': veiculo.get('modelo', ''),
                    'corCarro': veiculo.get('cor', ''),
                    'placaCarro': veiculo.get('placa', '')
                })
            else:
                # Se não estiverem em um subobjeto, procurar diretamente
                motorista_reformatado.update({
                    'modeloCarro': motorista_dados.get('modeloCarro', ''),
                    'corCarro': motorista_dados.get('corCarro', ''),
                    'placaCarro': motorista_dados.get('placaCarro', '')
                })
            
            # Adicionar avaliação e foto se disponíveis
            if 'avaliacao' in motorista_dados:
                motorista_reformatado['avaliacao'] = motorista_dados.get('avaliacao')
            if 'foto' in motorista_dados:
                motorista_reformatado['foto'] = motorista_dados.get('foto')
        
        logger.info(f"Enviando dados do motorista para passageiro: nome={motorista_reformatado['nome']}, cpf={motorista_reformatado['cpf']}")
        
        # Enviar a mensagem no formato esperado pelo cliente
        await self.send(text_data=json.dumps({
            'type': 'corrida_aceita',
            'corridaId': event.get('corridaId'),
            'motorista': motorista_reformatado,
            'message': 'Um motorista aceitou sua solicitação de corrida.'
        }))

    # Handler para notificação de início de corrida (enviado ao passageiro)
    async def corrida_iniciada(self, event):
        await self.send(text_data=json.dumps({
            'type': 'corrida_iniciada',
            'corridaId': event.get('corridaId'),
            'message': event.get('message', 'Sua corrida foi iniciada!')
        }))

    # Handler para notificação de finalização de corrida pelo motorista (enviado ao passageiro)
    async def corrida_finalizada_por_motorista(self, event):
        await self.send(text_data=json.dumps({
            'type': 'corrida_finalizada',
            'corridaId': event.get('corridaId'),
            'message': event.get('message', 'O motorista finalizou a corrida.')
        }))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']

        # Send message to WebSocket
        await self.send(json.dumps({
            'message': message
        }))