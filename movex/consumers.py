import json
import logging
import requests
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
    calcular_rota_simplificada_melhorada  # Add this import
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
    verificar_corrida_em_andamento_motorista,  # Adicionar importação da nova função
    verificar_corrida_em_andamento_passageiro,  # Adicionar a nova função
    # Adicionar os novos imports
    avaliar_motorista,
    avaliar_passageiro,
    obter_dados_avaliacao_corrida,
    atualizar_status_corrida  # Adicionar a nova função
)

logger = logging.getLogger(__name__)

class MoveXConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.user_info = None
        self.room_group_name = 'movex_general'
        
        # Adicionar ao grupo geral
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Enviar confirmação de conexão
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Conexão WebSocket estabelecida'
        }))
    
    async def disconnect(self, close_code):
        # Remover do grupo geral
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Adicionar log de desconexão
        logger.info(f"Cliente desconectado com código {close_code}")
        
        # Se for um motorista, além de atualizar status para offline, 
        # verificar corridas em andamento
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
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            # Adicionar log detalhado para todas as mensagens recebidas
            print(f"[DEBUG] Mensagem recebida: {event_type} - {text_data[:100]}...")
            
            if event_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': str(timezone.now())
                }))
                return
            
            # Evento de login para armazenar informações do usuário
            elif event_type == 'login':
                cpf = data.get('cpf')
                tipo_usuario = data.get('tipo')
                self.user_info = {
                    'cpf': cpf,
                    'tipo': tipo_usuario
                }
                
                if tipo_usuario == 'MOTORISTA':
                    # Atualizar status do motorista para DISPONÍVEL ao fazer login
                    await database_sync_to_async(atualizar_status_motorista)(
                        cpf, 'DISPONIVEL', True
                    )
                    logger.info(f"Motorista {cpf} conectado e status atualizado para DISPONIVEL")
                    
                    # Adicionar motorista ao grupo específico
                    motorista_group = f'motorista_{cpf}'
                    await self.channel_layer.group_add(
                        motorista_group,
                        self.channel_name
                    )
                
                elif tipo_usuario == 'PASSAGEIRO':
                    # Adicionar passageiro ao grupo específico
                    passageiro_group = f'passageiro_{cpf}'
                    await self.channel_layer.group_add(
                        passageiro_group,
                        self.channel_name
                    )
                
                await self.send(text_data=json.dumps({
                    'type': 'login_success',
                    'message': f'Login WebSocket bem-sucedido como {tipo_usuario}'
                }))
                return
            
            # Novo manipulador para o evento motorista_conectado
            elif event_type == 'motorista_conectado':
                cpf = data.get('cpf')
                if cpf:
                    self.user_info = {
                        'cpf': cpf,
                        'tipo': 'MOTORISTA'
                    }
                    
                    # Tentar atualizar status com tratamento de erro explícito
                    try:
                        print(f"[DEBUG] Recebido evento motorista_conectado para CPF {cpf}")
                        resultado = await database_sync_to_async(atualizar_status_motorista)(
                            cpf, 'DISPONIVEL', True
                        )
                        print(f"[DEBUG] Resultado da atualização de status: {'Sucesso' if resultado else 'Falha'}")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar status do motorista: {str(e)}")
                        import traceback
                        traceback.print_exc()
                    
                    logger.info(f"Motorista {cpf} conectado e status atualizado para DISPONIVEL")
                    
                    # Adicionar motorista ao grupo específico
                    motorista_group = f'motorista_{cpf}'
                    await self.channel_layer.group_add(
                        motorista_group,
                        self.channel_name
                    )
                    
                    # Enviar resposta de sucesso para o cliente
                    await self.send(text_data=json.dumps({
                        'type': 'connection_success',
                        'message': f'Motorista {cpf} conectado com sucesso',
                        'status_atualizado': True
                    }))
            
            # Manipulador explícito para alterar_status_motorista
            elif event_type == 'alterar_status_motorista':
                motorista_cpf = data.get('motoristaId')
                novo_status = data.get('status')
                
                if not motorista_cpf or not novo_status:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Dados incompletos para alterar status'
                    }))
                    return
                    
                esta_disponivel = novo_status == 'ONLINE'
                status_db = 'DISPONIVEL' if esta_disponivel else 'OFFLINE'
                
                await database_sync_to_async(atualizar_status_motorista)(
                    motorista_cpf, status_db, esta_disponivel
                )
                
                await self.send(json.dumps({
                    'type': 'status_alterado',
                    'status': novo_status,
                    'message': f'Status alterado para {novo_status}'
                }))
            
            # Novo evento para calcular rota
            elif event_type == 'calcular_rota':
                logger.info("🔄 Calculando rota entre dois pontos")
                
                # Extrair coordenadas de origem e destino
                start_lat = float(data.get('start_lat'))
                start_lng = float(data.get('start_lng'))
                end_lat = float(data.get('end_lat'))
                end_lng = float(data.get('end_lng'))
                
                # Dados do passageiro (para log e debug)
                nome_passageiro = data.get('nome_passageiro', '')
                sobrenome_passageiro = data.get('sobrenome_passageiro', '')
                cpf_passageiro = data.get('cpf_passageiro', '')
                
                logger.info(f"📍 Origem: {start_lat}, {start_lng}")
                logger.info(f"📍 Destino: {end_lat, end_lng}")
                logger.info(f"👤 Passageiro: {nome_passageiro} {sobrenome_passageiro} ({cpf_passageiro})")
                
                try:
                    # Usar a função buscar_rota_openroute aprimorada
                    resultado_rota = await buscar_rota_openroute(
                        start_lat, start_lng, end_lat, end_lng
                    )
                    
                    if resultado_rota and resultado_rota['success']:
                        # Verificar se há coordenadas suficientes para traçar a rota
                        if len(resultado_rota['coordinates']) < 2:
                            logger.warning("⚠️ Rota calculada com poucos pontos. Recalculando com método melhorado.")
                            # Forçar o uso do método alternativo melhorado
                            resultado_rota = calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)
                        
                        # Responder ao cliente com os detalhes da rota calculada
                        await self.send(json.dumps({
                            'type': 'rota_calculada',
                            'distancia': resultado_rota['distancia'],
                            'tempo_estimado': resultado_rota['tempo_estimado'],
                            'valor': resultado_rota['valor'],
                            'coordinates': resultado_rota['coordinates'],
                            'horario_pico': is_horario_pico(),
                            'origem': {
                                'latitude': start_lat,
                                'longitude': start_lng
                            },
                            'destino': {
                                'latitude': end_lat,
                                'longitude': end_lng
                            }
                        }))
                    else:
                        # Se falhar, usar o método alternativo melhorado diretamente
                        resultado_rota = calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)
                        
                        await self.send(json.dumps({
                            'type': 'rota_calculada',
                            'distancia': resultado_rota['distancia'],
                            'tempo_estimado': resultado_rota['tempo_estimado'],
                            'valor': resultado_rota['valor'],
                            'coordinates': resultado_rota['coordinates'],
                            'horario_pico': is_horario_pico(),
                            'modo_calculo': 'simplificado_melhorado',
                            'origem': {
                                'latitude': start_lat,
                                'longitude': start_lng
                            },
                            'destino': {
                                'latitude': end_lat,
                                'longitude': end_lng
                            }
                        }))
                except Exception as e:
                    logger.error(f"❌ Erro ao calcular rota: {str(e)}")
                    
                    # Em caso de erro, tentar o método alternativo antes de falhar completamente
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
                            'origem': {
                                'latitude': start_lat,
                                'longitude': start_lng
                            },
                            'destino': {
                                'latitude': end_lat,
                                'longitude': end_lng
                            }
                        }))
                    except Exception as e2:
                        # Informar o cliente sobre o erro
                        await self.send(json.dumps({
                            'type': 'erro_rota',
                            'message': f'Erro ao calcular rota: {str(e)}'
                        }))
                
                return
            
            # Evento para solicitar uma corrida
            elif event_type == 'solicitar_corrida':
                # 1. RECEBIMENTO DA SOLICITAÇÃO WEBSOCKET
                # Log dos dados recebidos na solicitação
                logger.info("🔄 Evento: solicitar_corrida")
                logger.info(f"👤 Passageiro: {json.dumps(data.get('passageiro'))}")
                logger.info(f"📍 Origem: {json.dumps(data.get('origem'))}")
                logger.info(f"📍 Destino: {json.dumps(data.get('destino'))}")
                logger.info(f"💰 Valor: R$ {data.get('valor')}")
                logger.info(f"⏱️ Tempo: {data.get('tempo_estimado')} min")
                logger.info(f"📏 Distância: {data.get('distancia')} km")
                
                # 2. VALIDAÇÃO DOS DADOS
                # Verificar se todos os campos obrigatórios estão presentes
                campos_obrigatorios = ['passageiro', 'origem', 'destino', 'valor', 'tempo_estimado', 'distancia']
                campos_faltantes = [campo for campo in campos_obrigatorios if campo not in data or not data.get(campo)]
                
                if campos_faltantes:
                    logger.error(f"Campos obrigatórios faltando: {', '.join(campos_faltantes)}")
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': f'Campos obrigatórios faltando: {", ".join(campos_faltantes)}'
                    }))
                    return
                
                # Verificar se os dados do passageiro estão completos
                passageiro_data = data.get('passageiro', {})
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
                
                # Verificar se as coordenadas são válidas
                origem = data.get('origem', {})
                destino = data.get('destino', {})
                
                if not origem.get('latitude') or not origem.get('longitude') or not destino.get('latitude') or not destino.get('longitude'):
                    logger.error("Coordenadas inválidas ou ausentes")
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Coordenadas de origem ou destino inválidas'
                    }))
                    return
                
                # 3. REGISTRO DA CORRIDA NO BANCO DE DADOS
                # Registrar a corrida no banco de dados
                origem_descricao = data.get('origem_descricao', 'Local de origem')
                destino_descricao = data.get('destino_descricao', 'Local de destino')
                
                # Garantir que o CPF do passageiro está sendo passado explicitamente
                passageiro_cpf = passageiro_data.get('cpf')
                
                # Atualizar o dicionário data para garantir que o CPF do passageiro está explícito 
                # (além de já estar contido em data['passageiro']['cpf'])
                data['passageiro_cpf'] = passageiro_cpf
                
                corrida_id = await database_sync_to_async(registrar_corrida)(data)
                
                if not corrida_id:
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Erro ao registrar a corrida.'
                    }))
                    return
                
                logger.info(f"Corrida registrada com ID: {corrida_id}")
                
                # 4. BUSCA DE MOTORISTAS DISPONÍVEIS
                # Buscar motoristas disponíveis próximos à localização de origem
                motoristas_disponiveis = await database_sync_to_async(buscar_motoristas_disponiveis)(
                    lat=data.get('origem', {}).get('latitude'),
                    lng=data.get('origem', {}).get('longitude')
                )
                
                if not motoristas_disponiveis:
                    # Atualizar a corrida como cancelada automaticamente se não houver motoristas
                    await database_sync_to_async(cancelar_corrida_sem_motoristas)(corrida_id)
                    await self.send(json.dumps({
                        'type': 'erro_corrida',
                        'message': 'Não há motoristas disponíveis no momento.'
                    }))
                    return
                
                # Confirmar ao passageiro que a corrida foi registrada
                await self.send(json.dumps({
                    'type': 'corrida_registrada',
                    'corridaId': str(corrida_id),
                    'message': 'Corrida registrada com sucesso, buscando motorista...'
                }))
                
                # 5. NOTIFICAÇÃO AOS MOTORISTAS DISPONÍVEIS
                # Enviar notificações para todos os motoristas disponíveis na área
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
            
            # Evento para aceitar uma corrida (por parte do motorista)
            elif event_type == 'aceitar_corrida':
                # Corrigir a incompatibilidade de nomenclatura - aceitar tanto corridaId quanto corrida_id
                corrida_id = data.get('corridaId') or data.get('corrida_id')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                status = data.get('status', 'ACEITA')  # Obter o status da mensagem, padrão 'ACEITA'

                if not corrida_id:
                    logger.error(f"Erro ao aceitar corrida: ID da corrida não fornecido nos campos 'corridaId' ou 'corrida_id'")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido'
                    }))
                    return
                    
                logger.info(f"Motorista {motorista_cpf} tentando aceitar corrida {corrida_id}")

                if not motorista_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Motorista não identificado'
                    }))
                    return

                # Atualizar corrida com o motorista que aceitou e o novo status
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

                        # Buscar dados do motorista para enviar ao passageiro
                        motorista_dados = await database_sync_to_async(buscar_dados_motorista)(motorista_cpf)

                        await self.channel_layer.group_send(
                            passageiro_group,
                            {
                                'type': 'corrida_aceita_por_motorista',
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
            
            # Evento para atualização de localização do motorista
            elif event_type == 'atualizar_localizacao':
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem atualizar localização'
                    }))
                    return
                
                # Verificar múltiplos formatos possíveis de recebimento dos dados de localização
                # 1. Formato direto: latitude e longitude são enviados diretamente
                # 2. Formato aninhado: location.latitude e location.longitude
                latitude_str = data.get('latitude')
                longitude_str = data.get('longitude')
                
                # Se não encontrar no formato direto, tenta buscar no objeto location
                if not latitude_str or not longitude_str:
                    location = data.get('location', {})
                    if isinstance(location, dict):
                        latitude_str = location.get('latitude')
                        longitude_str = location.get('longitude')
                
                # Verifica novamente se os valores foram encontrados
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
                
                # Atualizar a localização do motorista no banco de dados
                await database_sync_to_async(atualizar_localizacao_motorista)(
                    motorista_cpf, latitude, longitude
                )
                
                # Verificar se há corridas em andamento com este motorista para notificar os passageiros
                corrida_atual = await database_sync_to_async(obter_corrida_em_andamento)(motorista_cpf)
                
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
                
                # Exemplo de resposta de sucesso
                await self.send(json.dumps({
                    'type': 'localizacao_atualizada',
                    'message': 'Localização do motorista atualizada com sucesso'
                }))
            
            # Evento para motorista avisar que chegou - HANDLER UNIFICADO
            elif event_type == 'cheguei' or event_type == 'aviso_chegada':
                # Compatibilidade com os dois formatos de parâmetros
                corrida_id = data.get('corrida_id') or data.get('corridaId')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                status = 'MOTORISTA_CHEGOU'  # Status fixo para ambos os eventos
                
                # Log detalhado para ajudar na depuração
                logger.info(f"Processando evento de chegada (tipo: {event_type}). corrida_id: {corrida_id}, motorista_cpf: {motorista_cpf}")
                
                if not corrida_id:
                    logger.error(f"Erro ao processar chegada do motorista: ID da corrida não fornecido")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido'
                    }))
                    return
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem avisar que chegaram'
                    }))
                    return
                
                try:
                    # 1. Registrar o status no banco de dados
                    from corridas.models import Corrida
                    
                    try:
                        corrida = await database_sync_to_async(Corrida.objects.get)(id=corrida_id)
                        
                        # Verificar se o motorista é o mesmo da corrida
                        motorista_corrida = await database_sync_to_async(
                            lambda: corrida.motorista.usuario.cpf if corrida.motorista and corrida.motorista.usuario else None
                        )()
                        
                        if motorista_corrida != motorista_cpf:
                            logger.error(f"Motorista {motorista_cpf} não está associado à corrida {corrida_id}")
                            await self.send(json.dumps({
                                'type': 'erro',
                                'message': 'Você não está associado a esta corrida'
                            }))
                            return
                        
                        # Atualizar status da corrida
                        await database_sync_to_async(setattr)(corrida, 'status', status)
                        await database_sync_to_async(setattr)(corrida, 'data_chegada_motorista', timezone.now())
                        await database_sync_to_async(corrida.save)()
                        
                        logger.info(f"Status da corrida {corrida_id} atualizado para MOTORISTA_CHEGOU com sucesso")
                        
                        # 2. Buscar CPF do passageiro para notificação
                        passageiro_cpf = await database_sync_to_async(
                            lambda: corrida.passageiro.usuario.cpf if corrida.passageiro and corrida.passageiro.usuario else None
                        )()
                        
                        # 3. Enviar confirmação para o motorista
                        await self.send(json.dumps({
                            'type': 'chegada_registrada',
                            'corridaId': corrida_id,
                            'message': 'Chegada registrada com sucesso'
                        }))
                        
                        # 4. Notificar o passageiro - PARTE CRUCIAL!
                        if passageiro_cpf:
                            passageiro_group = f'passageiro_{passageiro_cpf}'
                            logger.info(f"Enviando notificação de chegada para passageiro {passageiro_cpf}")
                            
                            # O tipo de mensagem DEVE ser 'motorista_chegou' conforme esperado pelo frontend
                            await self.channel_layer.group_send(
                                passageiro_group,
                                {
                                    'type': 'motorista_chegou',
                                    'corridaId': corrida_id,
                                    'message': 'Seu motorista chegou ao local de embarque'
                                }
                            )
                            logger.info(f"Notificação enviada com sucesso para o grupo {passageiro_group}")
                        else:
                            logger.error(f"Não foi possível obter CPF do passageiro para notificação de chegada")
                    
                    except Corrida.DoesNotExist:
                        logger.error(f"Corrida {corrida_id} não encontrada")
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Corrida não encontrada'
                        }))
                        return
                
                except Exception as e:
                    logger.error(f"Exceção ao registrar chegada do motorista: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao registrar chegada: {str(e)}'
                    }))

            # Adicione um handler para o evento corrida_iniciada_por_motorista
            elif event_type == 'iniciar_corrida':
                # Aceitar tanto corridaId quanto corrida_id para compatibilidade
                corrida_id = data.get('corridaId') or data.get('corrida_id')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                status = data.get('status', 'EM_ANDAMENTO')  # Obter o status da mensagem
                
                # Log detalhado para ajudar na depuração
                logger.info(f"Processando iniciar_corrida. corrida_id: {corrida_id}, motorista_cpf: {motorista_cpf}")
                
                if not corrida_id:
                    logger.error(f"Erro ao processar iniciar_corrida: ID da corrida não fornecido")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido'
                    }))
                    return
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem iniciar uma corrida'
                    }))
                    return
                
                # Atualizar o status da corrida para EM_ANDAMENTO
                try:
                    sucesso, passageiro_cpf = await database_sync_to_async(iniciar_corrida)(
                        corrida_id, motorista_cpf, status
                    )
                    
                    if sucesso:
                        # Notificar o motorista
                        await self.send(json.dumps({
                            'type': 'corrida_iniciada',
                            'corridaId': corrida_id,
                            'message': 'Corrida iniciada com sucesso!'
                        }))
                        
                        # Notificar o passageiro
                        if passageiro_cpf:
                            passageiro_group = f'passageiro_{passageiro_cpf}'
                            
                            await self.channel_layer.group_send(
                                passageiro_group,
                                {
                                    'type': 'corrida_iniciada_por_motorista',
                                    'corridaId': corrida_id,
                                    'message': 'Sua corrida foi iniciada! Boa viagem!'
                                }
                            )
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível iniciar a corrida'
                        }))
                except Exception as e:
                    logger.error(f"Exceção ao iniciar corrida: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao iniciar corrida: {str(e)}'
                    }))
            
            # Novo evento para verificar corrida em andamento do motorista ao reconectar
            elif event_type == 'verificar_corrida_motorista':
                print(f"[DEBUG] Recebido evento verificar_corrida_motorista com dados: {data}")
                motorista_cpf = data.get('cpf')
                
                if not motorista_cpf:
                    print(f"[ERROR] CPF do motorista não fornecido em verificar_corrida_motorista")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF do motorista não fornecido'
                    }))
                    return
                
                # Adicionar o motorista ao grupo específico (caso ele não tenha sido adicionado antes)
                motorista_group = f'motorista_{motorista_cpf}'
                await self.channel_layer.group_add(
                    motorista_group,
                    self.channel_name
                )
                
                # Atualizar o user_info para garantir que o tipo e CPF estejam registrados
                self.user_info = {
                    'cpf': motorista_cpf,
                    'tipo': 'MOTORISTA'
                }
                
                print(f"[DEBUG] Verificando corrida em andamento para motorista: {motorista_cpf}")
                
                # Buscar corrida em andamento
                corrida_em_andamento = await database_sync_to_async(verificar_corrida_em_andamento_motorista)(
                    motorista_cpf
                )
                
                if corrida_em_andamento:
                    # Se encontrou uma corrida, notifica o motorista
                    print(f"[DEBUG] Corrida em andamento encontrada para motorista {motorista_cpf}: {corrida_em_andamento['corridaId']}")
                    await self.send(json.dumps({
                        'type': 'corrida_em_andamento',
                        'corrida': corrida_em_andamento,
                        'message': f"Corrida em andamento encontrada com status {corrida_em_andamento['status']}"
                    }))
                else:
                    # Se não há corridas, notifica que está livre
                    print(f"[DEBUG] Nenhuma corrida em andamento para motorista {motorista_cpf}")
                    await self.send(json.dumps({
                        'type': 'sem_corrida_ativa',
                        'message': 'Não há corridas ativas para este motorista'
                    }))
                
                return  # Importante: retornar após enviar a resposta

            # Novo evento para verificar corrida em andamento do passageiro
            elif event_type == 'verificar_corrida_passageiro':
                passageiro_cpf = data.get('cpf')
                
                if not passageiro_cpf:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'CPF do passageiro não fornecido'
                    }))
                    return
                
                # Buscar corrida em andamento do passageiro
                corrida_em_andamento = await database_sync_to_async(verificar_corrida_em_andamento_passageiro)(
                    passageiro_cpf
                )
                
                if corrida_em_andamento:
                    # Se encontrou uma corrida, notifica o passageiro
                    await self.send(json.dumps({
                        'type': 'corrida_em_andamento_passageiro',
                        'corrida': corrida_em_andamento,
                        'message': f"Corrida em andamento encontrada com status {corrida_em_andamento['status']}"
                    }))
                else:
                    # Se não há corridas, notifica que está livre
                    await self.send(json.dumps({
                        'type': 'sem_corrida_ativa_passageiro',
                        'message': 'Não há corridas ativas para este passageiro'
                    }))
            
            # Adicionar novos handlers para avaliações
            elif event_type == 'avaliar_motorista':
                corridaId = data.get('corridaId')
                avaliacao = data.get('avaliacao')
                comentario = data.get('comentario', '')
                passageiro_cpf = self.user_info.get('cpf') if self.user_info else None
                
                if not passageiro_cpf or not corridaId or not avaliacao:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Dados incompletos para avaliação.'
                    }))
                    return
                
                # Avaliar o motorista
                sucesso, motorista_cpf = await database_sync_to_async(avaliar_motorista)(
                    corridaId, passageiro_cpf, avaliacao, comentario
                )
                
                if sucesso:
                    # Notificar o passageiro
                    await self.send(json.dumps({
                        'type': 'avaliacao_registrada',
                        'message': 'Avaliação do motorista registrada com sucesso!'
                    }))
                    
                    # Notificar o motorista se estiver online
                    if motorista_cpf:
                        await self.channel_layer.group_send(
                            f'usuario_{motorista_cpf}',
                            {
                                'type': 'avaliacao_recebida',
                                'corridaId': corridaId,
                                'avaliacao': avaliacao,
                                'comentario': comentario,
                                'avaliador_tipo': 'PASSAGEIRO',
                                'message': 'Você recebeu uma nova avaliação!'
                            }
                        )
                else:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Não foi possível registrar a avaliação do motorista.'
                    }))

            elif event_type == 'avaliar_passageiro':
                corridaId = data.get('corridaId')
                avaliacao = data.get('avaliacao')
                comentario = data.get('comentario', '')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                
                if not motorista_cpf or not corridaId or not avaliacao:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Dados incompletos para avaliação.'
                    }))
                    return
                
                # Avaliar o passageiro
                sucesso, passageiro_cpf = await database_sync_to_async(avaliar_passageiro)(
                    corridaId, motorista_cpf, avaliacao, comentario
                )
                
                if sucesso:
                    # Notificar o motorista
                    await self.send(json.dumps({
                        'type': 'avaliacao_registrada',
                        'message': 'Avaliação do passageiro registrada com sucesso!'
                    }))
                    
                    # Notificar o passageiro se estiver online
                    if passageiro_cpf:
                        await self.channel_layer.group_send(
                            f'usuario_{passageiro_cpf}',
                            {
                                'type': 'avaliacao_recebida',
                                'corridaId': corridaId,
                                'avaliacao': avaliacao,
                                'comentario': comentario,
                                'avaliador_tipo': 'MOTORISTA',
                                'message': 'Você recebeu uma nova avaliação!'
                            }
                        )
                else:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Não foi possível registrar a avaliação do passageiro.'
                    }))

            elif event_type == 'verificar_avaliacao_corrida':
                corridaId = data.get('corridaId')
                
                if not corridaId:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido.'
                    }))
                    return
                
                # Obter dados de avaliação da corrida
                dados_avaliacao = await database_sync_to_async(obter_dados_avaliacao_corrida)(corridaId)
                
                if dados_avaliacao:
                    await self.send(json.dumps({
                        'type': 'dados_avaliacao',
                        'dados': dados_avaliacao
                    }))
                else:
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Não foi possível obter os dados de avaliação.'
                    }))
            
            # Evento para buscar cliente
            elif event_type == 'buscar_cliente':
                corrida_id = data.get('corrida_id')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None

                if not corrida_id or not motorista_cpf:
                    logger.error(f"Dados incompletos para buscar cliente: corrida_id={corrida_id}, motorista_cpf={motorista_cpf}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Dados incompletos para buscar cliente'
                    }))
                    return

                sucesso = await database_sync_to_async(atualizar_status_corrida)(corrida_id, 'A_CAMINHO')
                if sucesso:
                    logger.info(f"Status da corrida {corrida_id} atualizado para A_CAMINHO pelo motorista {motorista_cpf}")
                    await self.send(json.dumps({
                        'type': 'status_corrida_atualizado',
                        'corridaId': corrida_id,
                        'status': 'A_CAMINHO',
                        'message': 'Status atualizado para A_CAMINHO'
                    }))
                else:
                    logger.error(f"Erro ao atualizar status para A_CAMINHO: corrida_id={corrida_id}, motorista_cpf={motorista_cpf}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Erro ao atualizar status para A_CAMINHO'
                    }))

            # Novo handler para finalizar_corrida
            elif event_type == 'finalizar_corrida':
                # Aceitar tanto corridaId quanto corrida_id para compatibilidade
                corrida_id = data.get('corridaId') or data.get('corrida_id')
                motorista_cpf = self.user_info.get('cpf') if self.user_info else None
                status = data.get('status', 'FINALIZADA')  # Status padrão é FINALIZADA
                
                # Log detalhado para ajudar na depuração
                logger.info(f"Processando finalizar_corrida. corrida_id: {corrida_id}, motorista_cpf: {motorista_cpf}")
                
                if not corrida_id:
                    logger.error(f"Erro ao finalizar corrida: ID da corrida não fornecido")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'ID da corrida não fornecido'
                    }))
                    return
                
                if not motorista_cpf or self.user_info.get('tipo') != 'MOTORISTA':
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': 'Apenas motoristas podem finalizar uma corrida'
                    }))
                    return
                
                # Finalizar a corrida no banco de dados
                try:
                    sucesso, passageiro_cpf = await database_sync_to_async(finalizar_corrida)(
                        corrida_id, motorista_cpf, status
                    )
                    
                    if sucesso:
                        # Notificar o motorista
                        await self.send(json.dumps({
                            'type': 'corrida_finalizada',
                            'corridaId': corrida_id,
                            'message': 'Corrida finalizada com sucesso!'
                        }))
                        
                        # Notificar o passageiro
                        if passageiro_cpf:
                            passageiro_group = f'passageiro_{passageiro_cpf}'
                            
                            await self.channel_layer.group_send(
                                passageiro_group,
                                {
                                    'type': 'corrida_finalizada_por_motorista',
                                    'corridaId': corrida_id,
                                    'message': 'Sua corrida foi finalizada!'
                                }
                            )
                    else:
                        await self.send(json.dumps({
                            'type': 'erro',
                            'message': 'Não foi possível finalizar a corrida'
                        }))
                except Exception as e:
                    logger.error(f"Exceção ao finalizar corrida: {str(e)}")
                    await self.send(json.dumps({
                        'type': 'erro',
                        'message': f'Erro ao finalizar corrida: {str(e)}'
                    }))

            # Outros eventos podem ser adicionados aqui
        
        except Exception as e:
            print(f"[ERROR] Erro ao processar mensagem: {str(e)}")
            traceback.print_exc()  # Adicionar traceback para mais detalhes
            await self.send(json.dumps({
                'type': 'erro',
                'message': f'Erro ao processar solicitação: {str(e)}'
            }))
    
    # Métodos para enviar mensagens específicas
    async def nova_solicitacao_corrida(self, event):
        # Adicionar logs detalhados antes de enviar a notificação ao motorista
        print(f"\n==== ENVIANDO NOVA SOLICITAÇÃO PARA MOTORISTA ====")
        
        try:
            # Criar um dicionário limpo com os dados necessários
            mensagem = {
                'type': 'nova_corrida',  # ALTERADO: Usar 'nova_corrida' em vez de 'nova_solicitacao_corrida' para compatibilidade com app motorista
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
            
            # Garantir que campos necessários estão presentes
            if not mensagem['corridaId'] or not mensagem['passageiro'] or not mensagem['origem'] or not mensagem['destino']:
                print("⚠️ ALERTA: Dados incompletos na mensagem de solicitação de corrida!")
                for campo in ['corridaId', 'passageiro', 'origem', 'destino']:
                    if not mensagem.get(campo):
                        print(f"    - Campo {campo} está vazio ou ausente")
            
            # Validar os campos da mensagem para garantir que está tudo correto
            if 'origem' in mensagem and isinstance(mensagem['origem'], dict):
                if 'latitude' not in mensagem['origem'] or 'longitude' not in mensagem['origem']:
                    print("⚠️ ALERTA: Coordenadas de origem incompletas!")
            
            if 'destino' in mensagem and isinstance(mensagem['destino'], dict):
                if 'latitude' not in mensagem['destino'] or 'longitude' not in mensagem['destino']:
                    print("⚠️ ALERTA: Coordenadas de destino incompletas!")
            
            # Convertemos para JSON e de volta para validar que é um JSON válido
            json_str = json.dumps(mensagem)
            json.loads(json_str)  # Isso gerará uma exceção se o JSON for inválido
            
            print(f"Dados completos a serem enviados: {json.dumps(mensagem, indent=2, default=str)}")
            print(f"NOTA: O tipo da mensagem é '{mensagem['type']}'")
            
            # Enviar a mensagem ao cliente
            await self.send(json_str)
            print(f"==== MENSAGEM ENVIADA COM SUCESSO ====\n")
        except Exception as e:
            print(f"❌ ERRO AO ENVIAR MENSAGEM DE NOVA CORRIDA: {str(e)}")
            # Tente enviar uma versão mínima como fallback
            try:
                mensagem_minima = {
                    'type': 'nova_corrida',  # Mesmo tipo que na mensagem principal para consistência
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
                print("⚠️ Enviada mensagem mínima como fallback")
            except Exception as fallback_error:
                print(f"❌ ERRO NO FALLBACK: {str(fallback_error)}")
    
    async def corrida_aceita_por_motorista(self, event):
        # Log detalhado para depuração
        logger.info(f"Handler corrida_aceita_por_motorista chamado. Conteúdo: {json.dumps(event, default=str)}")
        
        try:
            # Enviar notificação ao passageiro que sua corrida foi aceita
            message = {
                'type': 'corrida_aceita_por_motorista',
                'corridaId': event['corridaId'],
                'motorista': event['motorista']
            }
            logger.info(f"Enviando para cliente: {json.dumps(message, default=str)}")
            
            await self.send(json.dumps(message))
            logger.info("Mensagem enviada com sucesso ao cliente WebSocket")
        except Exception as e:
            logger.error(f"Erro ao processar corrida_aceita_por_motorista: {str(e)}")
    
    async def localizacao_atualizada(self, event):
        # Enviar notificação de atualização de localização do motorista para o passageiro
        await self.send(json.dumps({
            'type': 'localizacao_motorista',
            'corridaId': event['corridaId'],
            'latitude': event['latitude'],
            'longitude': event['longitude']
        }))
    
    async def corrida_finalizada_por_motorista(self, event):
        # Enviar notificação ao passageiro que sua corrida foi finalizada
        await self.send(json.dumps({
            'type': 'corrida_finalizada',
            'corridaId': event['corridaId'],
            'message': event['message']
        }))
    
    async def corrida_cancelada_por_outro(self, event):
        # Enviar notificação ao usuário que a corrida foi cancelada pela outra parte
        await self.send(json.dumps({
            'type': 'corrida_cancelada',
            'corridaId': event['corridaId'],
            'message': event['message'],
            'motivo': event['motivo']
        }))
    
    async def motorista_chegou(self, event):
        # Enviar notificação ao passageiro que o motorista chegou
        await self.send(json.dumps({
            'type': 'motorista_chegou',
            'corridaId': event['corridaId'],
            'message': event['message']
        }))
    
    async def corrida_aceita_por_outro(self, event):
        # Enviar notificação ao motorista de que a corrida foi aceita por outro
        await self.send(json.dumps({
            'type': 'corrida_indisponivel',
            'corridaId': event['corridaId'],
            'message': event['message']
        }))
    
    async def motorista_desconectado(self, event):
        # Enviar notificação ao passageiro que o motorista se desconectou
        await self.send(json.dumps({
            'type': 'motorista_desconectado',
            'message': event['message']
        }))

    # Adicione um handler para o evento corrida_iniciada_por_motorista
    async def corrida_iniciada_por_motorista(self, event):
        # Enviar notificação ao passageiro que sua corrida foi iniciada
        await self.send(json.dumps({
            'type': 'corrida_iniciada',
            'corridaId': event['corridaId'],
            'message': event['message']
        }))

    # Adicionar novos métodos para lidar com notificações de avaliação
    async def avaliacao_recebida(self, event):
        # Enviar notificação de que o usuário recebeu uma avaliação
        await self.send(json.dumps({
            'type': 'avaliacao_recebida',
            'corridaId': event['corridaId'],
            'avaliacao': event['avaliacao'],
            'comentario': event.get('comentario'),
            'avaliador_tipo': event['avaliador_tipo'],
            'message': event['message']
        }))

    async def motorista_a_caminho(self, event):
        corrida_id = event.get('corrida_id')
        motorista_cpf = self.user_info.get('cpf') if self.user_info else None

        if not corrida_id or not motorista_cpf:
            await self.send(json.dumps({
                'type': 'erro',
                'message': 'Dados incompletos para atualizar status para A_CAMINHO'
            }))
            return

        logger.info(f"[DEBUG] Processando evento motorista_a_caminho: corrida_id={corrida_id}, motorista_cpf={motorista_cpf}")
        
        # Atualizar o status da corrida para "A_CAMINHO" no banco de dados
        sucesso = await database_sync_to_async(atualizar_status_corrida)(corrida_id, 'A_CAMINHO')
        
        if sucesso:
            logger.info(f"[SUCESSO] Status da corrida {corrida_id} atualizado para A_CAMINHO com sucesso")
            
            # Notificar o passageiro sobre o motorista a caminho
            # Recuperar o CPF do passageiro
            try:
                from corridas.models import Corrida
                corrida = await database_sync_to_async(Corrida.objects.get)(id=corrida_id)
                passageiro_cpf = await database_sync_to_async(lambda: corrida.passageiro.usuario.cpf if corrida.passageiro and corrida.passageiro.usuario else None)()
                
                if passageiro_cpf:
                    # Adicionar o passageiro ao grupo específico (caso ele não tenha sido adicionado antes)
                    passageiro_group = f'passageiro_{passageiro_cpf}'
                    
                    # Enviar notificação ao passageiro
                    await self.channel_layer.group_send(
                        passageiro_group,
                        {
                            'type': 'motorista_a_caminho_notificacao',
                            'corridaId': corrida_id,
                            'message': 'O motorista está a caminho',
                            'status': 'A_CAMINHO'
                        }
                    )
                    logger.info(f"[DEBUG] Notificação enviada ao passageiro {passageiro_cpf}")
            except Exception as e:
                logger.error(f"[ERRO] Falha ao notificar passageiro: {str(e)}")
            
            # Também enviar confirmação para o motorista
            await self.send(json.dumps({
                'type': 'status_corrida_atualizado',
                'corridaId': corrida_id,
                'status': 'A_CAMINHO',
                'message': 'Status atualizado para A_CAMINHO'
            }))
        else:
            logger.error(f"[ERRO] Falha ao atualizar o status da corrida {corrida_id} para A_CAMINHO")
            await self.send(json.dumps({
                'type': 'erro',
                'message': 'Erro ao atualizar status para A_CAMINHO'
            }))
            
    # Handler para notificar o passageiro que o motorista está a caminho
    async def motorista_a_caminho_notificacao(self, event):
        await self.send(json.dumps({
            'type': 'motorista_a_caminho',
            'corridaId': event['corridaId'],
            'message': event['message'],
            'status': event['status']
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
#tudo certo