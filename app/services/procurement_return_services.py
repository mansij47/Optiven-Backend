from app.db import db
from fastapi import HTTPException
from app.models.procurement_models import ReturnToVendorResponse

return_collection = db["ReturnToVendor"]

status_map = {
    0: "Returned",
    1: "Disabled",
    2: "Pending"
}

# # ✅ List of Return To Vendor
async def get_all_returns(store_id: str):
    try:
        # Fetch and sort in reverse (_id descending → newest first)
        returns_cursor = (
            return_collection.find({"store_id": store_id}, {"_id": 0})
            .sort("_id", -1)
        )

        returns = []
        async for item in returns_cursor:
            # Normalize status
            raw_status = item.get("status", 0)
            item["status"] = (
                status_map.get(raw_status, raw_status)
                if not isinstance(raw_status, str)
                else raw_status
            )
            
            # ✅ Fetch item details from ProductItems if returnable_item_ids exist
            returnable_item_ids = item.get("returnable_item_ids", [])
            if returnable_item_ids:
                items_details = []
                for item_id in returnable_item_ids:
                    item_doc = await db.ProductItems.find_one(
                        {"item_id": item_id, "store_id": store_id},
                        {"_id": 0}
                    )
                    if item_doc:
                        items_details.append({
                            "item_id": item_doc.get("item_id"),
                            "vendor_id": item_doc.get("vendor_id"),
                            "vendor_name": item_doc.get("vendor_name"),
                            "contract_id": item_doc.get("contract_id"),
                            "unit_price": item_doc.get("unit_price"),
                            "batch_number": item_doc.get("batch_number"),
                            "serial_number": item_doc.get("serial_no"),
                            "status": item_doc.get("status"),
                            "has_warranty": item_doc.get("has_warranty", False),
                            "warranty_tenure": item_doc.get("warranty_tenure", 0),
                            "warranty_unit": item_doc.get("warranty_unit", "months"),
                            "is_seller_returnable": item_doc.get("is_seller_returnable", False),
                            "seller_return_conditions": item_doc.get("seller_return_conditions", [])
                        })
                
                item["items_details"] = items_details
                item["item_count"] = len(items_details)
                item["has_item_details"] = len(items_details) > 0
            else:
                item["items_details"] = []
                item["item_count"] = 0
                item["has_item_details"] = False

            # ✅ Wrap in Pydantic model
            returns.append(ReturnToVendorResponse(**item))

        return returns

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving returns: {str(e)}")


#ReturnToVendor Details
async def get_return_by_id(store_id: str, return_id: str):
    result = await return_collection.find_one(
        {"store_id": store_id, "return_id": return_id},
        {"_id": 0}
    )

    if not result:
        raise HTTPException(status_code=404, detail="Return record not found")

    # Optionally map field if needed
    result["returnable_condition"] = "yes" if "yes" in result.get("product_condition", "").lower() else "no"
    
    # ✅ Fetch complete item details from ProductItems collection
    returnable_item_ids = result.get("returnable_item_ids", [])
    if returnable_item_ids:
        items_details = []
        for item_id in returnable_item_ids:
            item_doc = await db.ProductItems.find_one(
                {"item_id": item_id, "store_id": store_id},
                {"_id": 0}
            )
            if item_doc:
                items_details.append({
                    "item_id": item_doc.get("item_id"),
                    "item_name": item_doc.get("item_name"),
                    "vendor_id": item_doc.get("vendor_id"),
                    "vendor_name": item_doc.get("vendor_name"),
                    "contract_id": item_doc.get("contract_id"),
                    "purchase_date": item_doc.get("created_at"),
                    "unit_price": item_doc.get("unit_price"),
                    "batch_number": item_doc.get("batch_number"),
                    "serial_number": item_doc.get("serial_no"),
                    "status": item_doc.get("status"),
                    "has_warranty": item_doc.get("has_warranty", False),
                    "warranty_tenure": item_doc.get("warranty_tenure", 0),
                    "warranty_unit": item_doc.get("warranty_unit", "months"),
                    "is_consumer_returnable": item_doc.get("is_consumer_returnable", False),
                    "consumer_return_conditions": item_doc.get("consumer_return_conditions", []),
                    "is_seller_returnable": item_doc.get("is_seller_returnable", False),
                    "seller_return_conditions": item_doc.get("seller_return_conditions", [])
                })
        
        result["items_details"] = items_details
        result["item_count"] = len(items_details)
        result["has_item_details"] = len(items_details) > 0
    else:
        result["items_details"] = []
        result["item_count"] = 0
        result["has_item_details"] = False

    return result
