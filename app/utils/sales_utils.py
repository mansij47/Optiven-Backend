import re
from fastapi import HTTPException
from app.db import db  # Adjust import if your db connection is elsewhere
from app.utils.tax_utils import calculate_tax_amount, calculate_product_total_with_tax

async def generate_order_id():
    last_order = await db.SalesOrders.find_one(
        {"order_id": {"$regex": "^ORD\\d{3}$"}},{"_id": 0},
        sort=[("order_id", -1)]
    )

    if last_order and last_order.get("order_id", "").startswith("ORD"):
        try:
            last_number = int(last_order["order_id"][3:])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1

    return f"ORD{new_number:03d}"

def build_product_detail(inventory_item: dict, product_id: str, unit_price: float,
                         product_tax: float, order_quantity: int, inventory_quantity: int, 
                         consumer_return_conditions: list, selling_price: float = None,
                         seller_return_conditions: list = None, is_seller_returnable: bool = False,
                         is_consumer_returnable: bool = False):
    # ✅ Use selling_price for customer orders (what customer pays), fallback to unit_price if not provided
    price_for_customer = selling_price if selling_price and selling_price > 0 else unit_price
    
    line_total = price_for_customer * order_quantity
    tax = calculate_tax_amount(price_for_customer, product_tax, order_quantity)

    # Set default return conditions if none provided
    default_conditions = ["Wrong product", "Damaged on arrival", "Quality issues"]
    return_conditions = consumer_return_conditions if consumer_return_conditions else default_conditions
    
    # ✅ Default seller return conditions if none provided
    seller_conditions = seller_return_conditions if seller_return_conditions else []

    product_detail = {
        "product_id": product_id,
        "product_name": inventory_item["product_name"],
        "unit_price": price_for_customer,  # ✅ Store selling_price as unit_price for customer orders
        "selling_price": selling_price ,  # Store customer-paid price
        "category": inventory_item["category"],
        "order_quantity": order_quantity,
        "inventory_quantity": inventory_quantity,
        "tax": product_tax,
        "unit": inventory_item.get("unit", ""),
        "consumer_return_conditions": return_conditions,
        "seller_return_conditions": seller_conditions,
        "is_seller_returnable": is_seller_returnable,
        "is_consumer_returnable": is_consumer_returnable
    }

    return product_detail, line_total + tax


# -----------------------------------------
# Function to generate sequential customer_id starting from CUT001
# -----------------------------------------
async def generate_customer_id():
    # Find the last customer_id starting with CUT
    last_order = await db.SalesOrders.find_one(
        {"customer_id": {"$regex": "^CUST"}},
        sort=[("customer_id", -1)]
    )
    
    if last_order and "customer_id" in last_order:
        # Extract numeric part
        match = re.search(r"CUST(\d+)", last_order["customer_id"])
        if match:
            next_num = int(match.group(1)) + 1
        else:
            next_num = 1
    else:
        next_num = 1

    return f"CUST{str(next_num).zfill(3)}"


async def generate_request_id():
    last_request = await db.RequestedOrders.find_one(
        {"request_id": {"$regex": "^REQ\\d{3}$"}},{"_id": 0},
        sort=[("request_id", -1)]
    )
    if last_request and last_request.get("request_id", "").startswith("REQ"):
        try:
            last_number = int(last_request["request_id"][3:])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1

    return f"REQ{new_number:03d}"


def parse_status_string(status: str) -> str:
    if status == "0":
        return "received"
    elif status == "1":
        return "sold"
    return status  # or "unknown"

def parse_return_status(status: int) -> str:
    return "return" if status == 0 else "procurement"

