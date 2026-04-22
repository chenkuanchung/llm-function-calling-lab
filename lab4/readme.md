# LAB 4：SFT 微調一個可輸出 tool call 的模型（LoRA/QLoRA）

## 📌 學習目標
把模型微調到：工具選擇更穩、參數更準、追問更一致。

學完本 Lab 後，你將能夠：
- 理解 LoRA/QLoRA 微調的原理
- 使用 Transformers + PEFT 進行 SFT 訓練
- 調整訓練超參數
- 評估微調前後的效能差異

---

## 📂 檔案結構

```
lab4/
├── readme.md          # 本說明文件
├── train_lora.py      # LoRA 訓練腳本
└── infer_adapter.py   # 載入 Adapter 並推論

輸入目錄：
lab3/out/
├── train.json         # Lab3 生成的訓練資料（messages 格式，JSON array）
└── valid.json         # Lab3 生成的驗證資料（messages 格式，JSON array）

輸出目錄：
lab4/out_adapter/
├── adapter_model.safetensors  # LoRA 權重
├── adapter_config.json        # LoRA 設定
└── tokenizer files            # Tokenizer 檔案
```

---

## 🔧 環境準備

### 驗證安裝
```bash
python -c "import torch; print(torch.cuda.is_available())"
# 應該輸出 True
```

---

## 📖 核心概念

### (複習) 什麼是 LoRA？

**LoRA (Low-Rank Adaptation)** 是一種參數高效的微調方法。

傳統微調會更新模型的所有參數（數十億個），而 LoRA 只訓練一小組「低秩適配器」：

```
┌─────────────────────────────────────────────────────────────────┐
│  傳統 Fine-tuning                                                │
│  更新所有參數 → 需要大量 GPU 記憶體                               │
│                                                                 │
│  LoRA Fine-tuning                                               │
│  凍結原始權重 → 只訓練 Adapter（<1% 參數）                        │
│  記憶體需求大幅降低 ✓                                            │
└─────────────────────────────────────────────────────────────────┘
```

### LoRA 原理簡述

原始權重矩陣 W 被分解為：
```
W' = W + BA
```
其中：
- W：原始權重（凍結不更新）
- B, A：低秩矩陣（訓練目標）
- r：秩（rank），控制 Adapter 的大小

### 關鍵超參數

| 參數 | 說明 | 建議值 |
|-----|------|-------|
| `r` | LoRA 秩 | 8-64 |
| `lora_alpha` | 縮放係數 | 通常 2*r |
| `lora_dropout` | Dropout 機率 | 0.05-0.1 |
| `target_modules` | 要加 Adapter 的層 | q_proj, k_proj, v_proj, o_proj |
| `learning_rate` | 學習率 | 1e-4 ~ 5e-4 |
| `num_train_epochs` | 訓練 epoch 數 | 1-5 |

---

## 🚀 實作步驟

### Step 1：確認訓練資料

確保已完成 Lab3，並有以下檔案：
```bash
ls lab3/out/
# 應該看到 train.json, valid.json
```

如果沒有，請先完成 Lab3。

> 💡 本 Lab 會在訓練前自動用 tokenizer 的 `chat_template` 把 `messages`
> 轉成訓練用的 text 字串，不需要 Lab3 額外產出 text 格式檔案。


### Step 2：執行 LoRA 訓練

```bash
python -m lab4.train_lora
```

訓練過程會顯示 (示意)：
```
Step 1: loss = 2.5432
Step 2: loss = 1.8765
Step 3: loss = 1.2345
...
Saved adapter to out_adapter
```

### Step 3：測試微調後的模型

```bash
python -m lab4.infer_adapter
```

這會載入 Adapter 並執行一個測試 prompt。

### Step 4：與 Lab2 評估比較

用 Lab2 的評估系統比較微調前後的效能：

```python
# 修改 lab2/run_eval.py 使用微調後的模型
# 比較 tool_acc 和 args_exact 的變化
```

---

## 📊 訓練監控

### 觀察 Loss 曲線
- Loss 應該逐漸下降
- 如果 Loss 不下降：學習率可能太小
- 如果 Loss 震盪劇烈：學習率可能太大

### 驗證集 Loss
- 訓練時會在 validation set 上評估
- 如果 val_loss 上升而 train_loss 下降：過擬合！

### 預期結果
- 訓練後 valid_loss 應該低於訓練初期
- 在 Lab3 測試集上的 tool_acc 應該提升

