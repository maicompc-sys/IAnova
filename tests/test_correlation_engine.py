"""tests/test_correlation_engine.py"""
import numpy as np
import pandas as pd
import pytest

from engine.correlation_engine import (
    compute_correlation_matrix, flag_high_correlation_pairs, is_new_position_blocked,
)


def make_returns_df(n=100, seed=1):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 0.01, n)
    return pd.DataFrame({
        "EURUSD": base + rng.normal(0, 0.001, n),
        "GBPUSD": base * 0.9 + rng.normal(0, 0.002, n),
        "USDJPY": -base * 0.8 + rng.normal(0, 0.002, n),
        "BTCUSD": rng.normal(0, 0.03, n),
    })


def test_correlation_matrix_diagonal_is_one():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    for symbol in df.columns:
        assert abs(corr.loc[symbol, symbol] - 1.0) < 1e-9


def test_correlation_matrix_symmetric():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    assert np.allclose(corr.values, corr.values.T, atol=1e-9)


def test_flag_high_correlation_detects_known_pair():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    pairs = flag_high_correlation_pairs(corr, threshold=0.5)
    pair_symbols = [frozenset([a, b]) for a, b, _ in pairs]
    assert frozenset(["EURUSD", "GBPUSD"]) in pair_symbols


def test_flag_high_correlation_empty_when_threshold_too_high():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    pairs = flag_high_correlation_pairs(corr, threshold=0.999)
    assert all(abs(c) >= 0.999 for _, _, c in pairs)


def test_is_new_position_blocked_same_direction_positive_corr():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    open_positions = {"EURUSD": "BUY"}
    blocked, reason = is_new_position_blocked("GBPUSD", "BUY", open_positions, corr, threshold=0.5)
    assert blocked is True
    assert "correlacionado" in reason


def test_is_new_position_not_blocked_when_independent():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    open_positions = {"EURUSD": "BUY"}
    blocked, _ = is_new_position_blocked("BTCUSD", "BUY", open_positions, corr, threshold=0.5)
    assert blocked is False


def test_is_new_position_blocked_opposite_direction_negative_corr():
    df = make_returns_df()
    corr = compute_correlation_matrix(df)
    open_positions = {"EURUSD": "BUY"}
    blocked, _ = is_new_position_blocked("USDJPY", "SELL", open_positions, corr, threshold=0.5)
    assert blocked is True
