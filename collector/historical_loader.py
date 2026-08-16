"""
collector/historical_loader.py

Baixa historico de longo prazo (padrao: 1 ano) via MetaTrader5 para todos
os simbolos e timeframes definidos no config.yaml, salvando no TimescaleDB
com upsert idempotente (seguro para rodar multiplas vezes).

Uso:
    python -m collector.historical_loader              # ultimos 365 dias
    python -m collector.historical_loader --days 730   # ultimos 2 anos
    python -m collector.historical_loader --days 365 --symbols EURUSD USDJPY
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import yaml
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [hist-loader] %(message)s",
)
log = logging.getLogger(__name__)

TIMEFRAME_MAP: dict = {}  # preenchido apos import do mt5


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    d = cfg["database"]
    url = (
        f"postgresql+psycopg2://{d['user']}:{d['password']}"
        f"@{d['host']}:{d['port']}/{d['dbname']}"
    )
    return create_engine(url, pool_pre_ping=True)


def connect_mt5(cfg):
    import MetaTrader5 as mt5

    global TIMEFRAME_MAP
    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }

    terminal_path = cfg["mt5"].get("terminal_path")
    ok = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"Falha ao inicializar MT5: {mt5.last_error()}")

    info = mt5.account_info()
    if info is None:
        raise RuntimeError(
            "Nao foi possivel ler account_info - verifique se o MT5 esta logado."
        )
    log.info(
        f"Conectado: conta={info.login} servidor={info.server} "
        f"saldo={info.balance:.2f} equity={info.equity:.2f}"
    )
    return mt5


def upsert_candles(engine, symbol: str, timeframe_str: str, rates) -> int:
    """Insere ou atualiza candles no banco. Retorna quantidade inserida/atualizada."""
    if rates is None or len(rates) == 0:
        return 0

    sql = text("""
        INSERT INTO candles
            (time, symbol, timeframe, open, high, low, close, tick_volume, spread)
        VALUES
            (:time, :symbol, :timeframe, :open, :high, :low, :close, :tick_volume, :spread)
        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
            open        = EXCLUDED.open,
            high        = EXCLUDED.high,
            low         = EXCLUDED.low,
            close       = EXCLUDED.close,
            tick_volume = EXCLUDED.tick_volume,
            spread      = EXCLUDED.spread;
    """)

    rows = []
    for r in rates:
        spread = float(r["spread"]) if "spread" in r.dtype.names else None
        rows.append({
            "time":        datetime.fromtimestamp(r["time"], tz=timezone.utc),
            "symbol":      symbol,
            "timeframe":   timeframe_str,
            "open":        float(r["open"]),
            "high":        float(r["high"]),
            "low":         float(r["low"]),
            "close":       float(r["close"]),
            "tick_volume": int(r["tick_volume"]),
            "spread":      spread,
        })

    # Inserir em lotes de 1000 para evitar transacoes gigantes
    batch_size = 1000
    with engine.begin() as conn:
        for i in range(0, len(rows), batch_size):
            conn.execute(sql, rows[i : i + batch_size])

    return len(rows)


def candles_already_in_db(engine, symbol: str, timeframe_str: str) -> int:
    """Retorna quantos candles ja existem no banco para este par/timeframe."""
    sql = text(
        "SELECT COUNT(*) FROM candles WHERE symbol=:s AND timeframe=:tf"
    )
    with engine.connect() as conn:
        return conn.execute(sql, {"s": symbol, "tf": timeframe_str}).scalar() or 0


def load_history(
    mt5,
    engine,
    symbol: str,
    tf_str: str,
    date_from: datetime,
    date_to: datetime,
) -> int:
    """
    Baixa candles entre date_from e date_to e salva no banco.
    Tenta primeiro copy_rates_range (mais eficiente); se falhar com
    'Invalid params', faz fallback para copy_rates_from_pos em lotes,
    que funciona em qualquer tipo de conta MT5.
    Retorna numero de candles processados.
    """
    if tf_str not in TIMEFRAME_MAP:
        log.warning(f"Timeframe '{tf_str}' nao suportado - ignorando.")
        return 0

    if not mt5.symbol_select(symbol, True):
        log.warning(f"[{symbol}] nao disponivel no Market Watch - pulando.")
        return 0

    tf = TIMEFRAME_MAP[tf_str]

    # --- Tentativa 1: copy_rates_range (ideal) ---
    rates = mt5.copy_rates_range(symbol, tf, date_from, date_to)

    # --- Fallback: copy_rates_from_pos em lotes de ate 99.999 candles ---
    if rates is None or len(rates) == 0:
        log.info(
            f"[{symbol} {tf_str}] copy_rates_range sem dados "
            f"(erro={mt5.last_error()}) — tentando fallback por posicao..."
        )
        BATCH = 99_999          # limite interno do MT5
        all_rates = []
        last_dtype = None       # preserva dtype do ultimo batch valido
        pos = 0
        while True:
            batch = mt5.copy_rates_from_pos(symbol, tf, pos, BATCH)
            if batch is None or len(batch) == 0:
                break
            last_dtype = batch.dtype
            # Filtrar apenas o intervalo desejado (timestamps UTC)
            from_ts = date_from.timestamp()
            to_ts   = date_to.timestamp()
            filtered = [r for r in batch if from_ts <= r["time"] <= to_ts]
            all_rates.extend(filtered)
            # Se o candle mais antigo do lote ja esta antes de date_from, parar
            if batch[0]["time"] <= from_ts:
                break
            pos += BATCH

        if not all_rates or last_dtype is None:
            log.warning(f"[{symbol} {tf_str}] nenhum candle encontrado no intervalo solicitado.")
            return 0

        import numpy as np
        rates = np.array(all_rates, dtype=last_dtype)

    n = upsert_candles(engine, symbol, tf_str, rates)
    log.info(f"[{symbol} {tf_str}] {n:,} candles salvos ({date_from.date()} → {date_to.date()})")
    return n


def main():
    parser = argparse.ArgumentParser(description="Baixa historico de longo prazo via MT5.")
    parser.add_argument(
        "--days", type=int, default=365,
        help="Quantidade de dias de historico a baixar (padrao: 365)"
    )
    parser.add_argument(
        "--symbols", nargs="*", default=None,
        help="Sobrescreve a lista de simbolos do config (ex: EURUSD USDJPY)"
    )
    parser.add_argument(
        "--timeframes", nargs="*", default=None,
        help="Sobrescreve a lista de timeframes do config (ex: M5 H1)"
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="Caminho para o arquivo de configuracao"
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    mt5 = connect_mt5(cfg)
    engine = db_engine(cfg)

    symbols = args.symbols or cfg["symbols"]
    timeframes = args.timeframes or cfg["timeframes"]

    date_to   = datetime.now(tz=timezone.utc)
    date_from = date_to - timedelta(days=args.days)

    log.info(
        f"Iniciando download de {args.days} dias de historico "
        f"({date_from.date()} → {date_to.date()}) para "
        f"{len(symbols)} simbolo(s) x {len(timeframes)} timeframe(s)"
    )

    total_candles = 0
    summary = []

    for symbol in symbols:
        for tf_str in timeframes:
            antes = candles_already_in_db(engine, symbol, tf_str)
            n = load_history(mt5, engine, symbol, tf_str, date_from, date_to)
            depois = candles_already_in_db(engine, symbol, tf_str)
            novos = depois - antes
            total_candles += n
            summary.append({
                "symbol": symbol,
                "tf": tf_str,
                "baixados": n,
                "novos_no_banco": novos,
                "total_banco": depois,
            })

    # ---- Resumo final ----------------------------------------
    log.info("=" * 60)
    log.info(f"RESUMO DO DOWNLOAD HISTORICO ({args.days} dias)")
    log.info("=" * 60)
    log.info(f"{'Simbolo':<10} {'TF':<6} {'Baixados':>10} {'Novos':>8} {'Total no BD':>12}")
    log.info("-" * 60)
    for s in summary:
        log.info(
            f"{s['symbol']:<10} {s['tf']:<6} {s['baixados']:>10,} "
            f"{s['novos_no_banco']:>8,} {s['total_banco']:>12,}"
        )
    log.info("=" * 60)
    log.info(f"Total de candles processados: {total_candles:,}")
    log.info("Download historico concluido.")

    mt5.shutdown()


if __name__ == "__main__":
    main()
