import uuid
from bson import ObjectId
from fastapi import HTTPException, Request
from datetime import datetime
import bcrypt

from app.db import db
from app.models.super_admin_models import UserModel
from app.utils.auth import hash_password
from app.utils.email_utils import send_welcome_email


async def create_department_user(data, user_info):
    try:
        # Validate role
        if data.role not in ["sales", "procurement"]:
            raise HTTPException(status_code=400, detail="Invalid role/department")

        # Extract org and store IDs from token/user info
        org_id = user_info.get("org_id")
        store_id = user_info.get("store_id")

        if not org_id or not store_id:
            raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

        # Check if email already exists in Users collection
        existing = await db.Users.find_one({"email": data.email})
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Hash the password securely
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Current timestamp
        today = datetime.utcnow()

        # Generate a unique UUID for this employee
        new_id = str(uuid.uuid4())

        # Prepare user document using your Pydantic model
        user_doc = UserModel(
            id=new_id,
            name={
                "first_name": data.first_name,
                "last_name": data.last_name
            },
            email=data.email,
            password=hashed_password,
            role=data.role,
            org_id=org_id,
            phone=data.phone,
            store_id=store_id,
            status=1,
            joining_date=today,
            termination_date=None,
            first_login=True,
            extra=""
        )

        # Insert user into Users collection
        await db.Users.insert_one(user_doc.model_dump())

        # Push employee reference into the store's departments array in Stores collection
        try:
            # First check if store exists and initialize departments array if needed
            store = await db.Stores.find_one({"org_id": org_id, "store_id": store_id})
            if not store:
                raise HTTPException(status_code=404, detail="Store not found")
            
            # Initialize departments array if it doesn't exist
            if "departments" not in store:
                await db.Stores.update_one(
                    {"org_id": org_id, "store_id": store_id},
                    {"$set": {"departments": []}}
                )
            
            # Now add the employee to departments
            await db.Stores.update_one(
                {"org_id": org_id, "store_id": store_id},
                {"$push": {"departments": {"department": data.role, "employee_id": new_id}}}
            )
        except Exception as e:
            # If departments update fails, we should still create the user
            # but log the error for debugging
            print(f"Warning: Failed to update store departments: {str(e)}")
            # Don't fail the entire operation for this

        # Send welcome email with original password (handle errors)
        try:
            res = send_welcome_email(to_email=data.email, password=data.password)
            if not res:
                raise HTTPException(status_code=404, detail="Failed to send welcome email")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"User already exist: {str(e)}")

        # Return success message
        return {
            "message": f"{data.role.capitalize()} employee created and email sent successfully",
            "email": data.email,
            "employee_id": new_id  # returning new UUID as employee identifier
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")
    
async def get_all_employees(user_info):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    cursor = db.Users.find({"org_id": org_id, "store_id": store_id})
    employees = []
    async for emp in cursor:
        emp.pop("password", None)  # Hide password hash

        if "_id" in emp and isinstance(emp["_id"], ObjectId):
            emp["_id"] = str(emp["_id"])

        employees.append(emp)

    return employees


async def get_employee_by_id(emp_id: str, user_info):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    employee = await db.Users.find_one({"id": emp_id, "org_id": org_id, "store_id": store_id})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee.pop("password", None)

    if "_id" in employee and isinstance(employee["_id"], ObjectId):
        employee["_id"] = str(employee["_id"])

    return employee


async def update_employee_by_id(emp_id: str, data, user_info):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    update_data = {}

    if getattr(data, "first_name", None) or getattr(data, "last_name", None):
        update_data["name.first_name"] = getattr(data, "first_name", None)
        update_data["name.last_name"] = getattr(data, "last_name", None)

    if getattr(data, "email", None):
        existing = await db.Users.find_one({"email": data.email, "id": {"$ne": emp_id}})
        if existing:
            raise HTTPException(status_code=400, detail="Another user with this email already exists")
        update_data["email"] = data.email

    if getattr(data, "phone", None):
        update_data["phone"] = data.phone

    if getattr(data, "role", None):
        if data.role not in ["sales", "procurement"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        update_data["role"] = data.role

    if getattr(data, "password", None):
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        update_data["password"] = hashed_password

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    update_data["updated_at"] = datetime.utcnow()

    result = await db.Users.update_one(
        {"id": emp_id, "org_id": org_id, "store_id": store_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")

    if "role" in update_data:
        try:
            await db.Stores.update_one(
                {"org_id": org_id, "store_id": store_id, "departments.employee_id": emp_id},
                {"$set": {"departments.$.department": update_data["role"]}}
            )
        except Exception as e:
            print(f"Warning: Failed to update store departments: {str(e)}")
            # Don't fail the entire operation for this

    return {"message": "Employee updated successfully"}


async def delete_user_by_id(emp_id: str, user_info: dict):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    result = await db.Users.delete_one({"id": emp_id, "org_id": org_id, "store_id": store_id})

    try:
        await db.Stores.update_one(
            {"org_id": org_id, "store_id": store_id},
            {"$pull": {"departments": {"employee_id": emp_id}}}
        )
    except Exception as e:
        print(f"Warning: Failed to remove employee from store departments: {str(e)}")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"message": "Employee deleted successfully"}
