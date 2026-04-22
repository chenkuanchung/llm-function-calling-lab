"""
==============================================================================
Common 模組：工具 Schema 定義 (tool_schema.py)
==============================================================================

📌 本檔案功能：
    定義所有可用工具的 JSON Schema，包括：
    1. 工具名稱和描述
    2. 參數定義（類型、格式、是否必填）
    3. 參數約束（enum、pattern 等）

📖 JSON Schema 簡介：
    JSON Schema 是描述 JSON 資料格式的標準。
    我們用它來：
    1. 告訴 LLM 每個工具需要什麼參數
    2. 驗證 LLM 輸出的參數是否正確

🔧 使用方式：
    from common.tool_schema import TOOLS
    
    # 取得所有工具定義
    for tool in TOOLS:
        print(tool["name"], tool["description"])

📋 Schema 格式說明：
    {
        "name": "tool_name",           # 工具唯一名稱
        "description": "...",          # 功能描述（LLM 靠此選工具）
        "parameters": {                # 參數 Schema
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "參數描述",
                    "pattern": "正則表達式",
                    "enum": ["選項1", "選項2"]
                }
            },
            "required": ["param1"],    # 必填參數
            "additionalProperties": false  # 不允許額外參數
        }
    }

📖 各欄位說明：
    - name: 工具唯一名稱，LLM 呼叫時使用
    - description: 功能描述，這是 LLM 選擇工具的主要依據
    - parameters: 參數的 JSON Schema
      - type: 參數類型（string, number, boolean, object, array）
      - description: 參數說明，提供範例幫助 LLM 填入正確值
      - pattern: 正則表達式，用於驗證格式
      - enum: 限制參數只能是列表中的值
      - required: 必填參數列表
      - additionalProperties: 是否允許額外參數
"""


# ==============================================================================
# 工具定義
# ==============================================================================

