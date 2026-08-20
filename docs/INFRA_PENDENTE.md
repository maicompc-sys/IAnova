# Itens de infraestrutura transversais pendentes

Extraido do roadmap institucional (RESUMO_SISTEMA / roteiro das fases).
Nenhum destes bloqueia o fechamento da Fase 1, mas precisam de dono e prazo.

| Item | Por que importa | Status / Prioridade |
|---|---|---|
| Credenciais Telegram | Alertas de sinal/risco nao funcionam sem isso | Alta (rapido) - ver `docs/TELEGRAM_SETUP.md` |
| Calendario economico & Noticias reais | Insercao manual substituida por API Finnhub (`collector/news_collector.py`) | Concluído (Finnhub) |
| Monitoramento (Prometheus/Grafana) | Necessario antes da Fase 3 (execucao automatica) para observar producao 24/7 | Media-Alta (antes da Fase 3) |
| EA MQL5 de execucao | Nao existe ainda -- e o nucleo da Fase 3 (esqueleto inicial em `mql5/IAnova_EA.mq5`) | Alta (quando chegar na Fase 3) |
| Documentacao de decisoes de parametros | Toda mudanca de threshold registrada em `docs/DECISOES_PARAMETROS.md` | Concluído (`docs/DECISOES_PARAMETROS.md`) |


## Calendario economico - proximos passos sugeridos

- Avaliar API (ForexFactory nao tem API oficial estavel; considerar scrapers
  mantidos pela comunidade ou fontes alternativas como TradingEconomics/Finnhub).
- Definir schema de eventos (data, moeda, impacto, valor previsto/real) compativel
  com o bloqueio de sinal ja existente no risk manager.

## Monitoramento Prometheus/Grafana - proximos passos sugeridos

- Expor metricas do coletor e do backtester via `prometheus_client` (Python).
- Dashboards minimos: latencia MT5<->coletor<->banco, trades executados/dia,
  drawdown corrente, uptime dos processos (`start_all.ps1`).
- So e bloqueante para a Fase 3 (execucao automatica), nao para o Gate 2.

## Documentacao de decisoes de parametros - formato sugerido

Criar `docs/DECISOES_PARAMETROS.md` com uma entrada por mudanca:

```
## 2026-08-16 - min_signal_score M5 50 -> 65
Motivo: ativos volateis (XAUUSD/BTCUSD) geravam falsos positivos em M5.
Resultado esperado: reducao de trades de baixa qualidade.
Validado em: Gate 2 (rodada de 2026-08-16).
```
