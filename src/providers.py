from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class DataProviderError(RuntimeError):
    """A visible, recoverable data-source failure."""


REQUIRED_TOP_LEVEL = {
    "company",
    "financials",
    "valuation",
    "prices",
    "peers",
    "events",
}


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing = REQUIRED_TOP_LEVEL - set(payload)
    if missing:
        raise DataProviderError("数据缺少顶层字段：" + ", ".join(sorted(missing)))
    if len(payload["financials"]) < 2:
        raise DataProviderError("至少需要两个可比财务期间。")
    if not payload["prices"]:
        raise DataProviderError("价格序列为空。")
    return payload


class DemoProvider:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(__file__).resolve().parents[1] / "data" / "demo_000333.json"

    def fetch(self, symbol: str = "000333") -> Dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataProviderError(f"无法读取演示数据：{exc}") from exc
        payload["company"]["requested_symbol"] = symbol
        return validate_payload(payload)


class UploadedJsonProvider:
    def __init__(self, file_obj: Any) -> None:
        self.file_obj = file_obj

    def fetch(self, symbol: str = "000333") -> Dict[str, Any]:
        try:
            raw = self.file_obj.getvalue()
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
            raise DataProviderError(f"上传文件不是有效 JSON：{exc}") from exc
        return validate_payload(payload)


