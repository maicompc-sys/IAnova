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

## 2026-08-20 - Teste C: atr_tp_multiplier=2.5 em H1 (BTCUSD/XAUUSD)
- **Contexto:** Teste A (TP=2.0) resolveu timeout mas deixou PF no breakeven (0.92-1.24 em BTCUSD H1).
- **Hipótese:** R:R levemente acima de 1:1 (TP=2.5, SL=2.0, max_bars=30), focado apenas em H1, melhora o PF sem reintroduzir a perda por timeout do Teste B.
- **Resultados BTCUSD H1:**
  - Fold 1 (87 trades): SL=45, TP=32, Timeout=10 | WR=42.53%, PF=0.89, Sharpe=-0.94, MaxDD=8.32%
  - Fold 2 (100 trades): SL=50, TP=41, Timeout=9 | WR=46.00%, PF=1.04, Sharpe=0.45, MaxDD=6.51%
  - Fold 3 (77 trades): SL=34, TP=28, Timeout=15 | WR=46.75%, PF=1.04, Sharpe=0.44, MaxDD=10.11%
- **Resultados XAUUSD H1:**
  - Fold 1 (66 trades): TP=31, SL=28, Timeout=7 | WR=51.52%, PF=1.34, Sharpe=2.29, MaxDD=3.48% (Aprovado individualmente no fold)
  - Fold 2 (60 trades): SL=31, TP=20, Timeout=9 | WR=43.33%, PF=0.81, Sharpe=-1.53, MaxDD=9.55%
  - Fold 3 (67 trades): TP=35, SL=29, Timeout=3 | WR=53.73%, PF=1.50, Sharpe=3.39, MaxDD=4.95% (Aprovado individualmente no fold)
- **Status:** Gate 2 REPROVADO em ambos (exige aprovação em todos os 3 folds simultaneamente).
- **Decisão:**
  1. Em **BTCUSD H1**, o TP=2.5 piorou as métricas em relação ao Teste A (TP=2.0 alcançava PF de até 1.24 e WR de 55.68%).
  2. Em **XAUUSD H1**, 2 dos 3 folds bateram a meta de PF > 1.3 (1.34 e 1.50 com Sharpe > 2.0), demonstrando que o R:R 2.5 tem edge quando a taxa de acerto é > 51%, mas o Fold 2 (PF=0.81) reprovou o conjunto.
  3. **Próximo passo:** Seguir para o **Teste D** explorando o eixo de `min_signal_score` específico para H1 (ex: +10 pontos) a fim de filtrar sinais fracos no Fold 2 sem comprimir a amostra abaixo de 30 trades.

## 2026-08-20 - BTCUSD H1 revertido para TP=2.0 (Teste A era otimo)
Teste C (TP=2.5) piorou BTCUSD H1 (PF max 1.04 vs 1.24 no Teste A). Revertido.
BTCUSD H1 fica em espera de nova hipotese de ajuste.

## 2026-08-20 - Teste D: min_signal_score=60 em XAUUSD H1
- **Contexto:** Teste C aprovou 2/3 folds em XAUUSD H1 (PF 1.34 e 1.50), fold 2 reprovou (PF 0.81).
- **Hipótese:** score mais seletivo (60 vs 50) filtra sinais fracos também no fold 2 sem comprometer os demais.
- **Resultado:**
  - Fold 1 (64 trades): TP=30, SL=28, Timeout=6 | WR=51.56%, PF=1.31, Sharpe=2.11, MaxDD=3.94%
  - Fold 2 (57 trades): SL=30, TP=19, Timeout=8 | WR=42.11%, PF=0.79, Sharpe=-1.69, MaxDD=9.77%
  - Fold 3 (61 trades): TP=31, SL=27, Timeout=3 | WR=52.46%, PF=1.43, Sharpe=2.86, MaxDD=5.18%
- **Decisão:** Cenário C (sem melhora no fold 2). Elevar o min_signal_score para 60 não corrigiu o fold 2 (PF caiu de 0.81 para 0.79) e reduziu levemente a performance dos folds 1 e 3. Revertido min_signal_score para 50. XAUUSD H1 permanece com TP=2.5 e score=50 como melhor ponto encontrado.



