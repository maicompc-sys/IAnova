"""tests/test_risk_manager.py"""
import pytest
from risk.risk_manager import kelly_fraction, monte_carlo_drawdown


def test_kelly_fraction_zero_when_no_edge():
    assert kelly_fraction(win_rate=0.5, avg_win=1.0, avg_loss=1.0, max_fraction=0.25) == 0.0


def test_kelly_fraction_positive_with_edge():
    assert kelly_fraction(win_rate=0.6, avg_win=1.5, avg_loss=1.0, max_fraction=0.25) > 0.0


def test_kelly_fraction_capped_by_max_fraction():
    f = kelly_fraction(win_rate=0.9, avg_win=5.0, avg_loss=1.0, max_fraction=0.1)
    assert f <= 0.1


def test_kelly_fraction_zero_avg_loss_returns_zero():
    assert kelly_fraction(win_rate=0.6, avg_win=1.0, avg_loss=0.0, max_fraction=0.25) == 0.0


def test_monte_carlo_drawdown_higher_kelly_higher_ruin_risk():
    low_f = monte_carlo_drawdown(10000, 0.02, 0.5, 0.01, 0.01, n_trades=100, n_sims=300, seed=1)
    high_f = monte_carlo_drawdown(10000, 0.5, 0.5, 0.01, 0.01, n_trades=100, n_sims=300, seed=1)
    assert high_f["ruin_prob"] >= low_f["ruin_prob"]


def test_monte_carlo_drawdown_reproducible_with_seed():
    r1 = monte_carlo_drawdown(10000, 0.1, 0.55, 0.012, 0.01, n_trades=50, n_sims=200, seed=99)
    r2 = monte_carlo_drawdown(10000, 0.1, 0.55, 0.012, 0.01, n_trades=50, n_sims=200, seed=99)
    assert r1 == r2
