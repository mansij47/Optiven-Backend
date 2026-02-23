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
        
        # ✅ Check ALL orders to determine payment status
        # If ANY order is unpaid/pending, customer status is "Unpaid"
        customer_phone = customer.get("customer_phone")
        store_id_filter = {"customer_phone": customer_phone}
        if store_id:
            store_id_filter["store_id"] = store_id
        
        # Fetch all orders for this customer
        all_orders = await sales_orders_collection.find(store_id_filter).to_list(length=None)
        
        # Check if there are any unpaid orders
        has_unpaid_order = False
        for order in all_orders:
            order_payment_status = order.get("payment_status")
            order_status = order.get("order_status", "0")
            
            # Check if order is unpaid
            if order_payment_status:
                # If payment_status exists, check if it's not "Paid"
                if order_payment_status != "Paid":
                    has_unpaid_order = True
                    break
            else:
                # Fallback: if no payment_status field, check order_status
                # order_status "0" means pending/not sold = unpaid
                if str(order_status) == "0":
                    has_unpaid_order = True
                    break
        
        # Set customer payment status based on whether they have any unpaid orders
        customer["payment_status"] = "Unpaid" if has_unpaid_order else "Paid"
        
        # ✅ Set payment_date only if all orders are paid
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
    # Build match filter to get ONLY orders for this specific customer_id
    match_filter = {"customer_id": customer_id}
    if store_id:
        match_filter["store_id"] = store_id
    
    # First check if customer exists
    customer_check = await sales_orders_collection.find_one(match_filter)
    if not customer_check:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get customer aggregated data by phone number
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},  # Sort by date to get latest order first
        {
            "$group": {
                "_id": "$customer_id",  # ✅ Group by customer_id to get only THIS customer's orders
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
    customer.pop("_id", None)  # Remove _id from grouping, keep original customer_id
    # Keep latest_order_id for Mark as Paid functionality
    
    # Get order history - fetch ONLY orders for this specific customer_id
    orders_cursor = sales_orders_collection.find(match_filter).sort("created_at", -1)
    orders = await orders_cursor.to_list(length=None)
    
    # ✅ Ensure all orders have payment_status field for frontend consistency
    for order in orders:
        if "_id" in order:
            order["_id"] = str(order["_id"])
        
        # Set payment_status if not present
        if "payment_status" not in order or order["payment_status"] is None:
            order_status = order.get("order_status", "0")
            # If order is sold (order_status="1"), mark as Paid
            # If order is pending (order_status="0"), mark as Unpaid/Pending
            order["payment_status"] = "Paid" if order_status == "1" else "Unpaid"
    
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
                # ✅ Group by customer_id to show only individual customers, not all orders from same phone
                "_id": "$customer_id",
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
        
        # ✅ Check ALL orders to determine payment status
        # If ANY order is unpaid/pending, customer status is "Unpaid"
        customer_phone = customer.get("customer_phone")
        store_id_filter = {"customer_phone": customer_phone}
        if store_id:
            store_id_filter["store_id"] = store_id
        
        # Fetch all orders for this customer
        all_orders = await sales_orders_collection.find(store_id_filter).to_list(length=None)
        
        # Check if there are any unpaid orders
        has_unpaid_order = False
        for order in all_orders:
            order_payment_status = order.get("payment_status")
            order_status = order.get("order_status", "0")
            
            # Check if order is unpaid
            if order_payment_status:
                # If payment_status exists, check if it's not "Paid"
                if order_payment_status != "Paid":
                    has_unpaid_order = True
                    break
            else:
                # Fallback: if no payment_status field, check order_status
                # order_status "0" means pending/not sold = unpaid
                if str(order_status) == "0":
                    has_unpaid_order = True
                    break
        
        # Set customer payment status based on whether they have any unpaid orders
        customer["payment_status"] = "Unpaid" if has_unpaid_order else "Paid"
    
        # ✅ Set payment_date only if all orders are paid
        if customer["payment_status"] == "Paid":
            customer["payment_date"] = customer.get("payment_date", None)
        else:
            customer["payment_date"] = None
        
        customer.pop("all_products", None)
        customer.pop("latest_order_status", None)
        customer.pop("latest_payment_status", None)
        customer.pop("_id", None)  # Remove _id from grouping, keep original customer_id
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


async def create_customer(customer_data: dict, store_id: str) -> dict:
    """
    Create a new customer record.
    Note: Customers are primarily tracked through orders, so this creates a placeholder customer.
    """
    # Check if customer already exists with this phone number
    existing_customer = await sales_orders_collection.find_one(
        {"customer_phone": customer_data.get("customer_phone"), "store_id": store_id}
    )
    
    if existing_customer:
        raise HTTPException(
            status_code=400, 
            detail="Customer with this phone number already exists"
        )
    
    # Generate customer ID
    import uuid
    customer_id = f"CUST{str(uuid.uuid4())[:8].upper()}"
    
    # Create customer document
    customer_doc = {
        "customer_id": customer_id,
        "customer_name": customer_data.get("customer_name"),
        "customer_email": customer_data.get("customer_email"),
        "customer_phone": customer_data.get("customer_phone"),
        "delivery_address": customer_data.get("delivery_address"),
        "gst_number": customer_data.get("gst_number"),
        "store_id": store_id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    # Store in a separate Customers collection for direct customer management
    customers_collection = db["Customers"]
    await customers_collection.insert_one(customer_doc)
    
    return {
        "customer_id": customer_id,
        "message": "Customer created successfully"
    }


async def update_customer(customer_phone: str, update_data: dict, store_id: str) -> dict:
    """
    Update customer information across all their orders.
    Uses customer_phone as the primary identifier.
    """
    # Remove None values and fields that shouldn't be updated
    update_data = {k: v for k, v in update_data.items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Add updated_at timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update all orders with this customer phone
    result = await sales_orders_collection.update_many(
        {"customer_phone": customer_phone, "store_id": store_id},
        {"$set": update_data}
    )
    
    # Also update in Customers collection if exists
    customers_collection = db["Customers"]
    await customers_collection.update_one(
        {"customer_phone": customer_phone, "store_id": store_id},
        {"$set": update_data},
        upsert=False
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return {
        "message": "Customer updated successfully",
        "orders_updated": result.modified_count
    }


async def delete_customer(customer_phone: str, store_id: str) -> dict:
    """
    Delete customer and all associated orders.
    WARNING: This is a destructive operation.
    """
    # Check if customer has orders
    orders_count = await sales_orders_collection.count_documents(
        {"customer_phone": customer_phone, "store_id": store_id}
    )
    
    if orders_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Delete all orders for this customer
    delete_result = await sales_orders_collection.delete_many(
        {"customer_phone": customer_phone, "store_id": store_id}
    )
    
    # Delete from Customers collection
    customers_collection = db["Customers"]
    await customers_collection.delete_one(
        {"customer_phone": customer_phone, "store_id": store_id}
    )
    
    # Delete from CustomerHistory collection
    await customer_history_collection.delete_many(
        {"customer_phone": customer_phone, "store_id": store_id}
    )
    
    return {
        "message": "Customer and all associated orders deleted successfully",
        "orders_deleted": delete_result.deleted_count
    }
