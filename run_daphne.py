#!/usr/bin/env python
import os
import sys
import subprocess
import signal
import time
import requests
import shutil  # Para verificar se o ngrok está no PATH

def run_daphne():
    print("Iniciando servidor Daphne com configuração de debug...")
    
    # Definir variáveis de ambiente
    os.environ['DJANGO_SETTINGS_MODULE'] = 'movex.settings'
    os.environ['PYTHONUNBUFFERED'] = '1'  # Saída sem buffer
    os.environ['DJANGO_DEBUG'] = 'True'   # Forçar modo debug
    
    # Porta do servidor
    port = 8000

    # Comando Daphne com opções otimizadas
    cmd = [
        'daphne',
        '-v', '1',  # Ajustado para incluir nível de verbosidade
        '-b', '0.0.0.0',
        '-p', str(port),
        '--access-log', '-',  # Log de acesso no stdout
        '--http-timeout', '60',  # Timeout de 1 minuto para HTTP
        '--proxy-headers',  # Suporte para cabeçalhos de proxy
        'movex.asgi:application'
    ]
    
    print(f"Executando comando: {' '.join(cmd)}")
    
    # Iniciar o processo Daphne
    process = subprocess.Popen(cmd)
    
    try:
        print("Servidor Daphne iniciado. Pressione Ctrl+C para encerrar.")
        
        # Exibir algumas informações úteis
        print("\nURLs principais:")
        print(f"- Administração: /admin/")
        print(f"- Login Motorista: /api/usuarios/login/motorista/")
        print(f"- Buscar Dados: /api/usuarios/motorista/buscar_dados/")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        process.send_signal(signal.SIGINT)
        process.wait()
        print("Servidor encerrado.")

if __name__ == "__main__":
    run_daphne()
