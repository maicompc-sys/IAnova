"""tests/test_indicator_engine.py"""
import numpy as np
import pandas as pd
import pytest

from engine.indicator_engine import compute_indicators, classify_regime, signal_score


def make_synthetic_candles(n=100, trend=0.0005, seed=1):
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + trend + rng.normal(0, 0.002)))
    prices = np.array(prices)
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": prices, "high": prices * 1.001, "low": prices * 0.999, "close": prices,
    })


CFG_ENGINE = {"ema_fast": 9, "ema_slow": 21, "rsi_period": 14, "atr_period": 14,
              "bb_period": 20, "bb_std": 2.0}


def test_compute_indicators_returns_expected_columns():
    df = make_synthetic_candles()
    result = compute_indicators(df, CFG_ENGINE)
    for col in ["ema_fast", "ema_slow", "rsi", "atr", "bb_upper", "bb_lower", "returns"]:
        assert col in result.columns


def test_compute_indicators_last_row_not_nan():
    df = make_synthetic_candles()
    result = compute_indicators(df, CFG_ENGINE)
    assert not pd.isna(result["ema_slow"].iloc[-1])
    assert not pd.isna(result["rsi"].iloc[-1])


def test_classify_regime_uptrend():
    row = pd.Series({"ema_fast": 105.0, "ema_slow": 100.0})
    regime, confidence = classify_regime(row, drift_flag=False)
    assert regime == "trend_up"
    assert confidence > 0


def test_classify_regime_downtrend():
    row = pd.Series({"ema_fast": 95.0, "ema_slow": 100.0})
    regime, _ = classify_regime(row, drift_flag=False)
    assert regime == "trend_down"


def test_classify_regime_range_when_emas_close():
    row = pd.Series({"ema_fast": 100.01, "ema_slow": 100.0})
    regime, _ = classify_regime(row, drift_flag=False)
    assert regime == "range"


def test_classify_regime_nan_ema_returns_range():
    row = pd.Series({"ema_fast": np.nan, "ema_slow": 100.0})
    regime, confidence = classify_regime(row, drift_flag=False)
    assert regime == "range"
    assert confidence == 50.0


def test_classify_regime_drift_reduces_confidence():
    row = pd.Series({"ema_fast": 105.0, "ema_slow": 100.0})
    _, conf_no_drift = classify_regime(row, drift_flag=False)
    _, conf_with_drift = classify_regime(row, drift_flag=True)
    assert conf_with_drift <= conf_no_drift


def test_signal_score_bounded_0_100():
    row = pd.Series({"rsi": 55, "bb_upper": 110, "bb_lower": 90, "close": 100})
    score = signal_score(row, "trend_up", 90.0)
    assert 0 <= score <= 100


def test_signal_score_higher_for_strong_trend_confluence():
    row_strong = pd.Series({"rsi": 60, "bb_upper": 110, "bb_lower": 90, "close": 95})
    row_weak = pd.Series({"rsi": 85, "bb_upper": 110, "bb_lower": 90, "close": 109})
    score_strong = signal_score(row_strong, "trend_up", 90.0)
    score_weak = signal_score(row_weak, "trend_up", 10.0)
    assert score_strong > score_weak
