"""
Treino do ensemble de RL (PPO, A2C, SAC) via stable-baselines3 (Fase 2).

PRE-REQUISITO: Gate 2 aprovado. Ver rl/trading_env.py.

Este script e um ESQUELETO -- ainda nao foi rodado contra dados reais.
Nao existe garantia de que os hiperparametros abaixo sejam adequados;
ajuste com base em validacao walk-forward (mesmo processo do Gate 2).
"""
import argparse

import pandas as pd
from stable_baselines3 import PPO, A2C, SAC
from stable_baselines3.common.env_util import make_vec_env

from rl.trading_env import TradingEnv


def load_features(parquet_or_csv_path: str) -> pd.DataFrame:
    """Carrega o dataframe de features ja calculado (candles + indicadores)."""
    if parquet_or_csv_path.endswith(".parquet"):
        return pd.read_parquet(parquet_or_csv_path)
    return pd.read_csv(parquet_or_csv_path)


def make_env(df_features, window_size=50):
    return lambda: TradingEnv(df_features, window_size=window_size)


def train_agent(algo_name: str, df_features, total_timesteps: int = 100_000):
    env = make_vec_env(make_env(df_features), n_envs=1)

    algo_cls = {"ppo": PPO, "a2c": A2C, "sac": SAC}[algo_name.lower()]
    model = algo_cls("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=total_timesteps)
    model.save(f"models/{algo_name.lower()}_ianova")
    return model


def main():
    parser = argparse.ArgumentParser(description="Treina ensemble RL para IAnova (Fase 2)")
    parser.add_argument("--data", required=True, help="Caminho para features (csv/parquet)")
    parser.add_argument("--timesteps", type=int, default=100_000)
    parser.add_argument("--algos", nargs="+", default=["ppo", "a2c", "sac"])
    args = parser.parse_args()

    df_features = load_features(args.data)

    for algo_name in args.algos:
        print(f"Treinando {algo_name.upper()}...")
        train_agent(algo_name, df_features, total_timesteps=args.timesteps)


if __name__ == "__main__":
    main()
