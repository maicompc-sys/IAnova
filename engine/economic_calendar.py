"""
engine/economic_calendar.py

Filtro de calendario economico: pausa automatica de novas entradas em torno de
eventos de alto impacto (NFP, decisoes de juros, CPI).
"""
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [calendar] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    from sqlalchemy import create_engine
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def is_trading_paused(now: datetime, upcoming_events: pd.DataFrame, symbol_currency: str,
                       minutes_before: int = 15, minutes_after: int = 15) -> tuple:
    if upcoming_events.empty:
        return False, ""

    relevant = upcoming_events[
        (upcoming_events["currency"] == symbol_currency) &
        (upcoming_events["impact"] == "high")
    ]
    for _, event in relevant.iterrows():
        event_time = event["event_time"]
        window_start = event_time - timedelta(minutes=minutes_before)
        window_end = event_time + timedelta(minutes=minutes_after)
        if window_start <= now <= window_end:
            return True, f"Pausa por evento de alto impacto: {event.get('title', 'evento')} em {event_time}"
    return False, ""


def extract_currency_from_symbol(symbol: str) -> list:
    mapping = {
        "XAUUSD": ["USD", "XAU"], "XAGUSD": ["USD", "XAG"],
        "BTCUSD": ["USD", "BTC"], "BNBUSD": ["USD", "BNB"],
    }
    if symbol in mapping:
        return mapping[symbol]
    if len(symbol) == 6:
        return [symbol[:3], symbol[3:]]
    return [symbol]


def fetch_upcoming_events(engine, hours_ahead=6) -> pd.DataFrame:
    from sqlalchemy import text
    sql = text("""
        SELECT event_time, currency, impact, title FROM economic_events
        WHERE event_time BETWEEN now() - interval '2 hours' AND now() + interval :hours
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"hours": f"{hours_ahead} hours"})
    return df


def insert_manual_event(engine, event_time, currency, impact, title):
    from sqlalchemy import text
    sql = text("""
        INSERT INTO economic_events (event_time, currency, impact, title)
        VALUES (:event_time, :currency, :impact, :title)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"event_time": event_time, "currency": currency, "impact": impact, "title": title})


def should_pause_symbol(engine, cfg, symbol) -> tuple:
    now = datetime.now(timezone.utc)
    events = fetch_upcoming_events(engine, hours_ahead=6)
    currencies = extract_currency_from_symbol(symbol)
    for currency in currencies:
        paused, reason = is_trading_paused(
            now, events, currency,
            cfg["calendar"]["high_impact_pause_minutes_before"],
            cfg["calendar"]["high_impact_pause_minutes_after"],
        )
        if paused:
            return True, reason
    return False, ""
