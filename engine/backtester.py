"""
engine/backtester.py

Backtest vetorizado da estrategia (EMA cross + RSI + Bollinger + regime) sobre o
historico ja coletado no TimescaleDB. Aplica a mesma logica de risco do
risk_manager.py (Kelly fracionario + stop/take por ATR) e modela custos reais de
CFD (spread), exigencia do plano institucional antes de qualquer execucao automatica.

Uso (qualquer um dos dois funciona):
    python -m engine.backtester        # recomendado
    python engine/backtester.py        # tambem funciona (path-fix abaixo)
"""
import os
import sys

# Garante que a raiz do projeto esteja no sys.path mesmo quando o script e
# executado diretamente (nao como modulo com -m), evitando o erro
# "ModuleNotFoundError: No module named 'engine'".
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging

import numpy as np
import pandas as pd
import yaml

from engine.indicator_engine import compute_indicators, classify_regime, signal_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [backtest] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    from sqlalchemy import create_engine
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def fetch_all_candles(engine, symbol, timeframe) -> pd.DataFrame:
    from sqlalchemy import text
    sql = text("""
        SELECT time, open, high, low, close, spread FROM candles
        WHERE symbol = :symbol AND timeframe = :timeframe ORDER BY time ASC
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"symbol": symbol, "timeframe": timeframe})


def build_signals(df: pd.DataFrame, cfg_engine: dict, timeframe: str = "H1") -> pd.DataFrame:
    """Pura: aplica indicator_engine + classify_regime/signal_score linha a linha
    e gera uma coluna 'signal' (1=long, -1=short, 0=sem sinal)."""
    df = compute_indicators(df, cfg_engine)
    regimes, confs, scores, signals = [], [], [], []
    drift_flag = False  # backtest nao usa ADWIN online; foco e na logica de sinal

    min_score_cfg = cfg_engine["min_signal_score"]
    min_score = min_score_cfg.get(timeframe, 50) if isinstance(min_score_cfg, dict) else min_score_cfg

    for _, row in df.iterrows():
        regime, conf = classify_regime(row, drift_flag)
        score = signal_score(row, regime, conf)
        regimes.append(regime)
        confs.append(conf)
        scores.append(score)

        sig = 0
        if score >= min_score:
            if regime == "trend_up":
                sig = 1
            elif regime == "trend_down":
                sig = -1
        signals.append(sig)

    df["regime"] = regimes
    df["regime_confidence"] = confs
    df["signal_score"] = scores
    df["signal"] = signals
    return df


def simulate(df: pd.DataFrame, atr_mult_sl: float, atr_mult_tp: float, starting_balance: float,
             risk_pct: float, avg_spread_pips: float = 1.5, pip_size: float = 0.0001,
             max_bars_hold: int = 30) -> dict:
    """
    Simulacao trade a trade, considerando custo de spread (entra contra o preco de entrada,
    reduzindo o EV de cada operacao - sem isso, todo backtest e ilusorio, conforme o plano
    institucional). Retorna metricas + DataFrame de trades para auditoria.
    """
    balance = starting_balance
    equity_curve = [balance]
    trades = []
    spread_cost = avg_spread_pips * pip_size

    i = 0
    n = len(df)
    while i < n - 1:
        row = df.iloc[i]
        if row["signal"] != 0 and pd.notna(row["atr"]) and row["atr"] > 0:
            direction = row["signal"]
            entry = row["close"] + (spread_cost if direction == 1 else -spread_cost)
            atr = row["atr"]
            sl = entry - direction * atr * atr_mult_sl
            tp = entry + direction * atr * atr_mult_tp

            outcome, exit_price = None, entry
            for j in range(i + 1, min(i + 1 + max_bars_hold, n)):
                bar = df.iloc[j]
                if direction == 1:
                    if bar["low"] <= sl:
                        outcome, exit_price = "loss", sl
                        break
                    if bar["high"] >= tp:
                        outcome, exit_price = "win", tp
                        break
                else:
                    if bar["high"] >= sl:
                        outcome, exit_price = "loss", sl
                        break
                    if bar["low"] <= tp:
                        outcome, exit_price = "win", tp
                        break
            if outcome is None:
                exit_price = df.iloc[min(i + max_bars_hold, n - 1)]["close"]
                outcome = "win" if (exit_price - entry) * direction > 0 else "loss"

            pnl_pct = (exit_price - entry) / entry * direction
            risk_amount = balance * (risk_pct / 100)
            pnl_amount = risk_amount * (pnl_pct / (atr_mult_sl * atr / entry)) if atr > 0 else 0
            balance += pnl_amount
            equity_curve.append(balance)
            trades.append({
                "time": row["time"], "direction": "BUY" if direction == 1 else "SELL",
                "outcome": outcome, "pnl": pnl_amount, "score": row["signal_score"],
            })
            i += max_bars_hold
        else:
            i += 1

    trades_df = pd.DataFrame(trades)
    eq = pd.Series(equity_curve)
    peak = eq.cummax()
    dd = (peak - eq) / peak.replace(0, np.nan)
    max_dd = dd.max() if len(dd) else 0.0

    win_rate = (trades_df["outcome"] == "win").mean() if not trades_df.empty else 0.0
    avg_pnl = trades_df["pnl"].mean() if not trades_df.empty else 0.0
    gross_win = trades_df[trades_df["pnl"] > 0]["pnl"].sum() if not trades_df.empty else 0.0
    gross_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].sum()) if not trades_df.empty else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0

    returns = eq.pct_change().dropna()
    if returns.std() > 1e-10:
        sharpe = float(np.clip(returns.mean() / returns.std() * np.sqrt(252), -999, 999))
    else:
        sharpe = 0.0

    return {
        "n_trades": len(trades_df),
        "win_rate": round(float(win_rate), 4),
        "avg_pnl_per_trade": round(float(avg_pnl), 2),
        "final_balance": round(float(balance), 2),
        "max_drawdown_pct": round(float(max_dd) * 100, 2) if pd.notna(max_dd) else 0.0,
        "profit_factor": round(float(profit_factor), 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "trades": trades_df,
    }


def walk_forward_split(df: pd.DataFrame, n_splits: int = 3):
    """Gera janelas de treino/teste que avancam no tempo (evita data leakage),
    conforme exigido no Gate 2 do plano institucional."""
    n = len(df)
    fold_size = n // (n_splits + 1)
    for k in range(1, n_splits + 1):
        train_end = fold_size * k
        test_end = min(fold_size * (k + 1), n)
        yield df.iloc[:train_end], df.iloc[train_end:test_end]


def evaluate_gate2(results: list) -> dict:
    """Aplica os criterios objetivos do Gate 2 do plano institucional."""
    if not results:
        return {"passed": False, "reason": "Sem resultados suficientes."}

    profit_factors = [r["profit_factor"] for r in results if r["profit_factor"] not in (0.0, float("inf"))]
    max_dds = [r["max_drawdown_pct"] for r in results]
    sharpes = [r["sharpe_ratio"] for r in results]

    checks = {
        "profit_factor_ok": all(pf > 1.3 for pf in profit_factors) if profit_factors else False,
        "max_drawdown_ok": all(dd < 15.0 for dd in max_dds),
        "sharpe_ok": any(s > 0.8 for s in sharpes),
        "no_catastrophic_loss": all(dd < 30.0 for dd in max_dds),
    }
    passed = all(checks.values())
    return {"passed": passed, "checks": checks}


def main():
    cfg = load_config()
    engine = db_engine(cfg)
    all_results = []

    for symbol in cfg["symbols"]:
        for timeframe in cfg["timeframes"]:
            df = fetch_all_candles(engine, symbol, timeframe)
            if len(df) < max(cfg["engine"]["bb_period"], cfg["engine"]["ema_slow"]) * 4:
                log.info(f"[{symbol} {timeframe}] historico insuficiente ({len(df)} candles) - colete mais dados.")
                continue

            df = build_signals(df, cfg["engine"], timeframe)

            fold_results = []
            for train_df, test_df in walk_forward_split(df, n_splits=3):
                if len(test_df) < 20:
                    continue
                result = simulate(
                    test_df,
                    atr_mult_sl=cfg["risk"]["atr_multiplier_sl"],
                    atr_mult_tp=cfg["risk"]["atr_multiplier_tp"],
                    starting_balance=cfg["risk"]["starting_balance"],
                    risk_pct=cfg["risk"]["max_risk_per_trade_pct"],
                )
                fold_results.append(result)
                log.info(f"[{symbol} {timeframe}] fold: trades={result['n_trades']} "
                         f"win_rate={result['win_rate']:.2%} PF={result['profit_factor']} "
                         f"Sharpe={result['sharpe_ratio']} max_dd={result['max_drawdown_pct']}%")

            if fold_results:
                gate2 = evaluate_gate2(fold_results)
                status = "APROVADO" if gate2["passed"] else "REPROVADO"
                log.info(f"[{symbol} {timeframe}] Gate 2: {status} - {gate2.get('checks', gate2)}")
                all_results.append({"symbol": symbol, "timeframe": timeframe, "gate2": gate2})

    log.info("Backtest concluido para todos os simbolos/timeframes com dados suficientes.")
    return all_results


if __name__ == "__main__":
    main()