---

## 🔍 程式碼解析

### train_lora.py - 訓練腳本

```python
# 1. 載入資料集（Lab3 產出的 JSON array）
ds = load_dataset("json", data_files={
    "train": "lab3/out/train.json",
    "validation": "lab3/out/valid.json",
})

# 2. 載入 Tokenizer 和模型
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, ...)

# 3. 用 chat_template 把 messages 轉成 text
def format_example(ex):
    return {"text": tokenizer.apply_chat_template(
        ex["messages"], tokenize=False, add_generation_prompt=False
    )}
ds = ds.map(format_example, remove_columns=["messages"])

# 4. 設定 LoRA 配置
lora = LoraConfig(
    r=16,                    # 秩
    lora_alpha=32,           # 縮放
    lora_dropout=0.05,       # Dropout
    target_modules=[...],    # 目標層
)

# 5. 設定訓練參數
args = TrainingArguments(
    output_dir=OUT_DIR,
    num_train_epochs=2,
    learning_rate=2e-4,
    ...
)

# 6. 開始訓練
trainer = SFTTrainer(model, ...)
trainer.train()

# 7. 儲存 Adapter
trainer.save_model(OUT_DIR)
```

### infer_adapter.py - 推論腳本

```python
# 1. 載入基礎模型
base = AutoModelForCausalLM.from_pretrained(BASE)

# 2. 載入 LoRA Adapter
model = PeftModel.from_pretrained(base, ADAPTER)

# 3. 推論
inputs = tokenizer(prompt, return_tensors="pt")
out = model.generate(**inputs, ...)
```

---

## ✅ 練習任務

### 任務 1：調整超參數
嘗試不同的設定，觀察效果，調整超參數後在訓練一次：

（可以不用全部按照以下表格調整）

| 實驗 | 設定 | 預期效果 |
|-----|------|---------|
| A | r=8 | 較小的 Adapter，訓練快 |
| B | r=64 | 較大的 Adapter，可能更準 |
| C | lr=5e-5 | 較小學習率，訓練更穩 |
| D | epochs=5 | 更多訓練，可能過擬合 |

### 任務 2：擴充訓練資料 （Bonus）
回到 Lab3 擴充資料：
- [ ] 增加到 1000+ 筆訓練資料
- [ ] 重新訓練並比較效果

### 任務 3：aidaptiv（進階）（Bonus）
使用aidaptiv訓練更大的模型

### 任務 4：完整評估 
用 Lab2 的評估系統：
1. 記錄微調前的 baseline 指標
2. 訓練後重新評估
3. 比較差異

---

## 🎯 設計要點

### 資料量 vs 模型能力
- 資料量太少：模型可能過擬合
- 資料量足夠：模型能泛化到新案例
- 建議至少 100-200 筆高品質資料

### 訓練時間考量
- 小資料集：幾分鐘到半小時
- 大資料集：數小時
- 可以先用小資料驗證流程

### 常見問題排查

| 問題 | 可能原因 | 解決方案 |
|-----|---------|---------|
| OOM (Out of Memory) | GPU 記憶體不足 | 降低 batch_size、用 QLoRA |
| Loss 不下降 | 學習率太小 | 提高 learning_rate |
| Loss 震盪 | 學習率太大 | 降低 learning_rate |
| 過擬合 | 資料太少 | 增加資料、加強正則化 |

---

## ❓ 常見問題

**Q: LoRA vs QLoRA 差別？**
A: 
- LoRA：只加 Adapter，基礎模型用 fp16/bf16
- QLoRA：基礎模型用 4-bit 量化，記憶體需求更低

**Q: 訓練多久才夠？**
A: 觀察 validation loss：
- Loss 持續下降 → 繼續訓練
- Loss 開始上升 → 該停了（過擬合）

**Q: 可以在 CPU 上訓練嗎？**
A: 技術上可以，但會非常慢（數十倍以上）。強烈建議使用 GPU。

---

## 📚 延伸閱讀
- [LoRA 論文](https://arxiv.org/abs/2106.09685)
- [QLoRA 論文](https://arxiv.org/abs/2305.14314)
- [PEFT 官方文件](https://huggingface.co/docs/peft)
- [TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)

---

## ⏭️ 下一步
完成本 Lab 後，前往 **Lab5** 學習如何部署成可用的服務。
