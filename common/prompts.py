"""
==============================================================================
Common 模組：提示詞模板 (prompts.py)
==============================================================================

📌 本檔案功能：
    定義 LLM 使用的各種提示詞模板，包括：
    1. System Prompt - 設定 LLM 的角色和行為規則
    2. Tool Result Message - 格式化工具執行結果

📖 Prompt Engineering 重點：
    好的 System Prompt 應該包含：
    1. 角色定義：「你是什麼」
    2. 能力說明：「你可以做什麼」
    3. 輸出規則：「你應該怎麼回應」
    4. 限制條件：「你不應該做什麼」

🔧 使用方式：
    from common.prompts import system_prompt, tool_result_message
    
    # 取得 system prompt
    prompt = system_prompt()
    
    # 格式化工具結果
    msg = tool_result_message("get_order_status", {"ok": True, "status": "已出貨"})
"""

from .tool_schema import TOOLS
from .utils import pretty


def system_prompt() -> str:
    """
    生成 System Prompt
    
    System Prompt 是對話的第一個訊息，用於：
    1. 設定 LLM 的角色（訂單客服助理）
    2. 列出可用的工具及其 schema
    3. 定義輸出格式規則
    
    Returns:
        格式化的 system prompt 字串
    
    Example:
        >>> prompt = system_prompt()
        >>> print(prompt[:100])
        你是「訂單客服助理」。你可以選擇直接回答，或輸出一個「工具呼叫 JSON」。
    
    Prompt 結構說明：
    ┌─────────────────────────────────────────────────────────────────┐
    │  1. 角色定義                                                     │
    │     「你是訂單客服助理」                                          │
    │                                                                 │
    │  2. 可用工具                                                     │
    │     列出所有工具的 name, description, parameters                 │
    │                                                                 │
    │  3. 輸出規則                                                     │
    │     - 何時輸出 JSON（需要工具）                                   │
    │     - 何時追問（缺少參數）                                       │
    │     - 何時直接答（不需要工具）                                   │
    └─────────────────────────────────────────────────────────────────┘
    
    設計考量：
        - 使用 pretty(TOOLS) 將工具定義轉成 JSON，讓 LLM 更容易理解
        - 明確說明 JSON 格式，減少輸出錯誤
        - 強調「只輸出 JSON」避免混合自然語言
    """
    
    return f"""你是「訂單客服助理」。你可以選擇直接回答，或輸出一個「工具呼叫 JSON」。

可用工具（僅可從以下工具中選擇）：
{pretty(TOOLS)}

輸出規則（非常重要）：
1) 若需要呼叫工具，請「只輸出」一個 JSON 物件，格式必須是：
{{
  "type": "tool_call",
  "name": "<tool_name>",
  "arguments": {{ ... }}
}}
不可輸出其他文字。
2) 若資訊不足以呼叫工具，請先用自然語言「追問缺少的必要資訊」；此時不要輸出 JSON。
3) 若不需要工具，直接用自然語言回答。
"""


def tool_result_message(tool_name: str, tool_result: dict) -> str:
    """
    格式化工具執行結果的訊息
    
    當工具執行完畢後，我們需要把結果「餵回」給 LLM，
    讓它根據結果生成對使用者的回覆。
    
    這個函式會：
    1. 格式化工具結果為 JSON
    2. 提供指示，告訴 LLM 如何處理結果
    
    Args:
        tool_name: 執行的工具名稱
        tool_result: 工具回傳的結果字典
    
    Returns:
        格式化的訊息字串
    
    Example:
        >>> result = {"ok": True, "status": "已出貨", "tracking_no": "TWD12345678"}
        >>> msg = tool_result_message("get_order_status", result)
        >>> print(msg)
        工具 get_order_status 回傳結果（JSON）：
        {
          "ok": true,
          "status": "已出貨",
          "tracking_no": "TWD12345678"
        }
        請根據此結果，給使用者簡潔、正確的回覆。若工具回傳 ok=false，請向使用者說明並引導下一步。
    
    使用場景：
        這個訊息會作為 "user" 角色加入對話歷史：
        
        messages = [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": "查訂單 A123"},
            {"role": "assistant", "content": '{"type": "tool_call", ...}'},
            {"role": "user", "content": tool_result_message("get_order_status", result)},
            # LLM 會在這裡生成最終回覆
        ]
    
    設計考量：
        - 明確告訴 LLM 這是「工具回傳結果」
        - 提供處理指南（ok=false 時怎麼辦）
        - 使用 JSON 格式讓結果結構清楚
    """
    
    return f"""工具 {tool_name} 回傳結果（JSON）：
{pretty(tool_result)}
請根據此結果，給使用者簡潔、正確的回覆。若工具回傳 ok=false，請向使用者說明並引導下一步。"""
