"""
==============================================================================
Common 模組：工具呼叫驗證器 (validator.py)
==============================================================================

📌 本檔案功能：
    驗證 LLM 輸出的 tool_call 是否合法，包括：
    1. 結構驗證：是否有正確的欄位（type, name, arguments）
    2. 工具驗證：name 是否是已知的工具
    3. Schema 驗證：arguments 是否符合該工具的參數定義

📖 驗證的價值：
    LLM 的輸出不一定正確，可能有：
    - 格式錯誤（不是 JSON、缺少欄位）
    - 工具名稱錯誤（呼叫不存在的工具）
    - 參數錯誤（類型錯誤、格式不符、缺少必填）
    
    驗證可以在「執行前」發現這些問題，避免程式崩潰。

🔧 使用方式：
    from common.validator import validate_tool_call
    
    tool_call = {"type": "tool_call", "name": "get_order_status", "arguments": {...}}
    ok, err = validate_tool_call(tool_call)
    
    if ok:
        # 執行工具
        result = TOOL_REGISTRY[tool_call["name"]](**tool_call["arguments"])
    else:
        # 處理錯誤
        print(f"驗證失敗：{err}")
"""

from typing import Any, Dict, Tuple, Optional
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from .tool_schema import TOOLS


# ==============================================================================
# 建立工具索引
# ==============================================================================

TOOL_INDEX = {t["name"]: t for t in TOOLS}
"""
工具索引：name → tool_definition

用於快速查找工具的 schema。

Example:
    >>> TOOL_INDEX["get_order_status"]
    {"name": "get_order_status", "description": "...", "parameters": {...}}
"""


def validate_tool_call(tool_call: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    驗證 tool_call 是否合法
    
    這是驗證的主要函式，會執行多層檢查：
    
    ┌─────────────────────────────────────────────────────────────────┐
    │  檢查 1：是否為 dict                                             │
    │    tool_call 必須是字典類型                                      │
    │                                                                 │
    │  檢查 2：type 是否為 "tool_call"                                 │
    │    確保這是一個工具呼叫（不是其他類型的 JSON）                    │
    │                                                                 │
    │  檢查 3：name 是否為已知工具                                     │
    │    避免呼叫不存在的工具                                          │
    │                                                                 │
    │  檢查 4：arguments 是否為 dict                                   │
    │    參數必須是字典類型                                            │
    │                                                                 │
    │  檢查 5：arguments 是否符合 Schema                               │
    │    使用 jsonschema 驗證參數格式                                  │
    └─────────────────────────────────────────────────────────────────┘
    
    Args:
        tool_call: 要驗證的工具呼叫，預期格式：
            {
                "type": "tool_call",
                "name": "工具名稱",
                "arguments": {...}
            }
    
    Returns:
        Tuple[bool, Optional[str]]
        - (True, None)：驗證通過
        - (False, "錯誤訊息")：驗證失敗
    
    Example:
        # 正確的 tool_call
        >>> validate_tool_call({
        ...     "type": "tool_call",
        ...     "name": "get_order_status",
        ...     "arguments": {"order_id": "A123456789"}
        ... })
        (True, None)
        
        # 錯誤：未知的工具
        >>> validate_tool_call({
        ...     "type": "tool_call",
        ...     "name": "unknown_tool",
        ...     "arguments": {}
        ... })
        (False, "unknown_tool:unknown_tool")
        
        # 錯誤：參數格式不符
        >>> validate_tool_call({
        ...     "type": "tool_call",
        ...     "name": "get_order_status",
        ...     "arguments": {"order_id": "12345"}  # 缺少開頭字母
        ... })
        (False, "schema_validation_error:...")
    
    設計考量：
        - 回傳 Tuple 而非拋出異常，方便呼叫端處理
        - 錯誤訊息盡量具體，幫助除錯
    """
    
    # ==========================================================================
    # 檢查 1：是否為 dict
    # ==========================================================================
    if not isinstance(tool_call, dict):
        return False, "tool_call_not_object"
    
    # ==========================================================================
    # 檢查 2：type 是否為 "tool_call"
    # ==========================================================================
    # 這個欄位用於區分「工具呼叫」和「其他 JSON」
    # 例如 LLM 可能輸出其他類型的 JSON 回應
    if tool_call.get("type") != "tool_call":
        return False, "type_must_be_tool_call"
    
    # ==========================================================================
    # 檢查 3：name 是否為已知工具
    # ==========================================================================
    name = tool_call.get("name")
    if name not in TOOL_INDEX:
        return False, f"unknown_tool:{name}"
    
    # ==========================================================================
    # 檢查 4：arguments 是否為 dict
    # ==========================================================================
    args = tool_call.get("arguments")
    if not isinstance(args, dict):
        return False, "arguments_must_be_object"
    
    # ==========================================================================
    # 檢查 5：arguments 是否符合 Schema
    # ==========================================================================
    # 使用 jsonschema 套件進行驗證
    # Schema 定義在 tool_schema.py 中
    schema = TOOL_INDEX[name]["parameters"]
    
    try:
        validate(instance=args, schema=schema)
    except ValidationError as e:
        # 驗證失敗，回傳錯誤訊息
        # e.message 包含具體的錯誤說明
        return False, f"schema_validation_error:{e.message}"
    
    # ==========================================================================
    # 全部通過
    # ==========================================================================
    return True, None


def validate_tool_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    只驗證工具名稱是否有效
    
    這是一個較輕量的驗證，只檢查名稱是否在已知工具列表中。
    
    Args:
        name: 工具名稱
    
    Returns:
        (True, None) 或 (False, 錯誤訊息)
    
    Example:
        >>> validate_tool_name("get_order_status")
        (True, None)
        
        >>> validate_tool_name("unknown")
        (False, "unknown_tool:unknown")
    """
    
    if name in TOOL_INDEX:
        return True, None
    return False, f"unknown_tool:{name}"


def get_tool_schema(name: str) -> Optional[Dict[str, Any]]:
    """
    取得指定工具的參數 Schema
    
    Args:
        name: 工具名稱
    
    Returns:
        參數 Schema（dict），或 None
    
    Example:
        >>> schema = get_tool_schema("get_order_status")
        >>> print(schema["required"])
        ["order_id"]
    """
    
    tool = TOOL_INDEX.get(name)
    if tool:
        return tool.get("parameters")
    return None
