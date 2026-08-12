# CFD Adaptive System - Fase 1
## Motor tecnico classico + correlacao + VaR de portfolio + ambiente segregado

Implementa a Fase 1 do plano institucional: indicadores tecnicos (EMA/RSI/ATR/Bollinger),
deteccao de regime via ADWIN, correlacao rolante entre pares (Markowitz), VaR de portfolio
(parametrico + Monte Carlo), filtro de calendario economico, e suite de testes unitarios
com 39 casos de teste cobrindo todas as funcoes puras de calculo (100% passando).

## Simbolos configurados (conta Deriv-Demo 41207839)
EURUSD, GBPUSD, USDCHF, USDJPY, XAUUSD, BTCUSD

## Instalacao

```bash
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml

docker compose -f docker-compose.test.yml up -d
psql -h localhost -p 5433 -U postgres -d cfd_system_test -f database/schema.sql
pytest -v

docker compose -f docker-compose.prod.yml up -d
psql -h localhost -p 5432 -U postgres -d cfd_system -f database/schema.sql
python collector/mt5_collector.py
python engine/indicator_engine.py
python engine/correlation_engine.py
python gui/app.py
```

## Proximo passo (Fase 2)
Motor de ensemble de Reinforcement Learning (PPO/A2C/SAC) e arquitetura de execucao
Python + EA MQL5 fino, conforme o plano de implementacao v2.0.
