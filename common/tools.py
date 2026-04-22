"""
==============================================================================
Common 模組：Mock 工具實作 (tools.py)
==============================================================================

📌 本檔案功能：
    提供模擬的工具函式（Mock Tools），用於開發和測試。
    
    在實際部署中，這些函式會連接到真正的後端服務（資料庫、API 等）。
    但在 Lab 中，我們用 Mock 資料來模擬行為。

📖 Mock 資料的價值：
    1. 不需要真實後端也能開發和測試
    2. 可以控制各種情境（成功、失敗、找不到等）
    3. 快速迭代，不用擔心外部依賴

🔧 使用方式：
    from common.tools import TOOL_REGISTRY
    
    # 透過名稱呼叫工具
    result = TOOL_REGISTRY["get_order_status"](order_id="A123456789")
    print(result)
    # {"ok": True, "order_id": "A123456789", "status": "已出貨", ...}

📋 新增工具步驟：
    1. 在本檔案定義函式
    2. 在 TOOL_REGISTRY 中註冊
    3. 在 tool_schema.py 中定義 Schema
"""

from typing import Dict, Any
import random
import time


# ==============================================================================
# Mock 資料庫
# ==============================================================================

ORDERS = {
    "A123456789": {"status": "已出貨", "tracking_no": "TWD12345678"},
    "A000000001": {"status": "處理中", "tracking_no": None},
    "A999999999": {"status": "已取消", "tracking_no": None},
}
"""
模擬的訂單資料庫

格式：
    {
        "訂單編號": {
            "status": "訂單狀態",
            "tracking_no": "物流單號（可能為 None）"
        }
    }

測試案例：
    - A123456789：已出貨，有物流單號
    - A000000001：處理中，尚無物流單號
    - A999999999：已取消
    - 其他訂單編號：會回傳 ORDER_NOT_FOUND
"""

SHIPMENTS = {
    "TWD12345678": [
        {"ts": "2026-01-20 10:00", "node": "已收件"},
        {"ts": "2026-01-21 08:00", "node": "轉運中心"},
        {"ts": "2026-01-22 15:20", "node": "配送中"},
    ]
}
"""
模擬的物流資料庫

格式：
    {
        "物流單號": [
            {"ts": "時間戳", "node": "物流節點"},
            ...
        ]
    }

測試案例：
    - TWD12345678：有 3 個物流節點
    - 其他物流單號：會回傳 TRACKING_NOT_FOUND
"""

ORDER_ITEMS = {
    "A123456789": [
        {"sku": "SKU000001", "name": "藍牙耳機", "qty": 1, "price": 1290},
        {"sku": "SKU000002", "name": "充電線 1m", "qty": 2, "price": 199},
    ],
    "A000000001": [
        {"sku": "SKU000003", "name": "保溫瓶 500ml", "qty": 1, "price": 690},
    ],
    "A999999999": [
        {"sku": "SKU000004", "name": "運動毛巾", "qty": 3, "price": 250},
    ],
}
"""
模擬的訂單明細資料庫

格式：
    {
        "訂單編號": [
            {"sku": "商品編號", "name": "商品名稱", "qty": 數量, "price": 單價},
            ...
        ]
    }
"""

REFUND_CASES = {
    "R100001": {"order_id": "A123456789", "status": "審核中", "amount": 1688},
    "R100002": {"order_id": "A000000001", "status": "已退款", "amount": 690},
    "R100003": {"order_id": "A999999999", "status": "已駁回", "amount": 750},
}
"""
模擬的退款案件資料庫

格式：
    {
        "退款案件編號": {
            "order_id": "訂單編號",
            "status": "審核中 / 已退款 / 已駁回",
            "amount": 退款金額
        }
    }
"""

