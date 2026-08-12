"""tests/test_var_engine.py"""
import numpy as np
import pandas as pd
import pytest

from risk.var_engine import (
    parametric_var, monte_carlo_var, check_var_limit, portfolio_weights_from_positions,
)


def make_returns_df(n=250, seed=7):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "EURUSD": rng.normal(0.0001, 0.005, n),
        "XAUUSD": rng.normal(0.0002, 0.012, n),
        "BTCUSD": rng.normal(0.0005, 0.03, n),
    })


def test_parametric_var_positive_for_nonzero_exposure():
    df = make_returns_df()
    result = parametric_var(df, {"EURUSD": 0.5, "XAUUSD": 0.5}, confidence=0.95, horizon_days=1)
    assert result["var_pct"] > 0
    assert result["method"] == "parametric"


def test_parametric_var_higher_for_more_volatile_asset():
    df = make_returns_df()
    var_low_vol = parametric_var(df, {"EURUSD": 1.0}, confidence=0.95)
    var_high_vol = parametric_var(df, {"BTCUSD": 1.0}, confidence=0.95)
    assert var_high_vol["var_pct"] > var_low_vol["var_pct"]


def test_parametric_var_scales_with_confidence():
    df = make_returns_df()
    var_95 = parametric_var(df, {"EURUSD": 1.0}, confidence=0.95)
    var_99 = parametric_var(df, {"EURUSD": 1.0}, confidence=0.99)
    assert var_99["var_pct"] > var_95["var_pct"]


def test_monte_carlo_var_reasonable_range():
    df = make_returns_df()
    result = monte_carlo_var(df, {"EURUSD": 0.5, "XAUUSD": 0.5}, confidence=0.95, n_sims=5000)
    assert 0 < result["var_pct"] < 50


def test_monte_carlo_var_reproducible_with_seed():
    df = make_returns_df()
    weights = {"EURUSD": 0.5, "XAUUSD": 0.5}
    r1 = monte_carlo_var(df, weights, confidence=0.95, n_sims=2000, seed=123)
    r2 = monte_carlo_var(df, weights, confidence=0.95, n_sims=2000, seed=123)
    assert r1["var_pct"] == r2["var_pct"]


def test_check_var_limit_blocks_when_exceeded():
    blocked, reason = check_var_limit({"var_pct": 5.0}, max_portfolio_var_pct=3.0)
    assert blocked is True
    assert "excede" in reason


def test_check_var_limit_allows_when_within_range():
    blocked, reason = check_var_limit({"var_pct": 2.0}, max_portfolio_var_pct=3.0)
    assert blocked is False
    assert reason == ""


def test_portfolio_weights_from_positions_sign_convention():
    weights = portfolio_weights_from_positions(
        {"EURUSD": "BUY", "XAUUSD": "SELL"}, balance=10000.0,
        position_values={"EURUSD": 1000.0, "XAUUSD": 500.0})
    assert weights["EURUSD"] > 0
    assert weights["XAUUSD"] < 0


def test_portfolio_weights_zero_balance_returns_zero():
    weights = portfolio_weights_from_positions(
        {"EURUSD": "BUY"}, balance=0.0, position_values={"EURUSD": 1000.0})
    assert weights["EURUSD"] == 0.0
