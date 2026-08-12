"""tests/test_economic_calendar.py"""
from datetime import datetime, timezone
import pandas as pd
import pytest

from engine.economic_calendar import is_trading_paused, extract_currency_from_symbol


def test_extract_currency_forex_pair():
    assert extract_currency_from_symbol("EURUSD") == ["EUR", "USD"]


def test_extract_currency_metal():
    assert extract_currency_from_symbol("XAUUSD") == ["USD", "XAU"]


def test_extract_currency_crypto():
    assert extract_currency_from_symbol("BTCUSD") == ["USD", "BTC"]


def test_is_trading_paused_inside_window():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    events = pd.DataFrame([{"event_time": datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
                             "currency": "USD", "impact": "high", "title": "NFP"}])
    paused, reason = is_trading_paused(now, events, "USD", 15, 15)
    assert paused is True
    assert "NFP" in reason


def test_is_trading_paused_outside_window():
    now = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    events = pd.DataFrame([{"event_time": datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
                             "currency": "USD", "impact": "high", "title": "NFP"}])
    paused, _ = is_trading_paused(now, events, "USD", 15, 15)
    assert paused is False


def test_is_trading_paused_ignores_low_impact():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    events = pd.DataFrame([{"event_time": datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
                             "currency": "USD", "impact": "low", "title": "Minor Data"}])
    paused, _ = is_trading_paused(now, events, "USD", 15, 15)
    assert paused is False


def test_is_trading_paused_wrong_currency():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    events = pd.DataFrame([{"event_time": datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
                             "currency": "EUR", "impact": "high", "title": "ECB Rate Decision"}])
    paused, _ = is_trading_paused(now, events, "USD", 15, 15)
    assert paused is False


def test_is_trading_paused_empty_events():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    events = pd.DataFrame(columns=["event_time", "currency", "impact", "title"])
    paused, _ = is_trading_paused(now, events, "USD")
    assert paused is False
