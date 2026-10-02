from __future__ import annotations

from typing import Dict, List

from .models import Evidence, Metric


def build_evidence(metrics: List[Metric]) -> List[Evidence]:
    by_key: Dict[str, Metric] = {metric.key: metric for metric in metrics}
    evidence: List[Evidence] = []

    def add(dimension: str, statement: str, stance: str, keys: List[str], confidence: str = "medium") -> None:
        usable = [by_key[key] for key in keys if key in by_key and by_key[key].status == "valid"]
        source = "；".join(dict.fromkeys(metric.source for metric in usable)) or "无可用来源"
        period = "；".join(dict.fromkeys(metric.period for metric in usable)) or "未知"
        evidence.append(Evidence(
            evidence_id=f"E{len(evidence) + 1:02d}",
            dimension=dimension,
            statement=statement,
            stance=stance,
            metric_keys=keys,
            period=period,
            source=source,
            confidence=confidence,
            details={key: by_key[key].to_dict() for key in keys if key in by_key},
        ))

    revenue = by_key["revenue_growth"]
    profit = by_key["profit_growth"]
    cash = by_key["cash_profit_ratio"]
    pe_pct = by_key["pe_percentile"]
    drawdown = by_key["max_drawdown"]

    if revenue.status != "valid":
        add("增长", "营业收入增速因数据缺失或口径问题无法计算。", "unknown", ["revenue_growth"], "low")
    else:
        stance = "positive" if revenue.value > 5 else "negative" if revenue.value < 0 else "neutral"
        add("增长", f"营业收入同比为 {revenue.value:.1f}%。", stance, ["revenue_growth"], "high")

    if profit.status != "valid":
        add("增长", "归母净利润增速当前无法验证。", "unknown", ["profit_growth"], "low")
    else:
        stance = "positive" if profit.value > 5 else "negative" if profit.value < 0 else "neutral"
        add("增长", f"归母净利润同比为 {profit.value:.1f}%。", stance, ["profit_growth"], "high")

    if cash.status != "valid":
        add("质量", "现金利润比无法计算，暂不能判断利润现金含量。", "unknown", ["cash_profit_ratio"], "low")
    else:
        stance = "positive" if cash.value >= 1 else "negative" if cash.value < 0.7 else "neutral"
        add("质量", f"经营现金流与净利润之比为 {cash.value:.2f} 倍。", stance, ["cash_profit_ratio"], "high")

    if profit.status == "valid" and cash.status == "valid" and profit.value > 5 and cash.value < 1:
        add("质量", "利润增长，但经营现金流未能完全覆盖净利润，增长与现金兑现存在矛盾。", "mixed", ["profit_growth", "cash_profit_ratio"], "high")

    if pe_pct.status != "valid":
        add("估值", "缺少足够历史估值样本，当前估值位置无法确认。", "unknown", ["pe_percentile"], "low")
    else:
        stance = "negative" if pe_pct.value >= 75 else "positive" if pe_pct.value <= 25 else "neutral"
        add("估值", f"当前 PE 位于历史样本的 {pe_pct.value:.0f}% 分位。", stance, ["pe", "pe_percentile"], "medium")

    if drawdown.status == "valid":
        stance = "negative" if drawdown.value <= -20 else "neutral"
        add("行情", f"所给价格区间最大回撤为 {drawdown.value:.1f}%。", stance, ["volatility", "max_drawdown"], "high")
    else:
        add("行情", "价格样本不足，无法计算风险特征。", "unknown", ["volatility", "max_drawdown"], "low")

    return evidence

