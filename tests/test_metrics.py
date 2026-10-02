import math

from src.metrics import annualized_volatility, max_drawdown, percentile_rank, safe_growth, safe_ratio


def test_safe_growth():
    assert safe_growth(110, 100) == 10
    assert safe_growth(1, 0) is None
    assert safe_growth(None, 1) is None


def test_safe_ratio():
    assert safe_ratio(80, 100) == 0.8
    assert safe_ratio(80, 0) is None


def test_percentile_rank_ignores_missing():
    assert percentile_rank([1, 2, None, 3, 4], 2) == 50


def test_max_drawdown():
    assert math.isclose(max_drawdown([100, 120, 90, 110]), -25.0)


def test_volatility_needs_enough_samples():
    assert annualized_volatility([100, 101]) is None

