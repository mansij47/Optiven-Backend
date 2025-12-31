from typing import List, Optional
from app.db import db
from app.models.sales_model import CustomerModel
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

sales_orders_collection = db["SalesOrders"]
customer_history_collection = db["CustomerHistory"]


async def get_all_customers(store_id: Optional[str] = None) -> List[CustomerModel]:
    """
    Get all customers with aggregated purchase data from sales orders.
    Groups customers by phone number (primary) or email to prevent duplicates.
    """
    # Build match filter
    match_filter = {}
    if store_id:
        match_filter["store_id"] = store_id
    
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},  # Sort by date to get latest order first
        {
            "$group": {
                # ✅ Group by phone number (primary key for customer identity)
                "_id": "$customer_phone",
                "customer_id": {"$first": "$customer_id"},  # Keep first customer_id for reference
                "customer_name": {"$first": "$customer_name"},
                "customer_email": {"$first": "$customer_email"},
                "customer_phone": {"$first": "$customer_phone"},
                "delivery_address": {"$first": "$delivery_address"},
                "gst_number": {"$first": "$gst_number"},
                "store_id": {"$first": "$store_id"},
                "total_orders": {"$sum": 1},
                "total_purchase_amount": {"$sum": "$total_order_price"},
                "first_order_date": {"$min": "$created_at"},
                "last_order_date": {"$max": "$created_at"},
                "latest_order_status": {"$first": "$order_status"},  # Get latest order status
                "latest_payment_status": {"$first": "$payment_status"},  # ✅ Get payment status from latest order
                "latest_order_id": {"$first": "$order_id"},  # ✅ Get latest order ID for mark as paid
                "payment_date": {"$max": "$sold_at"},  # ✅ Get most recent payment date
                "all_products": {"$push": "$products"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "customer_id": 1,  # Use the first customer_id as reference
                "customer_name": 1,
                "customer_email": 1,
                "customer_phone": 1,
                "delivery_address": 1,
                "gst_number": 1,
                "store_id": 1,
                "total_orders": 1,
                "total_purchase_amount": 1,
                "first_order_date": 1,
                "last_order_date": 1,
                "latest_order_status": 1,
                "latest_payment_status": 1,
                "latest_order_id": 1,
                "payment_date": 1,
                "all_products": 1
            }
        },
        {"$sort": {"last_order_date": -1}}
    ]
    
    customers_cursor = sales_orders_collection.aggregate(pipeline)
    customers = await customers_cursor.to_list(length=None)
    
    # Calculate total purchase quantity and amount (with tax) from all products
    for customer in customers:
        total_quantity = 0
        total_amount_with_tax = 0.0
        all_products = customer.get("all_products", [])
        
        for product_list in all_products:
            for product in product_list:
                # Try both quantity and order_quantity fields
                quantity = product.get("quantity") or product.get("order_quantity", 0)
                if isinstance(quantity, str):
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        quantity = 0
                
                # Calculate product total with tax
                unit_price = float(product.get("unit_price", 0))
                tax = float(product.get("tax", 0))
                
                
                
                subtotal = quantity * unit_price
                tax_amount = (subtotal * tax) / 100
                product_total = subtotal + tax_amount
                
                total_quantity += quantity
                total_amount_with_tax += product_total
        
       
        customer["total_purchase_quantity"] = total_quantity
        customer["total_purchase_amount"] = round(total_amount_with_tax, 2)
        
        # ✅ Use payment_status from the latest order
        # If payment_status is not set (old orders), default based on order_status
        payment_status = customer.get("latest_payment_status")
        if payment_status:
            # "Paid" stays "Paid", "Pay Later" becomes "Unpaid" for display
            customer["payment_status"] = "Paid" if payment_status == "Paid" else "Unpaid"
        else:
            # Fallback for old orders without payment_status field
            order_status = customer.get("latest_order_status", "0")
            customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
        
        # ✅ Set payment_date only if status is Paid, otherwise None
        if customer["payment_status"] == "Paid":
            customer["payment_date"] = customer.get("payment_date", None)
        else:
            customer["payment_date"] = None
        
        # Remove temporary fields
        customer.pop("all_products", None)
        customer.pop("latest_order_status", None)
        customer.pop("latest_payment_status", None)
        # Keep latest_order_id for Mark as Paid functionality
        
        # Ensure datetime objects
        if customer.get("first_order_date"):
            customer["first_order_date"] = customer["first_order_date"]
        if customer.get("last_order_date"):
            customer["last_order_date"] = customer["last_order_date"]
        
        # Set created_at and updated_at
        customer["created_at"] = customer.get("first_order_date", datetime.utcnow())
        customer["updated_at"] = customer.get("last_order_date", datetime.utcnow())
    
    return [CustomerModel(**customer) for customer in customers]


