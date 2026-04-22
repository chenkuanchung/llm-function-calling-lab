# LAB 5：部署成可用的 Agent（含防呆、觀測、回歸）

## 📌 學習目標
做出「可上線思維」：驗證、重試、權限、安全、日誌、回歸測試。

學完本 Lab 後，你將能夠：
- 將 Function Calling Agent 封裝成 HTTP API
- 實作防呆機制（驗證、重試、錯誤處理）
- 設計觀測和日誌系統
- 建立自動化回歸測試

---

## 📂 檔案結構

```
lab5/
├── readme.md          # 本說明文件
├── app.py             # FastAPI 服務（HTTP API）
└── regression.py      # 回歸測試腳本

輸出目錄：
lab5_deploy_regression/
└── regression_trace.json  # 回歸測試結果
```

---

## 🔧 環境準備

### 安裝依賴
```bash
pip install fastapi uvicorn requests
```

### 確保 vLLM 服務運行
```bash
docker-compose up -d
```

---

## 📖 核心概念

### 從 Lab 到產品的差距

```
┌─────────────────────────────────────────────────────────────────┐
│  Lab 環境                          Production 環境              │
│  ────────                          ────────────                 │
│  - 單人測試                        - 多用戶併發                  │
│  - 手動重試                        - 自動重試機制                │
│  - 看終端輸出                      - 結構化日誌                  │
│  - 偶爾錯誤沒關係                  - 需要穩定可靠                │
│  - 沒有安全考量                    - 防止濫用/注入               │
└─────────────────────────────────────────────────────────────────┘
```

---

### 防呆機制設計

#### 1. Schema 驗證 + 自動重試
```
LLM 輸出 → 驗證 Schema → 失敗 → 重試（最多 N 次）→ 仍失敗 → 降級處理
```

#### 2. 工具白名單
```python
ALLOWED_TOOLS = {"get_order_status", "track_shipment", "create_refund_request"}

if tool_name not in ALLOWED_TOOLS:
    raise SecurityError("不允許的工具呼叫")
```

#### 3. 參數過濾
```python
# 防止 SQL Injection、Prompt Injection 等
def sanitize_order_id(order_id: str) -> str:
    if not re.match(r"^[A-Z]\d{9}$", order_id):
        raise ValueError("Invalid order_id format")
    return order_id
```

#### 4. Timeout 和錯誤處理
```python
try:
    result = tool_fn(**args, timeout=10)
except TimeoutError:
    return "工具執行超時，請稍後重試"
except Exception as e:
    log_error(e)
    return "系統暫時無法處理，請聯繫客服"
```

---

### 觀測與日誌

每次請求應該記錄：
| 欄位 | 說明 |
|-----|------|
| `request_id` | 唯一識別碼 |
| `timestamp` | 時間戳 |
| `user_input` | 使用者輸入 |
| `model_output` | LLM 原始輸出 |
| `tool_name` | 呼叫的工具 |
| `tool_args` | 工具參數 |
| `tool_result` | 工具執行結果 |
| `validation_error` | 驗證錯誤（如有） |
| `latency_ms` | 回應延遲 |

---

### 回歸測試

每次改動 prompt/模型/配置後，自動執行測試集並比較結果：

```
改動前基線               改動後結果              差異報告
───────────             ───────────             ─────────
tool_acc: 0.85    →     tool_acc: 0.82     →   ⚠️ 下降 3%
args_exact: 0.70  →     args_exact: 0.75   →   ✅ 上升 5%
```

---

## 🚀 實作步驟

### Step 1：啟動 FastAPI 服務

```bash
# 方式 1：使用 uvicorn
uvicorn lab5.app:app --host 0.0.0.0 --port 9000

# 方式 2：直接執行（如果有 __main__ 區塊）
python -m lab5.app
```

### Step 2：測試 API

使用 curl 測試：
```bash
curl -X POST http://localhost:9000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "幫我查訂單 A123456789 狀態"}]}'
```

或使用 Python：
```python
import requests

resp = requests.post(
    "http://localhost:9000/chat",
    json={"messages": [{"role": "user", "content": "幫我查訂單 A123456789 狀態"}]}
)
print(resp.json())
```

### Step 3：查看 API 文件

FastAPI 自動生成 API 文件：
- Swagger UI：http://localhost:9000/docs
- ReDoc：http://localhost:9000/redoc

### Step 4：執行回歸測試

確保服務運行中，然後執行：
```bash
python -m lab5.regression
```

