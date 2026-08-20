# Registro de Decisões de Parâmetros e Rastreabilidade

## 2026-08-20 - Diagnostico Gate 2 pos-exit_reason (365 dias de historico)
Contexto: primeira rodada completa do Gate 2 com 1 ano de dados reais (665.112 candles).
BTCUSD M5 fold 1: SL=155 TP=48 timeout=95 (298 trades). PF implicito ~0.60, expectativa -0.21R.
Causa raiz (ativos volateis - BTCUSD/XAUUSD): R:R nominal 1:2 nao compensa taxa de acerto baixa com TP distante.
Causa raiz (forex majors): min_signal_score + ADX>=25 gera <30 trades/fold em varios timeframes.
Decisao: nao afrouxar criterios do Gate 2. Testar ajustes de ATR multiplier isoladamente para volateis (ver Tarefa 2) e avaliar ampliacao de janela de fold para forex (ver Tarefa 3).
Status: Gate 2 reprovado em todos os ativos nesta rodada.