class HttpJsonProvider:
    """Adapter for a deployable finance-data bridge.

    The endpoint may wrap Fuyao, iFinD MCP or an internal service. It should
    return the canonical payload described in README.md.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.url = url or os.getenv("FINANCE_API_URL", "")
        self.api_key = api_key or os.getenv("FINANCE_API_KEY", "")

    def fetch(self, symbol: str = "000333") -> Dict[str, Any]:
        if not self.url:
            raise DataProviderError("尚未配置 FINANCE_API_URL。")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = requests.post(
                self.url,
                json={"symbol": symbol},
                headers=headers,
                timeout=(5, 25),
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise DataProviderError("金融数据接口超时。") from exc
        except requests.RequestException as exc:
            raise DataProviderError(f"金融数据接口失败：{exc}") from exc
        except ValueError as exc:
            raise DataProviderError("金融数据接口未返回有效 JSON。") from exc
        return validate_payload(payload)


class FuyaoProvider:
    """Native adapter for the public Fuyao A-share REST contract."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("FUYAO_API_KEY", "")
        self.base_url = (base_url or os.getenv("FUYAO_BASE_URL", "https://fuyao.aicubes.cn")).rstrip("/")
        self.session = session or requests.Session()
        self.request_ids = []

    @staticmethod
    def normalize_thscode(symbol: str) -> str:
        value = symbol.strip().upper()
        if value.endswith((".SH", ".SZ", ".BJ")):
            return value
        if not (len(value) == 6 and value.isdigit()):
            raise DataProviderError("股票代码应为 6 位数字或完整 thscode，例如 000333 / 000333.SZ。")
        if value.startswith("6"):
            return f"{value}.SH"
        if value.startswith(("4", "8")):
            return f"{value}.BJ"
        return f"{value}.SZ"

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise DataProviderError("尚未配置 FUYAO_API_KEY。请在本地 .env 或部署平台 Secrets 中配置。")
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers={"X-api-key": self.api_key, "Accept": "application/json"},
                timeout=(5, 30),
            )
            if response.status_code == 429:
                raise DataProviderError("扶摇接口触发限流，请稍后重试。")
            response.raise_for_status()
            envelope = response.json()
        except requests.Timeout as exc:
            raise DataProviderError(f"扶摇接口超时：{path}") from exc
        except requests.RequestException as exc:
            raise DataProviderError(f"扶摇接口请求失败：{path}：{exc}") from exc
        except ValueError as exc:
            raise DataProviderError(f"扶摇接口返回了非 JSON 响应：{path}") from exc
        if envelope.get("code") != 0:
            raise DataProviderError(
                f"扶摇业务错误 code={envelope.get('code')}：{envelope.get('message', '未知错误')}"
            )
        if envelope.get("request_id"):
            self.request_ids.append(envelope["request_id"])
        return envelope.get("data") or {}

    @staticmethod
    def _indicator_map(data: Dict[str, Any]) -> Dict[str, Optional[float]]:
        result: Dict[str, Optional[float]] = {}
        for ability in data.get("abilities", []):
            for item in ability.get("indicators", []):
                raw = item.get("value")
                try:
                    result[item["index_id"]] = float(raw) if raw is not None else None
                except (KeyError, TypeError, ValueError):
                    continue
        return result

    @staticmethod
    def _date_from_ms(value: Any) -> str:
        if value is None:
            return "未知"
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")

    def fetch(self, symbol: str = "000333") -> Dict[str, Any]:
        thscode = self.normalize_thscode(symbol)
        common = {"thscode": thscode, "period": "annual", "limit": 2}
        income_data = self._get("/api/a-share/financials/income-statements", common)
        cash_data = self._get("/api/a-share/financials/cash-flow-statements", common)
        income_rows = income_data.get("item", [])
        cash_rows = cash_data.get("item", [])
        if len(income_rows) < 2:
            raise DataProviderError("扶摇利润表不足两个可比年度，无法计算同比。")

        cash_by_period = {row.get("period_end_ms"): row for row in cash_rows}
        indicator_by_period: Dict[Any, Dict[str, Optional[float]]] = {}
        # The indicators endpoint uses yyyy-4 for annual reports. Failure of a
        # single optional indicator call should not hide valid statement data.
        for row in income_rows[:2]:
            report = f"{row.get('fiscal_year')}-4"
            try:
                indicator_data = self._get(
                    "/api/a-share/financials/indicators",
                    {"thscode": thscode, "report": report},
                )
                indicator_by_period[row.get("period_end_ms")] = self._indicator_map(indicator_data)
            except DataProviderError:
                indicator_by_period[row.get("period_end_ms")] = {}

        financials = []
        for row in income_rows[:2]:
            period_ms = row.get("period_end_ms")
            indicators = indicator_by_period.get(period_ms, {})
            cash = cash_by_period.get(period_ms, {})
            operating_income = row.get("operating_income")
            operating_costs = row.get("operating_costs")
            computed_margin = None
            if operating_income not in (None, 0) and operating_costs is not None:
                computed_margin = (float(operating_income) - float(operating_costs)) / float(operating_income) * 100
            financials.append({
                "period": str(row.get("fiscal_year") or self._date_from_ms(period_ms)),
                "revenue": operating_income,
                "net_profit": row.get("parent_holder_net_profit"),
                "operating_cash_flow": cash.get("act_cash_flow_net"),
                "gross_margin": indicators.get("sale_gross_margin", computed_margin),
                "roe": indicators.get("index_weighted_avg_roe"),
            })

        now_ms = int(time.time() * 1000)
        start_ms = now_ms - 370 * 24 * 60 * 60 * 1000
        price_data = self._get(
            "/api/a-share/prices/historical",
            {"thscode": thscode, "interval": "1d", "start": start_ms, "end": now_ms, "adjust": "forward"},
        )
        valuation_data = self._get("/api/a-share/valuations/snapshot", {"thscodes": thscode})
        valuation_rows = valuation_data.get("item", [])
        valuation = valuation_rows[0] if valuation_rows else {}
        prices = [
            {"date": self._date_from_ms(row.get("date_ms")), "close": row.get("close_price")}
            for row in price_data.get("item", [])
            if row.get("close_price") is not None
        ]
        if not prices:
            raise DataProviderError("扶摇历史行情为空，无法计算行情特征。")

        latest_period_ms = income_rows[0].get("period_end_ms")
        as_of_ms = max(filter(None, [price_data.get("timestamp"), valuation_data.get("timestamp"), latest_period_ms]))
        payload = {
            "company": {
                "symbol": thscode.split(".")[0],
                "thscode": thscode,
                "name": valuation.get("name") or thscode,
                "industry": "待补充（扶摇股票基础信息接口尚未开放）",
                "as_of": self._date_from_ms(as_of_ms),
                "source": "同花顺扶摇金融数据 API",
                "data_mode": "live",
            },
            "financials": financials,
            "valuation": {
                "current_pe": valuation.get("pe_ttm"),
                "current_pb": valuation.get("pb_mrq"),
                # Fuyao documents only a current valuation snapshot. Keeping
                # this empty makes the historical percentile explicitly unknown.
                "historical_pe": [],
                "historical_pb": [],
            },
            "prices": prices,
            "peers": [],
            "events": [],
            "trace": {"request_ids": self.request_ids, "thscode": thscode},
        }
        return validate_payload(payload)