async def get_customer_by_id(customer_id: str, store_id: Optional[str] = None) -> dict:
    """
    Get detailed customer information including order history.
    Finds customer by customer_id and aggregates all orders from that phone number.
    """
    # First, find the customer's phone number from the given customer_id
    customer_order = await sales_orders_collection.find_one(
        {"customer_id": customer_id},
        {"customer_phone": 1, "_id": 0}
    )
    
    if not customer_order or not customer_order.get("customer_phone"):
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer_phone = customer_order["customer_phone"]
    
    # Build match filter to get ALL orders with this phone number
    match_filter = {"customer_phone": customer_phone}
    if store_id:
        match_filter["store_id"] = store_id
    
    # Get customer aggregated data by phone number
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},  # Sort by date to get latest order first
        {
            "$group": {
                "_id": "$customer_phone",  # ✅ Group by phone to aggregate all orders
                "customer_id": {"$first": "$customer_id"},
                "customer_name": {"$first": "$customer_name"},
                "customer_email": {"$first": "$customer_email"},
                "customer_phone": {"$first": "$customer_phone"},
                "delivery_address": {"$first": "$delivery_address"},
                "gst_number": {"$first": "$gst_number"},
                "store_id": {"$first": "$store_id"},
                "total_orders": {"$sum": 1},
                "total_purchase_amount": {"$sum": "$total_order_price"},
                "first_order_date": {"$min": "$created_at"},
                "last_order_date": {"$max": "$created_at"},
                "latest_order_status": {"$first": "$order_status"},  # Get latest order status
                "latest_payment_status": {"$first": "$payment_status"},  # ✅ Get payment status from latest order
                "payment_date": {"$max": "$sold_at"},  # ✅ Get most recent payment date
                "all_products": {"$push": "$products"}
            }
        }
    ]
    
    customers_cursor = sales_orders_collection.aggregate(pipeline)
    customers = await customers_cursor.to_list(length=1)
    
    if not customers:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = customers[0]
    
    # Calculate total purchase quantity and amount (with tax)
    total_quantity = 0
    total_amount_with_tax = 0.0
    all_products = customer.get("all_products", [])
    
    for product_list in all_products:
        for product in product_list:
            # Try both quantity and order_quantity fields
            quantity = product.get("quantity") or product.get("order_quantity", 0)
            if isinstance(quantity, str):
                try:
                    quantity = int(quantity)
                except (ValueError, TypeError):
                    quantity = 0
            
            # Calculate product total with tax
            unit_price = float(product.get("unit_price", 0))
            tax = float(product.get("tax", 0))
            
            subtotal = quantity * unit_price
            tax_amount = (subtotal * tax) / 100
            product_total = subtotal + tax_amount
            
            total_quantity += quantity
            total_amount_with_tax += product_total
    
    customer["total_purchase_quantity"] = total_quantity
    customer["total_purchase_amount"] = round(total_amount_with_tax, 2)
    
    # ✅ Use payment_status from the latest order
    # If payment_status is not set (old orders), default based on order_status
    payment_status = customer.get("latest_payment_status")
    if payment_status:
        # "Paid" stays "Paid", "Pay Later" becomes "Unpaid" for display
        customer["payment_status"] = "Paid" if payment_status == "Paid" else "Unpaid"
    else:
        # Fallback for old orders without payment_status field
        order_status = customer.get("latest_order_status", "0")
        customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
    
    # ✅ Set payment_date only if status is Paid, otherwise None
    if customer["payment_status"] == "Paid":
        customer["payment_date"] = customer.get("payment_date", None)
    else:
        customer["payment_date"] = None
    
    customer.pop("all_products", None)
    customer.pop("latest_order_status", None)
    customer.pop("latest_payment_status", None)
    # Keep latest_order_id for Mark as Paid functionality
    
    # Get order history - fetch ALL orders with this phone number
    orders_cursor = sales_orders_collection.find(match_filter).sort("created_at", -1)
    orders = await orders_cursor.to_list(length=None)
    
    # Convert ObjectId to string in orders
    for order in orders:
        if "_id" in order:
            order["_id"] = str(order["_id"])
    
    customer["customer_id"] = customer.pop("_id")
    customer["orders"] = orders
    customer["created_at"] = customer.get("first_order_date", datetime.utcnow())
    customer["updated_at"] = customer.get("last_order_date", datetime.utcnow())
    
    return customer


