# Registro de Decisões de Parâmetros e Rastreabilidade

## 2026-08-20 - Diagnostico Gate 2 pos-exit_reason (365 dias de historico)
Contexto: primeira rodada completa do Gate 2 com 1 ano de dados reais (665.112 candles).
BTCUSD M5 fold 1: SL=155 TP=48 timeout=95 (298 trades). PF implicito ~0.60, expectativa -0.21R.
Causa raiz (ativos volateis - BTCUSD/XAUUSD): R:R nominal 1:2 nao compensa taxa de acerto baixa com TP distante.
Causa raiz (forex majors): min_signal_score + ADX>=25 gera <30 trades/fold em varios timeframes.
Decisao: nao afrouxar criterios do Gate 2. Testar ajustes de ATR multiplier isoladamente para volateis (ver Tarefa 2) e avaliar ampliacao de janela de fold para forex (ver Tarefa 3).
Status: Gate 2 reprovado em todos os ativos nesta rodada.

## 2026-08-20 - Experimento Tarefa 2 (BTCUSD/XAUUSD) - Teste A vs Teste B
### Teste A: Reducao de atr_tp_multiplier (4.0 -> 2.0, sl=2.0, max_bars=30)
- **Hipótese:** Reduzir o alvo de TP diminui a taxa de timeout e aumenta a captura de TP antes de reversões.
- **Resultados BTCUSD M5:**
  - Fold 1 (371 trades): SL=166, TP=148, Timeout=57 | WR=46.63%, PF=0.86, Sharpe=-2.49, MaxDD=25.60%
  - Fold 2 (417 trades): SL=188, TP=185, Timeout=44 | WR=48.68%, PF=0.97, Sharpe=-0.52, MaxDD=26.65%
  - Fold 3 (312 trades): TP=136, SL=128, Timeout=48 | WR=50.32%, PF=1.03, Sharpe=0.69, MaxDD=12.62%
- **Resultados XAUUSD M5:**
  - Fold 1 (164 trades): TP=75, SL=70, Timeout=19 | WR=53.66%, PF=1.09, Sharpe=1.13, MaxDD=13.31%
  - Fold 2 (199 trades): SL=92, TP=82, Timeout=25 | WR=49.75%, PF=0.92, Sharpe=-1.05, MaxDD=19.31%
  - Fold 3 (149 trades): TP=65, SL=56, Timeout=28 | WR=51.68%, PF=1.11, Sharpe=1.29, MaxDD=13.01%
- **Conclusão Teste A:** Timeouts caíram de ~32% para ~14%, taxa de TP subiu para ~48-52%. Contudo, com R:R nominal 1:1 e custo de spread, o Profit Factor oscilou entre 0.86 e 1.24 (insuficiente para Gate 2 > 1.3).

### Teste B: Aumento de max_bars_hold (30 -> 60, tp=4.0, sl=2.0)
- **Hipótese:** Manter TP em 4.0 e dar mais tempo para o trade desenvolver sem sofrer timeout.
- **Resultados BTCUSD M5:**
  - Fold 1 (288 trades): SL=182, TP=67, Timeout=39 | WR=33.33%, PF=0.81, Sharpe=-2.78, MaxDD=33.98%
  - Fold 2 (325 trades): SL=197, TP=85, Timeout=43 | WR=36.31%, PF=0.92, Sharpe=-1.25, MaxDD=29.69%
  - Fold 3 (251 trades): SL=149, TP=64, Timeout=38 | WR=33.86%, PF=0.91, Sharpe=-1.28, MaxDD=24.78%
- **Resultados XAUUSD M5:**
  - Fold 1 (125 trades): SL=64, TP=37, Timeout=24 | WR=41.60%, PF=1.24, Sharpe=2.22, MaxDD=8.74%
  - Fold 2 (165 trades): SL=97, TP=49, Timeout=19 | WR=36.97%, PF=1.03, Sharpe=0.55, MaxDD=13.58%
  - Fold 3 (122 trades): SL=69, TP=29, Timeout=24 | WR=37.70%, PF=0.95, Sharpe=-0.38, MaxDD=16.96%
- **Conclusão Teste B:** Aumentar `max_bars_hold` converteu a maioria dos timeouts em Stop Loss, derrubando o win rate para ~33-37% e resultando em PFs inferiores ao Teste A. Hipótese B descartada.

## 2026-08-20 - Avaliacao Tarefa 3 (Forex Majors - Amostra Insuficiente)
- **Teste com Folds Estendidos (n_splits=2, ~180 dias por fold):**
  - M5: Amostra < 5 trades por fold em todos os pares (EURUSD, GBPUSD, USDCHF, USDJPY).
  - M15: Amostra < 22 trades por fold em todos os pares.
  - H1: Apenas USDCHF atingiu >= 30 trades/fold (34 e 32), mas com PF=0.74 e 0.95. EURUSD, GBPUSD e USDJPY permaneceram < 30 trades/fold.
- **Decisão Formal:** Comprovado que `min_signal_score` elevado + filtro obrigatório de `ADX >= 25` em 1 ano de dados reais não gera densidade de amostragem estatisticamente válida para o Gate 2 nos pares forex majors. Não afrouxamos os critérios do Gate 2 nem os scores. **Os pares forex majors (EURUSD, GBPUSD, USDCHF, USDJPY) ficam formalmente fora do portfólio inicial** até termos histórico maior (ex.: 2-3 anos) ou um filtro de tendência adaptado e validado em novo ciclo experimental.