TOOLS = [
    # --------------------------------------------------------------------------
    # 工具 1：查詢訂單狀態
    # --------------------------------------------------------------------------
    # description 是 LLM 選擇工具的主要依據，應該清楚說明工具的用途
    # 括號中列出可能的結果，幫助 LLM 理解
    {
        "name": "get_order_status",
        "description": "查詢訂單狀態（出貨/配送/已取消等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    # description 提供範例格式，幫助 LLM 填入正確的值
                    # 如果使用者輸入「我的訂單是 A123456789」，
                    # LLM 應該能從中提取出訂單編號
                    "description": "訂單編號，例如 A123456789",
                    # pattern 是正則表達式，用於驗證參數格式：
                    # ^[A-Z] = 開頭是大寫字母
                    # \d{9} = 接著 9 個數字
                    # $ = 結尾
                    # 例如：A123456789 ✓, 123456789 ✗, A12345 ✗
                    "pattern": "^[A-Z]\\d{9}$"
                }
            },
            # required 列出必填的參數
            # 如果 LLM 沒有填入這些參數，驗證會失敗
            "required": ["order_id"],
            # additionalProperties: False 不允許額外的參數
            "additionalProperties": False
        },
    },
    
    # --------------------------------------------------------------------------
    # 工具 2：查詢物流狀態
    # --------------------------------------------------------------------------
    # 物流單號格式：TWD + 8 位數字，例如 TWD12345678
    {
        "name": "track_shipment",
        "description": "查詢物流最新節點（需要物流單號）。",
        "parameters": {
            "type": "object",
            "properties": {
                "tracking_no": {
                    "type": "string",
                    "description": "物流單號，例如 TWD12345678",
                    "pattern": "^TWD\\d{8}$"
                }
            },
            "required": ["tracking_no"],
            "additionalProperties": False
        },
    },
    
    # --------------------------------------------------------------------------
    # 工具 3：建立退款申請
    # --------------------------------------------------------------------------
    # 注意：order_id 和 reason 是必填，details 是選填
    # 如果使用者只說「我要退款」，LLM 應該追問 order_id 和 reason
    {
        "name": "create_refund_request",
        "description": "建立退款申請（原因與訂單編號必填）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "pattern": "^[A-Z]\\d{9}$"
                },
                "reason": {
                    "type": "string",
                    # enum 限制參數只能是列表中的值
                    # LLM 會從這些選項中選擇
                    # 如果使用者說「因為東西壞了」，LLM 應該對應到「商品瑕疵」
                    "enum": ["未收到貨", "商品瑕疵", "買錯/不需要", "重複下單", "其他"]
                },
                "details": {
                    "type": "string",
                    "description": "補充說明（可選）"
                },
            },
            "required": ["order_id", "reason"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 4：取消訂單
    # --------------------------------------------------------------------------
    # 已出貨或已取消的訂單會回傳 ORDER_CANNOT_CANCEL
    {
        "name": "cancel_order",
        "description": "取消尚未出貨的訂單（已出貨/已取消無法取消）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "訂單編號，例如 A123456789",
                    "pattern": "^[A-Z]\\d{9}$"
                }
            },
            "required": ["order_id"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 5：查詢訂單商品明細
    # --------------------------------------------------------------------------
    # 用於回答「我的訂單買了什麼」、「總共多少錢」這類問題
    {
        "name": "get_order_items",
        "description": "查詢訂單的商品明細（品名、數量、單價、小計、總額）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "訂單編號，例如 A123456789",
                    "pattern": "^[A-Z]\\d{9}$"
                }
            },
            "required": ["order_id"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 6：修改訂單配送地址
    # --------------------------------------------------------------------------
    # 4 個參數全部必填，避免使用者只給部分資訊就送出
    # 已出貨後會回傳 ADDRESS_LOCKED
    {
        "name": "update_shipping_address",
        "description": "修改尚未出貨訂單的配送地址（姓名、電話、地址三者皆必填）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "訂單編號，例如 A123456789",
                    "pattern": "^[A-Z]\\d{9}$"
                },
                "recipient": {
                    "type": "string",
                    "description": "收件人姓名"
                },
                "phone": {
                    "type": "string",
                    "description": "收件人聯絡電話，例如 0912345678",
                    "pattern": "^09\\d{8}$"
                },
                "address": {
                    "type": "string",
                    "description": "完整配送地址（含縣市、區、路名、門牌）"
                }
            },
            "required": ["order_id", "recipient", "phone", "address"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 7：查詢退款案件進度
    # --------------------------------------------------------------------------
    # 注意：這裡用退款「案件編號」（R + 6 位數字），不是訂單編號
    {
        "name": "get_refund_status",
        "description": "查詢退款案件的處理進度（審核中/已退款/已駁回），需要退款案件編號。",
        "parameters": {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "string",
                    "description": "退款案件編號，例如 R100001",
                    "pattern": "^R\\d{6}$"
                }
            },
            "required": ["case_id"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 8：套用優惠碼
    # --------------------------------------------------------------------------
    # 優惠碼為英數大寫，例如 WELCOME100、VIP500
    {
        "name": "apply_coupon",
        "description": "將優惠碼套用到指定訂單（會檢查是否過期、是否適用）。",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "訂單編號，例如 A123456789",
                    "pattern": "^[A-Z]\\d{9}$"
                },
                "coupon_code": {
                    "type": "string",
                    "description": "優惠碼（英數大寫），例如 WELCOME100",
                    "pattern": "^[A-Z0-9]{4,20}$"
                }
            },
            "required": ["order_id", "coupon_code"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 9：查詢商品庫存
    # --------------------------------------------------------------------------
    # 商品編號格式：SKU + 6 位數字
    {
        "name": "check_product_stock",
        "description": "查詢商品的目前庫存量與補貨預計到貨日。",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "商品編號（SKU），例如 SKU000001",
                    "pattern": "^SKU\\d{6}$"
                }
            },
            "required": ["sku"],
            "additionalProperties": False
        },
    },

    # --------------------------------------------------------------------------
    # 工具 10：轉接真人客服
    # --------------------------------------------------------------------------
    # 當問題超出助理可處理範圍時，建立真人客服轉接案件
    # topic 用 enum 限定主題；order_id 為選填
    {
        "name": "escalate_to_human",
        "description": "將案件轉接給真人客服處理（適用於投訴、複雜爭議或助理無法解決的情況）。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "諮詢主題分類",
                    "enum": ["帳務", "物流", "商品", "退換貨", "其他"]
                },
                "summary": {
                    "type": "string",
                    "description": "案件摘要（簡述使用者的問題或需求）"
                },
                "order_id": {
                    "type": "string",
                    "description": "相關訂單編號（可選）",
                    "pattern": "^[A-Z]\\d{9}$"
                }
            },
            "required": ["topic", "summary"],
            "additionalProperties": False
        },
    },
]


# ==============================================================================
# 輔助函式
# ==============================================================================

def get_tool_by_name(name: str) -> dict | None:
    """
    根據名稱取得工具定義
    
    Args:
        name: 工具名稱
        
    Returns:
        工具定義字典，如果找不到則回傳 None
    
    Example:
        >>> tool = get_tool_by_name("get_order_status")
        >>> print(tool["description"])
        查詢訂單狀態（出貨/配送/已取消等）。
    """
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tool_names() -> list[str]:
    """
    取得所有工具名稱
    
    Returns:
        工具名稱列表
    
    Example:
        >>> names = get_tool_names()
        >>> print(names)
        ['get_order_status', 'track_shipment', 'create_refund_request']
    """
    return [tool["name"] for tool in TOOLS]