async def search_customers(query: str, store_id: Optional[str] = None) -> List[CustomerModel]:
    """
    Search customers by name, email, or phone.
    """
    # Build match filter
    match_filter = {
        "$or": [
            {"customer_name": {"$regex": query, "$options": "i"}},
            {"customer_email": {"$regex": query, "$options": "i"}},
            {"customer_phone": {"$regex": query, "$options": "i"}}
        ]
    }
    
    if store_id:
        match_filter["store_id"] = store_id
    
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},  # Sort by date to get latest order first
        {
            "$group": {
                # ✅ Group by phone number to aggregate all orders from same customer
                "_id": "$customer_phone",
                "customer_id": {"$first": "$customer_id"},
                "customer_name": {"$first": "$customer_name"},
                "customer_email": {"$first": "$customer_email"},
                "customer_phone": {"$first": "$customer_phone"},
                "delivery_address": {"$first": "$delivery_address"},
                "gst_number": {"$first": "$gst_number"},
                "store_id": {"$first": "$store_id"},
                "total_orders": {"$sum": 1},
                "total_purchase_amount": {"$sum": "$total_order_price"},
                "first_order_date": {"$min": "$created_at"},
                "last_order_date": {"$max": "$created_at"},
                "latest_order_status": {"$first": "$order_status"},  # Get latest order status
                "latest_payment_status": {"$first": "$payment_status"},  # ✅ Get payment status from latest order
                "latest_order_id": {"$first": "$order_id"},  # ✅ Get latest order ID for mark as paid
                "payment_date": {"$max": "$sold_at"},  # ✅ Get most recent payment date
                "all_products": {"$push": "$products"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "customer_id": 1,
                "customer_name": 1,
                "customer_email": 1,
                "customer_phone": 1,
                "delivery_address": 1,
                "gst_number": 1,
                "store_id": 1,
                "total_orders": 1,
                "total_purchase_amount": 1,
                "first_order_date": 1,
                "last_order_date": 1,
                "latest_order_status": 1,
                "latest_payment_status": 1,
                "latest_order_id": 1,
                "payment_date": 1,
                "all_products": 1
            }
        },
        {"$sort": {"last_order_date": -1}}
    ]
    
    customers_cursor = sales_orders_collection.aggregate(pipeline)
    customers = await customers_cursor.to_list(length=None)
    
    # Calculate total purchase quantity and amount (with tax)
    for customer in customers:
        total_quantity = 0
        total_amount_with_tax = 0.0
        all_products = customer.get("all_products", [])
        
        for product_list in all_products:
            for product in product_list:
                # Try both quantity and order_quantity fields
                quantity = product.get("quantity") or product.get("order_quantity", 0)
                if isinstance(quantity, str):
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        quantity = 0
                
                # Calculate product total with tax
                unit_price = float(product.get("unit_price", 0))
                tax = float(product.get("tax", 0))
                
                subtotal = quantity * unit_price
                tax_amount = (subtotal * tax) / 100
                product_total = subtotal + tax_amount
                
                total_quantity += quantity
                total_amount_with_tax += product_total
        
        customer["total_purchase_quantity"] = total_quantity
        customer["total_purchase_amount"] = round(total_amount_with_tax, 2)
        
    # ✅ Use payment_status from the latest order
    # If payment_status is not set (old orders), default based on order_status
    payment_status = customer.get("latest_payment_status")
    if payment_status:
        # "Paid" stays "Paid", "Pay Later" becomes "Unpaid" for display
        customer["payment_status"] = "Paid" if payment_status == "Paid" else "Unpaid"
    else:
        # Fallback for old orders without payment_status field
        order_status = customer.get("latest_order_status", "0")
        customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
    
    # ✅ Set payment_date only if status is Paid, otherwise None
    if customer["payment_status"] == "Paid":
        customer["payment_date"] = customer.get("payment_date", None)
    else:
        customer["payment_date"] = None
    
    customer.pop("all_products", None)
    customer.pop("latest_order_status", None)
    customer.pop("latest_payment_status", None)
    # Keep latest_order_id for Mark as Paid functionality

