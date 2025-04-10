FROM mcr.microsoft.com/devcontainers/python:3.11

# Instale dependências adicionais do sistema
RUN apt-get update && apt-get install -y \
    libmysqlclient-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
