"""
notifier/telegram_notifier.py
Envia alertas via Telegram Bot API: novos sinais, bloqueios de risco, circuit breakers.
"""
import time
import logging

import yaml
import requests
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [telegram] %(message)s")
log = logging.getLogger(__name__)


def load_config(path="config/config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def db_engine(cfg):
    d = cfg["database"]
    url = f"postgresql+psycopg2://{d['user']}:{d['password']}@{d['host']}:{d['port']}/{d['dbname']}"
    return create_engine(url)


def send_alert(cfg, text_msg):
    token = cfg["telegram"]["bot_token"]
    chat_id = cfg["telegram"]["chat_id"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text_msg, "parse_mode": "Markdown"}, timeout=10)
        if resp.status_code != 200:
            log.warning(f"Falha ao enviar Telegram: {resp.text}")
    except Exception as e:
        log.exception(f"Erro ao enviar alerta Telegram: {e}")


def poll_new_signals(cfg, engine, last_seen_id):
    sql = text("SELECT id, time, symbol, direction, score, blocked_reason FROM signals WHERE id > :last_id ORDER BY id ASC")
    with engine.connect() as conn:
        rows = conn.execute(sql, {"last_id": last_seen_id}).fetchall()
    for row in rows:
        if row.blocked_reason:
            msg = f"*Sinal bloqueado*\nSimbolo: `{row.symbol}`\nMotivo: {row.blocked_reason}"
        else:
            msg = (f"*Novo sinal*\nSimbolo: `{row.symbol}`\nDirecao: *{row.direction}*\n"
                   f"Score: {row.score}/100\nHorario: {row.time}")
        send_alert(cfg, msg)
        last_seen_id = row.id
    return last_seen_id


def main():
    cfg = load_config()
    engine = db_engine(cfg)
    last_id = 0
    log.info("Notificador Telegram iniciado.")
    while True:
        try:
            last_id = poll_new_signals(cfg, engine, last_id)
        except Exception as e:
            log.exception(f"Erro no loop do notificador: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