async def sync_order_to_customer_history(order_id: str, store_id: str):
    """
    Sync a sold order to CustomerHistory collection.
    Stores complete order data with payment date tracking.
    - For Unpaid orders (order_status="0"): uses created_at as order_date
    - For Paid orders (order_status="1"): uses sold_at as payment_date
    """
    # Fetch the order from SalesOrders
    order = await sales_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id},
        {"_id": 0}  # Exclude MongoDB _id
    )
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    # Prepare history document with payment tracking
    order_status = order.get("order_status", "0")
    
    history_doc = {
        "order_id": order_id,
        "store_id": store_id,
        "customer_id": order.get("customer_id"),
        "customer_name": order.get("customer_name"),
        "customer_email": order.get("customer_email"),
        "customer_phone": order.get("customer_phone"),
        "delivery_address": order.get("delivery_address"),
        "gst_number": order.get("gst_number"),
        "products": order.get("products", []),
        "total_order_price": order.get("total_order_price", 0.0),
        "payment_status": "Paid" if order_status == "1" else "Unpaid",
        "order_date": order.get("created_at", datetime.utcnow()),  # ✅ When order was created (unpaid date)
        "payment_date": order.get("sold_at") if order_status == "1" else None,  # ✅ When order was paid (sold date)
        "created_at": order.get("created_at", datetime.utcnow()),
        "updated_at": order.get("updated_at", datetime.utcnow()),
        "synced_at": datetime.utcnow()  # When this record was synced to history
    }
    
    # Upsert: update if exists, insert if new
    result = await customer_history_collection.update_one(
        {"order_id": order_id, "store_id": store_id},
        {"$set": history_doc},
        upsert=True
    )
    
    return {
        "order_id": order_id,
        "synced": True,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "upserted": result.upserted_id is not None
    }


async def get_customer_history(customer_phone: str, store_id: Optional[str] = None) -> List[dict]:
    """
    Get complete order history for a customer from CustomerHistory collection.
    Groups all orders by customer phone number.
    """
    match_filter = {"customer_phone": customer_phone}
    if store_id:
        match_filter["store_id"] = store_id
    
    cursor = customer_history_collection.find(match_filter).sort("created_at", -1)
    history = await cursor.to_list(length=None)
    
    # Convert ObjectId to string if exists
    for record in history:
        if "_id" in record:
            record["_id"] = str(record["_id"])
    
    return history
