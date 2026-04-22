"""
==============================================================================
LAB 3：將 JSONL 轉換成 SFT 訓練格式
==============================================================================

📌 本檔案功能：
    將 messages 格式的 JSONL 轉換成 SFTTrainer 可用的 text 格式。

📖 格式轉換說明：

    輸入（messages 格式）：
    {
      "messages": [
        {"role": "system", "content": "你是客服助理"},
        {"role": "user", "content": "幫我查訂單"},
        {"role": "assistant", "content": "..."}
      ]
    }
    
    輸出（text 格式）：
    {
      "text": "<|system|>\n你是客服助理\n\n<|user|>\n幫我查訂單\n\n<|assistant|>\n..."
    }

📖 ChatML 格式說明：
    本檔案使用簡化的 ChatML 格式：
    - <|role|> 標記角色
    - 每個訊息後面加換行
    - 訊息之間用空行分隔

    實務上，不同模型可能需要不同格式：
    - Llama: [INST] ... [/INST]
    - Qwen: <|im_start|>role\ncontent<|im_end|>
    - ChatGPT: 直接用 messages

🔧 執行方式：
    python -m lab3.build_dataset
"""

import json
from pathlib import Path


def convert_messages_to_text(messages: list) -> str:
    """
    將 messages 列表轉換成單一文字字串
    
    這個函式是格式轉換的核心，將結構化的對話轉成純文字。
    
    Args:
        messages: 對話訊息列表
            [{"role": "system", "content": "..."},
             {"role": "user", "content": "..."},
             {"role": "assistant", "content": "..."}]
    
    Returns:
        格式化的文字字串
    
    Example:
        >>> messages = [
        ...     {"role": "system", "content": "你是客服助理"},
        ...     {"role": "user", "content": "幫我查訂單"},
        ...     {"role": "assistant", "content": "好的"}
        ... ]
        >>> text = convert_messages_to_text(messages)
        >>> print(text)
        <|system|>
        你是客服助理
        
        <|user|>
        幫我查訂單
        
        <|assistant|>
        好的
    
    注意事項：
        - 格式需要與模型的訓練格式一致
        - 不同模型可能需要不同的特殊 token
        - SFTTrainer 會根據 tokenizer 的 chat_template 處理
    """
    parts = []
    
    for m in messages:
        # 格式：<|role|>\ncontent\n
        role = m["role"]
        content = m["content"]
        parts.append(f"<|{role}|>\n{content}\n")
    
    # 用空行連接所有部分，並去除尾端多餘空白
    return "\n".join(parts).strip()


def convert_file(in_path: Path, out_path: Path) -> int:
    """
    轉換單一 JSONL 檔案
    
    讀取 messages 格式的 JSONL，轉換成 text 格式。
    
    Args:
        in_path: 輸入檔案路徑（messages 格式）
        out_path: 輸出檔案路徑（text 格式）
    
    Returns:
        處理的資料筆數
    
    Example:
        >>> count = convert_file(
        ...     Path("train.jsonl"),
        ...     Path("train_text.jsonl")
        ... )
        >>> print(f"轉換 {count} 筆資料")
    """
    rows = []
    
    # 讀取輸入檔案
    with open(in_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 解析 JSON
            ex = json.loads(line)
            
            # 取得 messages 並轉換
            messages = ex.get("messages", [])
            text = convert_messages_to_text(messages)
            
            # 建立輸出格式
            rows.append({"text": text})
    
    # 寫入輸出檔案
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    return len(rows)


def main():
    """
    主函式：轉換 train.jsonl 和 valid.jsonl
    
    流程：
    1. 讀取 lab3/out/train.jsonl
    2. 轉換成 text 格式
    3. 輸出到 lab3/out/train_text.jsonl
    4. 對 valid.jsonl 做同樣處理
    """
    
    # 定義路徑
    out_dir = Path("lab3/out")
    
    # 確認輸入檔案存在
    in_train = out_dir / "train.jsonl"
    in_valid = out_dir / "valid.jsonl"
    
    if not in_train.exists():
        print(f"錯誤：找不到 {in_train}")
        print("請先執行 python -m lab3.generate_data")
        return
    
    if not in_valid.exists():
        print(f"錯誤：找不到 {in_valid}")
        print("請先執行 python -m lab3.generate_data")
        return
    
    # 轉換訓練集
    print("轉換訓練集...")
    train_count = convert_file(in_train, out_dir / "train_text.jsonl")
    print(f"  轉換 {train_count} 筆")
    
    # 轉換驗證集
    print("轉換驗證集...")
    valid_count = convert_file(in_valid, out_dir / "valid_text.jsonl")
    print(f"  轉換 {valid_count} 筆")
    
    # 顯示完成訊息
    print("\n轉換完成！")
    print(f"  {out_dir / 'train_text.jsonl'}")
    print(f"  {out_dir / 'valid_text.jsonl'}")
    
    # 顯示範例
    print("\n輸出範例：")
    with open(out_dir / "train_text.jsonl", "r", encoding="utf-8") as f:
        first_line = f.readline()
        ex = json.loads(first_line)
        print(ex["text"][:500] + "..." if len(ex["text"]) > 500 else ex["text"])


# ==============================================================================
# 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()
