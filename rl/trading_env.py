"""
TradingEnv - Ambiente Gym-compatible para o ensemble de Reinforcement Learning (Fase 2).

PRE-REQUISITO: Gate 2 aprovado (profit factor > 1.3, drawdown < 15%, Sharpe > 0.8,
todos em amostra >= 30 trades/fold, em pelo menos 3 janelas). Nao rode treino de RL
antes disso -- nao faz sentido adicionar complexidade de ML sobre uma base que ainda
nao provou ter edge estatistico basico.

Este arquivo e um ESQUELETO. Ainda nao foi testado com dados reais.
"""
from __future__ import annotations

import numpy as np
import gymnasium as gym
from gymnasium import spaces


class TradingEnv(gym.Env):
    """
    Ambiente de simulacao para treino de agentes RL (PPO / A2C / SAC).

    Observacao: janela de candles + indicadores ja calculados pelo
    engine/indicator_engine.py (EMA, RSI, ATR, Bollinger, ADX, padrao de vela,
    regime ADWIN).

    Acao: Discrete(3) -> 0 = manter, 1 = comprar, 2 = vender.

    Recompensa: P&L ajustado a risco (nao P&L bruto). Sugestao inicial:
    reward = pnl_da_barra - lambda_risco * drawdown_incremental
    Ajuste lambda_risco experimentalmente; documentar a escolha em
    docs/DECISOES_PARAMETROS.md quando esse arquivo existir.
    """

    metadata = {"render_modes": []}

    def __init__(self, df_features, window_size: int = 50, lambda_risco: float = 0.5):
        super().__init__()
        self.df = df_features.reset_index(drop=True)
        self.window_size = window_size
        self.lambda_risco = lambda_risco

        n_features = self.df.shape[1]
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf,
            shape=(window_size, n_features),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(3)

        self._reset_state()

    def _reset_state(self):
        self.current_step = self.window_size
        self.position = 0  # -1 short, 0 flat, 1 long
        self.entry_price = None
        self.equity_curve = [1.0]
        self.peak_equity = 1.0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._reset_state()
        return self._get_observation(), {}

    def _get_observation(self):
        window = self.df.iloc[self.current_step - self.window_size:self.current_step]
        return window.values.astype(np.float32)

    def step(self, action):
        raise NotImplementedError(
            "TODO: implementar logica de entrada/saida de posicao, calculo de "
            "P&L da barra, penalizacao por drawdown incremental (lambda_risco) e "
            "condicao de termino do episodio. Usar o mesmo custo de spread do "
            "engine/backtester.py para manter paridade com o Gate 2."
        )

    def close(self):
        pass