COUPONS = {
    "WELCOME100": {"discount": 100, "min_spend": 500, "expired": False, "applicable": True},
    "VIP500": {"discount": 500, "min_spend": 3000, "expired": False, "applicable": True},
    "OLD2024": {"discount": 200, "min_spend": 1000, "expired": True, "applicable": True},
    "NEWUSERONLY": {"discount": 50, "min_spend": 0, "expired": False, "applicable": False},
}
"""
模擬的優惠券資料庫

測試案例：
    - WELCOME100、VIP500：可用
    - OLD2024：已過期 → COUPON_EXPIRED
    - NEWUSERONLY：不適用此訂單 → COUPON_NOT_APPLICABLE
    - 其他代碼：INVALID_COUPON
"""

PRODUCTS = {
    "SKU000001": {"name": "藍牙耳機", "in_stock_qty": 12, "restock_eta": None},
    "SKU000002": {"name": "充電線 1m", "in_stock_qty": 0, "restock_eta": "2026-05-01"},
    "SKU000003": {"name": "保溫瓶 500ml", "in_stock_qty": 5, "restock_eta": None},
    "SKU000004": {"name": "運動毛巾", "in_stock_qty": 30, "restock_eta": None},
}
"""
模擬的商品庫存資料庫

測試案例：
    - SKU000001 / SKU000003 / SKU000004：有貨
    - SKU000002：缺貨，預計 2026-05-01 到貨
    - 其他 SKU：PRODUCT_NOT_FOUND
"""

ADDRESSES = {
    "A000000001": {"recipient": "王小明", "phone": "0912345678", "address": "台北市信義區某路 1 號"},
    "A123456789": {"recipient": "陳大華", "phone": "0987654321", "address": "新北市板橋區某路 99 號"},
    "A999999999": {"recipient": "李美麗", "phone": "0922333444", "address": "桃園市中壢區某路 50 號"},
}
"""
模擬的配送地址資料庫（會被 update_shipping_address 修改）
"""


# ==============================================================================
# 工具函式
# ==============================================================================

def get_order_status(order_id: str) -> Dict[str, Any]:
    """
    查詢訂單狀態
    
    根據訂單編號查詢訂單的當前狀態和物流單號。
    
    Args:
        order_id: 訂單編號（格式：A + 9位數字）
    
    Returns:
        成功時：
        {
            "ok": True,
            "order_id": "A123456789",
            "status": "已出貨",
            "tracking_no": "TWD12345678"  # 可能為 None
        }
        
        失敗時：
        {
            "ok": False,
            "error": "ORDER_NOT_FOUND",
            "order_id": "A123456789"
        }
    
    Example:
        >>> get_order_status("A123456789")
        {"ok": True, "order_id": "A123456789", "status": "已出貨", "tracking_no": "TWD12345678"}
        
        >>> get_order_status("A000000000")
        {"ok": False, "error": "ORDER_NOT_FOUND", "order_id": "A000000000"}
    
    使用場景：
        - 使用者詢問「訂單 A123456789 到哪了」
        - LLM 呼叫此工具取得狀態
        - 根據狀態回覆使用者
    """
    # 模擬網路延遲（0.1 秒）
    # 在實際系統中，這是真實的 API 呼叫延遲
    time.sleep(0.1)
    
    # 查詢訂單
    if order_id not in ORDERS:
        # 找不到訂單
        return {
            "ok": False,
            "error": "ORDER_NOT_FOUND",
            "order_id": order_id
        }
    
    # 取得訂單資料
    data = ORDERS[order_id]
    
    return {
        "ok": True,
        "order_id": order_id,
        **data  # 展開 status, tracking_no
    }


