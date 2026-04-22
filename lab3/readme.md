# LAB 3：建立 SFT 資料（LLM 兩階段生成）

## 學習目標
製作「可用來訓練 Function Calling 行為」的 SFT 資料集。

學完本 Lab 後，你將能夠：
- 理解 SFT 訓練資料的格式要求
- 用 **LLM 兩階段生成**自動產出多元的訓練資料
- 用 JSON Schema 驗證 LLM 輸出、失敗時重試
- 將 messages 格式轉成 SFTTrainer 用的 text 格式


---

## 檔案結構

```
lab3/
├── readme.md          # 本說明文件
├── generate_data.py   # 自動生成訓練資料（LLM 兩階段生成）
└── build_dataset.py   # 將 JSONL 轉成 SFT 訓練格式

輸出目錄：
lab3/out/
├── train.jsonl        # 訓練集（messages 格式）
├── valid.jsonl        # 驗證集（messages 格式）
├── train_text.jsonl   # 訓練集（text 格式，供 SFTTrainer 使用）
└── valid_text.jsonl   # 驗證集（text 格式）
```

---

## 環境準備

### 1. Python 套件
```bash
pip install requests jsonschema
```

### 2. 必須先啟動 vLLM 服務
本 Lab **依賴 lab2 的 vLLM 服務**（同一個 endpoint）：

```
http://127.0.0.1:8299/v1/chat/completions
模型：Qwen2.5-3B-Instruct
```

請先確認 vLLM 已啟動（與 lab2 相同方式）。可用以下指令快速確認：
```bash
python -c "import requests; print(requests.get('http://127.0.0.1:8299/v1/models', timeout=5).status_code)"
```
若回 `200` 即可繼續。若連線被拒，請先把 vLLM 服務跑起來。

---

## 核心概念

### 什麼是 SFT (Supervised Fine-Tuning)？

SFT 是監督式微調，用標註好的「輸入-輸出」對來訓練模型。

對於 Function Calling，我們要教模型：
- 什麼時候應該呼叫工具
- 應該選擇哪個工具
- 參數應該填什麼值

---

### 訓練資料格式

#### 1. Messages 格式（原始格式）
```json
{
  "messages": [
    {"role": "system", "content": "你是訂單客服助理..."},
    {"role": "user", "content": "幫我查訂單 A123456789 狀態"},
    {"role": "assistant", "content": "{\"type\": \"tool_call\", ...}"}
  ]
}
```

#### 2. Text 格式（供 SFTTrainer 使用）
```json
{
  "text": "<|system|>\n你是訂單客服助理...\n\n<|user|>\n幫我查訂單...\n\n<|assistant|>\n{...}"
}
```

---

### 資料生成策略：LLM 兩階段生成

不再用「寫死的模板 + slot 字典」，而是**讓 LLM 兩步驟生成 QA**，
換取更高的多樣性（同一個 tool 每次的問法、用字、語氣都不一樣）。

```
┌────────────────────────────────────────────────────────────────┐
│  Step 0：random.choice(TOOLS) ─ 隨機抽一個工具                  │
│                                                                │
│  Step 1：LLM 生 args（answer 端先做）                           │
│     prompt: 給定該 tool 的 JSON Schema                          │
│     output: 一組合理且符合 schema 的 args (JSON)                 │
│     檢查: jsonschema.validate；失敗最多重試 3 次                 │
│                                                                │
│  Step 2：LLM 生 user query（根據 tool_call 反推使用者問句）       │
│     prompt: 給定 tool_call (name + args)                       │
│     output: 一句自然口語、且包含所有 args 值的中文問句            │
│                                                                │
│  Step 3：組成 {system, user, assistant tool_call} 三輪訊息      │
└────────────────────────────────────────────────────────────────┘
```

為什麼是「**先 answer 再 query**」？
- args 端有明確的 schema 可驗證 → LLM 隨意亂生也不會壞掉
- query 端只要包住 args 值就行 → 可以放開 temperature 拚多樣性
- 一致性自動保證：query 一定提到 args 值，不會出現 query/args 對不上

---

## 實作步驟

### Step 0：確認 vLLM 服務在跑（見上方環境準備）

### Step 1：生成訓練資料

```bash
python -m lab3.generate_data --num 200
```

可調參數：
- `--num`：要生成的範例總數（預設 200）
- `--seed`：隨機種子（預設 7）

執行時會即時印每筆生成結果（成功 ✓ / 失敗 ✗），例如：
```
  [   1] get_order_status         ✓  幫我查一下訂單 A123456789 現在到哪了
  [   2] update_shipping_address  ✓  我要把訂單 K739102835 的地址改寄到 ...
  [   3] create_refund_request    ✗ (失敗，重抽)
  [   4] track_shipment           ✓  TWD12345678 包裹送到了嗎
```

> 速度提醒：每筆需 2 次 LLM 呼叫，N=200 大約需要 5–15 分鐘（視 vLLM 機器而定）。
> 若只想快速驗證流程，先試 `--num 20`。

完成後在 `lab3/out/` 產出：
- `train.jsonl`：訓練集（80%）
- `valid.jsonl`：驗證集（20%）

