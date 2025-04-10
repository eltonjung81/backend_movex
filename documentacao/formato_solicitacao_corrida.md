# Formato de Dados para Solicitação de Corrida

Este documento descreve o formato de dados esperado ao solicitar uma corrida através da API WebSocket.

## Evento: `solicitar_corrida`

Quando um passageiro deseja solicitar uma corrida, o front-end deve enviar uma mensagem WebSocket com o seguinte formato:

```json
{
  "type": "solicitar_corrida",
  "passageiro": {
    "cpf": "12345678900",
    "nome": "Nome",
    "sobrenome": "Sobrenome",
    "telefone": "51999999999",
    "email": "passageiro@exemplo.com"  // Opcional
  },
  "origem": {
    "latitude": -30.0277,
    "longitude": -51.2287
  },
  "destino": {
    "latitude": -30.0377,
    "longitude": -51.2187
  },
  "origem_descricao": "Rua Exemplo, 123 - Centro",
  "destino_descricao": "Avenida Modelo, 456 - Bairro",
  "valor": 25.50,
  "distancia": 5.2,
  "tempo_estimado": 15,
  "info_adicional": "Por favor, aguarde na entrada principal" // Opcional
}
```

### Campos Obrigatórios:

- **type**: Deve ser "solicitar_corrida"
- **passageiro**: Objeto com informações do passageiro
  - **cpf**: CPF do passageiro
  - **nome**: Nome do passageiro
  - **sobrenome**: Sobrenome do passageiro
  - **telefone**: Telefone para contato
- **origem**: Objeto com coordenadas de origem
  - **latitude**: Latitude do ponto de origem
  - **longitude**: Longitude do ponto de origem
- **destino**: Objeto com coordenadas de destino
  - **latitude**: Latitude do ponto de destino
  - **longitude**: Longitude do ponto de destino
- **valor**: Valor estimado da corrida em reais
- **distancia**: Distância estimada em quilômetros
- **tempo_estimado**: Tempo estimado em minutos

### Campos Opcionais:

- **origem_descricao**: Descrição textual do local de origem
- **destino_descricao**: Descrição textual do local de destino
- **info_adicional**: Informações adicionais para o motorista
- **contato_alternativo**: Contato alternativo para o passageiro

## Resposta: `corrida_registrada`

Após o processamento bem-sucedido, o servidor responderá com:

```json
{
  "type": "corrida_registrada",
  "corridaId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Corrida registrada com sucesso"
}
```

## Resposta: `erro_corrida`

Em caso de erro, o servidor responderá com:

```json
{
  "type": "erro_corrida",
  "message": "Descrição do erro"
}
```

## Fluxo Completo

1. Passageiro envia solicitação de corrida
2. Servidor valida os dados
3. Servidor registra a corrida no banco de dados
4. Servidor notifica motoristas próximos
5. Motorista aceita a corrida
6. Servidor notifica o passageiro sobre a aceitação
7. Corrida prossegue normalmente

## Observações

- Todos os campos marcados como obrigatórios devem estar presentes na solicitação
- As coordenadas geográficas devem estar no formato WGS84 (padrão GPS)
- Os valores monetários devem ser enviados sem formatação, usando ponto como separador decimal
