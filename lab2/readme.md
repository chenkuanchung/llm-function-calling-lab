# LAB 2：建立評估系統 - 測試集與指標設計

## 📌 學習目標
建立可量化的評估系統：工具選擇率、參數正確率、端到端成功率。

學完本 Lab 後，你將能夠：
- 設計 Function Calling 的測試案例
- 實作自動化評估指標
- 理解 Train/Test 分離的重要性
- 建立回歸測試的概念

---

## 📂 檔案結構

```
lab2/
├── readme.md          # 本說明文件
├── eval_cases.json    # 測試案例集（JSON 陣列格式）
└── eval.py            # 讀取測試案例、執行推論、計算指標、輸出報告

common/                # 共用模組
└── ...
```

---

## 🔧 環境準備

確保 vLLM 服務已啟動：
```bash
docker-compose up -d
```

---

## 📖 核心概念

### 為什麼需要評估系統？

在 Lab1 中，我們用「手動測試」驗證系統行為。但這有問題：
- 難以重複：每次改 prompt 都要手動測一遍
- 不客觀：人的判斷可能有偏差
- 無法量化：「感覺比較好」不是好的指標

**評估系統的價值**：
1. 自動化：每次改動都能快速驗證
2. 量化：用數字說話（準確率、成功率）
3. 回歸測試：確保改動沒有「破壞」原有功能

---

### 測試案例格式

`eval_cases.json`（標準 JSON 陣列，整個檔案是一個 list）：

```json
[
  {
    "id": "c1",
    "messages": [{"role": "user", "content": "幫我查訂單 A123456789 目前狀態"}],
    "expect": {"tool": "get_order_status", "arguments": {"order_id": "A123456789"}}
  },
  {
    "id": "c2",
    "messages": [{"role": "user", "content": "我要查物流 TWD12345678 到哪了"}],
    "expect": {"tool": "track_shipment", "arguments": {"tracking_no": "TWD12345678"}}
  },
  {
    "id": "c3",
    "messages": [{"role": "user", "content": "我要退款"}],
    "expect": {"should_ask_clarification": true}
  }
]
```

| 欄位 | 說明 |
|-----|------|
| `id` | 測試案例唯一識別碼 |
| `messages` | 輸入的對話歷史 |
| `expect.tool` | 預期應該呼叫的工具（null 表示不應呼叫） |
| `expect.arguments` | 預期的參數值 |
| `expect.should_ask_clarification` | 預期應該追問（可選） |

---

### 評估指標

本 Lab 實作三個核心指標：

| 指標 | 說明 |
|------|------|
| `valid_rate` | 格式合法率：LLM 是否輸出合法的 JSON |
| `tool_acc` | 工具選擇準確率：是否選對工具 |
| `args_exact` | 參數完全相符率：參數填充是否正確 |

---

## 🚀 執行評估

```bash
python -m lab2.eval
```

這會：
1. 載入 `eval_cases.json`
2. 對每個案例呼叫 LLM
3. 計算各項指標
4. 輸出結果到終端機，並儲存至 `lab2_evaluation/eval_report.json`

### 輸出範例

```
============================================================
LAB2: Function Calling 評估
============================================================
載入 5 個測試案例
開始評估...

============================================================
評估結果
============================================================
總案例數：5
格式合法率   (valid_rate)：80.0%
工具選擇準確率 (tool_acc)：60.0%
參數完全相符率 (args_exact)：50.0%
============================================================
詳細報告：lab2_evaluation/eval_report.json
```

---

## 📊 測試案例類型

好的測試集應該涵蓋多種情況：

### 1. 正常呼叫（Happy Path）
```json
{"messages":[{"role":"user","content":"幫我查訂單 A123456789"}],"expect":{"tool":"get_order_status","arguments":{"order_id":"A123456789"}}}
```

### 2. 不需要呼叫工具
```json
{"messages":[{"role":"user","content":"你好，今天天氣如何？"}],"expect":{"tool":null}}
```

### 3. 需要追問
```json
{"messages":[{"role":"user","content":"我要退款"}],"expect":{"should_ask_clarification":true}}
```

---

## ✅ 練習任務

`eval.py` 中有三處 `TODO`，請依序完成：

### TODO 1：`tool_selection_correct`
判斷工具選擇是否正確：
- 若 `expect` 有 `"tool"` → 比對 `pred_tool == expect["tool"]`
- 若 `expect` 沒有 `"tool"` → `pred_tool` 應為 `None`

```python
def tool_selection_correct(pred_tool, expect):
    if "tool" in expect:
        return ...          # 填入比對邏輯
    return ...              # 填入沒有 tool 時的判斷
```

### TODO 2：`args_exact_match`
判斷參數是否完全相符：
- 若 `expect` 有 `"arguments"` → 比對 `pred_args == expect["arguments"]`
- 若 `expect` 沒有 `"arguments"` → `pred_args` 應為 `None`

```python
def args_exact_match(pred_args, expect):
    if "arguments" not in expect:
        return ...          # 填入沒有預期參數時的判斷
    return ...              # 填入有預期參數時的比對
```

### TODO 3：`run_one` 中的 JSON 提取與錯誤處理
LLM 有可能輸出格式破損的 JSON，必須用 `try/except` 保護解析邏輯：

```python
try:
    tool_call = extract_json_block(out)
    if tool_call is None:
        return pred           # LLM 沒有輸出 JSON（追問或直接回答，屬正常情況）
    ok, err = validate_tool_call(tool_call)
    pred["tool"]      = tool_call.get("name")
    pred["arguments"] = tool_call.get("arguments")
    pred["valid"]     = ok
    pred["error"]     = err
except Exception as e:
    pred["error"] = f"json_parse_error:{e}"
```

思考看看：
- `extract_json_block` 回傳 `None` 和拋出例外，分別代表什麼情況？
- 為什麼要用 `except Exception` 而不是只抓 `json.JSONDecodeError`？

---

### 延伸練習(Bonus)：擴充測試集
將 `eval_cases.json` 擴充到 20-30 個案例，涵蓋：
- [ ] 各種工具的正常呼叫
- [ ] 不需要工具的情況（閒聊、概念問題）
- [ ] 需要追問的情況
- [ ] 參數格式邊界情況（例如訂單號格式錯誤）

---

## 🎯 設計要點

### Train/Test 分離

**重要原則**：測試集不能用於訓練！

```
              ┌─────────────────┐
              │   全部資料       │
              └────────┬────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
    ┌─────▼─────┐            ┌─────▼─────┐
    │ 訓練集     │            │ 測試集     │
    │ (Lab3用)  │            │ (Lab2用)  │
    └───────────┘            └───────────┘
```

如果測試集被用於調整模型/prompt，評估結果就會「過擬合」，不能反映真實能力。

### 指標解讀

| 指標低 | 可能原因 |
|-------|---------|
| `valid_rate` 低 | Prompt 不夠明確、模型輸出不穩定 |
| `tool_acc` 低 | 工具 description 不夠清楚 |
| `args_exact` 低 | 參數 description 不夠明確、缺少範例 |

---

## ❓ 常見問題

**Q: 測試案例要多少才夠？**
A: 取決於工具數量和複雜度。建議：
- 每個工具至少 5-10 個正面案例
- 整體至少 30-50 個案例
- 涵蓋各種邊界情況

**Q: 如何處理「追問」的評估？**
A: 目前簡化處理：只標記 `should_ask_clarification`。進階做法是檢查 LLM 回覆是否真的在追問。

---

## ⏭️ 下一步
完成本 Lab 後，前往 **Lab3** 學習如何建立 SFT 訓練資料。
