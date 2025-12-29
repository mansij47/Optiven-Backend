from typing import List, Optional
from app.db import db
from app.models.sales_model import CustomerModel
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime

sales_orders_collection = db["SalesOrders"]


async def get_all_customers(store_id: Optional[str] = None) -> List[CustomerModel]:
    """
    Get all customers with aggregated purchase data from sales orders.
    Groups customers by customer_id and aggregates their total orders, purchase amount, and quantity.
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
                "_id": "$customer_id",
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
                "all_products": {"$push": "$products"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "customer_id": "$_id",
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
        
        # Convert order_status to payment_status: "1" = Paid, "0" = Unpaid
        order_status = customer.get("latest_order_status", "0")
        customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
        
        # Remove temporary fields
        customer.pop("all_products", None)
        customer.pop("latest_order_status", None)
        
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
    """
    # Build match filter
    match_filter = {"customer_id": customer_id}
    if store_id:
        match_filter["store_id"] = store_id
    
    # Get customer aggregated data
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1}},  # Sort by date to get latest order first
        {
            "$group": {
                "_id": "$customer_id",
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
    
    # Convert order_status to payment_status: "1" = Paid, "0" = Unpaid
    order_status = customer.get("latest_order_status", "0")
    customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
    
    customer.pop("all_products", None)
    customer.pop("latest_order_status", None)
    
    # Get order history
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
                "_id": "$customer_id",
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
                "all_products": {"$push": "$products"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "customer_id": "$_id",
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
        
        # Convert order_status to payment_status: "1" = Paid, "0" = Unpaid
        order_status = customer.get("latest_order_status", "0")
        customer["payment_status"] = "Paid" if str(order_status) == "1" else "Unpaid"
        
        customer.pop("all_products", None)
        customer.pop("latest_order_status", None)
        
        customer["created_at"] = customer.get("first_order_date", datetime.utcnow())
        customer["updated_at"] = customer.get("last_order_date", datetime.utcnow())
    
    return [CustomerModel(**customer) for customer in customers]
