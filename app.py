from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.diagnosis import generate_diagnosis
from src.evidence import build_evidence
from src.metrics import calculate_metrics
from src.models import Evidence, Metric
from src.providers import DataProviderError, DemoProvider, FuyaoProvider, HttpJsonProvider, UploadedJsonProvider


load_dotenv()
st.set_page_config(page_title="证据镜 · 个股诊断", page_icon="🔎", layout="wide")


def metric_text(metric: Metric) -> str:
    if metric.status != "valid" or metric.value is None:
        return "无法计算"
    decimals = 2 if metric.unit == "倍" else 1
    return f"{metric.value:.{decimals}f}{metric.unit}"


def render_finding(title: str, items: List[Dict[str, Any]], tone: str) -> None:
    colors = {"good": "#EAF7EF", "bad": "#FFF0F0", "mixed": "#FFF7E6", "unknown": "#EEF2F7"}
    st.markdown(f"#### {title}")
    if not items:
        st.caption("本次没有形成此类结论。")
        return
    for item in items:
        ids = "、".join(item.get("evidence_ids", []))
        st.markdown(
            f"<div style='padding:12px 14px;margin:7px 0;border-radius:10px;background:{colors[tone]};'>"
            f"{item.get('text', '')}<br><small>证据：{ids}</small></div>",
            unsafe_allow_html=True,
        )


def render_evidence(item: Evidence) -> None:
    icon = {"positive": "🟢", "negative": "🔴", "mixed": "🟠", "neutral": "🔵", "unknown": "⚪"}.get(item.stance, "⚪")
    with st.expander(f"{icon} {item.evidence_id} · {item.dimension}｜{item.statement}"):
        st.write(f"**证据属性：** {item.stance}　 **置信度：** {item.confidence}")
        st.write(f"**期间：** {item.period}")
        st.write(f"**来源：** {item.source}")
        for key, detail in item.details.items():
            value = detail.get("value")
            display = "无法计算" if value is None else f"{value:.2f}{detail.get('unit', '')}"
            st.markdown(f"**{detail.get('label', key)}：{display}**")
            st.caption(f"公式：{detail.get('formula')}｜原始字段：{', '.join(detail.get('raw_fields', []))}｜状态：{detail.get('status')}")


st.title("证据镜 · 个股多维诊断")
st.caption("把客观事实、分析推断、矛盾证据与未知信息分开呈现。结果不构成投资建议。")

with st.sidebar:
    st.header("诊断设置")
    symbol = st.text_input("股票代码", value="000333", max_chars=10)
    source_mode = st.radio("数据来源", ["内置演示数据", "扶摇实时 REST", "上传标准 JSON", "HTTP 数据桥"], index=0)
    upload = None
    if source_mode == "上传标准 JSON":
        upload = st.file_uploader("上传 JSON", type=["json"])
    if source_mode == "HTTP 数据桥":
        if os.getenv("FINANCE_API_URL"):
            st.success("已从环境变量读取接口地址")
        else:
            st.warning("请配置 FINANCE_API_URL")
    if source_mode == "扶摇实时 REST":
        if os.getenv("FUYAO_API_KEY"):
            st.success("已读取 FUYAO_API_KEY")
        else:
            st.warning("请在环境变量或部署 Secrets 中配置 FUYAO_API_KEY")
    question = st.selectbox(
        "诊断问题",
        ["经营质量是否改善，当前估值是否与基本面匹配？", "主要的正面、负面和矛盾证据是什么？", "目前还有哪些信息无法验证？"],
    )
    run = st.button("开始诊断", type="primary", width="stretch")
    st.divider()
    st.caption("LLM 状态：" + ("已配置" if os.getenv("LLM_API_KEY") else "未配置，将使用确定性归纳"))

if not run:
    st.info("从左侧选择数据源并点击“开始诊断”。第一次体验建议使用内置演示数据。")
    st.stop()

try:
    if source_mode == "内置演示数据":
        provider = DemoProvider()
    elif source_mode == "扶摇实时 REST":
        provider = FuyaoProvider()
    elif source_mode == "上传标准 JSON":
        if upload is None:
            st.warning("请先上传符合 README 数据契约的 JSON 文件。")
            st.stop()
        provider = UploadedJsonProvider(upload)
    else:
        provider = HttpJsonProvider()
    payload = provider.fetch(symbol)
except DataProviderError as exc:
    st.error(str(exc))
    st.caption("数据源失败不会被解释为公司表现正常。请检查接口、字段映射或上传文件。")
    st.stop()

company = payload["company"]
if company.get("data_mode") == "demo":
    st.warning("当前展示的是合成演示数据，不是真实财务或行情数据，不得用于投资判断。")

st.subheader(f"{company.get('name', '未知公司')} · {company.get('symbol', symbol)}")
st.caption(f"行业：{company.get('industry', '未知')}｜数据截至：{company.get('as_of', '未知')}｜来源：{company.get('source', '未知')}")

metrics = calculate_metrics(payload)
evidence = build_evidence(metrics)
diagnosis = generate_diagnosis(question, evidence)

st.markdown("### 诊断摘要")
st.write(diagnosis.summary)
mode_label = "LLM 基于证据解释" if diagnosis.mode == "llm" else "确定性规则归纳（未调用或未成功调用 LLM）"
st.caption(f"生成方式：{mode_label}")

headline_keys = ["revenue_growth", "profit_growth", "cash_profit_ratio", "pe", "pe_percentile", "max_drawdown"]
headline = [metric for key in headline_keys for metric in metrics if metric.key == key]
columns = st.columns(len(headline))
for column, metric in zip(columns, headline):
    column.metric(metric.label, metric_text(metric))

left, right = st.columns(2)
with left:
    render_finding("正面证据", diagnosis.positive_findings, "good")
    render_finding("矛盾证据", diagnosis.contradictions, "mixed")
with right:
    render_finding("负面证据", diagnosis.negative_findings, "bad")
    render_finding("未知信息", diagnosis.unknowns, "unknown")

st.markdown("### 证据回溯")
st.caption("展开任意证据，可查看数据期间、来源、公式、原始字段和计算状态。")
for item in evidence:
    render_evidence(item)

chart_left, chart_right = st.columns(2)
with chart_left:
    st.markdown("### 价格样本")
    price_frame = pd.DataFrame(payload["prices"])
    st.line_chart(price_frame.set_index("date")["close"])
with chart_right:
    st.markdown("### 同行对比")
    peer_frame = pd.DataFrame(payload.get("peers", []))
    if peer_frame.empty:
        st.info("暂无同行数据。")
    else:
        st.dataframe(peer_frame, width="stretch", hide_index=True)

st.markdown("### 继续研究")
for prompt in diagnosis.follow_up_questions:
    st.markdown(f"- {prompt}")

with st.expander("查看本次结构化输出"):
    st.json({
        "question": question,
        "diagnosis": diagnosis.to_dict(),
        "evidence": [item.to_dict() for item in evidence],
    })

st.caption("免责声明：本工具用于展示证据组织与研究流程，不提供确定性涨跌预测、收益承诺或直接买卖建议。")
