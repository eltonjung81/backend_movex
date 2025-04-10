# MoveX API - Documentação

## Endpoints de Usuários

### Registro de Motorista
**Endpoint:** `/api/usuarios/registro/motorista/`
**Método:** POST
**Descrição:** Registra um novo motorista no sistema.

**Formato de dados esperado:**
```json
{
  "usuario": {
    "cpf": "12345678900",
    "nome": "Nome",
    "sobrenome": "Sobrenome",
    "password": "senha123",
    "password2": "senha123",
    "telefone": "51999999999",
    "email": "email@exemplo.com" // Se vazio, será gerado automaticamente
  },
  "cnh": "1234567890",
  "categoria_cnh": "B",
  "placa_veiculo": "ABC1234",
  "modelo_veiculo": "Modelo do Carro",
  "cor_veiculo": "Cor do Carro", // Opcional, padrão é "Não informado"
  "ano_veiculo": 2023 // Opcional, padrão é 2023
}
```

**Resposta de sucesso:**
```json
{
  "message": "Motorista cadastrado com sucesso!"
}
```

### Registro de Passageiro
**Endpoint:** `/api/usuarios/registro/passageiro/`
**Método:** POST
**Descrição:** Registra um novo passageiro no sistema.

**Formato de dados esperado:**
```json
{
  "cpf": "98765432100",
  "nome": "Nome",
  "sobrenome": "Sobrenome",
  "password": "senha123",
  "password2": "senha123",
  "telefone": "51988888888",
  "email": "passageiro@exemplo.com",
  "data_nascimento": "1990-01-01", // Opcional
  "passageiro": {
    "endereco": "Endereço do passageiro" // Opcional
  }
}
```

**Resposta de sucesso:**
```json
{
  "message": "Passageiro cadastrado com sucesso!"
}
```

# Documentação de Eventos WebSocket - MoveX

Este documento lista todos os eventos WebSocket utilizados na comunicação em tempo real do sistema MoveX, separados por aplicativo (Motorista e Passageiro) e por direção (Emissão e Escuta).

## Aplicativo do Motorista

### Eventos Emitidos pelo Motorista

| Evento | Descrição | Parâmetros | Quando é emitido |
|--------|-----------|------------|------------------|
| `login` | Identifica o motorista no sistema | `{type: 'login', cpf: string, tipo: 'MOTORISTA'}` | Ao iniciar a sessão |
| `alterar_status_motorista` | Altera status entre online/offline | `{type: 'alterar_status_motorista', motoristaId: string, status: 'ONLINE' or 'OFFLINE'}` | Ao clicar no botão de status |
| `aceitar_corrida` | Aceita uma solicitação de corrida | `{type: 'aceitar_corrida', corridaId: string, motoristaId: string}` | Ao clicar em "Aceitar" |
| `recusar_corrida` | Recusa uma solicitação de corrida | `{type: 'recusar_corrida', corridaId: string, motoristaId: string}` | Ao confirmar recusa |
| `aviso_chegada` | Avisa ao passageiro que chegou ao local de embarque | `{type: 'aviso_chegada', corridaId: string, motoristaId: string}` | Ao clicar em "Avisar Chegada" |
| `iniciar_corrida` | Inicia a corrida após embarque do passageiro | `{type: 'iniciar_corrida', corridaId: string, motoristaId: string}` | Ao clicar em "Iniciar Corrida" |
| `atualizar_localizacao` | Envia a localização atual do motorista | `{type: 'atualizar_localizacao', motoristaId: string, latitude: number, longitude: number}` | Periodicamente durante a corrida |
| `finalizar_corrida` | Finaliza a corrida quando o destino é alcançado | `{type: 'finalizar_corrida', corridaId: string, motoristaId: string}` | Ao clicar em "Finalizar Corrida" |
| `cancelar_corrida` | Cancela uma corrida já aceita | `{type: 'cancelar_corrida', corridaId: string, motoristaId: string, motivo: string}` | Ao cancelar uma corrida |
| `ping` | Mantém a conexão ativa | `{type: 'ping'}` | A cada 30 segundos |

### Eventos Escutados pelo Motorista

| Evento | Descrição | Dados Recebidos | Ação Tomada |
|--------|-----------|-----------------|-------------|
| `nova_solicitacao` | Nova solicitação de corrida | Dados completos do passageiro, origem, destino, valor, etc. | Exibe para aceitar/recusar |
| `corrida_cancelada` | Passageiro cancelou a corrida | `{type: 'corrida_cancelada', corridaId: string, message: string}` | Limpa interface e notifica motorista |
| `corrida_confirmada` | Confirmação que a corrida foi aceita | `{type: 'corrida_confirmada', corridaId: string}` | Atualiza status para "A_CAMINHO" |
| `corrida_indisponivel` | Corrida aceita por outro motorista | `{type: 'corrida_indisponivel', corridaId: string, message: string}` | Remove da tela |
| `pong` | Resposta ao ping | `{type: 'pong', timestamp: string}` | Confirma conexão ativa |
| `erro` | Notificação de erro | `{type: 'erro', message: string}` | Exibe alerta |
| `connection_established` | Confirmação de conexão | `{type: 'connection_established', message: string}` | Atualiza estado de conexão |

