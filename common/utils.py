"""
==============================================================================
Common 模組：共用工具函式 (utils.py)
==============================================================================

📌 本檔案功能：
    提供各 Lab 共用的輔助函式，包括：
    1. JSON 提取 - 從文字中提取 JSON 物件
    2. 格式化輸出 - 將物件轉成易讀的 JSON 字串

📖 設計原則：
    - 功能單一：每個函式只做一件事
    - 容錯處理：盡量不拋出異常，而是回傳 None
    - 易於測試：純函式，無副作用

🔧 使用方式：
    from common.utils import extract_json_block, pretty
    
    # 從 LLM 輸出提取 JSON
    json_obj = extract_json_block('{"name": "test"}')
    
    # 格式化輸出
    print(pretty({"key": "value"}))
"""

import json
import re
from typing import Any, Dict, Optional


def extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """
    從文字中提取第一個 JSON 物件
    
    LLM 的輸出可能包含 JSON 和自然語言混合的內容，
    這個函式會嘗試從中提取出 JSON 物件。
    
    Args:
        text: 可能包含 JSON 的文字
    
    Returns:
        解析成功的 JSON 物件（dict），或 None
    
    提取策略：
    ┌─────────────────────────────────────────────────────────────────┐
    │  策略 1：尋找 ```json ... ``` 區塊                               │
    │    適用於 LLM 用 markdown code block 包裝的情況                  │
    │                                                                 │
    │  策略 2：尋找 {...} 並用括號匹配                                 │
    │    適用於 LLM 直接輸出 JSON 的情況                               │
    └─────────────────────────────────────────────────────────────────┘
    
    Example:
        # 從 markdown code block 提取
        >>> text = '```json\n{"name": "test"}\n```'
        >>> extract_json_block(text)
        {"name": "test"}
        
        # 從純文字提取
        >>> text = '這是 JSON: {"name": "test"} 結束'
        >>> extract_json_block(text)
        {"name": "test"}
        
        # 無法提取
        >>> extract_json_block("沒有 JSON")
        None
    
    注意事項：
        - 只提取第一個 JSON 物件（dict，不是 list）
        - 巢狀的 JSON 也可以處理
        - 如果 JSON 格式錯誤，回傳 None
    """
    
    # 空值檢查
    if not text:
        return None
    
    # ==========================================================================
    # 策略 1：尋找 ```json ... ``` 區塊
    # ==========================================================================
    # 這是 LLM 常用的格式，用 markdown code block 包裝 JSON
    # 例如：
    # ```json
    # {"type": "tool_call", "name": "get_order_status", ...}
    # ```
    
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            # JSON 格式錯誤，繼續嘗試其他策略
            pass
    
    # ==========================================================================
    # 策略 2：括號匹配（Brace Matching）
    # ==========================================================================
    # 找到第一個 {，然後匹配到對應的 }
    # 這可以處理巢狀的 JSON
    
    start = text.find("{")
    if start == -1:
        # 沒有找到 {
        return None
    
    # 用深度計數來找到配對的 }
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                # 找到配對的 }
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # 不是合法的 JSON
                    return None
    
    # 沒有找到配對的 }
    return None


def pretty(obj: Any) -> str:
    """
    將物件格式化為易讀的 JSON 字串
    
    用於除錯輸出、日誌記錄、和餵給 LLM 的訊息。
    
    Args:
        obj: 要格式化的物件（dict, list, str, int, etc.）
    
    Returns:
        格式化的 JSON 字串（帶縮排）
    
    Example:
        >>> print(pretty({"name": "test", "value": 123}))
        {
          "name": "test",
          "value": 123
        }
        
        >>> print(pretty([1, 2, 3]))
        [
          1,
          2,
          3
        ]
    
    特性：
        - ensure_ascii=False：保留中文（不轉成 \uXXXX）
        - indent=2：使用 2 空格縮排
    """
    
    return json.dumps(obj, ensure_ascii=False, indent=2)


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全的 JSON 解析（不拋出異常）
    
    Args:
        text: 要解析的 JSON 字串
        default: 解析失敗時的預設值
    
    Returns:
        解析成功的物件，或預設值
    
    Example:
        >>> safe_json_loads('{"key": "value"}')
        {"key": "value"}
        
        >>> safe_json_loads('invalid json', default={})
        {}
    """
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default
