
from fastapi import HTTPException, Request
from datetime import datetime
from app.db import db  # Adjust to your actual DB import
from app.models.store_model import StaffInput


async def get_store_detail_by_token(request: Request):
    store_id = request.state.user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Missing store_id in token")

    store = await db.Stores.find_one({"store_id": store_id})
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    store["_id"] = str(store["_id"])
    return store
async def update_store_by_token(updates: dict, request: Request):
    store_id = request.state.user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Missing store_id in token")

    updates["updated_at"] = datetime.utcnow().isoformat()

    result = await db["Stores"].update_one(
        {"store_id": store_id},
        {"$set": updates}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Store not found or no changes made")

    return {"message": "Store updated successfully"}

async def add_staff_to_department(department: str, staff: StaffInput, request: Request):
    store_id = request.state.user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Missing store_id in token")

    field_path = f"department.{department}"
    result = await db["Stores"].update_one(
        {"store_id": store_id},
        {
            "$push": {field_path: staff.model_dump()},
            "$set": {"updated_at": datetime.utcnow().isoformat()}
        }
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Failed to add staff to department")

    return {"message": f"Staff added to {department} department successfully"}

async def update_staff_in_department(department: str, staff_id: str, staff: StaffInput, request: Request):
    store_id = request.state.user.get("store_id")
    field_path = f"department.{department}"

    result = await db["Stores"].update_one(
        {"store_id": store_id, f"{field_path}.staff_id": staff_id},
        {
            "$set": {
                f"{field_path}.$": staff.model_dump(),
                "updated_at": datetime.utcnow().isoformat()
            }
        }
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Staff not found or update failed")
    return {"message": f"Staff in {department} updated successfully"}

async def delete_staff_from_department(department: str, staff_id: str, request: Request):
    store_id = request.state.user.get("store_id")
    field_path = f"department.{department}"

    result = await db["Stores"].update_one(
        {"store_id": store_id},
        {
            "$pull": {field_path: {"staff_id": staff_id}},
            "$set": {"updated_at": datetime.utcnow().isoformat()}
        }
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Staff not found or already removed")
    return {"message": f"Staff removed from {department} successfully"}