## Aplicativo do Passageiro

### Eventos Emitidos pelo Passageiro

| Evento | Descrição | Parâmetros | Quando é emitido |
|--------|-----------|------------|------------------|
| `login` | Identifica o passageiro no sistema | `{type: 'login', cpf: string, tipo: 'PASSAGEIRO'}` | Ao iniciar a sessão |
| `calcular_rota` | Solicita cálculo de rota | `{type: 'calcular_rota', start_lat: number, start_lng: number, end_lat: number, end_lng: number, nome_passageiro: string, sobrenome_passageiro: string, cpf_passageiro: string}` | Ao selecionar destino |
| `solicitar_corrida` | Solicita uma corrida | Dados completos de passageiro, origem, destino, etc. | Ao clicar em "Chamar Motorista" |
| `cancelar_corrida` | Cancela uma corrida | `{type: 'cancelar_corrida', cpf_passageiro: string, motoristaId: string}` | Ao clicar em "Desistir" |
| `ping` | Mantém a conexão ativa | `{type: 'ping'}` | A cada 30 segundos |
| `passageiro_conectado` | Notifica conexão do passageiro | `{type: 'passageiro_conectado', cpf_passageiro: string, nome: string, sobrenome: string}` | Ao estabelecer conexão |

### Eventos Escutados pelo Passageiro

| Evento | Descrição | Dados Recebidos | Ação Tomada |
|--------|-----------|-----------------|-------------|
| `rota_calculada` | Resultado do cálculo de rota | Distância, tempo, valor, coordenadas, etc. | Exibe informações da rota no mapa |
| `erro_rota` | Erro no cálculo da rota | `{type: 'erro_rota', message: string}` | Exibe mensagem de erro |
| `corrida_registrada` | Confirmação que a corrida foi registrada | `{type: 'corrida_registrada', corridaId: string, message: string}` | Atualiza estado da corrida |
| `erro_registro_corrida` | Erro ao registrar corrida | `{type: 'erro_registro_corrida', message: string}` | Exibe mensagem de erro |
| `motorista_aceitou` | Um motorista aceitou a corrida | Dados do motorista (nome, veículo, etc) | Exibe informações do motorista |
| `localizacao_motorista` | Atualização da localização do motorista | Coordenadas atualizadas | Atualiza posição no mapa |
| `motorista_chegou` | Motorista chegou ao local de embarque | `{type: 'motorista_chegou', message: string}` | Notifica o passageiro |
| `corrida_finalizada` | Corrida foi finalizada pelo motorista | `{type: 'corrida_finalizada', message: string}` | Atualiza status e pede avaliação |
| `motorista_desconectado` | Motorista se desconectou temporariamente | `{type: 'motorista_desconectado', message: string}` | Exibe alerta |
| `pong` | Resposta ao ping | `{type: 'pong', timestamp: string}` | Confirma conexão ativa |
| `connection_established` | Confirmação de conexão | `{type: 'connection_established', message: string}` | Atualiza estado de conexão |

## Fluxo Completo de Comunicação

1. **Início**:
   - Passageiro e Motorista se conectam via WebSocket
   - Ambos enviam `login` para identificação

2. **Solicitação de Corrida**:
   - Passageiro calcula rota (`calcular_rota`)
   - Passageiro solicita corrida (`solicitar_corrida`)
   - Motoristas disponíveis recebem notificação (`nova_solicitacao`)

3. **Aceitação da Corrida**:
   - Motorista aceita a corrida (`aceitar_corrida`)
   - Passageiro recebe notificação (`motorista_aceitou`)
   - Outros motoristas recebem notificação (`corrida_indisponivel`)

4. **Durante a Corrida**:
   - Motorista atualiza localização (`atualizar_localizacao`)
   - Passageiro recebe atualizações (`localizacao_motorista`)
   - Motorista avisa chegada (`aviso_chegada`)
   - Motorista inicia corrida (`iniciar_corrida`)

5. **Finalização**:
   - Motorista finaliza corrida (`finalizar_corrida`)
   - Passageiro recebe notificação (`corrida_finalizada`)
   - Ambos podem avaliar a corrida

## Códigos de Exemplo

### Exemplo: Solicitar Corrida (Passageiro)

```javascript
const dadosCorrida = {
  type: 'solicitar_corrida',
  passageiro: {
    cpf: '12345678900',
    nome: 'João',
    sobrenome: 'Silva',
    telefone: '11999999999'
  },
  origem: {
    latitude: -23.550520,
    longitude: -46.633308
  },
  destino: {
    latitude: -23.557996,
    longitude: -46.639035
  },
  distancia: 2.5,
  tempo_estimado: 10,
  valor: 15.5
};

socket.send(JSON.stringify(dadosCorrida));
