"""
engine/correlation_engine.py

Modulo de correlacao rolante entre pares - implementa a logica de diversificacao
de Markowitz (Nobel 1990): evita que o sistema acumule exposicao direcional
duplicada. Funcoes de calculo sao puras; I/O usa imports lazy de sqlalchemy.
"""
import logging
import time

import numpy as np
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [correlation] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    from sqlalchemy import create_engine
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def compute_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    return returns_df.corr(method="pearson")


def flag_high_correlation_pairs(corr_matrix: pd.DataFrame, threshold: float = 0.7) -> list:
    pairs = []
    symbols = corr_matrix.columns.tolist()
    for i, a in enumerate(symbols):
        for b in symbols[i + 1:]:
            corr = corr_matrix.loc[a, b]
            if pd.notna(corr) and abs(corr) >= threshold:
                pairs.append((a, b, round(float(corr), 4)))
    return pairs


def is_new_position_blocked(symbol: str, direction: str, open_positions: dict,
                             corr_matrix: pd.DataFrame, threshold: float = 0.7) -> tuple:
    if symbol not in corr_matrix.columns:
        return False, ""
    for other_symbol, other_direction in open_positions.items():
        if other_symbol == symbol or other_symbol not in corr_matrix.columns:
            continue
        corr = corr_matrix.loc[symbol, other_symbol]
        if pd.isna(corr):
            continue
        same_direction_bet = (
            (corr > 0 and direction == other_direction) or
            (corr < 0 and direction != other_direction)
        )
        if abs(corr) >= threshold and same_direction_bet:
            return True, (f"Exposicao duplicada: {symbol} {direction} correlacionado "
                           f"({corr:.2f}) com posicao aberta em {other_symbol} {other_direction}")
    return False, ""


def fetch_returns_matrix(engine, symbols, timeframe, window=100) -> pd.DataFrame:
    from sqlalchemy import text
    frames = {}
    for symbol in symbols:
        sql = text("""
            SELECT time, close FROM candles WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY time DESC LIMIT :limit
        """)
        with engine.connect() as conn:
            df = pd.read_sql(sql, conn, params={"symbol": symbol, "timeframe": timeframe, "limit": window})
        df = df.sort_values("time").set_index("time")
        frames[symbol] = df["close"].pct_change()
    return pd.DataFrame(frames).dropna(how="all")


def persist_correlations(engine, corr_matrix, timeframe):
    from sqlalchemy import text
    sql = text("""
        INSERT INTO correlations (time, symbol_a, symbol_b, timeframe, correlation)
        VALUES (now(), :a, :b, :timeframe, :corr)
        ON CONFLICT DO NOTHING
    """)
    symbols = corr_matrix.columns.tolist()
    with engine.begin() as conn:
        for i, a in enumerate(symbols):
            for b in symbols[i + 1:]:
                corr = corr_matrix.loc[a, b]
                if pd.notna(corr):
                    conn.execute(sql, {"a": a, "b": b, "timeframe": timeframe, "corr": float(corr)})


def run_once(cfg, engine):
    for timeframe in cfg["timeframes"]:
        returns = fetch_returns_matrix(engine, cfg["symbols"], timeframe,
                                        window=cfg["engine"]["correlation_window"])
        if returns.shape[0] < 20:
            continue
        corr_matrix = compute_correlation_matrix(returns)
        persist_correlations(engine, corr_matrix, timeframe)
        high_corr = flag_high_correlation_pairs(corr_matrix, cfg["risk"]["max_correlation_exposure"])
        if high_corr:
            log.info(f"[{timeframe}] pares altamente correlacionados: {high_corr}")


def main():
    cfg = load_config()
    engine = db_engine(cfg)
    log.info("Motor de correlacao iniciado.")
    while True:
        try:
            run_once(cfg, engine)
        except Exception as e:
            log.exception(f"Erro no ciclo de correlacao: {e}")
        time.sleep(30)


if __name__ == "__main__":
    main()
