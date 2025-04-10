# Documentação do Servidor WebSocket - MoveX

## Funcionamento do Sistema WebSocket

O servidor WebSocket do MoveX é responsável pela comunicação em tempo real entre passageiros e motoristas, gerenciando toda a lógica de corridas desde a solicitação até a finalização.

## Imports Principais

- `json`: Para serialização e desserialização de dados
- `AsyncWebsocketConsumer`: Base para consumidores WebSocket assíncronos
- `database_sync_to_async`: Decorator para operações de banco de dados assíncronas
- Funções de `utils.py`: Cálculos de distância, verificação de horário de pico, etc.
- Funções de `database_services.py`: Operações com banco de dados

## Solicitações Recebidas pelo Servidor

| Evento | Origem | Descrição | Parâmetros Principais |
|--------|--------|-----------|------------------------|
| `ping` | Ambos | Verificação de conexão | `{type: 'ping'}` |
| `login` | Ambos | Identificação de usuário | `{type: 'login', cpf: string, tipo: string}` |
| `calcular_rota` | Passageiro | Calcular rota entre origem e destino | `{type: 'calcular_rota', start_lat: number, start_lng: number, end_lat: number, end_lng: number}` |
| `solicitar_corrida` | Passageiro | Solicitar uma nova corrida | `{type: 'solicitar_corrida', passageiro: object, origem: object, destino: object, valor: number, distancia: number, tempo_estimado: number}` |
| `aceitar_corrida` | Motorista | Aceitar uma corrida disponível | `{type: 'aceitar_corrida', corridaId: string, motoristaId: string}` |
| `atualizar_localizacao` | Motorista | Atualizar posição do motorista | `{type: 'atualizar_localizacao', motoristaId: string, latitude: number, longitude: number}` |
| `finalizar_corrida` | Motorista | Encerrar uma corrida | `{type: 'finalizar_corrida', corridaId: string, motoristaId: string}` |
| `cancelar_corrida` | Ambos | Cancelar uma corrida | `{type: 'cancelar_corrida', corridaId: string, motivo: string}` |
| `aviso_chegada` | Motorista | Avisar chegada ao local de embarque | `{type: 'aviso_chegada', corridaId: string, motoristaId: string}` |

## Emissões Enviadas pelo Servidor

| Evento | Destino | Descrição | Dados Incluídos |
|--------|---------|-----------|-----------------|
| `connection_established` | Ambos | Confirmação de conexão | Mensagem de confirmação |
| `pong` | Ambos | Resposta ao ping | Timestamp atual |
| `login_success` | Ambos | Confirmação de login | Tipo de usuário logado |
| `rota_calculada` | Passageiro | Resultado do cálculo de rota | Distância, tempo, valor, coordenadas |
| `erro_rota` | Passageiro | Erro ao calcular rota | Mensagem de erro |
| `corrida_registrada` | Passageiro | Confirmação de registro da corrida | ID da corrida, mensagem |
| `erro_corrida` | Ambos | Erro relacionado a corridas | Mensagem de erro |
| `corrida_aceita` | Motorista | Confirmação de aceitação da corrida | ID da corrida, mensagem |
| `erro` | Ambos | Mensagens de erro gerais | Mensagem de erro |

## Comunicações Entre Grupos (Channel Layer)

| Evento | Emissor → Receptor | Descrição | Dados Principais |
|--------|-------------------|-----------|------------------|
| `nova_solicitacao_corrida` | Servidor → Motoristas | Nova solicitação de corrida | Detalhes completos da corrida |
| `corrida_aceita_por_motorista` | Servidor → Passageiro | Motorista aceitou a corrida | Dados do motorista e veículo |
| `localizacao_atualizada` | Servidor → Passageiro | Atualização da posição do motorista | Coordenadas atualizadas |
| `corrida_finalizada_por_motorista` | Servidor → Passageiro | Corrida finalizada pelo motorista | ID da corrida, mensagem |
| `corrida_cancelada_por_outro` | Servidor → Ambos | Aviso de cancelamento pela outra parte | ID da corrida, motivo |
| `motorista_chegou` | Servidor → Passageiro | Motorista chegou ao local de embarque | ID da corrida, mensagem |
| `corrida_aceita_por_outro` | Servidor → Outros motoristas | Corrida já foi aceita | ID da corrida, mensagem |
| `motorista_desconectado` | Servidor → Passageiro | Motorista temporariamente desconectado | Mensagem de aviso |

## Fluxo de Comunicação de uma Corrida

1. **Solicitação de Corrida**:
   - Passageiro solicita cálculo de rota (`calcular_rota`)
   - Servidor responde com detalhes da rota (`rota_calculada`)
   - Passageiro solicita corrida (`solicitar_corrida`)
   - Servidor registra corrida e notifica motoristas próximos (`nova_solicitacao_corrida`)

2. **Aceitação da Corrida**:
   - Motorista aceita corrida (`aceitar_corrida`)
   - Servidor atualiza banco de dados e notifica:
     - O motorista que aceitou (`corrida_aceita`)
     - O passageiro (`corrida_aceita_por_motorista`)
     - Outros motoristas (`corrida_aceita_por_outro`)

3. **Durante a Corrida**:
   - Motorista atualiza localização (`atualizar_localizacao`)
   - Servidor repassa atualizações ao passageiro (`localizacao_atualizada`)
   - Motorista avisa chegada (`aviso_chegada`)
   - Servidor notifica passageiro (`motorista_chegou`)

4. **Finalização da Corrida**:
   - Motorista finaliza corrida (`finalizar_corrida`)
   - Servidor atualiza banco de dados e notifica passageiro (`corrida_finalizada_por_motorista`)

5. **Cancelamento** (pode ocorrer em qualquer momento):
   - Usuário cancela corrida (`cancelar_corrida`)
   - Servidor registra cancelamento e notifica a outra parte (`corrida_cancelada_por_outro`)

## Validações e Tratamentos de Erro

- Validação de campos obrigatórios em solicitações
- Verificação de autorização (apenas motoristas podem atualizar localização, etc.)
- Verificação de estado válido para transições (ex: só pode finalizar corrida em andamento)
- Tratamento de exceções para todas as operações de banco de dados
- Log detalhado de erros para depuração

## Integração com Banco de Dados

Todas as operações de banco de dados são tratadas de forma assíncrona usando `database_sync_to_async` para evitar bloqueio da thread do servidor WebSocket. As funções de banco de dados estão separadas no arquivo `database_services.py` para melhor organização.