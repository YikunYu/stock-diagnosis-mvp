# 证据镜：A 股多维诊断

一个证据优先的 AI Native 个股研究 MVP。它把确定性指标计算与 LLM 解释分开，并将结果组织为正面、负面、矛盾和未知证据。产品不输出确定性涨跌预测、收益承诺或直接买卖建议。

> 仓库内置的是**合成演示数据**，不是美的集团的真实财务或行情数据。它只用于验证产品主链路。提交或演示真实研究结论前，必须通过上传 JSON 或 HTTP 数据桥接入可追溯的真实数据。

## 产品主链路

```text
用户问题
  → 标准化金融数据
  → Python 确定性计算
  → 结构化证据
  → LLM 基于证据解释
  → 正面 / 负面 / 矛盾 / 未知
  → 点击回溯来源、期间、公式和原始字段
```

## 快速启动

需要 Python 3.9 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

打开终端显示的本地地址。第一次运行选择“内置演示数据”。

## 数据来源模式

### 1. 内置演示数据

开箱即用，用于验证页面、计算、证据追溯和异常处理。页面会持续显示演示数据警告。

### 2. 扶摇实时 REST

项目已原生接入扶摇公开 REST 契约。配置：

```text
FUYAO_API_KEY=your-secret
FUYAO_BASE_URL=https://fuyao.aicubes.cn
```

应用会调用历史日 K、最近两期年报利润表、现金流量表、财务指标和最新估值快照。扶摇当前只提供最新估值快照，不提供历史估值序列，因此真实模式下“PE 历史分位”会明确显示为无法验证，而不会用演示值填充。

### 3. 上传标准 JSON

页面侧边栏可上传真实数据 JSON。数据需要符合下述契约。

### 4. HTTP 数据桥

配置：

```text
FINANCE_API_URL=https://your-bridge.example.com/stock-diagnosis
FINANCE_API_KEY=your-secret
```

应用向该地址发送：

```json
{"symbol": "000333"}
```

数据桥可以封装扶摇金融 API、iFinD MCP 或企业内部服务。使用数据桥的原因是不同账号和工具的鉴权、字段名及调用协议可能不同；外部差异只应存在于适配层，不能渗透到指标与诊断层。

## 标准数据契约

最小示例：

```json
{
  "company": {
    "symbol": "000333",
    "name": "公司名称",
    "industry": "行业",
    "as_of": "2026-09-30",
    "source": "数据源名称",
    "data_mode": "live"
  },
  "financials": [
    {
      "period": "2025Q3",
      "revenue": 100,
      "net_profit": 10,
      "operating_cash_flow": 12,
      "gross_margin": 25,
      "roe": 18
    },
    {
      "period": "2026Q3",
      "revenue": 110,
      "net_profit": 11,
      "operating_cash_flow": 9,
      "gross_margin": 26,
      "roe": 19
    }
  ],
  "valuation": {
    "current_pe": 15,
    "current_pb": 3,
    "historical_pe": [12, 14, 16],
    "historical_pb": [2, 3, 4]
  },
  "prices": [
    {"date": "2026-09-29", "close": 50},
    {"date": "2026-09-30", "close": 51}
  ],
  "peers": [
    {"symbol": "000001", "name": "同行公司", "revenue_growth": 5, "profit_growth": 8, "roe": 15, "pe": 12}
  ],
  "events": []
}
```

货币字段必须使用相同单位；同比期间必须可比；百分比字段统一使用 `25.3` 表示 `25.3%`，不要使用 `0.253`。

## LLM 配置

应用支持 OpenAI-compatible Chat Completions 接口：

```text
LLM_API_KEY=your-secret
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your-json-capable-model
```

没有密钥或调用失败时，应用自动降级为确定性证据归纳，并在页面明确标记。真实密钥不得提交到仓库。

LLM 只负责：

- 理解诊断问题；
- 组织证据；
- 解释支持、反对、矛盾和未知信息；
- 提出后续研究问题。

Python 负责：

- 同比、比率、估值分位、波动率和回撤计算；
- 数据缺失和零分母处理；
- 证据 ID 与来源生成；
- 校验 LLM 是否引用了不存在的证据。

## 测试

```bash
pytest -q
```

当前自动化测试覆盖正常链路、字段缺失、零分母、证据引用和关键计算。人工测试清单见 [docs/TESTING.md](docs/TESTING.md)。

## 部署到 Streamlit Community Cloud

1. 将仓库推送到 GitHub。
2. 在 Streamlit Community Cloud 创建应用，入口文件选择 `app.py`。
3. 在应用 Secrets 中配置环境变量；不要上传 `.env`。
4. 部署后分别测试演示模式、真实数据模式、接口失败和 LLM 失败。

## 已知边界

- 当前仓库不假设扶摇或 iFinD 的私有鉴权与字段协议，需在数据桥中做一次真实字段映射。
- 内置样本是合成数据，不能作为公司研究结论。
- 基期为零或负数时，常规同比百分比容易误导，当前实现将其标记为无法按常规口径计算。
- 同行表目前只展示输入结果，尚未自动生成同行排名证据。
- 事件数据已纳入数据契约，但尚未参与核心诊断。
- 历史估值分位依赖输入样本的时间跨度和频率，正式使用时必须在页面披露口径。
- 产品用于研究辅助，不替代持牌机构意见。

## 项目文件

```text
app.py                  Streamlit 页面
src/providers.py        数据源适配和契约校验
src/metrics.py          确定性计算
src/evidence.py         证据生成和冲突识别
src/diagnosis.py        LLM 调用、引用验证与降级
data/demo_000333.json   明确标注的合成演示数据
tests/                  自动化测试
docs/AI_USAGE.md        AI 使用与人工验证记录
docs/TESTING.md         测试说明
```
