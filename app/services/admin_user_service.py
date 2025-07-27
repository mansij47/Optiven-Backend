from bson import ObjectId
from fastapi import HTTPException, Request
from datetime import datetime
import bcrypt
from pymongo import DESCENDING

from app.db import db
# from app.services.admin_setup_service import hash_password
# from app.utils.email_forgot import send_reset_email

async def create_department_user(data, user_info):
    try:
        if data.role not in ["sales", "procurement"]:
            raise HTTPException(status_code=400, detail="Invalid role/department")

        # Get org/store from token only
        org_id = user_info.get("org_id")
        store_id = user_info.get("store_id")

        if not org_id or not store_id:
            raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

        # Check if email already exists
        existing = await db.Users.find_one({"email": data.email})
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Auto-generate custom user_id
        prefix = "PR" if data.role == "procurement" else "SA"

        last_user = await db.Users.find_one(
            {"role": data.role},
            sort=[("user_id", DESCENDING)]
        )

        if last_user and "user_id" in last_user:
            last_id = int(last_user["user_id"][2:])
            new_id = f"{prefix}{str(last_id + 1).zfill(3)}"
        else:
            new_id = f"{prefix}001"

        # Hash password
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        today = datetime.utcnow()

        # Prepare user document
        user_doc = {
            "id": new_id,
            "name": {
                "first_name": data.first_name,
                "last_name": data.last_name
            },
            "email": data.email,
            "password": hashed_password,
            "role": data.role,
            "org_id": org_id,
            "store_id": store_id,
            "status": 1,
            "joining_date": today,
            "termination_date": None
        }

        # Insert into Users collection
        await db.Users.insert_one(user_doc)

        # Update department array in Stores
        await db.Stores.update_one(
            {"org_id": org_id, "store_id": store_id},
            {
                "$push": {
                    "departments": {
                        "department": data.role,
                        "employee_id": new_id
                    }
                }
            }
        )

        return {
            "message": f"{data.role.capitalize()} employee created successfully",
            "employee_id": new_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")




async def delete_user_by_id(user_id: str, request: Request):
    try:
        User_id = ObjectId(user_id)
    except:    
        raise HTTPException(status_code=400, detail="Invalid ObjectID format")

    user_token_data = request.state.user
    if not user_token_data or not all(k in user_token_data for k in ["org_id", "store_id", "role"]):
        raise HTTPException(status_code=403, detail="Invalid or missing token data")

    org_id = user_token_data["org_id"]
    store_id = user_token_data["store_id"]

    # Step 1: Find the user first
    user = await db.Users.find_one({"_id": User_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Step 2: Delete user
    result = await db.Users.delete_one({"_id": User_id})

    # Step 3: Remove from store's departments array
    await db.Stores.update_one(
        {"org_id": org_id, "store_id": store_id},
        {
            "$pull": {
                "departments": {
                    "department": user["role"],
                    "employee_id": str(User_id)
                }
            }
        }
    )

    return {"message": "User and department reference deleted successfully"}


#forgot password handler
async def reset_password(email: str, user_id: str, new_password: str):
    # Validate ObjectId
    try:
        obj_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.Users.find_one({"_id": obj_id, "email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_pw = hash_password(new_password)
    await db.Users.update_one(
        {"_id": obj_id},
        {"$set": {"password": hashed_pw}}
    )

    return {"message": "Password updated successfully"}