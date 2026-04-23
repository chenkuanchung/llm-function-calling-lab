"""
==============================================================================
LAB 4：評估微調後的 LoRA 模型效能
==============================================================================
"""
import json
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# 引入 Lab 1 & 2 寫好的共用工具與評估邏輯
from common.prompts import system_prompt
from common.utils import extract_json_block
from lab2.eval import validate_tool_call, tool_selection_correct, args_exact_match

# 路徑設定 (對齊你目前的環境)
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_DIR = "lab4/out_adapter"
CASES_PATH = "lab2/eval_cases.json"

def main():
    print("=" * 60)
    print("LAB 4: 微調後模型自動化評估 (LoRA)")
    print("=" * 60)
    
    # ==========================================================
    # 1. 載入 Tokenizer 與掛載 LoRA 的模型 (全域只載入一次)
    # ==========================================================
    print("載入 Tokenizer 與基礎模型...")
    tok = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
        
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.bfloat16, device_map="auto"
    )
    
    print(f"掛載 LoRA Adapter: {ADAPTER_DIR}...")
    model = PeftModel.from_pretrained(base, ADAPTER_DIR)
    model.eval() # 設定為推論模式

    # ==========================================================
    # 2. 讀取 Lab 2 的 32 筆測試案例
    # ==========================================================
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)
    print(f"\n載入 {len(cases)} 個測試案例，開始評估...\n")

    rows = []
    for c in cases:
        # 組合 System Prompt 與 User 輸入
        messages = [{"role": "system", "content": system_prompt()}] + c["messages"]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(text, return_tensors="pt").to(model.device)
        
        # 執行推論
        with torch.no_grad():
            out_tokens = model.generate(
                                            **inputs, 
                                            max_new_tokens=200, 
                                            do_sample=True,     # 允許取樣
                                            temperature=0.6,    # 對齊 Lab 2
                                            top_p=0.2           # 對齊 Lab 2
                                        )
        
        # 截斷前面的 prompt，只取模型新生成的文字
        out_text = tok.decode(out_tokens[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        # ==========================================================
        # 3. 沿用 Lab 2 的驗證邏輯打分數
        # ==========================================================
        pred = {"raw": out_text, "tool": None, "arguments": None, "valid": False, "error": None}
        expect = c["expect"]
        
        try:
            tool_call = extract_json_block(out_text)
            if tool_call is not None:
                ok, err = validate_tool_call(tool_call)
                pred["tool"] = tool_call.get("name")
                pred["arguments"] = tool_call.get("arguments")
                pred["valid"] = ok
                pred["error"] = err
        except Exception as e:
            pred["error"] = f"json_parse_error:{e}"
            
        row = {
            "id": c["id"],
            "valid": pred["valid"],
            "pred_tool": pred["tool"],
            "pred_args": pred["arguments"],
            "expect": expect,
            "tool_ok": tool_selection_correct(pred["tool"], expect),
            "args_ok": args_exact_match(pred["arguments"], expect) if "arguments" in expect else None
        }
        rows.append(row)
        
        # 顯示單筆進度
        status = "✅" if (row["tool_ok"] and row["args_ok"] is not False) else "❌"
        print(f"  [{c['id']:>3s}] {status} (預測 Tool: {row['pred_tool']})")

    # ==========================================================
    # 4. 計算總指標並輸出
    # ==========================================================
    n = len(rows)
    valid_rate = sum(1 for r in rows if r["valid"]) / n
    tool_acc = sum(1 for r in rows if r["tool_ok"]) / n
    args_cases = [r for r in rows if r["args_ok"] is not None]
    args_exact = sum(1 for r in args_cases if r["args_ok"]) / len(args_cases) if args_cases else 0.0

    print("\n" + "=" * 60)
    print("🎯 微調後模型評估結果 (請與 Lab 2 進行比較)")
    print("=" * 60)
    print(f"總案例數：{n}")
    print(f"格式合法率     (valid_rate)：{valid_rate:.1%} ")
    print(f"工具選擇準確率   (tool_acc)：{tool_acc:.1%} ")
    print(f"參數完全相符率 (args_exact)：{args_exact:.1%} ")
    print("=" * 60)

if __name__ == "__main__":
    main()