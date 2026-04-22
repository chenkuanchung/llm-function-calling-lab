"""
==============================================================================
LAB 4：LoRA 微調訓練腳本
==============================================================================

📌 本檔案功能：
    使用 LoRA (Low-Rank Adaptation) 微調語言模型，
    讓它更穩定地輸出 Function Calling 格式。

📖 LoRA 原理簡述：
    傳統微調會更新模型所有參數（數十億個），需要大量 GPU 記憶體。
    LoRA 只訓練一小組「低秩適配器」，參數量 < 1%，記憶體需求大幅降低。
    
    數學上：W' = W + BA
    - W：原始權重（凍結）
    - B, A：低秩矩陣（訓練目標）

🔧 執行方式：
    python -m lab4.train_lora

📋 環境需求：
    - GPU：至少 8GB VRAM
    - 套件：torch, transformers, datasets, peft, trl, accelerate

📂 輸入/輸出：
    輸入：lab3/out/train.json, valid.json  （messages 格式的 JSON array）
    輸出：out_adapter/
"""

import os
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig
from peft import LoraConfig
import torch


# ==============================================================================
# 設定（可透過環境變數覆蓋）
# ==============================================================================

# 基礎模型名稱
# 可以改成其他模型，例如：
# - "meta-llama/Llama-3.2-3B-Instruct"
MODEL_NAME = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")
"""
基礎模型選擇：
- Qwen2.5-3B-Instruct：中文能力好，3B 參數適中
- Llama 系列：英文能力強
- Mistral 系列：平衡的選擇
"""

# 訓練資料路徑（Lab3 的輸出，messages 格式的 JSON array）
TRAIN_PATH = os.getenv("TRAIN_JSON", "lab3/out/train.json")
VALID_PATH = os.getenv("VALID_JSON", "lab3/out/valid.json")

# 輸出目錄
OUT_DIR = os.getenv("OUT_DIR", "lab4/out_adapter")


