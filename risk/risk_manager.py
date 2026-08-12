"""
risk/risk_manager.py
Gestao de risco integrada: Kelly fracionario + VaR de portfolio + bloqueio por
correlacao + circuit breakers diario/semanal.
"""
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from risk.var_engine import parametric_var, check_var_limit, portfolio_weights_from_positions
from engine.correlation_engine import is_new_position_blocked

logging.basicConfig(level=logging.INFO, format="%(asctime)s [risk] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    from sqlalchemy import create_engine
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


@dataclass
class RiskDecision:
    approved: bool
    position_size: float
    stop_loss: float
    take_profit: float
    kelly_fraction: float
    reason: str


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, max_fraction: float = 0.25) -> float:
    if avg_loss <= 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    f = win_rate - (q / b) if b > 0 else 0.0
    f = max(0.0, f)
    return min(f, max_fraction)


def monte_carlo_drawdown(balance: float, kelly_f: float, win_rate: float, avg_win_pct: float,
                          avg_loss_pct: float, n_trades: int = 200, n_sims: int = 1000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    max_drawdowns = []
    for _ in range(n_sims):
        eq = balance
        peak = balance
        max_dd = 0.0
        for _ in range(n_trades):
            stake = eq * kelly_f
            if rng.random() < win_rate:
                eq += stake * avg_win_pct
            else:
                eq -= stake * avg_loss_pct
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
            if eq <= 0:
                break
        max_drawdowns.append(max_dd)
    return {
        "p50_drawdown": float(np.percentile(max_drawdowns, 50)),
        "p95_drawdown": float(np.percentile(max_drawdowns, 95)),
        "ruin_prob": float(np.mean([d >= 0.99 for d in max_drawdowns])),
    }


def historical_win_stats(engine, symbol, lookback=100):
    from sqlalchemy import text
    sql = text("""
        SELECT result_pips FROM signals
        WHERE symbol = :symbol AND executed = TRUE AND closed_at IS NOT NULL
        ORDER BY time DESC LIMIT :lookback
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"symbol": symbol, "lookback": lookback})
    if df.empty or len(df) < 20:
        return None
    wins = df[df["result_pips"] > 0]["result_pips"]
    losses = df[df["result_pips"] <= 0]["result_pips"]
    win_rate = len(wins) / len(df)
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = abs(losses.mean()) if len(losses) else 1e-6
    return {"win_rate": win_rate, "avg_win": avg_win, "avg_loss": avg_loss, "n": len(df)}


def evaluate_trade(engine, cfg, symbol, entry_price, atr_value, direction, current_balance,
                    today_pnl_pct, week_pnl_pct, open_positions, corr_matrix,
                    returns_matrix, position_values) -> RiskDecision:
    risk_cfg = cfg["risk"]

    if today_pnl_pct <= -risk_cfg["max_daily_drawdown_pct"]:
        return RiskDecision(False, 0, 0, 0, 0, "Circuit breaker DIARIO de drawdown atingido")
    if week_pnl_pct <= -risk_cfg["max_weekly_drawdown_pct"]:
        return RiskDecision(False, 0, 0, 0, 0, "Circuit breaker SEMANAL de drawdown atingido")

    blocked, reason = is_new_position_blocked(
        symbol, direction, open_positions, corr_matrix, risk_cfg["max_correlation_exposure"]
    )
    if blocked:
        return RiskDecision(False, 0, 0, 0, 0, reason)

    weights = portfolio_weights_from_positions(open_positions, current_balance, position_values)
    weights[symbol] = weights.get(symbol, 0.0) + (1 if direction == "BUY" else -1) * 0.02
    if not returns_matrix.empty:
        var_result = parametric_var(returns_matrix, weights, risk_cfg["var_confidence"], risk_cfg["var_horizon_days"])
        var_blocked, var_reason = check_var_limit(var_result, risk_cfg["max_portfolio_var_pct"])
        if var_blocked:
            return RiskDecision(False, 0, 0, 0, 0, var_reason)

    stats = historical_win_stats(engine, symbol)
    if stats is None:
        win_rate, avg_win_pct, avg_loss_pct = 0.5, 0.01, 0.01
    else:
        win_rate = stats["win_rate"]
        avg_win_pct = stats["avg_win"] / entry_price
        avg_loss_pct = stats["avg_loss"] / entry_price

    f = kelly_fraction(win_rate, avg_win_pct, avg_loss_pct, risk_cfg["max_kelly_fraction"])
    mc = monte_carlo_drawdown(current_balance, f, win_rate, avg_win_pct, avg_loss_pct)
    if mc["ruin_prob"] > 0.05:
        f = f * 0.5
        log.warning(f"{symbol}: risco de ruina elevado ({mc['ruin_prob']:.2%}), reduzindo Kelly.")

    risk_amount = current_balance * min(f, risk_cfg["max_risk_per_trade_pct"] / 100)
    position_size = round(risk_amount / (atr_value * risk_cfg["atr_multiplier_sl"]), 2) if atr_value > 0 else 0.01
    position_size = max(0.01, position_size)

    if direction == "BUY":
        stop_loss = entry_price - atr_value * risk_cfg["atr_multiplier_sl"]
        take_profit = entry_price + atr_value * risk_cfg["atr_multiplier_tp"]
    else:
        stop_loss = entry_price + atr_value * risk_cfg["atr_multiplier_sl"]
        take_profit = entry_price - atr_value * risk_cfg["atr_multiplier_tp"]

    return RiskDecision(
        approved=True, position_size=position_size,
        stop_loss=round(stop_loss, 5), take_profit=round(take_profit, 5),
        kelly_fraction=round(f, 4),
        reason=f"win_rate={win_rate:.2%} p95_dd={mc['p95_drawdown']:.2%} ruin={mc['ruin_prob']:.2%}",
    )
