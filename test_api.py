import requests
import json

# URL base da API
BASE_URL = 'http://192.168.1.104:8000/api/'

def test_login():
    """Testa o endpoint de login do motorista"""
    # Note que a URL agora inclui 'usuarios/' que era omitido no include do urls.py
    url = BASE_URL + 'usuarios/login/motorista/' 
    data = {
        'cpf': '97683078039',
        'password': '123'
    }
    
    print(f"\n----- Testando login de motorista -----")
    print(f"URL: {url}")
    print(f"Dados: {data}")
    
    try:
        # Adicionando verificações de conectividade mais detalhadas
        print(f"Testando conexão com: {BASE_URL}")
        base_response = requests.get(BASE_URL, timeout=5)
        print(f"Resposta base: {base_response.status_code}")
        
        # Para debug: tentar URLs diferentes
        alt_url = 'http://192.168.1.104:8000/admin/'
        print(f"Testando URL alternativa: {alt_url}")
        alt_response = requests.get(alt_url, timeout=5)
        print(f"Resposta alternativa: {alt_response.status_code}")
        
        # Tentar o login
        response = requests.post(url, json=data)
        print(f"Status: {response.status_code}")
        print(f"Headers: {response.headers}")
        print(f"Resposta: {response.text[:200]}")
        return response.json() if response.ok else None
    except Exception as e:
        print(f"Erro: {str(e)}")
        return None

def test_buscar_dados(token=None, cpf='97683078039'):
    """Testa o endpoint buscar_dados do motorista"""
    url = BASE_URL + 'usuarios/motorista/buscar_dados/'
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = {'cpf': cpf}
    
    print(f"\n----- Testando buscar dados do motorista -----")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Dados: {data}")
    
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Resposta: {response.text[:200]}")
        return response.json() if response.ok else None
    except Exception as e:
        print(f"Erro: {str(e)}")
        return None

# Executa os testes
if __name__ == "__main__":
    login_result = test_login()
    if login_result and login_result.get('token'):
        token = login_result.get('token')
        test_buscar_dados(token)
    else:
        test_buscar_dados()
