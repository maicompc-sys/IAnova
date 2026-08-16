# IAnova — Resumo Completo do Sistema

> Repositório: https://github.com/maicompc-sys/IAnova
> Gerado em: 2026-08-16

---

## O que é o IAnova?

Sistema institucional de análise e geração de sinais para trading de CFDs (Forex + Cripto),
conectado ao MetaTrader 5 como fonte de dados, com armazenamento em TimescaleDB
(PostgreSQL com extensão de séries temporais) e notificação via Telegram.

---

## Arquitetura do Sistema

```
MetaTrader 5 (Deriv-Demo)
        │
        ▼
[collector/] ─────────────────────────────────► TimescaleDB (Docker)
  mt5_collector.py  (tempo real, loop 5s)              │
  historical_loader.py (carga histórica)                │
                                                        ▼
                                              [engine/indicator_engine.py]
                                              (loop 5s, consome candles)
                                                        │
                                              ├── Calcula: EMA 9/21, RSI 14,
                                              │   ATR 14, Bollinger 20, ADX 14,
                                              │   padrão de vela
                                              ├── Classifica regime: trend_up /
                                              │   trend_down / range
                                              ├── Calcula signal_score (0–100)
                                              └── Persiste em tabelas indicators/signals
                                                        │
                                           ┌────────────┴─────────────┐
                                           ▼                          ▼
                                  [notifier/]                     [gui/app.py]
                               Telegram bot                    Dashboard web
                               (alerta sinais)                 (porta 8080)
                                           │
                                           ▼
                                  [risk/]
                              risk_manager.py + var_engine.py
                              (VaR, Kelly, limites diários/semanais)
```

---

## Módulos Implementados

| Módulo                  | Arquivo(s)                              | Status                          |
|-------------------------|-----------------------------------------|---------------------------------|
| Coletor tempo real      | collector/mt5_collector.py              | ✅ Completo                      |
| Carga histórica         | collector/historical_loader.py          | ✅ Completo (fallback robusto)   |
| Motor de indicadores    | engine/indicator_engine.py              | ✅ Completo                      |
| Backtester walk-forward | engine/backtester.py                    | ✅ Completo                      |
| Correlação              | engine/correlation_engine.py            | ✅ Completo                      |
| Calendário econômico    | engine/economic_calendar.py             | ✅ Completo                      |
| Gestão de risco         | risk/risk_manager.py + var_engine.py    | ✅ Completo                      |
| GUI / Dashboard         | gui/app.py                              | ✅ Completo                      |
| Notificador Telegram    | notifier/                               | ✅ Completo                      |
| Schema banco de dados   | database/schema.sql                     | ✅ Completo                      |
| Script de inicialização | start_all.ps1                           | ✅ Completo                      |
| Validação de setup      | check_setup.py                          | ✅ Completo                      |
| Testes unitários        | tests/ (5 arquivos)                     | ✅ 39 testes                     |

---

## Lógica de Sinal (estado atual)

### Indicadores calculados

| Indicador       | Parâmetro         | Papel                              |
|-----------------|-------------------|------------------------------------|
| EMA rápida      | período 9         | Regime de mercado                  |
| EMA lenta       | período 21        | Regime de mercado                  |
| RSI             | período 14        | Filtro sobrecompra/sobrevenda       |
| ATR             | período 14        | Dimensionamento de SL/TP           |
| Bollinger Bands | período 20, 2σ    | Posição relativa do preço          |
| ADX             | período 14        | Gate obrigatório: ≥ 25             |
| Padrão de vela  | —                 | Confirmação de entrada: +15 pts    |

### Classificação de Regime

- trend_up   → EMA diff > +0.10%
- trend_down → EMA diff < -0.10%
- range      → entre ±0.10%

### Score de Sinal (0–100 pts)

  Bloco 1 – Regime + EMA confidence   → até 40 pts
  Bloco 2 – ADX ≥ 25 (gate)          → bloqueio se falhar (−30 pts)
  Bloco 3 – RSI alinhado              → +20 pts
  Bloco 4 – Bollinger position        → +20 pts
  Bloco 5 – Padrão de vela            → +15 pts (bônus)

### Score mínimo por timeframe

| Timeframe | Score mínimo |
|-----------|-------------|
| M5        | 65          |
| M15       | 60          |
| H1        | 50          |

---

## Gestão de Risco

| Parâmetro                   | Valor     |
|-----------------------------|-----------|
| Saldo inicial (backtest)    | R$ 10.000 |
| Risco máximo por trade      | 1%        |
| Stop Loss                   | ATR × 1.5 |
| Take Profit                 | ATR × 3.0 |
| R:R                         | ~1:2 (break-even ≈ 33% win rate) |
| Max drawdown diário         | 5%        |
| Max drawdown semanal        | 10%       |
| Max correlação entre posições | 0.70    |
| VaR confiança               | 95%       |
| Kelly fracionário máx       | 0.25      |