並印出每個 tool 的分布（10 個 tool 隨機抽選，總體大致均衡）。

### Step 2：轉換成 SFT 訓練格式
```bash
python -m lab3.build_dataset
```

產出：
- `train_text.jsonl`
- `valid_text.jsonl`

### Step 3：驗證轉換結果
```bash
head -1 lab3/out/train_text.jsonl
```

---

## 資料範例

每筆都是「user 自然語句 → assistant 輸出 tool_call JSON」的單輪對話：

```json
{
  "messages": [
    {"role": "system", "content": "你是訂單客服助理。可用工具：[...]"},
    {"role": "user", "content": "幫我查訂單 A123456789 進度，今天能到嗎"},
    {"role": "assistant", "content": "{\"type\": \"tool_call\", \"name\": \"get_order_status\", \"arguments\": {\"order_id\": \"A123456789\"}}"}
  ]
}
```

---

## 程式碼解析

### `generate_data.py`：核心兩階段

**(1) llm() 包裝**：本檔自有的 vLLM 呼叫，可調 temperature（預設 0.9 / top_p 0.95，比 lab2 的 call_llm 多樣化）：
```python
def llm(messages, temperature=0.9, top_p=0.95) -> str:
    payload = {"model": MODEL_NAME, "messages": messages, ...}
    return requests.post(VLLM_URL, json=payload).json()["choices"][0]["message"]["content"]
```

**(2) Step 1 — generate_args()**：給 schema 生 args，jsonschema 驗證，失敗重試：
```python
def generate_args(tool_def, max_retries=3):
    messages = _build_args_prompt(tool_def)
    for _ in range(max_retries):
        raw = llm(messages, temperature=0.9)
        obj = _extract_first_json(raw)
        ok, _ = _validate_args(obj, tool_def)
        if ok:
            return obj
    return None
```

**(3) Step 2 — generate_user_query()**：給 tool_call 反推自然問句：
```python
def generate_user_query(tool_call_obj):
    messages = _build_query_prompt(tool_call_obj)
    return llm(messages, temperature=1.0).strip()
```

**(4) 主迴圈**：失敗就重抽，直到累積到 N 筆：
```python
while len(data) < num_examples:
    tool_def = random.choice(TOOLS)
    ex = make_example(tool_def)
    if ex is None:
        continue
    data.append(ex)
```

### Prompt 設計重點

- **ARGS_GEN_SYSTEM**：強調必填、選填的隨機性、各種 pattern/enum 限制、值要寫實
- **QUERY_GEN_SYSTEM**：要求繁中口語、要包含 args 所有值、風格要多樣（禮貌 / 急躁 / 含糊…），且**只回那一句話**

如果發現生成品質不理想，**改 prompt 是第一手段**（比改程式有效）。

### `build_dataset.py`：格式轉換
```python
def convert(in_path, out_path):
    # messages 格式 → "<|role|>\ncontent" 格式 → {"text": "..."}
```

---

## 練習任務

### 任務 1：調 prompt 增加多樣性
- [ ] 在 `QUERY_GEN_SYSTEM` 加入更多風格描述（例如「有時用 emoji」「偶爾打錯字」）
- [ ] 比較修改前後生成的 user query 風格差異

### 任務 2：擴充資料量
- [ ] 用 `python -m lab3.generate_data --num 500` 生 500 筆，觀察分布與失敗率
- [ ] 估算每筆生成的平均成本（時間）

### 任務 3：強化 schema 驗證
- [ ] 把 `max_retries` 從 3 調到 5，觀察成功率變化
- [ ] 嘗試在 `_validate_args()` 後加自訂檢查（例如禁止 `details` 與 `reason` 內容相同）

### 任務 4：加 Few-Shot 範例
- [ ] 在 `ARGS_GEN_SYSTEM` 或 `QUERY_GEN_SYSTEM` 加入 1–2 個 few-shot 範例
- [ ] 觀察是否提升小模型的生成穩定度

---

## 設計要點

### 為什麼 args 端先做？
- args 有 schema 可硬性驗證，不合就 retry → 確保訓練資料 100% 合法
- query 端只要包住 args 值，**對錯不存在**，可以放心拉高 temperature

### 為什麼用 vLLM 而不是寫死模板？
- 模板法上限是「模板數量 × slot 組合」，本質有限
- LLM 在每筆呼叫都會用不同口吻、語序、用詞 → 接近真實用戶的長尾分布

### 為什麼 LLM 自己生 args 不會出格？
- prompt 中明確給出 JSON Schema（含 pattern、enum、required）
- 我們用 `jsonschema.validate` 驗，不通過直接重試
- 對 Qwen2.5-3B 等級的模型，三次內成功率通常 > 90%

### Train/Test 分離
本 Lab 的 args 都是 LLM 隨機生的，與 lab2 評測集裡的固定 ID 幾乎不會碰撞，
但實務上仍建議在訓練前以 ID 做去重。

---


## 下一步
完成本 Lab 後，前往 **Lab4** 使用這些資料進行 LoRA 微調。
