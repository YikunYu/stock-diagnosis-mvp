from __future__ import annotations

import math
import statistics
from typing import Any, Dict, Iterable, List, Optional

from .models import Metric


def safe_growth(current: Any, previous: Any) -> Optional[float]:
    # A non-positive base makes the conventional percentage growth rate
    # misleading (for example, a loss turning into profit). Treat it as a
    # separate situation instead of emitting a mathematically valid but
    # economically confusing percentage.
    if current is None or previous is None or float(previous) <= 0:
        return None
    return (float(current) - float(previous)) / float(previous) * 100.0


def safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def percentile_rank(values: Iterable[Any], current: Any) -> Optional[float]:
    clean = [float(v) for v in values if v is not None]
    if not clean or current is None:
        return None
    return sum(value <= float(current) for value in clean) / len(clean) * 100.0


def annualized_volatility(closes: Iterable[Any]) -> Optional[float]:
    clean = [float(value) for value in closes if value is not None and float(value) > 0]
    if len(clean) < 3:
        return None
    returns = [math.log(clean[index] / clean[index - 1]) for index in range(1, len(clean))]
    return statistics.stdev(returns) * math.sqrt(252) * 100.0


def max_drawdown(closes: Iterable[Any]) -> Optional[float]:
    clean = [float(value) for value in closes if value is not None]
    if not clean:
        return None
    peak = clean[0]
    worst = 0.0
    for value in clean:
        peak = max(peak, value)
        if peak != 0:
            worst = min(worst, (value / peak - 1.0) * 100.0)
    return worst


def _metric(
    key: str,
    label: str,
    value: Optional[float],
    unit: str,
    period: str,
    source: str,
    formula: str,
    raw_fields: List[str],
) -> Metric:
    return Metric(
        key=key,
        label=label,
        value=value,
        unit=unit,
        period=period,
        source=source,
        formula=formula,
        raw_fields=raw_fields,
        status="valid" if value is not None and math.isfinite(value) else "not_calculable",
        note="无法计算：字段缺失或分母为零" if value is None else "",
    )


def calculate_metrics(payload: Dict[str, Any]) -> List[Metric]:
    periods = sorted(payload["financials"], key=lambda row: row["period"])
    previous, current = periods[-2], periods[-1]
    source = payload["company"].get("source", "未注明来源")
    period = current["period"]
    valuation = payload.get("valuation", {})
    closes = [row.get("close") for row in payload.get("prices", [])]

    metrics = [
        _metric("revenue_growth", "营业收入同比", safe_growth(current.get("revenue"), previous.get("revenue")), "%", period, source, "(本期营业收入/上期营业收入-1)×100", ["revenue"]),
        _metric("profit_growth", "归母净利润同比", safe_growth(current.get("net_profit"), previous.get("net_profit")), "%", period, source, "(本期归母净利润/上期归母净利润-1)×100", ["net_profit"]),
        _metric("gross_margin", "毛利率", current.get("gross_margin"), "%", period, source, "数据源披露值", ["gross_margin"]),
        _metric("roe", "ROE", current.get("roe"), "%", period, source, "数据源披露值", ["roe"]),
        _metric("cash_profit_ratio", "经营现金流/净利润", safe_ratio(current.get("operating_cash_flow"), current.get("net_profit")), "倍", period, source, "经营活动现金流净额/归母净利润", ["operating_cash_flow", "net_profit"]),
        _metric("pe", "当前 PE", valuation.get("current_pe"), "倍", payload["company"].get("as_of", "未知"), source, "数据源披露值", ["current_pe"]),
        _metric("pe_percentile", "PE 历史分位", percentile_rank(valuation.get("historical_pe", []), valuation.get("current_pe")), "%", payload["company"].get("as_of", "未知"), source, "历史样本中小于等于当前 PE 的占比", ["current_pe", "historical_pe"]),
        _metric("volatility", "年化波动率", annualized_volatility(closes), "%", payload["company"].get("as_of", "未知"), source, "日对数收益率标准差×√252", ["prices.close"]),
        _metric("max_drawdown", "区间最大回撤", max_drawdown(closes), "%", payload["company"].get("as_of", "未知"), source, "区间内相对历史峰值的最大跌幅", ["prices.close"]),
    ]
    return metrics
