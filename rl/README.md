# Fase 2 - Ensemble de Reinforcement Learning

Status: NAO INICIADA. Pre-requisito obrigatorio: Gate 2 aprovado na Fase 1
(profit factor > 1.3, drawdown < 15%, Sharpe > 0.8, amostra >= 30 trades/fold,
em pelo menos 3 janelas walk-forward). Nao pule essa etapa.

## Passo a passo (do roadmap)

1. `trading_env.py` - TradingEnv Gym-compatible (esqueleto criado, `step()` ainda
   precisa ser implementado com a logica real de entrada/saida e recompensa
   ajustada a risco).
2. `train_ensemble.py` - treina PPO, A2C e SAC via stable-baselines3, cada um
   de forma independente sobre o mesmo ambiente.
3. Ensemble por votacao ponderada (a implementar): combinar decisoes dos 3
   agentes com peso proporcional a performance recente de cada um.
4. Camada de meta-decisao (a implementar): classificador que decide, pela
   condicao de mercado (tendencia forte / lateral / alta volatilidade de
   noticia), se confia mais no motor tecnico classico ou no ensemble de RL.
5. Validacao: mesmo processo de walk-forward do Gate 2, comparando tecnico
   puro vs. RL puro vs. hibrido. So avanca se o hibrido superar o tecnico puro
   de forma consistente.

## Como rodar (local, apos ter dados e Gate 2 aprovado)

```
pip install -r requirements-rl.txt
python -m rl.train_ensemble --data caminho/para/features.parquet --timesteps 100000
```

## Ainda faltam (nao commitado)

- Implementacao real de `TradingEnv.step()`
- Logica de ensemble por votacao ponderada
- Classificador de meta-decisao
- Script de validacao walk-forward comparando tecnico vs RL vs hibrido
