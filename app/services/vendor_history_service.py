from app.db import db
from datetime import datetime
from fastapi import Request
from bson import ObjectId

PURCHASE_ORDERS = db.PurchaseOrders
RETURN_TO_VENDOR = db.ReturnToVendor
CONTRACTS = db.Contracts

# Status mappings
RECEIVED_MAP = {0: "Waiting", 1: "Received"}
VALIDATION_MAP = {0: "Pending", 1: "Completed"}
RETURN_STATUS_MAP = {0: "Returned", 1: "Disabled", 2: "Pending"}


def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


async def get_vendor_history(vendor_id: str, request: Request):
    """
    Fetch complete vendor history including:
    - Purchase orders
    - Returns to vendor
    - Contract details
    """
    user = request.state.user
    store_id = str(user.get("store_id"))
    org_id = str(user.get("org_id"))

    # Get vendor details first - try both vendor_id and _id
    vendor = await db.Vendors.find_one({
        "vendor_id": vendor_id,
        "store_id": store_id,
        "org_id": org_id
    })
    
    # If not found by vendor_id, try by MongoDB _id
    if not vendor:
        try:
            vendor = await db.Vendors.find_one({
                "_id": ObjectId(vendor_id),
                "store_id": store_id,
                "org_id": org_id
            })
        except:
            pass

    if not vendor:
        return None

    vendor_name = vendor.get("vendor_name")

    # 1. Fetch all contracts for this vendor
    contracts_cursor = CONTRACTS.find({
        "vendor_name": vendor_name,
        "store_id": store_id,
    }).sort("_id", -1)

    contracts = []
    contract_ids = []
    async for contract in contracts_cursor:
        contract_id = contract.get("contract_id")
        contract_ids.append(contract_id)
        
        contracts.append({
            "contract_id": contract_id,
            "product_name": contract.get("product_name"),
            "quantity": contract.get("quantity"),
            "unit": contract.get("unit"),
            "unit_price": contract.get("unit_price"),
            "tax": contract.get("tax"),
            "total_amount": (contract.get("quantity") or 0) * (contract.get("unit_price") or 0) + (contract.get("tax") or 0),
            "status": contract.get("status"),
            "date_of_delivery": contract.get("date_of_delivery"),
            "category": contract.get("category"),
            "sub_category": contract.get("sub_category"),
            "created_at": serialize_datetime(contract.get("created_at"))
        })

    # 2. Fetch all purchase orders - match ONLY by vendor_name and vendor_id
    purchase_orders_query = {
        "store_id": store_id,
        "$or": [
            {"vendor_name": vendor_name},
            {"vendor_id": vendor.get("vendor_id")}
        ]
    }
    
    purchase_orders_cursor = PURCHASE_ORDERS.find(purchase_orders_query).sort("_id", -1)

    purchase_orders = []
    async for order in purchase_orders_cursor:
        # Normalize status
        raw_received = order.get("received_status", 0)
        received_status = RECEIVED_MAP.get(raw_received, raw_received) if isinstance(raw_received, int) else raw_received

        raw_validation = order.get("validation_status", 0)
        validation_status = VALIDATION_MAP.get(raw_validation, raw_validation) if isinstance(raw_validation, int) else raw_validation

        purchase_orders.append({
            "order_id": order.get("order_id"),
            "contract_id": order.get("contract_id"),
            "product_name": order.get("product_name"),
            "quantity": order.get("quantity"),
            "expected_quantity": order.get("expected_quantity"),
            "received_quantity": order.get("received_quantity"),
            "unit": order.get("unit"),
            "unit_price": order.get("unit_price"),
            "amount": order.get("amount"),
            "delivery_date": order.get("delivery_date"),
            "received_status": received_status,
            "validation_status": validation_status,
            "category": order.get("category"),
            "sub_category": order.get("sub_category"),
            "is_product_damaged": order.get("is_product_damaged", False)
        })

    # 3. Fetch all returns to vendor - match ONLY by vendor_name and vendor_id
    returns_query = {
        "store_id": store_id,
        "$or": [
            {"vendor_name": vendor_name},
            {"vendor_id": vendor.get("vendor_id")}
        ]
    }
    
    returns_cursor = RETURN_TO_VENDOR.find(returns_query).sort("_id", -1)

    returns = []
    async for return_item in returns_cursor:
        raw_status = return_item.get("status", 0)
        status = RETURN_STATUS_MAP.get(raw_status, raw_status) if isinstance(raw_status, int) else raw_status

        returns.append({
            "return_id": return_item.get("return_id"),
            "order_id": return_item.get("order_id"),
            "contract_id": return_item.get("contract_id"),
            "product_name": return_item.get("product_name"),
            "original_quantity": return_item.get("original_quantity"),
            "return_quantity": return_item.get("return_quantity"),
            "unit": return_item.get("unit"),
            "unit_price": return_item.get("unit_price"),
            "return_amount": return_item.get("return_amount"),
            "total_price": return_item.get("total_price"),
            "product_condition": return_item.get("product_condition"),
            "return_reason": return_item.get("return_reason"),
            "status": status,
            "delivery_date": return_item.get("delivery_date"),
            "purchase_date": return_item.get("purchase_date")
        })

    # 4. Calculate summary statistics
    total_purchases = len(purchase_orders)
    total_returns = len(returns)
    total_spent = sum(order.get("amount", 0) for order in purchase_orders)
    total_returned_amount = sum(float(ret.get("return_amount", 0)) for ret in returns)

    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor_name,
        "summary": {
            "total_contracts": len(contracts),
            "total_purchases": total_purchases,
            "total_returns": total_returns,
            "total_spent": total_spent,
            "total_returned_amount": total_returned_amount,
            "net_spent": total_spent - total_returned_amount
        },
        "contracts": contracts,
        "purchase_orders": purchase_orders,
        "returns": returns
    }
