import uuid
import logging
import re
from decimal import Decimal
from django.utils import timezone
from usuarios.models import Usuario, Motorista, Passageiro
from corridas.models import Corrida
from .utils import calcular_distancia

logger = logging.getLogger(__name__)

def verificar_corridas_em_andamento(cpf_motorista):
    """Verifica se o motorista possui corridas em andamento e marca como temporariamente indisponível"""
    try:
        usuario = Usuario.objects.get(cpf=cpf_motorista, tipo_usuario='MOTORISTA')
        motorista = Motorista.objects.get(usuario=usuario)
        
        # Buscar corridas aceitas por este motorista
        corridas_ativas = Corrida.objects.filter(
            motorista=motorista,
            status__in=['ACEITA', 'EM_ANDAMENTO']
        )
        
        for corrida in corridas_ativas:
            # Marcar corrida como temporariamente interrompida
            corrida.motorista_temporariamente_desconectado = True
            corrida.save()
            
            logger.info(f"Corrida {corrida.id} marcada como temporariamente interrompida devido à desconexão do motorista")
                
        return True, [c.passageiro.usuario.cpf for c in corridas_ativas if c.passageiro and c.passageiro.usuario]
    except Exception as e:
        logger.error(f"Erro ao verificar corridas em andamento: {str(e)}")
        return False, []

