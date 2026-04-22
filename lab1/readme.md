# LAB 1：Function Calling 入門與工具 Schema 設計

## 📌 學習目標
把自然語言任務穩定轉成「工具呼叫（JSON args）」並能跑通一次端到端流程。

學完本 Lab 後，你將能夠：
- 理解 Function Calling 的運作原理
- 設計符合 JSON Schema 的工具定義
- 實作 LLM → 工具呼叫 → 執行 → 回覆 的完整流程

---

## 📂 檔案結構

```
lab1/
├── readme.md          # 本說明文件
└── run_chat.py        # 主程式：互動式聊天 + 工具呼叫

common/                # 共用模組（所有 Lab 共用）
├── tools.py           # Mock 工具實作（模擬後端服務）
├── tool_schema.py     # 工具的 JSON Schema 定義
├── prompts.py         # System prompt 和提示詞模板
├── llm_client.py      # vLLM API 客戶端
└── utils.py           # 共用工具函式
```

---

## 🔧 環境準備

### Step 1：啟動 vLLM 服務
```bash
docker-compose up -d
```
這會啟動一個 vLLM 服務，預設使用 `Qwen2.5-3B-Instruct` 模型。

### Step 2：安裝 Python 依賴
```bash
pip install requests jsonschema
```

### Step 3：確認服務正常
```bash
curl http://localhost:8299/v1/models
```
應該會看到模型清單。

---

## 📖 核心概念

### 什麼是 Function Calling？
Function Calling 是讓 LLM 能「選擇工具」並「填入參數」的機制：

```
使用者輸入 → LLM 判斷 → 輸出工具呼叫 JSON → 執行工具 → 將結果餵回 LLM → 生成回覆
```

### 工具定義 (Tool Schema)
每個工具需要定義：
1. **name**：工具名稱（唯一識別）
2. **description**：功能描述（LLM 靠此選工具）
3. **parameters**：參數的 JSON Schema（包含類型、必填、格式限制）

範例（查訂單狀態）：
```json
{
  "name": "get_order_status",
  "description": "查詢訂單狀態（出貨/配送/已取消等）。",
  "parameters": {
    "type": "object",
    "properties": {
      "order_id": {
        "type": "string",
        "description": "訂單編號，例如 A123456789",
        "pattern": "^[A-Z]\\d{9}$"
      }
    },
    "required": ["order_id"]
  }
}
```

### 工具呼叫輸出格式
當 LLM 決定呼叫工具時，輸出格式為：
```json
{
  "type": "tool_call",
  "name": "get_order_status",
  "arguments": {
    "order_id": "A123456789"
  }
}
```

---

## 🚀 實作步驟

### Step 1：了解可用工具
查看 `common/tool_schema.py`，本 Lab 提供 3 個工具：

| 工具名稱 | 用途 | 必填參數 |
|---------|------|---------|
| `get_order_status` | 查詢訂單狀態 | `order_id` (格式: A + 9位數字) |
| `track_shipment` | 查詢物流進度 | `tracking_no` (格式: TWD + 8位數字) |
| `create_refund_request` | 建立退款申請 | `order_id`, `reason` |

### Step 2：了解 Mock 工具
查看 `common/tools.py`，這些是模擬的後端服務：
- 內建測試訂單：`A123456789`（已出貨）、`A000000001`（處理中）、`A999999999`（已取消）
- 內建物流單號：`TWD12345678`

### Step 3：執行互動聊天
在專案根目錄執行：
```bash
python -m lab1.run_chat
```

### Step 4：測試以下對話
試著輸入這些句子，觀察 LLM 的行為：

**測試 1：正常工具呼叫**
```
User> 幫我查訂單 A123456789 狀態
```
預期：LLM 輸出 `get_order_status` 工具呼叫 → 執行 → 回覆訂單狀態

**測試 2：物流查詢**
```
User> 物流單號 TWD12345678 到哪了
```
預期：LLM 輸出 `track_shipment` 工具呼叫

**測試 3：缺少參數（觀察追問行為）**
```
User> 我要申請退款
```
預期：LLM 應該「追問」缺少的 order_id 和 reason

**測試 4：不需要工具**
```
User> 你好，請問營業時間是幾點？
```
預期：LLM 直接用自然語言回答，不呼叫工具

---

## 🔍 程式碼解析

### 主迴圈流程 (`run_chat.py`)

```
1. 初始化 LLM Client 和 messages（含 system prompt）
2. 迴圈：
   a. 讀取使用者輸入
   b. 呼叫 LLM 生成回應
   c. 嘗試從回應中提取 JSON
   d. 如果是工具呼叫：
      - 執行工具函式
      - 將結果餵回 LLM 生成最終回覆
   e. 如果不是工具呼叫：直接顯示回應
```

---

## ✅ 練習任務

### 任務 1：觀察工具描述的影響
修改 `common/tool_schema.py` 中某個工具的 description，觀察 LLM 選工具的行為是否改變。

### 任務 2：新增一個工具
在 `common/tool_schema.py` 和 `common/tools.py` 中新增一個工具，例如：
- `search_products(keyword, category)` - 搜尋商品
- `check_inventory(product_id)` - 查庫存

### 任務 3：測試邊界情況
- 輸入格式錯誤的訂單編號（如 `123456`）
- 查詢不存在的訂單
- 觀察 LLM 如何處理工具回傳的錯誤

---

## ❓ 常見問題

**Q: 為什麼 LLM 有時候不輸出 JSON？**
A: 可能是 prompt 不夠明確，或輸入不需要工具。可以加強 system prompt 的指示。

**Q: 如何支援更多工具？**
A: 在 `tool_schema.py` 新增 schema，在 `tools.py` 新增實作函式並註冊到 `TOOL_REGISTRY`。

---

## 📚 延伸閱讀
- [JSON Schema 規範](https://json-schema.org/)
- [OpenAI Function Calling 文件](https://platform.openai.com/docs/guides/function-calling)

---

## ⏭️ 下一步
完成本 Lab 後，前往 **Lab3** 學習評估系統設計。
