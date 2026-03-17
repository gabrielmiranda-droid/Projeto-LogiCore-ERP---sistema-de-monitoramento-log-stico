# LogiCore ERP

LogiCore ERP e um projeto de portfolio em Python para monitoramento logistico, operacao de frota, telemetria simulada, rastreamento ao vivo, gestao de pedidos e faturamento simulado.

O sistema foi pensado para demonstrar uma arquitetura backend organizada com FastAPI, integracao com mapas, dashboard operacional e fluxo empresarial completo, do pedido ate a nota fiscal simulada.

## Descricao do Projeto

Distribuidoras e operacoes logisticos costumam depender de varios sistemas isolados para acompanhar frota, pedidos, alertas e faturamento. O LogiCore ERP centraliza esse fluxo em uma unica base:

- simulador de telemetria para veiculos
- backend FastAPI para regras de negocio e persistencia
- dashboard Streamlit para operacao
- live tracking separado para rastreamento em tempo real
- emissao de nota fiscal simulada em PDF e XML

## Principais Funcionalidades

- Cadastro e relacionamento entre clientes, produtos, pedidos, itens, motoristas, veiculos, rotas, telemetria, alertas e notas fiscais
- Simulador de caminhoes percorrendo rotas predefinidas
- Backend FastAPI com API REST organizada por camadas
- Dashboard Streamlit com KPIs, alertas, faturamento e monitoramento por veiculo
- Rota planejada com OSRM e fallback local quando o servico externo nao estiver disponivel
- Live tracking em HTML + JavaScript + Leaflet, separado do Streamlit
- Gatilho automatico de nota fiscal simulada ao colocar pedido em `EM_ROTA`
- Geracao de PDF e XML com persistencia em disco e registro no banco
- Logs estruturados e testes automatizados

## Tecnologias Utilizadas

- Python 3.12 ou 3.13
- FastAPI
- SQLAlchemy ORM
- Pydantic
- SQLite por padrao, com estrutura pronta para PostgreSQL
- Streamlit
- Folium
- Geopy
- Leaflet + OpenStreetMap
- OSRM
- ReportLab
- Pytest
- Docker e Docker Compose

## Arquitetura do Sistema

```text
simulador -> backend FastAPI -> dashboard / live tracking
```

Fluxo principal:

1. O simulador envia pacotes de telemetria para a API.
2. O backend persiste eventos, calcula alertas e atualiza o estado operacional.
3. O dashboard consome os endpoints para exibir KPIs, operacao e faturamento.
4. O live tracking usa bootstrap HTTP + WebSocket para rastreamento em tempo real.
5. Quando um pedido muda para `EM_ROTA`, o sistema gera automaticamente uma nota fiscal simulada.

## Estrutura de Pastas

```text
app/
  api/routes        -> endpoints FastAPI
  core              -> configuracao e logging
  db                -> sessao, engine e inicializacao do banco
  models            -> entidades ORM
  repositories      -> acesso a dados
  schemas           -> contratos Pydantic
  services          -> regras de negocio
  utils             -> funcoes auxiliares
dashboard/          -> aplicacao Streamlit
live_tracking/      -> mapa ao vivo em HTML/JS
scripts/            -> seed e utilitarios
simulator/          -> simulador de telemetria
storage/            -> PDFs e XMLs gerados
tests/              -> testes automatizados
```

## Como Rodar o Projeto Localmente

Compatibilidade recomendada no Windows:

- recomendado: Python `3.12`
- suportado: Python `3.13`
- nao recomendado no momento: Python `3.14`

### 1. Criar ambiente virtual

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Se necessario, use Python `3.13`:

```bash
py -3.13 -m venv .venv
```

### 2. Popular dados iniciais

```bash
python scripts/seed_data.py
```

### 3. Subir o backend

```bash
python -m uvicorn app.main:app --reload
```

### 4. Subir o dashboard

```bash
streamlit run dashboard/app.py
```

### 5. Rodar o simulador

```bash
python -m simulator.truck_simulator
```

### 6. Abrir a aplicacao

- API / Swagger: `http://127.0.0.1:8000/docs`
- Dashboard Streamlit: `http://127.0.0.1:8501`
- Live tracking: `http://127.0.0.1:8000/live-tracking/`

## Variaveis de Ambiente Relevantes

Exemplo em `.env`:

```bash
LOGICORE_API_URL=http://localhost:8000/api
LOGICORE_LIVE_TRACKING_URL=http://localhost:8000/live-tracking/
OSRM_DIRECTIONS_URL=https://router.project-osrm.org/route/v1/driving
DATABASE_URL=sqlite:///./logi_core.db
```

Se o OSRM nao estiver acessivel, o sistema continua funcionando com a rota persistida no banco.

## Exemplos de Uso

### Fluxo operacional

1. Inicie a API.
2. Inicie o dashboard.
3. Rode o simulador.
4. Acompanhe a frota no dashboard.
5. Abra o live tracking para o mapa em tempo real.

### Fluxo de faturamento

1. Crie um pedido em `POST /api/orders`.
2. Atualize o status para `EM_ROTA`.
3. Consulte a nota em `GET /api/orders/{order_id}/invoice`.
4. Baixe o PDF ou XML gerado.

### Endpoints principais

- `POST /api/telemetry`
- `GET /api/vehicles/summary`
- `GET /api/vehicles/{vehicle_id}/overview`
- `GET /api/routes`
- `GET /api/routes/{route_id}`
- `GET /api/routes/vehicles/{vehicle_id}/planned`
- `GET /api/alerts`
- `POST /api/orders`
- `PATCH /api/orders/{order_id}/status`
- `GET /api/orders/{order_id}/invoice`
- `GET /api/invoices`
- `GET /api/invoices/{invoice_id}`
- `GET /api/invoices/{invoice_id}/pdf`
- `WS /ws/vehicle/{vehicle_id}`

## Como o Sistema Funciona

Resumo do fluxo:

```text
Simulador -> Backend -> Dashboard -> Rastreamento
```

Detalhamento:

- O simulador gera telemetria e envia para o FastAPI.
- O backend valida, persiste, calcula alertas e atualiza o estado da frota.
- O dashboard consome dados consolidados para KPIs, visao geral, veiculo individual e faturamento.
- O live tracking usa uma interface separada para o mapa em tempo real, sem depender de rerender do Streamlit.

## Melhorias Futuras

- Autenticacao e controle de acesso
- Filas para ingestao assincrona de telemetria
- Observabilidade com Prometheus e Grafana
- Frontend dedicado em React
- Regras fiscais mais detalhadas
- Mais rotas e cenarios operacionais

## Licenca

Este projeto pode ser publicado como portfolio academico e profissional. Se desejar, adicione uma licenca formal como MIT antes da publicacao no GitHub.
