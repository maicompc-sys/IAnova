"""
collector/news_collector.py

Coletor de noticias e eventos de mercado via API Finnhub.
Identifica noticias de alto impacto e persiste no TimescaleDB (tabela economic_events)
para alimentar o filtro de pausa de entradas no motor de risco/calendario.

Uso:
    python -m collector.news_collector
"""
import logging
import os
import re
import sys
from datetime import datetime, timezone
import requests
import yaml
from sqlalchemy import create_engine, text

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [news-collector] %(message)s")
log = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

HIGH_IMPACT_KEYWORDS = [
    r"\bNFP\b", r"\bnon-farm\b", r"\bCPI\b", r"\binflation\b",
    r"\brate decision\b", r"\binterest rate\b", r"\bfed\b", r"\bfomc\b",
    r"\becb\b", r"\bboj\b", r"\bboe\b", r"\bpowell\b", r"\blagarde\b",
    r"\bemergency rate\b", r"\btariff\b", r"\bwar\b", r"\bsanctions\b",
    r"\bdefault\b", r"\bbank run\b", r"\bsec lawsuit\b", r"\bliquidation\b"
]

CURRENCY_KEYWORDS = {
    "USD": [r"\busd\b", r"\bfed\b", r"\bfomc\b", r"\bpowell\b", r"\bunited states\b", r"\bus economy\b", r"\bdollar\b"],
    "EUR": [r"\beur\b", r"\becb\b", r"\blagarde\b", r"\beurozone\b", r"\beuro\b"],
    "GBP": [r"\bgbp\b", r"\bboe\b", r"\bbank of england\b", r"\bpound\b", r"\buk economy\b"],
    "JPY": [r"\bjpy\b", r"\bboj\b", r"\bbank of japan\b", r"\byen\b", r"\bueda\b"],
    "BTC": [r"\bbtc\b", r"\bbitcoin\b", r"\bcrypto\b", r"\bsec\b", r"\betf\b"],
    "XAU": [r"\bgold\b", r"\bxau\b", r"\bbullion\b", r"\byields\b"],
}


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def fetch_finnhub_news(api_key: str, category: str = "general") -> list:
    """Busca noticias da API Finnhub por categoria (general, forex, crypto)."""
    if not api_key:
        log.warning("Chave de API Finnhub nao configurada.")
        return []
    url = f"{FINNHUB_BASE_URL}/news?category={category}&token={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        log.error(f"Erro Finnhub ({resp.status_code}): {resp.text}")
        return []
    except Exception as e:
        log.exception(f"Falha na requisicao Finnhub: {e}")
        return []


def classify_news_impact(headline: str, summary: str = "") -> tuple:
    """Classifica o impacto (high/low) e identifica as moedas/ativos impactados."""
    text_content = f"{headline} {summary}".lower()
    is_high = any(re.search(kw, text_content, re.IGNORECASE) for kw in HIGH_IMPACT_KEYWORDS)
    impact = "high" if is_high else "low"

    affected_currencies = []
    for curr, patterns in CURRENCY_KEYWORDS.items():
        if any(re.search(pat, text_content, re.IGNORECASE) for pat in patterns):
            affected_currencies.append(curr)

    if not affected_currencies:
        affected_currencies = ["USD"]  # Default para noticias globais

    return impact, affected_currencies


def sync_news_to_db(engine, api_key: str, categories: list = None) -> int:
    """Baixa noticias e insere eventos de alto impacto no banco economic_events."""
    if categories is None:
        categories = ["forex", "crypto", "general"]

    total_inserted = 0
    sql_check = text("SELECT 1 FROM economic_events WHERE title = :title AND event_time = :event_time LIMIT 1")
    sql_insert = text("""
        INSERT INTO economic_events (event_time, currency, impact, title, actual)
        VALUES (:event_time, :currency, :impact, :title, :actual)
    """)

    for cat in categories:
        items = fetch_finnhub_news(api_key, cat)
        log.info(f"[{cat}] {len(items)} noticias recebidas do Finnhub.")
        for item in items:
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            ts = item.get("datetime")
            if not headline or not ts:
                continue

            event_time = datetime.fromtimestamp(ts, tz=timezone.utc)
            impact, currencies = classify_news_impact(headline, summary)

            if impact == "high":
                with engine.begin() as conn:
                    for curr in currencies:
                        exists = conn.execute(sql_check, {"title": headline, "event_time": event_time}).scalar()
                        if not exists:
                            conn.execute(sql_insert, {
                                "event_time": event_time,
                                "currency": curr,
                                "impact": "high",
                                "title": headline,
                                "actual": item.get("source", "Finnhub")
                            })
                            total_inserted += 1

    log.info(f"Sincronizacao concluida: {total_inserted} novos eventos de alto impacto registrados.")
    return total_inserted


def main():
    cfg = load_config()
    api_key = cfg.get("news", {}).get("api_key") or cfg.get("calendar", {}).get("api_key")
    if not api_key:
        log.error("Finnhub api_key nao encontrada no config.yaml.")
        return

    engine = db_engine(cfg)
    categories = cfg.get("news", {}).get("categories", ["forex", "crypto", "general"])
    sync_news_to_db(engine, api_key, categories)


if __name__ == "__main__":
    main()
