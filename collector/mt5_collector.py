"""
collector/mt5_collector.py
Coletor de dados via MetaTrader5 para CFDs na conta Deriv-Demo (Windows apenas).
"""
import time
import logging
from datetime import datetime, timezone

import yaml
import MetaTrader5 as mt5
import redis
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [collector] %(message)s")
log = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
}


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def connect_mt5(cfg):
    terminal_path = cfg["mt5"].get("terminal_path")
    ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"Falha ao inicializar MT5: {mt5.last_error()}")
    info = mt5.account_info()
    if info is None:
        raise RuntimeError("Nao foi possivel ler account_info - verifique se o MT5 esta logado.")
    log.info(f"Conectado a conta {info.login} ({info.server}) saldo={info.balance} equity={info.equity}")
    return info


def db_engine(cfg):
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def upsert_candles(engine, symbol, timeframe_str, rates):
    if rates is None or len(rates) == 0:
        return 0
    rows = []
    for r in rates:
        spread = float(r["spread"]) if "spread" in r.dtype.names else None
        rows.append({
            "time": datetime.fromtimestamp(r["time"], tz=timezone.utc),
            "symbol": symbol, "timeframe": timeframe_str,
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "tick_volume": int(r["tick_volume"]), "spread": spread,
        })
    sql = text("""
        INSERT INTO candles (time, symbol, timeframe, open, high, low, close, tick_volume, spread)
        VALUES (:time, :symbol, :timeframe, :open, :high, :low, :close, :tick_volume, :spread)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, tick_volume = EXCLUDED.tick_volume, spread = EXCLUDED.spread;
    """)
    with engine.begin() as conn:
        for row in rows:
            conn.execute(sql, row)
    return len(rows)


def collect_loop(cfg, engine, r):
    symbols = cfg["symbols"]
    timeframes = cfg["timeframes"]
    n_candles = 500
    log.info(f"Iniciando coleta para {len(symbols)} simbolos x {len(timeframes)} timeframes")

    while True:
        for symbol in symbols:
            if mt5.symbol_select(symbol, True) is False:
                log.warning(f"Simbolo {symbol} nao disponivel - verifique o Market Watch.")
                continue
            for tf_str in timeframes:
                tf = TIMEFRAME_MAP[tf_str]
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_candles)
                if rates is None:
                    continue
                upsert_candles(engine, symbol, tf_str, rates)
                last = rates[-1]
                r.publish(f"candles:{symbol}:{tf_str}",
                          str({"symbol": symbol, "timeframe": tf_str,
                               "close": float(last["close"]), "time": int(last["time"])}))
        time.sleep(2)


def main():
    cfg = load_config()
    connect_mt5(cfg)
    engine = db_engine(cfg)
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    try:
        collect_loop(cfg, engine, r)
    except KeyboardInterrupt:
        log.info("Encerrando coletor...")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