這會：
1. 讀取 Lab2 的測試案例
2. 對每個案例呼叫 API
3. 記錄結果到 `lab5_deploy_regression/regression_trace.json`

### Step 5：比較回歸結果

手動檢查或寫腳本比較：
```python
import json

# 載入本次結果
with open("lab5_deploy_regression/regression_trace.json") as f:
    current = json.load(f)

# 載入上次結果（如果有）
# with open("baseline.json") as f:
#     baseline = json.load(f)

# 比較...
```

---

## 🔍 程式碼解析

### app.py - FastAPI 服務

```python
# 定義 Request/Response 格式
class ChatReq(BaseModel):
    messages: List[Dict[str, Any]]

class ChatResp(BaseModel):
    messages: List[Dict[str, Any]]
    trace: Dict[str, Any]       # 觀測資訊

# API 端點
@app.post("/chat")
def chat(req: ChatReq):
    # 1. 組合 system prompt + 使用者訊息
    # 2. 呼叫 LLM
    # 3. 驗證 tool_call（如果有）
    # 4. 失敗則重試
    # 5. 執行工具
    # 6. 餵回結果，生成最終回覆
    # 7. 回傳結果 + trace
```

### regression.py - 回歸測試

```python
def main():
    # 1. 載入 Lab3 測試案例
    # 2. 對每個案例呼叫 /chat API
    # 3. 記錄 trace
    # 4. 輸出到 JSON
```

---

## ✅ 練習任務

### 任務 1：加入 Rate Limiting
防止單一用戶過度呼叫：
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("10/minute")  # 每分鐘最多 10 次
def chat(req: ChatReq):
    ...
```

### 任務 2：加入結構化日誌
使用 `logging` 或 `structlog`：
```python
import structlog
logger = structlog.get_logger()

logger.info(
    "chat_request",
    request_id=uuid4(),
    user_input=user_message,
    tool_name=tool_call.get("name"),
    latency_ms=elapsed_ms
)
```

### 任務 3：實作健康檢查端點
```python
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "llm_status": check_llm_connection(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

### 任務 4：Dockerize 部署
建立 Dockerfile：
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "lab5.app:app", "--host", "0.0.0.0", "--port", "9000"]
```

### 任務 5：完善回歸測試
- 計算各項指標（tool_acc, args_exact）
- 與 baseline 比較並產生 diff 報告
- 設定 CI/CD 在指標下降時失敗

---

## 🎯 設計要點

### 可靠性工程

| 策略 | 說明 |
|-----|------|
| 重試 | Schema 驗證失敗時重試（最多 N 次） |
| 超時 | 設定工具執行的超時時間 |
| 降級 | 工具不可用時，回覆友善訊息 |
| 熔斷 | 連續失敗超過閾值時，暫停呼叫 |

### 安全考量

| 風險 | 防護 |
|-----|------|
| Prompt Injection | 過濾/驗證使用者輸入 |
| 越權呼叫 | 工具白名單 |
| 資源耗盡 | Rate Limiting |
| 資料洩漏 | 日誌脫敏 |

### 觀測金三角

1. **Logs**：結構化日誌，記錄每次請求
2. **Metrics**：指標監控（延遲、錯誤率、呼叫量）
3. **Traces**：分散式追蹤（如果有多服務）

---

## ❓ 常見問題

**Q: 為什麼需要 trace？**
A: Trace 記錄了處理過程的每個步驟，方便：
- 除錯問題
- 分析效能瓶頸
- 驗證行為是否正確

**Q: 如何處理高併發？**
A: 
- 使用 async/await
- 加入請求佇列
- 水平擴展（多實例）

**Q: 回歸測試要多頻繁？**
A: 
- 每次改動後：快速回歸（核心案例）
- 每日/每週：完整回歸（全部案例）

---

## 📚 延伸閱讀
- [FastAPI 官方文件](https://fastapi.tiangolo.com/)
- [12-Factor App](https://12factor.net/)
- [可靠性工程實踐](https://sre.google/sre-book/table-of-contents/)

---

## 🎉 恭喜完成課程！

您已經完成了 Function Calling 的完整學習路徑：

| Lab | 內容 |
|-----|------|
| Lab1 | Function Calling 基礎 |
| Lab2 | 評估系統設計 |
| Lab3 | SFT 資料集建立 |
| Lab4 | LoRA 微調訓練 |
| Lab5 | 部署與回歸測試 |

**下一步建議**：
1. 將學到的知識應用到實際專案
2. 嘗試不同的模型和工具組合
3. 持續優化並建立更完善的測試集
