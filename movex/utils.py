import datetime
import logging
import requests
from math import radians, cos, sin, asin, sqrt
from asgiref.sync import sync_to_async
from corridas.models import Corrida
import json
import math
from decimal import Decimal
from datetime import datetime, time

logger = logging.getLogger(__name__)

# Chave da API OpenRouteService
OPEN_ROUTE_SERVICE_APIKEY = "5b3ce3597851110001cf624862f702b709e14c648658e373a59b59de"
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# Configurações de tarifas
TARIFA_BASE = 2.5
TARIFA_KM = 0.9
TARIFA_MINUTO = 0.15
TARIFA_MINIMA = 5.0
MULTIPLICADOR_HORARIO_PICO = 1.35

# Horários de pico (horário comercial)
HORARIO_PICO_MANHA_INICIO = time(6, 0)
HORARIO_PICO_MANHA_FIM = time(9, 0)
HORARIO_PICO_TARDE_INICIO = time(17, 0)
HORARIO_PICO_TARDE_FIM = time(20, 0)

# Função para calcular distância entre coordenadas geográficas usando a fórmula de Haversine
def calcular_distancia(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em km entre duas coordenadas geográficas
    usando a fórmula de Haversine
    """
    # Converter para números para garantir
    try:
        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)
    except (ValueError, TypeError) as e:
        logger.error(f"Erro ao converter coordenadas: {e}")
        logger.error(f"Valores recebidos: lat1={lat1}, lon1={lon1}, lat2={lat2}, lon2={lon2}")
        # Retornar 0 em caso de erro, para evitar quebrar a aplicação
        return 0
    
    # Raio da Terra em km
    R = 6371.0
    
    # Converter de graus para radianos
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)  # Corrigido: Definir corretamente lon2_rad
    
    # Diferença de latitude e longitude
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distancia = R * c
    
    return distancia

# Função para verificar se o horário atual é horário de pico
def is_horario_pico():
    """
    Verifica se o horário atual é considerado horário de pico
    """
    agora = datetime.now().time()
    
    # Verificar se estamos no horário de pico da manhã ou da tarde
    pico_manha = HORARIO_PICO_MANHA_INICIO <= agora <= HORARIO_PICO_MANHA_FIM
    pico_tarde = HORARIO_PICO_TARDE_INICIO <= agora <= HORARIO_PICO_TARDE_FIM
    
    return pico_manha or pico_tarde

# Função para calcular o valor da corrida
def calcular_valor_corrida(distancia_km, tempo_minutos):
    """
    Calcula o valor da corrida baseado na distância e tempo
    """
    try:
        # Converter para float se necessário
        distancia_km = float(distancia_km)
        tempo_minutos = float(tempo_minutos)
        
        # Valor fixo por quilômetro
        valor_por_km = 2.10
        
        # Verificar se está no horário de pico
        if is_horario_pico():
            valor_por_km *= 1.4  # Aumento de 40% no horário de pico
        
        # Verificar se está no horário noturno (após as 20h)
        agora = datetime.now().time()
        if agora >= time(20, 0):
            valor_por_km *= 1.6  # Aumento de 60% no horário noturno
        
        # Calcular valor total
        valor_total = distancia_km * valor_por_km
        
        # Aplicar regras para corridas de até 5 km
        if distancia_km <= 5:
            valor_total = max(10.0, valor_total)  # Valor mínimo de R$ 10,00
            valor_total = min(10.0, valor_total)  # Valor máximo de R$ 10,00
        
        # Arredondar para 2 casas decimais
        return round(valor_total, 2)
    except Exception as e:
        logger.error(f"Erro ao calcular valor da corrida: {e}")
        # Retornar a tarifa mínima em caso de erro
        return 10.0  # Valor mínimo para corridas de até 5 km

# Função auxiliar para serializar objetos Decimal para JSON
def decimal_serializer(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError("Tipo não serializável")

# Função para consultar rota no OSRM
async def buscar_rota_openroute(start_lat, start_lng, end_lat, end_lng):
    """
    Função renomeada mas mantida para compatibilidade.
    Agora usa diretamente a API OSRM para cálculo de rotas sem tentar OpenRoute
    """
    # Logar apenas início da operação, sem repetir coordenadas detalhadas
    logger.info(f"Buscando rota: [{start_lat:.6f},{start_lng:.6f}] → [{end_lat:.6f},{end_lng:.6f}]")
    
    # Usar diretamente a API OSRM que está funcionando
    try:
        # OSRM é um serviço alternativo e gratuito que funciona corretamente
        logger.info("Usando API OSRM para rota")
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true"
        }
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info("API OSRM: resposta recebida")
                        return processar_resposta_osrm(data, logger)
                    else:
                        error_text = await response.text()
                        logger.error(f"Erro na API OSRM: {response.status}")
                        # Se falhar, vamos para o cálculo simplificado
                        raise Exception(f"Erro na API OSRM: {response.status}")
        except (ImportError, ModuleNotFoundError):
            # Fallback para requests
            logger.info("Fallback: usando requests para API OSRM")
            import requests
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info("API OSRM (via requests): resposta recebida")
                return processar_resposta_osrm(data, logger)
            else:
                logger.error(f"Erro na API OSRM (requests): {response.status_code}")
                raise Exception(f"Erro na API OSRM: {response.status_code}")
                
    except Exception as e:
        # Se todas as tentativas falharem, usar cálculo simplificado melhorado
        logger.warning(f"Usando cálculo alternativo após falha na API OSRM: {str(e)}")
        # Método simplificado como última opção
        return calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng)

async def buscar_rota_alternativa(start_lat, start_lng, end_lat, end_lng, logger):
    """Usa uma API alternativa para calcular rotas quando a principal falha"""
    # OSRM é um serviço alternativo e gratuito que pode ser usado
    logger.info("Tentando API alternativa (OSRM)")
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true"
    }
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("API alternativa: resposta recebida")
                    return processar_resposta_osrm(data, logger)
                else:
                    raise Exception(f"Erro na API alternativa: {response.status}")
    except (ImportError, ModuleNotFoundError):
        # Fallback para requests
        import requests
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info("API alternativa (via requests): resposta recebida")
            return processar_resposta_osrm(data, logger)
        else:
            raise Exception(f"Erro na API alternativa: {response.status_code}")

def processar_resposta_osrm(data, logger):
    """Processa a resposta da API OSRM"""
    if "routes" in data and len(data["routes"]) > 0:
        route = data["routes"][0]
        distancia_km = route["distance"] / 1000
        tempo_minutos = int(route["duration"] / 60)
        valor = calcular_valor_corrida(distancia_km, tempo_minutos)
        
        # Extrair coordenadas da geometria
        coordinates = []
        if "geometry" in route and "coordinates" in route["geometry"]:
            # Converter de [lon, lat] para nosso formato {latitude, longitude}
            for coord in route["geometry"]["coordinates"]:
                coordinates.append({
                    "latitude": coord[1],
                    "longitude": coord[0]
                })
        
        logger.info(f"Rota calculada via API alternativa: {distancia_km:.2f}km, {tempo_minutos}min, {len(coordinates)} pontos")
        
        return {
            "success": True,
            "distancia": distancia_km,
            "tempo_estimado": tempo_minutos,
            "valor": valor,
            "coordinates": coordinates
        }
    else:
        return None

def processar_resposta_openroute(data, logger):
    """Processa a resposta da API OpenRouteService"""
    try:
        # Verificar se a resposta contém dados de rota
        if "features" in data and len(data["features"]) > 0:
            # Extrair dados da primeira rota encontrada
            route = data["features"][0]
            
            if "properties" in route and "segments" in route["properties"]:
                # Extrair distância e duração
                segment = route["properties"]["segments"][0]
                distancia_km = segment["distance"] / 1000  # Converter metros para km
                tempo_minutos = int(segment["duration"] / 60)  # Converter segundos para minutos
                
                # Calcular valor da corrida
                valor = calcular_valor_corrida(distancia_km, tempo_minutos)
                
                # Extrair coordenadas do trajeto
                coordinates = []
                if "geometry" in route and "coordinates" in route["geometry"]:
                    # As coordenadas no OpenRouteService vêm como [longitude, latitude]
                    # Precisamos converter para o formato esperado: {latitude, longitude}
                    for coord in route["geometry"]["coordinates"]:
                        coordinates.append({
                            "latitude": coord[1],
                            "longitude": coord[0]
                        })
                
                logger.info(f"Rota calculada: {distancia_km:.2f}km, {tempo_minutos}min, {len(coordinates)} pontos")
                
                return {
                    "success": True,
                    "distancia": distancia_km,
                    "tempo_estimado": tempo_minutos,
                    "valor": valor,
                    "coordinates": coordinates
                }
    
    except Exception as e:
        logger.error(f"Erro ao processar resposta: {str(e)}")
    
    # Em caso de erro, retornar None para usar o fallback
    return None

def calcular_rota_simplificada_melhorada(start_lat, start_lng, end_lat, end_lng):
    """
    Calcula uma rota simplificada, mas com alguns pontos intermediários
    para simular melhor uma rota que segue ruas
    """
    import logging
    import random
    from math import sin, cos, radians
    
    logger = logging.getLogger(__name__)
    
    # Calcular distância direta
    distancia_km = calcular_distancia(start_lat, start_lng, end_lat, end_lng)
    
    # Estimar tempo baseado na distância (assumindo velocidade média de 30 km/h)
    tempo_estimado_min = max(5, int(distancia_km * 2))  # 2 minutos por km, mínimo 5 minutos
    
    # Calcular valor
    valor = calcular_valor_corrida(distancia_km, tempo_estimado_min)
    
    # Criar pontos intermediários para simular uma rota mais realista
    coordinates = []
    coordinates.append({"latitude": start_lat, "longitude": start_lng})
    
    # Número de pontos intermediários baseado na distância
    num_pontos = max(10, int(distancia_km * 5))  # Pelo menos 10 pontos, ou 5 pontos por km
    
    # Calcular incrementos para distribuir os pontos
    lat_inc = (end_lat - start_lat) / (num_pontos + 1)
    lng_inc = (end_lng - start_lng) / (num_pontos + 1)
    
    # Adicionar variação para simular curvas da estrada
    max_variacao = 0.0005  # Ajuste conforme necessário para simular curvas
    
    for i in range(1, num_pontos + 1):
        # Calcular ponto base na linha reta
        base_lat = start_lat + lat_inc * i
        base_lng = start_lng + lng_inc * i
        
        # Adicionar variação para simular curvas
        # Usando funções trigonométricas para criar padrões mais realistas
        variacao_lat = max_variacao * sin(radians(i * 30)) * (random.random() - 0.5)
        variacao_lng = max_variacao * cos(radians(i * 30)) * (random.random() - 0.5)
        
        coordinates.append({
            "latitude": base_lat + variacao_lat,
            "longitude": base_lng + variacao_lng
        })
    
    coordinates.append({"latitude": end_lat, "longitude": end_lng})
    
    logger.info(f"Rota calculada com método alternativo melhorado: {distancia_km:.2f}km, {tempo_estimado_min}min, {len(coordinates)} pontos")
    
    return {
        "success": True,
        "distancia": distancia_km,
        "tempo_estimado": tempo_estimado_min,
        "valor": valor,
        "coordinates": coordinates
    }

def cancelar_corrida(corrida_id, user_cpf, user_tipo, motivo, status):
    try:
        corrida = Corrida.objects.get(id=corrida_id)
        if user_tipo == 'PASSAGEIRO' and corrida.passageiro.cpf == user_cpf:
            outro_cpf = corrida.motorista.cpf
        elif user_tipo == 'MOTORISTA' and corrida.motorista.cpf == user_cpf:
            outro_cpf = corrida.passageiro.cpf
        else:
            return False, None

        corrida.status = status
        corrida.motivo_cancelamento = motivo
        corrida.save()
        return True, outro_cpf
    except Corrida.DoesNotExist:
        return False, None

# Função auxiliar para depuração de WebSocket
def debug_websocket_message(message_type, data, direction='SEND'):
    """
    Registra informações detalhadas sobre mensagens WebSocket para depuração
    com nível de detalhamento reduzido para mensagens comuns
    """
    try:
        # Filtra tipos de mensagens para reduzir logs
        if message_type in ['ping', 'pong', 'heartbeat', 'atualizar_localizacao']:
            return  # Não logar esses tipos comuns
            
        # Para eventos importantes, logar apenas o tipo sem o payload completo
        if direction == 'SEND':
            logger.debug(f"WS→ {message_type}")
        else:
            logger.debug(f"WS← {message_type}")
            
    except Exception as e:
        logger.error(f"Erro ao registrar mensagem WebSocket: {e}")
