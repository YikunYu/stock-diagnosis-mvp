import copy

from src.diagnosis import deterministic_diagnosis
from src.evidence import build_evidence
from src.metrics import calculate_metrics
import pytest

from src.providers import DataProviderError, DemoProvider, FuyaoProvider


def test_demo_pipeline_has_traceable_evidence():
    payload = DemoProvider().fetch()
    metrics = calculate_metrics(payload)
    evidence = build_evidence(metrics)
    result = deterministic_diagnosis(evidence)
    valid_ids = {item.evidence_id for item in evidence}
    assert evidence
    assert result.summary
    for group in (result.positive_findings, result.negative_findings, result.contradictions, result.unknowns):
        for finding in group:
            assert set(finding["evidence_ids"]).issubset(valid_ids)


def test_missing_value_becomes_unknown_not_normal():
    payload = copy.deepcopy(DemoProvider().fetch())
    payload["financials"][-1]["net_profit"] = None
    evidence = build_evidence(calculate_metrics(payload))
    assert any(item.stance == "unknown" and "净利润" in item.statement for item in evidence)


def test_zero_denominator_does_not_crash():
    payload = copy.deepcopy(DemoProvider().fetch())
    payload["financials"][-1]["net_profit"] = 0
    metrics = calculate_metrics(payload)
    cash = next(item for item in metrics if item.key == "cash_profit_ratio")
    assert cash.status == "not_calculable"


@pytest.mark.parametrize(
    "symbol,expected",
    [("000333", "000333.SZ"), ("600519", "600519.SH"), ("430047", "430047.BJ"), ("000333.SZ", "000333.SZ")],
)
def test_fuyao_symbol_normalization(symbol, expected):
    assert FuyaoProvider.normalize_thscode(symbol) == expected


def test_fuyao_requires_secret():
    provider = FuyaoProvider(api_key="")
    provider.api_key = ""
    with pytest.raises(DataProviderError, match="FUYAO_API_KEY"):
        provider.fetch("000333")
