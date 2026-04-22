"""
==============================================================================
LAB 4：載入 LoRA Adapter 並推論
==============================================================================

📌 本檔案功能：
    載入訓練好的 LoRA Adapter，測試微調後的模型效果。

📖 推論流程：
    1. 載入基礎模型
    2. 載入 LoRA Adapter（疊加在基礎模型上）
    3. 輸入 prompt，生成輸出
    4. 比較微調前後的差異

🔧 執行方式：
    python -m lab4.infer_adapter

📋 注意事項：
    - 需要先完成 train_lora.py 的訓練
    - Adapter 路徑預設為 out_adapter
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


# ==============================================================================
# 設定（可透過環境變數覆蓋）
# ==============================================================================

# 基礎模型名稱（必須與訓練時相同）
BASE_MODEL = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")

# LoRA Adapter 路徑（train_lora.py 的輸出）
ADAPTER_DIR = os.getenv("ADAPTER_DIR", "out_adapter")


def generate(prompt: str, use_adapter: bool = True) -> str:
    """
    使用模型生成回應
    
    Args:
        prompt: 輸入的提示詞
        use_adapter: 是否載入 LoRA Adapter
                     True = 使用微調後的模型
                     False = 使用原始模型（用於比較）
    
    Returns:
        模型生成的文字
    
    Example:
        >>> prompt = "<|system|>\n你是客服助理\n<|user|>\n查訂單 A123\n<|assistant|>\n"
        >>> output = generate(prompt, use_adapter=True)
        >>> print(output)
    """
    
    # ==========================================================================
    # Step 1: 載入 Tokenizer
    # ==========================================================================
    print("載入 Tokenizer...")
    
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    
    # 設定 padding token
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    
    # ==========================================================================
    # Step 2: 載入基礎模型
    # ==========================================================================
    print("載入基礎模型...")
    
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    
    # ==========================================================================
    # Step 3: 載入 LoRA Adapter（如果需要）
    # ==========================================================================
    if use_adapter:
        print(f"載入 LoRA Adapter: {ADAPTER_DIR}")
        
        # PeftModel.from_pretrained() 會將 Adapter 疊加到基礎模型上
        # 數學上：W' = W + BA（原始權重 + Adapter）
        model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    else:
        print("使用原始模型（不載入 Adapter）")
        model = base
    
    # 設定為評估模式
    model.eval()
    
    # ==========================================================================
    # Step 4: 生成回應
    # ==========================================================================
    print("生成回應...")
    
    # Tokenize 輸入
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    
    # 生成
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=200,     # 最多生成 200 個 token
            do_sample=False,        # 不使用取樣（確定性輸出）
            # 如果要加入隨機性，可以改成：
            # do_sample=True,
            # temperature=0.7,
            # top_p=0.9,
        )
    
    # 解碼輸出
    return tok.decode(out[0], skip_special_tokens=True)


def main():
    """
    主函式：測試微調後的模型
    
    會執行以下測試：
    1. 使用微調後的模型生成回應
    2. （可選）比較與原始模型的差異
    """
    
    print("=" * 60)
    print("LAB4: 測試微調後的模型")
    print("=" * 60)
    
    # ==========================================================================
    # 檢查 Adapter 是否存在
    # ==========================================================================
    if not os.path.exists(ADAPTER_DIR):
        print(f"\n錯誤：找不到 Adapter 目錄 {ADAPTER_DIR}")
        print("請先執行 python -m lab4.train_lora 進行訓練")
        return
    
    # ==========================================================================
    # 測試 Prompt
    # ==========================================================================
    # 使用與訓練資料相同的格式
    test_prompt = """<|system|>
你是訂單客服助理。
<|user|>
幫我查訂單 A123456789 狀態
<|assistant|>
"""
    
    print("\n測試 Prompt：")
    print("-" * 40)
    print(test_prompt)
    print("-" * 40)
    
    # ==========================================================================
    # 使用微調後的模型
    # ==========================================================================
    print("\n[使用微調後的模型]")
    
    output_with_adapter = generate(test_prompt, use_adapter=True)
    
    print("\n生成結果：")
    print("-" * 40)
    # 只顯示 assistant 的回應部分
    if "<|assistant|>" in output_with_adapter:
        response = output_with_adapter.split("<|assistant|>")[-1].strip()
    else:
        response = output_with_adapter
    print(response)
    print("-" * 40)
    
    # ==========================================================================
    # （可選）比較原始模型
    # ==========================================================================
    # 如果要比較，取消下面的註解
    # 
    # print("\n[使用原始模型（比較用）]")
    # output_without_adapter = generate(test_prompt, use_adapter=False)
    # print("\n生成結果：")
    # print("-" * 40)
    # if "<|assistant|>" in output_without_adapter:
    #     response = output_without_adapter.split("<|assistant|>")[-1].strip()
    # else:
    #     response = output_without_adapter
    # print(response)
    # print("-" * 40)
    
    # ==========================================================================
    # 更多測試案例
    # ==========================================================================
    print("\n" + "=" * 60)
    print("更多測試案例")
    print("=" * 60)
    
    test_cases = [
        "我要申請退款",                          # 預期：追問
        "物流單號 TWD12345678 到哪了",           # 預期：tool_call
        "訂單 A000000001 退款，原因是商品瑕疵",  # 預期：tool_call
    ]
    
    for i, user_input in enumerate(test_cases, 1):
        prompt = f"""<|system|>
你是訂單客服助理。
<|user|>
{user_input}
<|assistant|>
"""
        print(f"\n測試案例 {i}：{user_input}")
        print("-" * 40)
        
        output = generate(prompt, use_adapter=True)
        
        if "<|assistant|>" in output:
            response = output.split("<|assistant|>")[-1].strip()
        else:
            response = output
        
        print(response)
    
    print("\n" + "=" * 60)
    print("測試完成！")
    print("下一步：用 Lab2 的評估系統進行量化評估")
    print("=" * 60)


# ==============================================================================
# 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()