def buscar_motoristas_disponiveis(lat, lng, raio_km=10):
    """Busca motoristas disponíveis próximos às coordenadas informadas"""
    try:
        print(f"[DEBUG] Buscando motoristas disponíveis próximos a: {lat}, {lng}")
        
        # Buscar todos os motoristas disponíveis
        motoristas = Motorista.objects.filter(
            esta_disponivel=True,
            status='DISPONIVEL'
        ).select_related('usuario')
        
        print(f"[DEBUG] Encontrados {motoristas.count()} motoristas com status 'DISPONIVEL'")
        for m in motoristas:
            print(f"[DEBUG] - Motorista: {m.usuario.nome} {m.usuario.sobrenome}, CPF: {m.cpf}, Status: {m.status}, Disponível: {m.esta_disponivel}")
        
        # Filtrar por distância se coordenadas foram fornecidas
        motoristas_proximos = []
        
        if lat and lng:
            for motorista in motoristas:
                # MODIFICADO: Usar preferencialmente as coordenadas armazenadas do motorista
                # E usar valores padrão somente se necessário
                motorista_lat = float(motorista.ultima_latitude) if motorista.ultima_latitude else None
                motorista_lng = float(motorista.ultima_longitude) if motorista.ultima_longitude else None
                
                # Se não tivermos coordenadas reais, pular este motorista
                if motorista_lat is None or motorista_lng is None:
                    print(f"[DEBUG] Motorista {motorista.cpf} sem coordenadas válidas, usando coordenadas padrão para testes")
                    # Para fins de teste, usar a mesma localização do passageiro com pequena variação
                    motorista_lat = lat + 0.001 * (hash(motorista.cpf) % 10 - 5)  # Variação aleatória mas determinística
                    motorista_lng = lng + 0.001 * (hash(motorista.cpf[::-1]) % 10 - 5)
                
                distancia = calcular_distancia(lat, lng, motorista_lat, motorista_lng)
                
                # Log da distância para debug
                print(f"[DEBUG] Motorista {motorista.cpf} está a {distancia:.2f} km do passageiro")
                
                if distancia <= raio_km:
                    motorista_info = {
                        'cpf': motorista.cpf,
                        'nome': motorista.usuario.get_full_name(),
                        'distancia': distancia,
                        'veiculo': {
                            'modelo': motorista.modelo_veiculo,
                            'placa': motorista.placa_veiculo,
                            'cor': motorista.cor_veiculo
                        }
                    }
                    
                    print(f"[DEBUG] Motorista próximo encontrado: {motorista.usuario.get_full_name()} (CPF: {motorista.cpf}) a {distancia:.2f} km")
                    motoristas_proximos.append(motorista_info)
        else:
            # Se não houver coordenadas, retorna todos os disponíveis com aviso
            print("[WARNING] Coordenadas não fornecidas, retornando todos os motoristas disponíveis")
            for motorista in motoristas:
                motorista_info = {
                    'cpf': motorista.cpf,
                    'nome': motorista.usuario.get_full_name(),
                    'veiculo': {
                        'modelo': motorista.modelo_veiculo,
                        'placa': motorista.placa_veiculo,
                        'cor': motorista.cor_veiculo
                    }
                }
                
                print(f"[DEBUG] Motorista disponível: {motorista.usuario.get_full_name()} (CPF: {motorista.cpf})")
                motoristas_proximos.append(motorista_info)
        
        print(f"[DEBUG] Total de motoristas próximos encontrados: {len(motoristas_proximos)}")
        return motoristas_proximos
        
    except Exception as e:
        print(f"[ERROR] Erro ao buscar motoristas disponíveis: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def registrar_corrida(dados):
    """Registra uma nova corrida no banco de dados"""
    try:
        passageiro_cpf = dados.get('passageiro', {}).get('cpf')
        
        if not passageiro_cpf:
            logger.error("CPF do passageiro não fornecido")
            return None
        
        # Buscar o passageiro pelo CPF
        try:
            usuario = Usuario.objects.get(cpf=passageiro_cpf, tipo_usuario='PASSAGEIRO')
            passageiro = Passageiro.objects.get(usuario=usuario)
        except (Usuario.DoesNotExist, Passageiro.DoesNotExist):
            logger.error(f"Passageiro não encontrado para o CPF: {passageiro_cpf}")
            return None
        
        # Obter dados de origem e destino
        origem = dados.get('origem', {})
        destino = dados.get('destino', {})
        
        origem_lat = origem.get('latitude', 0)
        origem_lng = origem.get('longitude', 0)
        origem_descricao = dados.get('origem_descricao', 'Local de origem')
        
        destino_lat = destino.get('latitude', 0)
        destino_lng = destino.get('longitude', 0)
        destino_descricao = dados.get('destino_descricao', 'Local de destino')
        
        # Capturar informações de contato do passageiro para o motorista
        telefone_passageiro = dados.get('passageiro', {}).get('telefone', usuario.telefone)
        
        # Criar o registro da corrida com ID único
        corrida_id = uuid.uuid4()
        
        # Extrair tempo_estimado usando regex para pegar somente dígitos
        tempo_str = str(dados.get('tempo_estimado', 0))
        logger.info(f"Tempo estimado (original): '{tempo_str}'")
        match = re.search(r'\d+', tempo_str)
        tempo_int = int(match.group(0)) if match else 0
        logger.info(f"Tempo estimado (extraído): {tempo_int}")
        
        # Imprime todos os dados antes de criar a corrida para debug
        logger.info(f"Dados para criar corrida: origem_lat={origem_lat}, origem_lng={origem_lng}, "
                   f"destino_lat={destino_lat}, destino_lng={destino_lng}, "
                   f"valor={dados.get('valor', 0)}, distancia={dados.get('distancia', 0)}, "
                   f"tempo_estimado={tempo_int}")
        
        try:
            corrida = Corrida.objects.create(
                id=corrida_id,
                passageiro=passageiro,
                status='PENDENTE',
                origem_lat=Decimal(str(origem_lat)),
                origem_lng=Decimal(str(origem_lng)),
                origem_descricao=origem_descricao,
                destino_lat=Decimal(str(destino_lat)),
                destino_lng=Decimal(str(destino_lng)),
                destino_descricao=destino_descricao,
                valor=Decimal(str(dados.get('valor', 0))),
                distancia=Decimal(str(dados.get('distancia', 0))),
                tempo_estimado=tempo_int  # Usamos o valor extraído
            )
            logger.info(f"Corrida registrada com sucesso! ID: {corrida_id}")
            return corrida_id
        except ValueError as ve:
            logger.error(f"Erro de conversão ao criar corrida: {ve}")
            for key, value in dados.items():
                logger.info(f"Dado: {key} = {value} (tipo: {type(value)})")
            raise
        
    except Exception as e:
        logger.error(f"Erro ao registrar corrida: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def aceitar_corrida(corrida_id, motorista_cpf, status='ACEITA'):
    """Motorista aceita uma corrida pendente e sistema notifica os demais motoristas"""
    try:
        # Verificar se a corrida existe e está pendente
        try:
            corrida = Corrida.objects.get(id=corrida_id, status='PENDENTE')
        except Corrida.DoesNotExist:
            logger.error(f"Corrida não encontrada ou não está pendente: {corrida_id}")
            return False, None, []

        # Buscar o motorista pelo CPF
        try:
            usuario = Usuario.objects.get(cpf=motorista_cpf, tipo_usuario='MOTORISTA')
            motorista = Motorista.objects.get(usuario=usuario)
        except (Usuario.DoesNotExist, Motorista.DoesNotExist):
            logger.error(f"Motorista não encontrado para o CPF: {motorista_cpf}")
            return False, None, []

        # Atualizar a corrida
        corrida.motorista = motorista
        corrida.status = status  # Usar o status fornecido
        corrida.data_aceite = timezone.now()
        corrida.save()

        # Atualizar status do motorista para ocupado
        motorista.status = 'OCUPADO'
        motorista.esta_disponivel = False
        motorista.save()

        logger.info(f"Corrida {corrida_id} aceita pelo motorista {motorista_cpf} com status {status}")

        # Buscar todos os motoristas ativos para notificá-los sobre a corrida já aceita
        outros_motoristas = Motorista.objects.filter(
            esta_disponivel=True,
            status='DISPONIVEL'
        ).exclude(usuario__cpf=motorista_cpf).select_related('usuario')

        # Coletar CPFs dos outros motoristas para notificação
        outros_cpfs = [m.usuario.cpf for m in outros_motoristas]

        logger.info(f"Notificando {len(outros_cpfs)} outros motoristas que a corrida foi aceita")

        # Retorna True, o CPF do passageiro e a lista de outros motoristas para notificação
        return True, corrida.passageiro.usuario.cpf, outros_cpfs

    except Exception as e:
        logger.error(f"Erro ao aceitar corrida: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None, []

def atualizar_status_motorista(cpf, status, esta_disponivel):
    """
    Atualiza o status de disponibilidade do motorista.
    Retorna True se o status foi atualizado com sucesso, False caso contrário.
    """
    try:
        print(f"[DEBUG] Tentando atualizar status do motorista {cpf} para {status} (disponível: {esta_disponivel})")
        
        from django.utils import timezone
        from usuarios.models import Motorista
        
        # Buscar o motorista pelo CPF
        motorista = Motorista.objects.filter(cpf=cpf).first()
        
        if not motorista:
            print(f"[ERROR] Motorista com CPF {cpf} não encontrado")
            return False
        
        # Registrar status anterior para logging
        status_anterior = motorista.status
        disponivel_anterior = motorista.esta_disponivel
        
        # Atualizar status
        motorista.status = status
        motorista.esta_disponivel = esta_disponivel
        
        # Se ficar disponível, atualizar também a localização
        if esta_disponivel:
            motorista.ultima_atualizacao_localizacao = timezone.now()
        
        # Salvar as alterações usando update_fields para garantir que apenas os campos alterados sejam atualizados
        motorista.save(update_fields=['status', 'esta_disponivel', 'ultima_atualizacao_localizacao'])

        # Também fazer um update direto para garantir a atualização dos dados
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE usuarios_motorista SET status = %s, esta_disponivel = %s WHERE cpf = %s", 
            [status, esta_disponivel, cpf]
        )
        
        print(f"[DEBUG] Status do motorista {cpf} atualizado com sucesso: {status_anterior} -> {status}, {disponivel_anterior} -> {esta_disponivel}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Erro ao atualizar status do motorista {cpf}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def limpar_corrida_da_memoria(corrida_id):
    """
    Remove referências a uma corrida específica da memória para evitar loops de solicitação.
    Útil após cancelamentos ou finalizações de corrida.

    Args:
        corrida_id: ID da corrida a ser limpa da memória
    
    Returns:
        bool: True se sucesso, False caso contrário
    """
    try:
        # Remover da memória do sistema - por exemplo, limpar caches específicos para esta corrida
        from movex.consumers import historico_chat_cache, request_rate_limiter
        
        # Limpar referências no cache de histórico de chat
        chaves_para_remover = []
        for chave in historico_chat_cache.keys():
            # A chave é (cpf, corrida_id)
            if chave[1] == corrida_id:
                chaves_para_remover.append(chave)
        
        for chave in chaves_para_remover:
            if chave in historico_chat_cache:
                del historico_chat_cache[chave]
                
        # Limpar referências no limitador de taxa
        chaves_rate_para_remover = []
        for chave in request_rate_limiter.keys():
            # A chave é (cpf, request_type, parameter)
            if chave[2] == str(corrida_id):
                chaves_rate_para_remover.append(chave)
                
        for chave in chaves_rate_para_remover:
            if chave in request_rate_limiter:
                del request_rate_limiter[chave]
                
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao limpar corrida {corrida_id} da memória: {str(e)}")
        return False

def buscar_dados_motorista(cpf_motorista):
    """
    Busca os dados do motorista com o CPF informado.
    """
    try:
        # Tenta buscar o motorista pelo CPF
        motorista = Motorista.objects.get(cpf=cpf_motorista)
        
        # Acessar os atributos pessoais através do relacionamento com Usuario
        return {
            'cpf': motorista.cpf,  # Use CPF como identificador em vez de ID
            'nome': motorista.usuario.nome if hasattr(motorista, 'usuario') else '',
            'sobrenome': motorista.usuario.sobrenome if hasattr(motorista, 'usuario') else '',
            'telefone': motorista.usuario.telefone if hasattr(motorista, 'usuario') else '',
            'veiculo': {
                'modelo': motorista.modelo_veiculo,
                'placa': motorista.placa_veiculo,
                'cor': motorista.cor_veiculo
            }
        }
    except Exception as e:
        # Logar o erro detalhado para ajudar na depuração
        import traceback
        print(f"Erro ao buscar dados do motorista {cpf_motorista}: {e}")
        print(traceback.format_exc())
        return None

def atualizar_localizacao_motorista(cpf, latitude, longitude):
    """Atualiza a localização de um motorista"""
    try:
        usuario = Usuario.objects.get(cpf=cpf, tipo_usuario='MOTORISTA')
        motorista = Motorista.objects.get(usuario=usuario)
        
        # Assumindo que você tenha esses campos no modelo Motorista
        # Se não tiver, você precisará adicionar ou usar outra tabela
        motorista.ultima_latitude = Decimal(str(latitude))
        motorista.ultima_longitude = Decimal(str(longitude))
        motorista.ultima_atualizacao_localizacao = timezone.now()
        motorista.save()
        
        #logger.info(f"Localização do motorista {cpf} atualizada: {latitude}, {longitude}")
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar localização do motorista: {str(e)}")
        return False

def obter_corrida_em_andamento(cpf_motorista):
    """Obtém a corrida em andamento de um motorista"""
    try:
        usuario = Usuario.objects.get(cpf=cpf_motorista, tipo_usuario='MOTORISTA')
        motorista = Motorista.objects.get(usuario=usuario)
        
        # Buscar corrida em andamento
        corrida = Corrida.objects.filter(
            motorista=motorista,
            status__in=['ACEITA', 'EM_ANDAMENTO']
        ).first()
        
        if corrida:
            return {
                'corrida_id': str(corrida.id),
                'passageiro_cpf': corrida.passageiro.usuario.cpf if corrida.passageiro else None,
                'status': corrida.status
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao obter corrida em andamento: {str(e)}")
        return None

def finalizar_corrida(corrida_id, motorista_cpf, status='FINALIZADA'):
    """Finaliza uma corrida"""
    try:
        # Verificar se a corrida existe e está em andamento
        corrida = Corrida.objects.get(id=corrida_id)
        
        # Verificar se o motorista é o mesmo da corrida
        usuario = Usuario.objects.get(cpf=motorista_cpf, tipo_usuario='MOTORISTA')
        motorista = Motorista.objects.get(usuario=usuario)
        
        if corrida.motorista != motorista:
            logger.error(f"Motorista {motorista_cpf} não está associado à corrida {corrida_id}")
            return False, None
        
        # Verificar se o status da corrida permite finalização
        if corrida.status not in ['ACEITA', 'EM_ANDAMENTO', 'MOTORISTA_CHEGOU']:
            logger.error(f"Corrida {corrida_id} não pode ser finalizada com status {corrida.status}")
            return False, None
        
        # Atualizar a corrida
        # Se o status recebido for FINALIZADA_PENDENTE_AVALIACAO, tratamos internamente como FINALIZADA
        status_interno = 'FINALIZADA' if status == 'FINALIZADA_PENDENTE_AVALIACAO' else status
        corrida.status = status_interno
        corrida.data_fim = timezone.now()
        corrida.save()
        
        # Log o status original para depuração
        if status != status_interno:
            logger.info(f"Status original 'FINALIZADA_PENDENTE_AVALIACAO' convertido para 'FINALIZADA' internamente")
        
        # Atualizar status do motorista
        motorista.status = 'DISPONIVEL'
        motorista.esta_disponivel = True
        motorista.save()
        
        logger.info(f"Corrida {corrida_id} finalizada pelo motorista {motorista_cpf} com status {status_interno}")
        
        # Retorna True e o CPF do passageiro para notificação
        return True, corrida.passageiro.usuario.cpf if corrida.passageiro else None
        
    except Exception as e:
        logger.error(f"Erro ao finalizar corrida: {str(e)}")
        return False, None

def cancelar_corrida(corrida_id, user_cpf, user_tipo, motivo, status='CANCELADA'):
    """Cancela uma corrida"""
    try:
        # Verificar se a corrida existe
        corrida = Corrida.objects.filter(id=corrida_id).first()
        if not corrida:
            logger.error(f"Corrida com ID {corrida_id} não encontrada")
            return False, None
        
        # Verificar se o usuário está associado à corrida
        if user_tipo == 'MOTORISTA':
            usuario = Usuario.objects.get(cpf=user_cpf, tipo_usuario='MOTORISTA')
            motorista = Motorista.objects.get(usuario=usuario)
            
            if corrida.motorista != motorista:
                logger.error(f"Motorista {user_cpf} não está associado à corrida {corrida_id}")
                return False, None
            
            outro_cpf = corrida.passageiro.usuario.cpf if corrida.passageiro else None
        else:  # PASSAGEIRO
            usuario = Usuario.objects.get(cpf=user_cpf, tipo_usuario='PASSAGEIRO')
            passageiro = Passageiro.objects.get(usuario=usuario)
            
            if corrida.passageiro != passageiro:
                logger.error(f"Passageiro {user_cpf} não está associado à corrida {corrida_id}")
                return False, None
            
            outro_cpf = corrida.motorista.usuario.cpf if corrida.motorista else None
        
        # Verificar se o status da corrida permite cancelamento
        if corrida.status not in ['PENDENTE', 'ACEITA', 'EM_ANDAMENTO', 'MOTORISTA_CHEGOU']:
            logger.error(f"Corrida {corrida_id} não pode ser cancelada com status {corrida.status}")
            return False, None
        
        # Atualizar a corrida
        corrida.status = status  # Usar o status fornecido em vez de hardcoded 'CANCELADA'
        corrida.motivo_cancelamento = motivo
        corrida.cancelada_por_tipo = user_tipo
        corrida.cancelada_por_cpf = user_cpf
        corrida.data_cancelamento = timezone.now()
        corrida.save()
        
        # Se tiver motorista, atualizar status
        if corrida.motorista:
            motorista = corrida.motorista
            motorista.status = 'DISPONIVEL'
            motorista.esta_disponivel = True
            motorista.save()
        
        logger.info(f"Corrida {corrida_id} cancelada por {user_tipo} {user_cpf}. Motivo: {motivo}")
        
        # Sincronizar o estado em memória das corridas em andamento
        try:
            # Garantir que essa corrida seja removida de qualquer cache em memória
            global corridas_em_andamento
            if 'corridas_em_andamento' in globals() and corridas_em_andamento and corrida.id in corridas_em_andamento:
                del corridas_em_andamento[corrida.id]
                logger.info(f"Corrida {corrida_id} removida do cache em memória após cancelamento")
            
            # Sincronizar todas as corridas em andamento
            sincronizar_corridas_em_andamento()
        except Exception as sync_error:
            logger.error(f"Erro ao sincronizar estado em memória após cancelamento: {str(sync_error)}")
        
        # Retorna True e o CPF da outra parte para notificação
        return True, outro_cpf
        
    except Exception as e:
        logger.error(f"Erro ao cancelar corrida: {str(e)}")
        return False, None

def registrar_chegada_motorista(corrida_id, motorista_cpf):
    """Registra a chegada do motorista ao local de embarque"""
    try:
        corrida = Corrida.objects.get(id=corrida_id)
        corrida.status = 'MOTORISTA_CHEGOU'
        corrida.data_chegada_motorista = timezone.now()
        corrida.save()
        return True
    except Corrida.DoesNotExist:
        logger.error(f"Corrida {corrida_id} não encontrada para registrar chegada")
        return False

def cancelar_corrida_sem_motoristas(corrida_id):
    """Cancela uma corrida automaticamente quando não há motoristas disponíveis"""
    try:
        corrida = Corrida.objects.get(id=corrida_id)
        corrida.status = 'CANCELADA'
        corrida.motivo_cancelamento = 'Não havia motoristas disponíveis no momento'
        corrida.cancelada_por_tipo = 'SISTEMA'
        corrida.data_cancelamento = timezone.now()
        corrida.save()
        logger.info(f"Corrida {corrida_id} cancelada automaticamente por falta de motoristas disponíveis")
        return True
    except Exception as e:
        logger.error(f"Erro ao cancelar corrida sem motoristas: {str(e)}")
        return False

def iniciar_corrida(corrida_id, motorista_cpf, status='EM_ANDAMENTO'):
    """Inicia uma corrida após o motorista chegar e o passageiro embarcar"""
    try:
        # Verificar se a corrida existe e está com status de motorista chegou
        try:
            corrida = Corrida.objects.get(id=corrida_id)
        except Corrida.DoesNotExist:
            logger.error(f"Corrida {corrida_id} não encontrada para iniciar")
            return False, None
            
        # Verificar se o motorista é o mesmo da corrida
        try:
            usuario = Usuario.objects.get(cpf=motorista_cpf, tipo_usuario='MOTORISTA')
            motorista = Motorista.objects.get(usuario=usuario)
            
            if corrida.motorista != motorista:
                logger.error(f"Motorista {motorista_cpf} não está associado à corrida {corrida_id}")
                return False, None
        except (Usuario.DoesNotExist, Motorista.DoesNotExist):
            logger.error(f"Motorista {motorista_cpf} não encontrado")
            return False, None
        
        # Atualizar o status da corrida para EM_ANDAMENTO
        corrida.status = status
        corrida.data_inicio = timezone.now()
        corrida.save()
        
        logger.info(f"Corrida {corrida_id} iniciada pelo motorista {motorista_cpf}. Status atualizado para: {status}")
        
        # Retornar True e o CPF do passageiro para notificação
        return True, corrida.passageiro.usuario.cpf if corrida.passageiro else None
    except Exception as e:
        logger.error(f"Erro ao iniciar corrida: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

# Função para verificar corridas em andamento do motorista
def verificar_corrida_em_andamento_motorista(motorista_cpf):
    """
    Verifica se existe alguma corrida em andamento para o motorista especificado.
    
    Args:
        motorista_cpf: CPF do motorista
    
    Returns:
        dict: Informações da corrida em andamento ou None
    """
    from corridas.models import Corrida
    
    try:
        print(f"[DEBUG] Verificando corridas em andamento para motorista CPF: {motorista_cpf}")
        
        # Verificar explicitamente se o status NÃO é CANCELADA ou FINALIZADA
        corridas = Corrida.objects.filter(
            motorista__cpf=motorista_cpf,  # Usando o campo cpf dentro do relacionamento
            status__in=['ACEITA', 'MOTORISTA_CHEGOU', 'EM_ANDAMENTO', 'A_CAMINHO']
        ).exclude(
            status__in=['CANCELADA', 'FINALIZADA']  # Excluir explicitamente corridas canceladas ou finalizadas
        ).order_by('-data_solicitacao')
        
        print(f"[DEBUG] Total de corridas encontradas: {corridas.count()}")
        
        if not corridas.exists():
            print(f"[DEBUG] Nenhuma corrida em andamento encontrada para motorista {motorista_cpf}")
            return None
            
        # Pegar a corrida mais recente
        corrida = corridas.first()
        print(f"[DEBUG] Corrida encontrada ID: {corrida.id}, status: {corrida.status}")
        
        # Log adicional para verificar se a corrida foi cancelada
        if hasattr(corrida, 'data_cancelamento') and corrida.data_cancelamento:
            print(f"[ALERTA] Corrida {corrida.id} está marcada com data de cancelamento ({corrida.data_cancelamento}), mas status é {corrida.status}")
            # Se a corrida tiver data de cancelamento mas não estiver com status CANCELADA, recusar
            return None
            
        # Se encontrar uma corrida, retornar os dados no formato necessário
        return {
            'corridaId': str(corrida.id),
            'passageiro': {
                'cpf': corrida.passageiro.usuario.cpf if corrida.passageiro and corrida.passageiro.usuario else None,
                'nome': corrida.passageiro.usuario.nome if corrida.passageiro and corrida.passageiro.usuario else None,
                'sobrenome': corrida.passageiro.usuario.sobrenome if corrida.passageiro and corrida.passageiro.usuario else None,
                'telefone': corrida.passageiro.usuario.telefone if corrida.passageiro and corrida.passageiro.usuario else None
            },
            'origem': {
                'latitude': float(corrida.origem_lat),
                'longitude': float(corrida.origem_lng),
                'descricao': corrida.origem_descricao
            },
            'destino': {
                'latitude': float(corrida.destino_lat),
                'longitude': float(corrida.destino_lng),
                'descricao': corrida.destino_descricao
            },
            'status': corrida.status,
            'distancia': float(corrida.distancia),
            'tempo_estimado': corrida.tempo_estimado,
            'valor': float(corrida.valor)
        }
    except Exception as e:
        import logging
        import traceback
        logging.error(f"Erro ao verificar corrida em andamento para motorista {motorista_cpf}: {str(e)}")
        traceback.print_exc()  # Adicionar traceback para mais detalhes
        return None

def verificar_corrida_em_andamento_passageiro(passageiro_cpf):
    """Verifica se o passageiro tem alguma corrida em andamento e retorna os detalhes"""
    try:
        usuario = Usuario.objects.get(cpf=passageiro_cpf, tipo_usuario='PASSAGEIRO')
        passageiro = Passageiro.objects.get(usuario=usuario)
        
        # Buscar corrida atual do passageiro (em qualquer estado que não seja finalizado ou cancelado)
        corrida = Corrida.objects.filter(
            passageiro=passageiro,
            status__in=['PENDENTE', 'ACEITA', 'MOTORISTA_CHEGOU', 'EM_ANDAMENTO']
        ).order_by('-data_aceite').first()
        
        if not corrida:
            logger.info(f"Nenhuma corrida em andamento para o passageiro {passageiro_cpf}")
            return None
        
        # Montar objeto de resposta com todos os dados necessários
        motorista_info = None
        if corrida.motorista:
            motorista = corrida.motorista
            motorista_info = {
                'nome': motorista.usuario.get_full_name(),
                'cpf': motorista.usuario.cpf,
                'telefone': motorista.usuario.telefone,
                'modeloCarro': motorista.modelo_veiculo,
                'corCarro': motorista.cor_veiculo,
                'placaCarro': motorista.placa_veiculo
            }
        
        # Converter valores decimais para float para serialização JSON
        resposta = {
            'corridaId': str(corrida.id),
            'status': corrida.status,
            'motorista': motorista_info,
            'origem': {
                'latitude': float(corrida.origem_lat),
                'longitude': float(corrida.origem_lng),
                'descricao': corrida.origem_descricao
            },
            'destino': {
                'latitude': float(corrida.destino_lat),
                'longitude': float(corrida.destino_lng),
                'descricao': corrida.destino_descricao
            },
            'valor': float(corrida.valor),
            'distancia': float(corrida.distancia),
            'tempo_estimado': corrida.tempo_estimado,
            'data_solicitacao': corrida.data_solicitacao.isoformat(),
            'data_aceite': corrida.data_aceite.isoformat() if corrida.data_aceite else None,
            'data_chegada': corrida.data_chegada_motorista.isoformat() if hasattr(corrida, 'data_chegada_motorista') and corrida.data_chegada_motorista else None,
            'data_inicio': corrida.data_inicio.isoformat() if hasattr(corrida, 'data_inicio') and corrida.data_inicio else None
        }
        
        logger.info(f"Corrida em andamento encontrada para o passageiro {passageiro_cpf}: ID {corrida.id}, status {corrida.status}")
        return resposta
        
    except Exception as e:
        logger.error(f"Erro ao buscar corrida em andamento do passageiro: {str(e)}")
        return None

def avaliar_motorista(corrida_id, passageiro_cpf, avaliacao, comentario=None):
    """
    Passageiro avalia o motorista após a corrida
    - avaliacao: valor de 1 a 5 estrelas
    - comentario: comentário opcional sobre a experiência
    """
    try:
        # Verificar se a corrida existe e está finalizada
        corrida = Corrida.objects.get(id=corrida_id)
        
        if corrida.status not in ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO']:
            logger.error(f"Tentativa de avaliar motorista para corrida não finalizada: {corrida_id}")
            return False, None
            
        # Verificar se o passageiro é o mesmo da corrida
        usuario = Usuario.objects.get(cpf=passageiro_cpf, tipo_usuario='PASSAGEIRO')
        passageiro = Passageiro.objects.get(usuario=usuario)
        
        if corrida.passageiro != passageiro:
            logger.error(f"Passageiro {passageiro_cpf} não autorizado a avaliar esta corrida: {corrida_id}")
            return False, None
            
        # Verificar se o motorista está atribuído à corrida
        if not corrida.motorista:
            logger.error(f"Corrida {corrida_id} não possui motorista para avaliar")
            return False, None
            
        # Garantir que avaliação está entre 1 e 5
        avaliacao_normalizada = max(1, min(5, int(avaliacao)))
        
        # Registrar a avaliação na corrida
        corrida.avaliacao_motorista = avaliacao_normalizada
        corrida.comentario_motorista = comentario
        corrida.data_avaliacao_motorista = timezone.now()
        corrida.save(update_fields=['avaliacao_motorista', 'comentario_motorista', 'data_avaliacao_motorista'])
        
        # Atualizar a média de avaliações do motorista
        motorista = corrida.motorista
        
        # OTIMIZAÇÃO: Usar agregação do Django para calcular a média diretamente
        from django.db.models import Avg
        nova_media = Corrida.objects.filter(
            motorista=motorista,
            avaliacao_motorista__isnull=False
        ).aggregate(media=Avg('avaliacao_motorista'))['media']
        
        if nova_media is not None:
            motorista.avaliacao_media = nova_media
            motorista.save(update_fields=['avaliacao_media'])
            logger.info(f"Média de avaliações do motorista atualizada: {nova_media:.2f}")
        
        logger.info(f"Avaliação do motorista realizada com sucesso: corrida {corrida_id}, passageiro {passageiro_cpf}, nota {avaliacao_normalizada}")
        logger.info(f"Motorista da corrida {corrida_id} avaliado com {avaliacao_normalizada} estrelas pelo passageiro {passageiro_cpf}")
        
        # Retornar True e o CPF do motorista para notificação
        return True, motorista.usuario.cpf
        
    except Corrida.DoesNotExist:
        logger.error(f"Corrida {corrida_id} não encontrada para avaliação")
        return False, None
    except (Usuario.DoesNotExist, Passageiro.DoesNotExist):
        logger.error(f"Passageiro com CPF {passageiro_cpf} não encontrado")
        return False, None
    except Exception as e:
        logger.error(f"Erro ao avaliar motorista: {str(e)}")
        return False, None

def avaliar_passageiro(corrida_id, motorista_cpf, avaliacao, comentario=None):
    """
    Motorista avalia o passageiro após a corrida
    - avaliacao: valor de 1 a 5 estrelas
    - comentario: comentário opcional sobre a experiência
    """
    try:
        # Verificar se a corrida existe e está finalizada
        corrida = Corrida.objects.get(id=corrida_id)
        
        if corrida.status not in ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO']:
            logger.error(f"Tentativa de avaliar passageiro para corrida não finalizada: {corrida_id}")
            return False, None
            
        # Verificar se o motorista é o mesmo da corrida
        usuario = Usuario.objects.get(cpf=motorista_cpf, tipo_usuario='MOTORISTA')
        motorista = Motorista.objects.get(usuario=usuario)
        
        if corrida.motorista != motorista:
            logger.error(f"Motorista {motorista_cpf} não autorizado a avaliar esta corrida: {corrida_id}")
            return False, None
            
        # Verificar se o passageiro está atribuído à corrida
        if not corrida.passageiro:
            logger.error(f"Corrida {corrida_id} não possui passageiro para avaliar")
            return False, None
            
        # Garantir que avaliação está entre 1 e 5
        avaliacao_normalizada = max(1, min(5, int(avaliacao)))
        
        # Registrar a avaliação na corrida
        corrida.avaliacao_passageiro = avaliacao_normalizada
        corrida.comentario_passageiro = comentario
        corrida.data_avaliacao_passageiro = timezone.now()
        corrida.save(update_fields=['avaliacao_passageiro', 'comentario_passageiro', 'data_avaliacao_passageiro'])
        
        # Atualizar a média de avaliações do passageiro
        passageiro = corrida.passageiro
        corridas_avaliadas = Corrida.objects.filter(
            passageiro=passageiro,
            avaliacao_passageiro__isnull=False
        )
        
        total_avaliacoes = corridas_avaliadas.count()
        soma_avaliacoes = sum(c.avaliacao_passageiro for c in corridas_avaliadas)
        
        if total_avaliacoes > 0:
            passageiro.avaliacao_media = soma_avaliacoes / total_avaliacoes
            passageiro.save(update_fields=['avaliacao_media'])
            
        logger.info(f"Passageiro da corrida {corrida_id} avaliado com {avaliacao_normalizada} estrelas pelo motorista {motorista_cpf}")
        
        # Retornar True e o CPF do passageiro para notificação
        return True, passageiro.usuario.cpf
        
    except Corrida.DoesNotExist:
        logger.error(f"Corrida {corrida_id} não encontrada para avaliação")
        return False, None
    except (Usuario.DoesNotExist, Motorista.DoesNotExist):
        logger.error(f"Motorista com CPF {motorista_cpf} não encontrado")
        return False, None
    except Exception as e:
        logger.error(f"Erro ao avaliar passageiro: {str(e)}")
        return False, None

def obter_dados_avaliacao_corrida(corrida_id):
    """
    Retorna os dados de avaliação de uma corrida específica
    Útil para verificar se ambas as partes já avaliaram
    """
    try:
        corrida = Corrida.objects.get(id=corrida_id)
        
        # Preparar os dados de avaliação da corrida
        dados_avaliacao = {
            'corridaId': str(corrida.id),
            'status': corrida.status,
            'avaliacao_motorista': {
                'nota': corrida.avaliacao_motorista,
                'comentario': corrida.comentario_motorista,
                'data': corrida.data_avaliacao_motorista.isoformat() if corrida.data_avaliacao_motorista else None,
                'realizada': corrida.avaliacao_motorista is not None
            },
            'avaliacao_passageiro': {
                'nota': corrida.avaliacao_passageiro,
                'comentario': corrida.comentario_passageiro,
                'data': corrida.data_avaliacao_passageiro.isoformat() if corrida.data_avaliacao_passageiro else None,
                'realizada': corrida.avaliacao_passageiro is not None
            },
            'ambos_avaliaram': (corrida.avaliacao_motorista is not None) and (corrida.avaliacao_passageiro is not None)
        }
        
        logger.info(f"Dados de avaliação obtidos para corrida {corrida_id}")
        return dados_avaliacao
        
    except Corrida.DoesNotExist:
        logger.error(f"Corrida {corrida_id} não encontrada ao obter dados de avaliação")
        return None
    except Exception as e:
        logger.error(f"Erro ao obter dados de avaliação da corrida: {str(e)}")
        return None

def atualizar_status_corrida(corrida_id, novo_status):
    """
    Atualiza o status de uma corrida no banco de dados.
    """
    try:
        logger.info(f"[DEBUG] Iniciando atualização de status da corrida {corrida_id} para {novo_status}")
        
        try:
            corrida = Corrida.objects.get(id=corrida_id)
        except Corrida.DoesNotExist:
            logger.error(f"[ERRO] Corrida {corrida_id} não encontrada para atualização de status")
            return False
            
        status_anterior = corrida.status
        logger.info(f"[DEBUG] Status atual da corrida {corrida_id}: {status_anterior}")
        
        # Verificar se é uma transição de status válida
        status_validos = {
            'PENDENTE': ['ACEITA', 'CANCELADA'],
            'ACEITA': ['A_CAMINHO', 'MOTORISTA_CHEGOU', 'CANCELADA'],
            'A_CAMINHO': ['MOTORISTA_CHEGOU', 'CANCELADA'],
            'MOTORISTA_CHEGOU': ['EM_ANDAMENTO', 'CANCELADA'],
            'EM_ANDAMENTO': ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO', 'CANCELADA'],
            'FINALIZADA_PENDENTE_AVALIACAO': ['FINALIZADA'],
            'FINALIZADA': [],  # Status final
            'CANCELADA': []    # Status final
        }
        
        if status_anterior in status_validos and novo_status not in status_validos.get(status_anterior, []):
            logger.warning(f"[AVISO] Transição de status inválida: de {status_anterior} para {novo_status}")
            # Permitir a transição mesmo assim, apenas registrando o aviso
        
        corrida.status = novo_status
        logger.info(f"[DEBUG] Novo status definido: {corrida.status}")
        
        # Se estiver finalizando a corrida, registrar a data de finalização
        if novo_status in ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO'] and status_anterior not in ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO']:
            corrida.data_fim = timezone.now()
            logger.info(f"[DEBUG] Data de finalização registrada: {corrida.data_fim}")
            
            # Se o motorista existe, atualizar seu status
            if corrida.motorista:
                motorista = corrida.motorista
                motorista_antes = f"Status: {motorista.status}, Disponível: {motorista.esta_disponivel}"
                
                motorista.status = 'DISPONIVEL'
                motorista.esta_disponivel = True
                motorista.save(update_fields=['status', 'esta_disponivel'])
                
                logger.info(f"[DEBUG] Status do motorista atualizado: {motorista_antes} -> Status: DISPONIVEL, Disponível: True")
        
        # Adicionar registro de data específico para cada transição de status
        if novo_status == 'A_CAMINHO' and not hasattr(corrida, 'data_a_caminho'):
            corrida.data_a_caminho = timezone.now()
            logger.info(f"[DEBUG] Data 'a caminho' registrada: {corrida.data_a_caminho}")
        elif novo_status == 'MOTORISTA_CHEGOU' and not hasattr(corrida, 'data_chegada_motorista'):
            corrida.data_chegada_motorista = timezone.now()
            logger.info(f"[DEBUG] Data de chegada do motorista registrada: {corrida.data_chegada_motorista}")
        elif novo_status == 'EM_ANDAMENTO' and not hasattr(corrida, 'data_inicio'):
            corrida.data_inicio = timezone.now()
            logger.info(f"[DEBUG] Data de início da corrida registrada: {corrida.data_inicio}")
        elif novo_status in ['FINALIZADA', 'FINALIZADA_PENDENTE_AVALIACAO'] and not hasattr(corrida, 'data_fim'):
            corrida.data_fim = timezone.now()
            logger.info(f"[DEBUG] Data de finalização registrada: {corrida.data_fim}")
        
        # Garantir a persistência imediata da alteração com flush
        try:
            corrida.save()
            from django.db import connection
            connection.commit()
            logger.info(f"[SUCESSO] Status da corrida {corrida_id} atualizado de {status_anterior} para {novo_status}")
            return True
        except Exception as save_error:
            logger.error(f"[ERRO] Falha ao salvar alteração no banco de dados: {str(save_error)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
    except Exception as e:
        logger.error(f"[ERRO] Erro ao atualizar status da corrida {corrida_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def registrar_mensagem_chat(corrida_id, tipo_remetente, conteudo):
    """
    Registra uma nova mensagem de chat no banco de dados
    
    Args:
        corrida_id: UUID da corrida
        tipo_remetente: 'PASSAGEIRO' ou 'MOTORISTA'
        conteudo: texto da mensagem
        
    Returns:
        mensagem: objeto MensagemChat se registrado com sucesso, None caso contrário
    """
    try:
        from corridas.models import Corrida, MensagemChat
        
        # Verificar se a corrida existe
        try:
            corrida = Corrida.objects.get(id=corrida_id)
        except Corrida.DoesNotExist:
            logger.error(f"Corrida {corrida_id} não encontrada")
            return None
            
        # Verificar se o tipo de remetente é válido
        if tipo_remetente not in ['PASSAGEIRO', 'MOTORISTA']:
            logger.error(f"Tipo de remetente inválido: {tipo_remetente}")
            return None
            
        # Registrar a mensagem
        mensagem = MensagemChat.objects.create(
            corrida=corrida,
            tipo_remetente=tipo_remetente,
            conteudo=conteudo
        )
        
        logger.info(f"Mensagem de chat registrada. ID: {mensagem.id}, Corrida: {corrida_id}, Remetente: {tipo_remetente}")
        return mensagem
        
    except Exception as e:
        logger.error(f"Erro ao registrar mensagem de chat: {str(e)}")
        return None

def obter_mensagens_chat(corrida_id, marcar_como_lidas=False):
    """
    Obtém todas as mensagens de chat de uma corrida
    
    Args:
        corrida_id: UUID da corrida
        marcar_como_lidas: se True, marca todas as mensagens como lidas
        
    Returns:
        lista de mensagens no formato de dicionário
    """
    try:
        from corridas.models import Corrida, MensagemChat
        
        # Verificar se a corrida existe
        try:
            corrida = Corrida.objects.get(id=corrida_id)
        except Corrida.DoesNotExist:
            logger.error(f"Corrida {corrida_id} não encontrada")
            return []
            
        # Obter as mensagens
        mensagens = MensagemChat.objects.filter(corrida=corrida).order_by('data_envio')
        
        # Marcar como lidas, se solicitado
        if marcar_como_lidas:
            mensagens.filter(lida=False).update(lida=True)
            
        # Converter para formato de dicionário
        resultado = []
        for msg in mensagens:
            resultado.append({
                'id': str(msg.id),
                'remetente': msg.tipo_remetente,
                'conteudo': msg.conteudo,
                'data_envio': msg.data_envio.isoformat(),
                'lida': msg.lida
            })
            
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao obter mensagens de chat: {str(e)}")
        return []

def sincronizar_corridas_em_andamento():
    """Sincroniza o estado das corridas em andamento no banco de dados com as variáveis em memória."""
    try:
        # Buscar todas as corridas em andamento no banco de dados
        corridas_ativas = Corrida.objects.filter(status__in=['ACEITA', 'EM_ANDAMENTO'])

        # Atualizar as variáveis em memória (exemplo: corridas_em_andamento)
        global corridas_em_andamento
        corridas_em_andamento = {corrida.id: corrida for corrida in corridas_ativas}

        logger.info("Sincronização de corridas em andamento concluída com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao sincronizar corridas em andamento: {str(e)}")
