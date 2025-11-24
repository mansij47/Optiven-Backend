from app.db import db
from fastapi import HTTPException
from app.models.procurement_models import ReturnToVendorResponse
from bson import ObjectId

return_collection = db["ReturnToVendor"]

# Status mapping for backward compatibility with old numeric values
# New entries should use string statuses: "pending", "completed", "returned", "disabled"
status_map = {
    # Legacy numeric values (for backward compatibility)
    0: "returned",
    1: "disabled",
    2: "pending",
    # String values (preferred format)
    "pending": "pending",
    "completed": "completed",
    "returned": "returned",
    "disabled": "disabled"
}

# # ✅ List of Return To Vendor
async def get_all_returns(store_id: str):
    try:
        # Fetch and sort in reverse (_id descending → newest first)
        returns_cursor = (
            return_collection.find({"store_id": store_id})
            .sort("_id", -1)
        )

        returns = []
        async for item in returns_cursor:
            # Convert ObjectId to string for frontend
            if "_id" in item:
                item["_id"] = str(item["_id"])
            
            # Normalize status - handle both numeric (legacy) and string statuses
            raw_status = item.get("status", "pending")  # Default to 'pending' if not set
            if isinstance(raw_status, str):
                # Use status_map for consistency, then capitalize for display
                normalized = status_map.get(raw_status.lower(), raw_status.lower())
                item["status"] = normalized.capitalize()
            else:
                # Legacy numeric values - convert to string then capitalize
                normalized = status_map.get(raw_status, "pending")
                item["status"] = normalized.capitalize()
            
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
        {"store_id": store_id, "return_id": return_id}
    )

    if not result:
        raise HTTPException(status_code=404, detail="Return record not found")

    # Convert ObjectId to string for frontend
    if "_id" in result:
        result["_id"] = str(result["_id"])

    # Normalize status field for consistency
    raw_status = result.get("status", "pending")
    if isinstance(raw_status, str):
        # Use status_map for consistency, then capitalize for display
        normalized = status_map.get(raw_status.lower(), raw_status.lower())
        result["status"] = normalized.capitalize()
    else:
        # Legacy numeric values - convert to string then capitalize
        normalized = status_map.get(raw_status, "pending")
        result["status"] = normalized.capitalize()

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


# Mark Return to Vendor as Completed (Return Received)
async def mark_return_received(store_id: str, return_ids: list):
    """
    Update status of vendor return orders from 'pending' to 'completed'
    when returns are received from vendor
    """
    try:
        updated_count = 0
        failed_returns = []
        
        for return_id in return_ids:
            # Check if return exists and is in pending status
            return_doc = await return_collection.find_one({
                "store_id": store_id,
                "return_id": return_id
            })
            
            if not return_doc:
                failed_returns.append({"return_id": return_id, "reason": "Return not found"})
                continue
            
            # Update status to completed
            result = await return_collection.update_one(
                {"store_id": store_id, "return_id": return_id},
                {"$set": {"status": "completed"}}
            )
            
            if result.modified_count > 0:
                updated_count += 1
            else:
                failed_returns.append({"return_id": return_id, "reason": "Update failed"})
        
        return {
            "message": f"Successfully marked {updated_count} return(s) as received",
            "updated_count": updated_count,
            "total_requested": len(return_ids),
            "failed_returns": failed_returns
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating return status: {str(e)}")


# Delete Return to Vendor Order
async def delete_return_order(store_id: str, identifier: str):
    """
    Delete a vendor return order by MongoDB ObjectId or return_id
    """
    try:
        # Try to delete by ObjectId first if valid format
        if ObjectId.is_valid(identifier):
            result = await return_collection.delete_one({
                "_id": ObjectId(identifier),
                "store_id": store_id
            })
            
            if result.deleted_count > 0:
                return {
                    "message": f"Successfully deleted return order",
                    "deleted_count": 1
                }
        
        # If not found by ObjectId or invalid format, try by return_id
        result = await return_collection.delete_one({
            "return_id": identifier,
            "store_id": store_id
        })
        
        if result.deleted_count > 0:
            return {
                "message": f"Successfully deleted return order",
                "deleted_count": 1
            }
        else:
            raise HTTPException(status_code=404, detail="Return order not found")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting return order: {str(e)}")
