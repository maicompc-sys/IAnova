"""
risk/var_engine.py
Value at Risk (VaR) de portfolio - parametrico e Monte Carlo.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm


def parametric_var(returns_matrix: pd.DataFrame, weights: dict, confidence: float = 0.95,
                    horizon_days: int = 1) -> dict:
    symbols = [s for s in weights if s in returns_matrix.columns]
    if not symbols:
        return {"var_pct": 0.0, "method": "parametric"}

    w = np.array([weights[s] for s in symbols])
    cov_matrix = returns_matrix[symbols].cov().values

    portfolio_variance = w.T @ cov_matrix @ w
    portfolio_std = np.sqrt(max(portfolio_variance, 0.0))

    z_score = norm.ppf(confidence)
    var_pct = z_score * portfolio_std * np.sqrt(horizon_days)

    return {
        "var_pct": round(float(var_pct) * 100, 4),
        "portfolio_std": round(float(portfolio_std), 6),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "method": "parametric",
    }


def monte_carlo_var(returns_matrix: pd.DataFrame, weights: dict, confidence: float = 0.95,
                     horizon_days: int = 1, n_sims: int = 10000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    symbols = [s for s in weights if s in returns_matrix.columns]
    if not symbols:
        return {"var_pct": 0.0, "method": "monte_carlo"}

    w = np.array([weights[s] for s in symbols])
    mean_returns = returns_matrix[symbols].mean().values
    cov_matrix = returns_matrix[symbols].cov().values

    simulated_returns = rng.multivariate_normal(mean_returns, cov_matrix, size=n_sims)
    portfolio_returns = simulated_returns @ w
    horizon_returns = portfolio_returns * np.sqrt(horizon_days)

    var_pct = -np.percentile(horizon_returns, (1 - confidence) * 100)

    return {
        "var_pct": round(float(var_pct) * 100, 4),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "n_sims": n_sims,
        "method": "monte_carlo",
    }


def check_var_limit(var_result: dict, max_portfolio_var_pct: float) -> tuple:
    if var_result["var_pct"] > max_portfolio_var_pct:
        return True, (f"VaR de portfolio ({var_result['var_pct']:.2f}%) excede o limite "
                       f"configurado ({max_portfolio_var_pct:.2f}%) - novas posicoes bloqueadas.")
    return False, ""


def portfolio_weights_from_positions(open_positions: dict, balance: float, position_values: dict) -> dict:
    weights = {}
    for symbol, direction in open_positions.items():
        value = position_values.get(symbol, 0.0)
        sign = 1 if direction == "BUY" else -1
        weights[symbol] = sign * (value / balance) if balance > 0 else 0.0
    return weights