def track_shipment(tracking_no: str) -> Dict[str, Any]:
    """
    查詢物流狀態
    
    根據物流單號查詢最新的配送進度。
    
    Args:
        tracking_no: 物流單號（格式：TWD + 8位數字）
    
    Returns:
        成功時：
        {
            "ok": True,
            "tracking_no": "TWD12345678",
            "events": [
                {"ts": "2026-01-20 10:00", "node": "已收件"},
                {"ts": "2026-01-21 08:00", "node": "轉運中心"},
                {"ts": "2026-01-22 15:20", "node": "配送中"}
            ]
        }
        
        失敗時：
        {
            "ok": False,
            "error": "TRACKING_NOT_FOUND",
            "tracking_no": "TWD12345678"
        }
    
    Example:
        >>> track_shipment("TWD12345678")
        {"ok": True, "tracking_no": "TWD12345678", "events": [...]}
    
    使用場景：
        - 使用者詢問「物流 TWD12345678 到哪了」
        - LLM 呼叫此工具取得物流節點
        - 根據最新節點回覆使用者
    """
    # 模擬網路延遲
    time.sleep(0.1)
    
    # 查詢物流
    if tracking_no not in SHIPMENTS:
        return {
            "ok": False,
            "error": "TRACKING_NOT_FOUND",
            "tracking_no": tracking_no
        }
    
    # 取得物流事件（最多回傳最近 3 筆）
    events = SHIPMENTS[tracking_no][-3:]
    
    return {
        "ok": True,
        "tracking_no": tracking_no,
        "events": events
    }


def create_refund_request(
    order_id: str, 
    reason: str, 
    details: str = ""
) -> Dict[str, Any]:
    """
    建立退款申請
    
    為指定訂單建立退款申請，會產生一個案件編號。
    
    Args:
        order_id: 訂單編號
        reason: 退款原因（必須是預定義的選項之一）
        details: 補充說明（可選）
    
    Returns:
        成功時：
        {
            "ok": True,
            "case_id": "R123456",
            "order_id": "A123456789",
            "reason": "商品瑕疵",
            "details": "...",
            "message": "退款申請已建立，客服將於 1-2 個工作天內處理。"
        }
        
        失敗時（訂單不存在）：
        {
            "ok": False,
            "error": "ORDER_NOT_FOUND",
            "order_id": "A123456789"
        }
        
        失敗時（訂單已取消）：
        {
            "ok": False,
            "error": "ORDER_ALREADY_CANCELLED",
            "order_id": "A999999999"
        }
    
    Example:
        >>> create_refund_request("A123456789", "商品瑕疵", "收到時螢幕有裂痕")
        {"ok": True, "case_id": "R123456", ...}
    
    使用場景：
        - 使用者說「我要退款，訂單 A123456789，因為商品壞了」
        - LLM 呼叫此工具建立退款申請
        - 回覆使用者案件編號和後續處理時間
    """
    # 模擬網路延遲
    time.sleep(0.1)
    
    # 檢查訂單是否存在
    if order_id not in ORDERS:
        return {
            "ok": False,
            "error": "ORDER_NOT_FOUND",
            "order_id": order_id
        }
    
    # 檢查訂單是否已取消
    if ORDERS[order_id]["status"] == "已取消":
        return {
            "ok": False,
            "error": "ORDER_ALREADY_CANCELLED",
            "order_id": order_id
        }
    
    # 產生退款案件編號（隨機 6 位數）
    case_id = f"R{random.randint(100000, 999999)}"
    
    return {
        "ok": True,
        "case_id": case_id,
        "order_id": order_id,
        "reason": reason,
        "details": details,
        "message": "退款申請已建立，客服將於 1-2 個工作天內處理。"
    }