async def fetch_inventory_details(product_id: str, store_id: str):
    inventory_item = await db.Inventory.find_one({
        "product_id": product_id,
        "store_id": store_id
    }, {"_id": 0})

    if not inventory_item:
        raise HTTPException(status_code=404, detail=f"Product with ID {product_id} not found in inventory.")

    # ✅ Calculate average selling_price from ProductItems (source of truth for customer pricing)
    items_cursor = db.ProductItems.find({
        "product_id": product_id,
        "store_id": store_id,
        "status": "available"
    }, {"unit_price": 1, "selling_price": 1, "_id": 0})
    
    items = await items_cursor.to_list(length=None)
    
    unit_price = 0.0
    average_selling_price = 0.0
    
    if items:
        total_unit_price = 0.0
        total_selling_price = 0.0
        valid_count = 0
        
        for item in items:
            try:
                # Get unit_price (cost price)
                price_value = item.get("unit_price", 0)
                if isinstance(price_value, str):
                    price_value = float(price_value) if price_value and price_value != "0" else 0.0
                else:
                    price_value = float(price_value)
                
                # Get selling_price (what customer pays)
                selling_value = item.get("selling_price", 0)
                if isinstance(selling_value, str):
                    selling_value = float(selling_value) if selling_value and selling_value != "0" else 0.0
                else:
                    selling_value = float(selling_value)
                
                if price_value > 0:
                    total_unit_price += price_value
                    total_selling_price += selling_value if selling_value > 0 else price_value
                    valid_count += 1
            except (ValueError, TypeError):
                continue
        
        if valid_count > 0:
            unit_price = round(total_unit_price / valid_count, 2)
            average_selling_price = round(total_selling_price / valid_count, 2)
    
    # If still 0, try Inventory table as fallback
    if unit_price == 0:
        try:
            inv_price = inventory_item.get("unit_price", 0)
            if isinstance(inv_price, str):
                unit_price = float(inv_price) if inv_price and inv_price != "0" else 0.0
            else:
                unit_price = float(inv_price)
        except (ValueError, TypeError):
            unit_price = 0.0
    
    if unit_price == 0:
        raise HTTPException(status_code=500, detail=f"Invalid unit price for product ID {product_id}.")

    try:
        product_tax = float(inventory_item.get("tax", 0))
    except (ValueError, TypeError):
        product_tax = 0

    # Get available quantity from ProductItems
    inventory_quantity = await db.ProductItems.count_documents({
        "product_id": product_id,
        "store_id": store_id,
        "status": "available"
    })
    
    consumer_return_conditions = inventory_item.get("consumer_return_conditions", [])
    
    # ✅ Include seller returnability fields for proper return handling
    seller_return_conditions = inventory_item.get("seller_return_conditions", [])
    is_seller_returnable = inventory_item.get("is_seller_returnable", False)
    
    # ✅ Auto-correct: if seller_return_conditions exist but flag is False, correct it
    if seller_return_conditions and not is_seller_returnable:
        is_seller_returnable = True
        print(f"[AUTO-CORRECT] Product {product_id}: seller_return_conditions exist but is_seller_returnable was False. Setting to True.")
    
    is_consumer_returnable = inventory_item.get("is_consumer_returnable", False)
    
    # ✅ Auto-correct: if consumer_return_conditions exist but flag is False, correct it
    if consumer_return_conditions and not is_consumer_returnable:
        is_consumer_returnable = True
        print(f"[AUTO-CORRECT] Product {product_id}: consumer_return_conditions exist but is_consumer_returnable was False. Setting to True.")

    return {
        "inventory_item": inventory_item,
        "unit_price": unit_price,
        "average_selling_price": average_selling_price,
        "product_tax": product_tax,
        "inventory_quantity": inventory_quantity,
        "consumer_return_conditions": consumer_return_conditions,
        "seller_return_conditions": seller_return_conditions,
        "is_seller_returnable": is_seller_returnable,
        "is_consumer_returnable": is_consumer_returnable
    }

# --- Helper function to generate new return_id ---
async def generate_return_id():
    latest = await db.ReturnOrders.find_one({},{"_id": 0}, sort=[("return_id", -1)])
    if latest and "return_id" in latest:
        last_num = int(latest["return_id"].replace("RET", ""))
        return f"RET{last_num + 1:03d}"
    else:
        return "RET001"
    