---

## Backtester — Gate 2

O backtester usa walk-forward com 3 splits (sem data leakage) e avalia:

| Critério           | Threshold                              |
|--------------------|----------------------------------------|
| Profit Factor      | > 1.3 em todos os folds               |
| Max Drawdown       | < 15% em todos os folds               |
| Sharpe Ratio       | > 0.8 em pelo menos 1 fold            |
| Perda catastrófica | < 30% em qualquer fold                |

O spread é modelado explicitamente em cada entrada (CFD real).

Como executar:
  python -m engine.backtester

---

## Ativos e Timeframes Monitorados

Símbolos:    EURUSD, GBPUSD, USDCHF, USDJPY, XAUUSD, BTCUSD
Timeframes:  M5, M15, H1
Conta:       Deriv-Demo (MT5, login 41207839)

Grupos de símbolos definidos no config:
  usd_pairs:   EURUSD, GBPUSD, USDCHF, USDJPY
  safe_haven:  XAUUSD, USDCHF, USDJPY
  risk_on:     BTCUSD, GBPUSD

---

## Infraestrutura

| Componente         | Tecnologia                                        |
|--------------------|---------------------------------------------------|
| Banco de dados     | TimescaleDB (PostgreSQL) via Docker, porta 5433   |
| Schema             | Tabelas: candles, indicators, signals             |
| Orquestração       | docker-compose.test.yml / docker-compose.prod.yml |
| Ambiente Python    | venv/ + requirements.txt                          |
| Inicialização      | start_all.ps1 (Docker + 3 processos separados)    |

---

## Histórico de Commits (resumo)

  dc1f1f6  chore: adiciona start_all.ps1, atualiza requirements.txt
  28b1503  docs: atualiza docstring backtester com lógica atual (ADX, vela, score por tf)
  c32eb32  feat: ADX + padrão de vela + fix Sharpe overflow
  3d1d892  fix: corrige AttributeError batch.dtype quando copy_rates retorna None
  74a4e49  feat: ajustes de parâmetros e loader histórico robusto
             - config: min_signal_score por timeframe (M5=65, M15=60, H1=50)
             - engine: ema threshold 0.05→0.10, confidence scale 200→400
             - backtester: build_signals recebe timeframe para score correto
             - loader: fallback copy_rates_from_pos quando copy_rates_range falha
  b08c3ee  fix: sys.path para funcionar com python -m e python direto
  b917ec1  feat: backtester walk-forward com custo de spread e Gate 2
  adf1284  feat: check_setup.py (valida MT5, Postgres e tabelas)
  f2fa47b  Fase 1 (lote 6): coletor MT5, GUI, notificador e 39 testes
  cfe6a5f  Fase 1 (lote 5): motor técnico e risk (VaR, risk manager)
  cf6fa75  Fase 1 (lote 3): config example e schema TimescaleDB
  5d6ea7e  Fase 1 (lote 2): pytest.ini, docker-compose, README
  4aa5219  Fase 1: versão completa inicial

---

## Estado Atual do Desenvolvimento

### ✅ Concluído

- Toda a Fase 1 implementada (coletor, motor técnico, risco, GUI, notificador, 39 testes)
- Backtester walk-forward com Gate 2 completo
- ADX como gate obrigatório (evita entradas em mercado lateral)
- Confirmação de entrada por padrão de vela (engolfo, martelo, shooting star)
- Historical loader com fallback robusto (copy_rates_range → copy_rates_from_pos)
- Script start_all.ps1 orquestra tudo com 1 comando

### 🔲 Próximas etapas sugeridas

1. Preencher telegram.bot_token e telegram.chat_id no config.yaml
2. Rodar check_setup.py para validar conexão MT5 + banco
3. Popular o banco: python -m collector.historical_loader
4. Rodar backtester:  python -m engine.backtester
5. Verificar se o Gate 2 é aprovado e ajustar parâmetros se necessário
6. Migrar de conta demo para conta real quando Gate 2 aprovado

---

## Como Iniciar o Sistema

1. Abra o MetaTrader 5 e faça login na conta Deriv-Demo
2. Execute no PowerShell:
     .\start_all.ps1
   O script irá:
     - Verificar/iniciar o Docker Desktop
     - Subir o TimescaleDB via docker-compose
     - Aplicar o schema SQL
     - Abrir 3 terminais: coletor, motor de indicadores e GUI

3. Acesse o dashboard em: http://localhost:8080

---

NOTA: O sistema está em modo DEMO (Deriv-Demo).
      As credenciais do Telegram ainda precisam ser preenchidas no config.yaml.