def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    取消訂單

    根據訂單編號取消訂單。已出貨或已取消的訂單無法取消。

    Args:
        order_id: 訂單編號

    Returns:
        成功時：
        {"ok": True, "order_id": "...", "status": "已取消", "message": "..."}

        失敗時：
        {"ok": False, "error": "ORDER_NOT_FOUND" | "ORDER_CANNOT_CANCEL", ...}

    使用場景：
        - 使用者說「幫我取消訂單 A000000001」
        - 已出貨（A123456789）或已取消（A999999999）會回傳錯誤
    """
    time.sleep(0.1)

    if order_id not in ORDERS:
        return {"ok": False, "error": "ORDER_NOT_FOUND", "order_id": order_id}

    current = ORDERS[order_id]["status"]
    if current in ("已出貨", "已取消"):
        return {
            "ok": False,
            "error": "ORDER_CANNOT_CANCEL",
            "order_id": order_id,
            "current_status": current,
        }

    ORDERS[order_id]["status"] = "已取消"
    return {
        "ok": True,
        "order_id": order_id,
        "status": "已取消",
        "message": "訂單已取消，若已扣款將於 3-5 個工作天內退回。",
    }


def get_order_items(order_id: str) -> Dict[str, Any]:
    """
    查詢訂單商品明細

    根據訂單編號查詢該訂單包含的商品（品名、數量、單價、小計）。

    Args:
        order_id: 訂單編號

    Returns:
        成功時：
        {
            "ok": True,
            "order_id": "...",
            "items": [{"sku": "...", "name": "...", "qty": N, "price": N, "subtotal": N}, ...],
            "total": 總金額
        }

        失敗時：
        {"ok": False, "error": "ORDER_NOT_FOUND" | "ITEMS_NOT_FOUND", ...}
    """
    time.sleep(0.1)

    if order_id not in ORDERS:
        return {"ok": False, "error": "ORDER_NOT_FOUND", "order_id": order_id}

    items = ORDER_ITEMS.get(order_id)
    if not items:
        return {"ok": False, "error": "ITEMS_NOT_FOUND", "order_id": order_id}

    enriched = [
        {**it, "subtotal": it["qty"] * it["price"]} for it in items
    ]
    total = sum(it["subtotal"] for it in enriched)

    return {
        "ok": True,
        "order_id": order_id,
        "items": enriched,
        "total": total,
    }


def update_shipping_address(
    order_id: str,
    recipient: str,
    phone: str,
    address: str,
) -> Dict[str, Any]:
    """
    修改訂單配送地址

    僅在訂單尚未出貨（即「處理中」）時可修改。

    Args:
        order_id: 訂單編號
        recipient: 收件人姓名
        phone: 收件人聯絡電話
        address: 完整配送地址

    Returns:
        成功時：
        {"ok": True, "order_id": "...", "address": {...}, "message": "..."}

        失敗時：
        {"ok": False, "error": "ORDER_NOT_FOUND" | "ADDRESS_LOCKED", ...}
    """
    time.sleep(0.1)

    if order_id not in ORDERS:
        return {"ok": False, "error": "ORDER_NOT_FOUND", "order_id": order_id}

    status = ORDERS[order_id]["status"]
    if status != "處理中":
        return {
            "ok": False,
            "error": "ADDRESS_LOCKED",
            "order_id": order_id,
            "current_status": status,
        }

    new_address = {"recipient": recipient, "phone": phone, "address": address}
    ADDRESSES[order_id] = new_address

    return {
        "ok": True,
        "order_id": order_id,
        "address": new_address,
        "message": "配送地址已更新。",
    }


def get_refund_status(case_id: str) -> Dict[str, Any]:
    """
    查詢退款案件進度

    Args:
        case_id: 退款案件編號（格式：R + 6 位數字）

    Returns:
        成功時：
        {"ok": True, "case_id": "...", "order_id": "...", "status": "...", "amount": N}

        失敗時：
        {"ok": False, "error": "REFUND_CASE_NOT_FOUND", "case_id": "..."}
    """
    time.sleep(0.1)

    if case_id not in REFUND_CASES:
        return {"ok": False, "error": "REFUND_CASE_NOT_FOUND", "case_id": case_id}

    return {"ok": True, "case_id": case_id, **REFUND_CASES[case_id]}


def apply_coupon(order_id: str, coupon_code: str) -> Dict[str, Any]:
    """
    套用優惠碼到訂單

    Args:
        order_id: 訂單編號
        coupon_code: 優惠碼（英數，例如 WELCOME100）

    Returns:
        成功時：
        {"ok": True, "order_id": "...", "coupon_code": "...", "discount": N, "message": "..."}

        失敗時：
        {"ok": False, "error": "ORDER_NOT_FOUND" | "INVALID_COUPON" | "COUPON_EXPIRED" | "COUPON_NOT_APPLICABLE", ...}
    """
    time.sleep(0.1)

    if order_id not in ORDERS:
        return {"ok": False, "error": "ORDER_NOT_FOUND", "order_id": order_id}

    coupon = COUPONS.get(coupon_code)
    if coupon is None:
        return {"ok": False, "error": "INVALID_COUPON", "coupon_code": coupon_code}

    if coupon["expired"]:
        return {"ok": False, "error": "COUPON_EXPIRED", "coupon_code": coupon_code}

    if not coupon["applicable"]:
        return {
            "ok": False,
            "error": "COUPON_NOT_APPLICABLE",
            "coupon_code": coupon_code,
            "order_id": order_id,
        }

    return {
        "ok": True,
        "order_id": order_id,
        "coupon_code": coupon_code,
        "discount": coupon["discount"],
        "message": f"已套用優惠碼，折抵 {coupon['discount']} 元。",
    }


def check_product_stock(sku: str) -> Dict[str, Any]:
    """
    查詢商品庫存

    Args:
        sku: 商品編號（格式：SKU + 6 位數字）

    Returns:
        成功時：
        {
            "ok": True,
            "sku": "...",
            "name": "...",
            "in_stock_qty": N,
            "restock_eta": "YYYY-MM-DD" | None
        }

        失敗時：
        {"ok": False, "error": "PRODUCT_NOT_FOUND", "sku": "..."}
    """
    time.sleep(0.1)

    if sku not in PRODUCTS:
        return {"ok": False, "error": "PRODUCT_NOT_FOUND", "sku": sku}

    return {"ok": True, "sku": sku, **PRODUCTS[sku]}


def escalate_to_human(topic: str, summary: str, order_id: str = "") -> Dict[str, Any]:
    """
    轉接真人客服

    當問題超出助理可處理範圍時，建立真人客服轉接案件。

    Args:
        topic: 諮詢主題（必須是預定義選項之一）
        summary: 案件摘要（簡述使用者問題）
        order_id: 相關訂單編號（可選）

    Returns:
        {
            "ok": True,
            "ticket_id": "T123456",
            "topic": "...",
            "order_id": "...",
            "summary": "...",
            "message": "已為您轉接真人客服，預計 X 分鐘內專員會與您聯繫。"
        }
    """
    time.sleep(0.1)

    ticket_id = f"T{random.randint(100000, 999999)}"

    return {
        "ok": True,
        "ticket_id": ticket_id,
        "topic": topic,
        "order_id": order_id,
        "summary": summary,
        "message": "已為您轉接真人客服，預計 5 分鐘內專員會與您聯繫。",
    }


# ==============================================================================
# 工具註冊表
# ==============================================================================

TOOL_REGISTRY = {
    "get_order_status": get_order_status,
    "track_shipment": track_shipment,
    "create_refund_request": create_refund_request,
    "cancel_order": cancel_order,
    "get_order_items": get_order_items,
    "update_shipping_address": update_shipping_address,
    "get_refund_status": get_refund_status,
    "apply_coupon": apply_coupon,
    "check_product_stock": check_product_stock,
    "escalate_to_human": escalate_to_human,
}
"""
工具註冊表

將工具名稱映射到實際的函式。

使用方式：
    tool_fn = TOOL_REGISTRY["get_order_status"]
    result = tool_fn(order_id="A123456789")
    
    # 或使用動態名稱
    name = tool_call["name"]
    args = tool_call["arguments"]
    result = TOOL_REGISTRY[name](**args)

新增工具：
    1. 定義函式
    2. 在這裡註冊：TOOL_REGISTRY["new_tool"] = new_tool_fn
    3. 在 tool_schema.py 新增 Schema
"""