def main():
    """
    主函式：執行 LoRA 訓練
    
    流程：
    ┌─────────────────────────────────────────────────────────────────┐
    │  1. 載入資料集（JSON → HuggingFace Dataset）                     │
    │  2. 載入 Tokenizer 和基礎模型                                    │
    │  3. 用 chat_template 把 messages 轉成訓練用的 text              │
    │  4. 設定 LoRA 配置（秩、目標層等）                               │
    │  5. 設定訓練參數（學習率、batch size 等）                        │
    │  6. 建立 SFTTrainer 並開始訓練                                   │
    │  7. 儲存 Adapter 權重                                           │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    print("=" * 60)
    print("LAB4: LoRA 微調訓練")
    print("=" * 60)
    print(f"基礎模型：{MODEL_NAME}")
    print(f"訓練資料：{TRAIN_PATH}")
    print(f"輸出目錄：{OUT_DIR}")
    print("=" * 60)
    
    # ==========================================================================
    # Step 1: 載入資料集
    # ==========================================================================
    # load_dataset("json", ...) 支援兩種 JSON 格式：
    #   - JSON Lines（每行一個物件）
    #   - JSON array（整份檔案是一個 [ {...}, {...} ] 陣列）← 本 Lab 用這種
    print("\n[Step 1] 載入資料集...")

    ds = load_dataset(
        "json",
        data_files={
            "train": TRAIN_PATH,
            "validation": VALID_PATH,
        },
    )

    print(f"  訓練集：{len(ds['train'])} 筆")
    print(f"  驗證集：{len(ds['validation'])} 筆")

    # ==========================================================================
    # Step 2: 載入 Tokenizer 和模型
    # ==========================================================================
    print("\n[Step 2] 載入 Tokenizer 和模型...")
    
    # 載入 Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    
    # 設定 padding token
    # 有些模型沒有 pad_token，需要手動設定
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        print("  注意：設定 pad_token = eos_token")

    # 載入基礎模型
    # torch_dtype=torch.bfloat16：使用 bf16 精度，減少記憶體使用
    # device_map="auto"：自動分配到可用的 GPU
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.bfloat16,  # 或 torch.float16
        device_map="auto",
    )
    
    print(f"  模型已載入到：{model.device}")

    # ==========================================================================
    # Step 3: 把 messages 轉成訓練用的 text
    # ==========================================================================
    # Lab3 輸出的是 messages 格式（list of {role, content}），
    # 這裡用模型自帶的 chat_template 把它拼成一整段 text 字串，
    # 之後交給 SFTTrainer 的 dataset_text_field="text" 使用。
    print("\n[Step 3] 套用 chat_template 轉成 text 欄位...")

    def format_example(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    ds = ds.map(format_example, remove_columns=["messages"])
    print(f"  範例 text 片段：{ds['train'][0]['text'][:80]}...")

    # ==========================================================================
    # Step 4: 設定 LoRA 配置
    # ==========================================================================
    # LoRA 的關鍵超參數說明：
    #
    # r (rank)：低秩矩陣的秩
    #   - 越大 → Adapter 越大 → 表達能力越強 → 記憶體越多
    #   - 建議範圍：8-64
    #
    # lora_alpha：縮放係數
    #   - 影響 Adapter 的更新幅度
    #   - 通常設為 2*r
    #
    # lora_dropout：Dropout 機率
    #   - 防止過擬合
    #   - 建議：0.05-0.1
    #
    # target_modules：要加 Adapter 的層
    #   - 通常選 attention 的 projection 層
    #   - q_proj, k_proj, v_proj, o_proj 是常見選擇
    
    print("\n[Step 4] 設定 LoRA 配置...")
    
    lora_config = LoraConfig(
        r=16,                   # 秩：16 是常用的起始值
        lora_alpha=32,          # 縮放係數：通常 2*r
        lora_dropout=0.05,      # Dropout
        bias="none",            # 不訓練 bias（減少參數）
        task_type="CAUSAL_LM",  # 任務類型：因果語言模型
        target_modules=[        # 目標層：Attention 的各個 projection
            "q_proj",           # Query projection
            "k_proj",           # Key projection
            "v_proj",           # Value projection
            "o_proj",           # Output projection
        ],
    )
    
    print(f"  LoRA rank: {lora_config.r}")
    print(f"  LoRA alpha: {lora_config.lora_alpha}")
    print(f"  Target modules: {lora_config.target_modules}")
    
    # ==========================================================================
    # Step 5: 設定訓練參數
    # ==========================================================================
    # TrainingArguments 包含所有訓練相關的設定
    #
    # 關鍵參數說明：
    # - num_train_epochs：訓練幾個 epoch
    # - per_device_train_batch_size：每個 GPU 的 batch size
    # - gradient_accumulation_steps：梯度累積（等效放大 batch size）
    # - learning_rate：學習率（LoRA 通常用較大的學習率）
    # - warmup_ratio：學習率預熱比例
    # - bf16：使用 bf16 精度
    
    print("\n[Step 5] 設定訓練參數...")
    
    training_args = SFTConfig(
        output_dir=OUT_DIR,
        
        # 訓練設定
        num_train_epochs=3,                 # 訓練 2 個 epoch
        per_device_train_batch_size=1,      # 每 GPU batch size（根據記憶體調整）
        per_device_eval_batch_size=1,       # 評估 batch size
        gradient_accumulation_steps=16,      # 梯度累積 16 步 
        max_length=6144,
        
        # 學習率設定
        learning_rate=2e-4,                 # LoRA 常用較大學習率
        warmup_ratio=0.03,                  # 3% 的步數用於預熱
        max_grad_norm=1.0,                  # 梯度裁剪
        
        # 日誌和儲存
        logging_steps=1,                   # 每 1 步記錄一次
        # eval_strategy="epoch",        # 按步數評估
        save_strategy="epoch",
        
        # 精度和優化
        bf16=True,                          # 使用 bf16（需要支援的 GPU）
        optim="adamw_torch",                # 優化器
        
        # 其他
        report_to="none",                   # 不回報到 wandb 等平台
    )
    
    print(f"  Epochs: {training_args.num_train_epochs}")
    print(f"  Batch size: {training_args.per_device_train_batch_size}")
    print(f"  Learning rate: {training_args.learning_rate}")
    
    # ==========================================================================
    # Step 6: 建立 SFTTrainer 並開始訓練
    # ==========================================================================
    # SFTTrainer 是 TRL 提供的監督式微調訓練器
    # 它會自動處理：
    # - 資料 tokenization
    # - LoRA 的初始化和訓練
    # - 訓練迴圈
    
    print("\n[Step 6] 建立 Trainer 並開始訓練...")
    
    trainer = SFTTrainer(
        model=model,
        train_dataset=ds["train"],
        # eval_dataset=ds["validation"],
        peft_config=lora_config,            # LoRA 配置
        args=training_args,
    )
    
    # 開始訓練！
    print("\n開始訓練...")
    print("-" * 40)
    
    trainer.train()
    
    print("-" * 40)
    print("訓練完成！")
    
    # ==========================================================================
    # Step 7: 儲存 Adapter 權重
    # ==========================================================================
    print("\n[Step 7] 儲存 Adapter...")
    
    # 儲存 LoRA Adapter
    trainer.save_model(OUT_DIR)
    
    # 儲存 Tokenizer（推論時需要）
    tokenizer.save_pretrained(OUT_DIR)
    
    print(f"  Adapter 已儲存到：{OUT_DIR}")
    
    # 顯示儲存的檔案
    import os
    files = os.listdir(OUT_DIR)
    print(f"  檔案清單：")
    for f in files:
        print(f"    - {f}")
    
    print("\n" + "=" * 60)
    print("訓練完成！")
    print("下一步：使用 python -m lab4.infer_adapter 測試模型")
    print("=" * 60)


# ==============================================================================
# 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()