# --- Helper function to enrich products with item-level details ---
async def enrich_products(products: list, return_quantity: int, reason: str, order_id: str = None, store_id: str = None):
    """
    Enrich products with item-level tracking including:
    - Specific item IDs being returned
    - Vendor information per item
    - Warranty details per item
    - Return conditions per item
    """
    print("Incoming products:", products)
    enriched_products = []
    skipped_products = []  # Track products that are skipped
    total_amount = 0.0

    for product in products:
        product_id = product.get("product_id")
        product_name = product.get("product_name")
        # ✅ Use selling_price (what customer paid) instead of unit_price (cost price)
        selling_price = product.get("selling_price", 0.0)
        unit_price = product.get("unit_price", 0.0)  # Keep for reference
        tax = product.get("tax", 0.0)

        if not product_id or not product_name:
            skipped_products.append({
                "product_id": product_id,
                "reason": "Missing product_id or product_name"
            })
            continue

        # Fetch additional inventory info
        inventory = await db.Inventory.find_one({"product_id": product_id}, {"_id": 0})
        if not inventory:
            skipped_products.append({
                "product_id": product_id,
                "reason": "Product not found in Inventory"
            })
            continue

        # ✅ Use return conditions from the SOLD ORDER (what was valid at time of sale)
        # NOT from current Inventory (which may have changed)
        product_return_conditions = product.get("consumer_return_conditions", [])
        is_customer_returnable = product.get("is_consumer_returnable", False)
        
        # ✅ Get seller returnability from the SOLD ORDER (what was valid at time of sale)
        seller_return_conditions = product.get("seller_return_conditions", [])
        is_seller_returnable = product.get("is_seller_returnable", False)
        
        # Only fallback to inventory if sold order doesn't have the data
        if not product_return_conditions:
            product_return_conditions = inventory.get("consumer_return_conditions", [])
        if not is_customer_returnable:
            is_customer_returnable = inventory.get("is_consumer_returnable", False)
        
        # ✅ Fallback to inventory for seller returnability if not in sold order
        if not seller_return_conditions:
            seller_return_conditions = inventory.get("seller_return_conditions", [])
        if not is_seller_returnable:
            is_seller_returnable = inventory.get("is_seller_returnable", False)
        
        # ✅ Auto-correct: if seller_return_conditions exist but flag is False, correct it
        if seller_return_conditions and not is_seller_returnable:
            is_seller_returnable = True
            print(f"[AUTO-CORRECT in enrich_products] Product {product_id}: seller_return_conditions exist but is_seller_returnable was False. Setting to True.")

        print(f"Checking {product_id}: is_customer_returnable={is_customer_returnable}, conditions={product_return_conditions}, reason={reason}")
        print(f"[DEBUG] Seller returnability: is_seller_returnable={is_seller_returnable}, seller_conditions={seller_return_conditions}")

        # Validate return eligibility based on conditions from sold order
        if not product_return_conditions:
            skipped_products.append({
                "product_id": product_id,
                "reason": "No return conditions found for the product"
            })
            continue
        
        if reason not in product_return_conditions:
            skipped_products.append({
                "product_id": product_id,
                "reason": f"Reason '{reason}' not in return conditions: {product_return_conditions}"
            })
            continue
        
        try:
            return_quantity = int(return_quantity)
            selling_price = float(selling_price) if selling_price else float(unit_price)  # Fallback to unit_price if no selling_price
            unit_price = float(unit_price)
            tax = float(tax)
        except (ValueError, TypeError):
            skipped_products.append({
                "product_id": product_id,
                "reason": "Invalid return_quantity, selling_price or tax format"
            })
            continue

        # ✅ ITEM-BASED APPROACH: Get specific item IDs and their details
        item_ids_to_return = product.get("item_ids", [])
        items_details = []
        
        if order_id and store_id and item_ids_to_return:
            # Fetch actual item details from ProductItems collection
            for item_id in item_ids_to_return[:return_quantity]:  # Only get items being returned
                item = await db.ProductItems.find_one({
                    "item_id": item_id,
                    "product_id": product_id,
                    "store_id": store_id
                }, {"_id": 0})
                
                if item:
                    # ✅ Get selling_price from the actual sold item (price at time of sale)
                    item_selling_price = item.get("selling_price", selling_price)
                    
                    items_details.append({
                        "item_id": item_id,
                        "vendor_id": item.get("vendor_id"),
                        "vendor_name": item.get("vendor_name", "Unknown"),
                        "contract_id": item.get("contract_id"),
                        "purchase_date": item.get("purchase_date"),
                        "delivery_date": item.get("delivery_date"),
                        "unit_price": item.get("unit_price", unit_price),
                        "selling_price": item_selling_price,  # ✅ Actual selling price
                        "batch_number": item.get("batch_number"),
                        "serial_number": item.get("serial_number"),
                        "has_warranty": item.get("has_warranty", False),
                        "warranty_tenure": item.get("warranty_tenure", 0),
                        "warranty_unit": item.get("warranty_unit", "months"),
                        "is_consumer_returnable": item.get("is_consumer_returnable", is_customer_returnable),
                        "consumer_return_conditions": item.get("consumer_return_conditions", product_return_conditions),
                        "is_seller_returnable": item.get("is_seller_returnable", is_seller_returnable),  # ✅ Use from sold order
                        "seller_return_conditions": item.get("seller_return_conditions", seller_return_conditions)  # ✅ Use from sold order
                    })

        # ✅ Calculate tax-inclusive return amount using SELLING_PRICE (what customer paid)
        # Returns: quantity × (selling_price + tax_amount_per_unit)
        item_amount = calculate_product_total_with_tax(selling_price, tax, return_quantity)
        total_amount += item_amount

        # Build enriched product with item-level details
        enriched_product = {
            "product_id": product_id,
            "product_name": product_name,
            "category": inventory.get("category", product.get("category")),
            "sub_category": inventory.get("sub_category", product.get("sub_category")),
            "unit": inventory.get("unit", product.get("unit", "pcs")),
            "return_quantity": return_quantity,
            "unit_price": unit_price,  # Cost price (for reference)
            "selling_price": selling_price,  # ✅ Actual selling price (what customer paid)
            "tax": tax,
            "total_price": item_amount,
            "return_amount": str(item_amount),
            "original_quantity": product.get("order_quantity", return_quantity),
            "is_customer_returnable": is_customer_returnable,
            "consumer_return_conditions": product_return_conditions,  # ✅ Use conditions from sold order
            "is_seller_returnable": is_seller_returnable,  # ✅ Use from sold order (with fallback and auto-correct)
            "seller_return_conditions": seller_return_conditions,  # ✅ Use from sold order (with fallback)
            "return_reason": reason
        }
        
        # ✅ Add item-level tracking information
        if items_details:
            enriched_product["item_ids"] = [item["item_id"] for item in items_details]
            enriched_product["items"] = items_details
            
            # Use vendor info from first item (or aggregate if needed)
            if items_details[0].get("vendor_id"):
                enriched_product["vendor_id"] = items_details[0]["vendor_id"]
                enriched_product["vendor_name"] = items_details[0]["vendor_name"]
                enriched_product["contract_id"] = items_details[0]["contract_id"]
                enriched_product["purchase_date"] = items_details[0]["purchase_date"]
                enriched_product["delivery_date"] = items_details[0]["delivery_date"]
                enriched_product["has_warranty"] = items_details[0]["has_warranty"]
                enriched_product["warranty_tenure"] = items_details[0]["warranty_tenure"]
                enriched_product["warranty_unit"] = items_details[0]["warranty_unit"]
        else:
            # Fallback: If no item details, try to get from product or use defaults
            enriched_product["item_ids"] = item_ids_to_return[:return_quantity]
            enriched_product["vendor_name"] = product.get("vendor_name", "Unknown")
            enriched_product["has_warranty"] = product.get("has_warranty", False)
            enriched_product["warranty_tenure"] = product.get("warranty_tenure", 0)
            enriched_product["warranty_unit"] = product.get("warranty_unit", "months")

        enriched_products.append(enriched_product)

    print("Enriched Products:", enriched_products)
    print("Skipped Products:", skipped_products)

    return enriched_products, total_amount, skipped_products


