import uuid
import logging
import re
from decimal import Decimal
from django.utils import timezone
from usuarios.models import Usuario, Motorista, Passageiro
from corridas.models import Corrida
from .utils import calcular_distancia

logger = logging.getLogger(__name__)

# Inicialização da variável global para armazenar corridas em andamento
corridas_em_andamento = {}

def sincronizar_corridas_em_andamento():
    """Sincroniza o estado das corridas pendentes no banco de dados com as variáveis em memória."""
    try:
        # Buscar apenas corridas PENDENTES
        corridas_pendentes = Corrida.objects.filter(status='PENDENTE')
        global corridas_em_andamento
        corridas_em_andamento = {corrida.id: corrida for corrida in corridas_pendentes}
        logger.info("Sincronização de corridas pendentes em memória concluída com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao sincronizar corridas pendentes: {str(e)}")

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

        # Após aceitar, remover da memória se existir
        global corridas_em_andamento
        if 'corridas_em_andamento' in globals() and corridas_em_andamento and corrida.id in corridas_em_andamento:
            del corridas_em_andamento[corrida.id]
            logger.info(f"Corrida {corrida.id} removida do cache em memória após ser aceita")

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

        # Após iniciar, remover da memória se existir
        global corridas_em_andamento
        if 'corridas_em_andamento' in globals() and corridas_em_andamento and corrida.id in corridas_em_andamento:
            del corridas_em_andamento[corrida.id]
            logger.info(f"Corrida {corrida.id} removida do cache em memória após ser iniciada")
        
        # Retornar True e o CPF do passageiro para notificação
        return True, corrida.passageiro.usuario.cpf if corrida.passageiro else None
    except Exception as e:
        logger.error(f"Erro ao iniciar corrida: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

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

        # Após finalizar, remover da memória se existir
        global corridas_em_andamento
        if 'corridas_em_andamento' in globals() and corridas_em_andamento and corrida.id in corridas_em_andamento:
            del corridas_em_andamento[corrida.id]
            logger.info(f"Corrida {corrida.id} removida do cache em memória após ser finalizada")
        
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

        # Após cancelar, remover da memória se existir
        global corridas_em_andamento
        if corridas_em_andamento and corrida.id in corridas_em_andamento:
            del corridas_em_andamento[corrida.id]
            logger.info(f"Corrida {corrida.id} removida do cache em memória após cancelamento")
        
        # Sincronizar o estado em memória das corridas em andamento
        try:
            # Garantir que essa corrida seja removida de qualquer cache em memória
            if corrida.id in corridas_em_andamento:
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

def limpar_corrida_da_memoria(corrida_id):
    """
    Remove uma corrida específica da memória.
    Usado principalmente quando uma corrida é excluída via admin.
    """
    try:
        global corridas_em_andamento
        if corrida_id in corridas_em_andamento:
            del corridas_em_andamento[corrida_id]
            logger.info(f"Corrida {corrida_id} removida do cache em memória após ser excluída via admin")
            return True
        return False
    except Exception as e:
        logger.error(f"Erro ao limpar corrida {corrida_id} da memória: {str(e)}")
        return False
