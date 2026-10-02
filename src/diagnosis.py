from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Set

import requests

from .models import Diagnosis, Evidence


SYSTEM_PROMPT = """你是谨慎的上市公司研究助手。你只能基于给定 evidence 作答。
严格区分事实、推断、矛盾与未知。每项发现必须提供 evidence_ids，且 ID 必须来自输入。
不得添加输入中不存在的数字，不得预测确定性涨跌，不得承诺收益，不得直接建议买入或卖出。
仅返回 JSON，字段必须为 summary、positive_findings、negative_findings、contradictions、unknowns、follow_up_questions。
四类 findings 的元素格式为 {\"text\": string, \"evidence_ids\": [string]}。"""


def deterministic_diagnosis(evidence: List[Evidence]) -> Diagnosis:
    groups: Dict[str, List[Dict[str, Any]]] = {
        "positive": [], "negative": [], "mixed": [], "unknown": []
    }
    for item in evidence:
        target = item.stance if item.stance in groups else "unknown" if item.stance == "unknown" else None
        if target:
            groups[target].append({"text": item.statement, "evidence_ids": [item.evidence_id]})
    summary = "证据显示公司同时存在支持因素与需要进一步核验的因素；结论不构成投资建议。"
    if groups["unknown"]:
        summary += " 部分维度因数据不足无法确认。"
    return Diagnosis(
        summary=summary,
        positive_findings=groups["positive"],
        negative_findings=groups["negative"],
        contradictions=groups["mixed"],
        unknowns=groups["unknown"],
        follow_up_questions=[
            "最近一期利润变化主要由主营业务还是非经常性项目驱动？",
            "现金流与利润差异是否会在后续报告期收敛？",
            "同行采用相同口径后，公司处于什么位置？",
        ],
        mode="deterministic",
    )


def _validate_citations(result: Dict[str, Any], valid_ids: Set[str]) -> None:
    for key in ("positive_findings", "negative_findings", "contradictions", "unknowns"):
        if not isinstance(result.get(key), list):
            raise ValueError(f"AI 输出字段 {key} 不是数组")
        for item in result[key]:
            cited = set(item.get("evidence_ids", []))
            if not cited or not cited.issubset(valid_ids):
                raise ValueError(f"AI 输出包含无效或缺失的证据引用：{cited}")


def generate_diagnosis(question: str, evidence: List[Evidence]) -> Diagnosis:
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        return deterministic_diagnosis(evidence)
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4.1-mini")
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "question": question,
                "evidence": [item.to_dict() for item in evidence],
            }, ensure_ascii=False)},
        ],
    }
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=(5, 45),
        )
        response.raise_for_status()
        result = json.loads(response.json()["choices"][0]["message"]["content"])
        _validate_citations(result, {item.evidence_id for item in evidence})
        return Diagnosis(**result, mode="llm")
    except (requests.RequestException, KeyError, TypeError, ValueError, json.JSONDecodeError):
        fallback = deterministic_diagnosis(evidence)
        fallback.summary = "AI 解释暂时不可用，以下为确定性证据归纳。" + fallback.summary
        return fallback

