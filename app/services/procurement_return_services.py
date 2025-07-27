from app.db import db
from fastapi import HTTPException
from app.models.procurement_models import ReturnToVendorResponse

return_collection = db["ReturnToVendor"]

status_map = {
    0: "Returned",
    1: "Disabled",
    2: "Pending"
}

#List of Return To Vendor
async def get_all_returns(store_id: str):
    returns_cursor = return_collection.find({"store_id": store_id}, {"_id": 0})
    returns = []
    async for item in returns_cursor:
        item["status"] = status_map.get(item.get("status", 0), "Returned")
        returns.append(ReturnToVendorResponse(**item))
    return returns


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

    return result
