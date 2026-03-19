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
        if data.role not in ["sales", "procurement", "admin"]:
            raise HTTPException(status_code=400, detail="Invalid role/department")

        # Extract org and store IDs from token/user info
        org_id = user_info.get("org_id")
        store_id = user_info.get("store_id")

        if not org_id or not store_id:
            raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

        normalized_email = data.email.strip().lower()

        # Check if email already exists in current store only
        existing = await db.Users.find_one(
            {
                "email": normalized_email,
                "org_id": org_id,
                "store_id": store_id,
            }
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists in this store",
            )

        # Hash the password securely
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Current timestamp
        today = datetime.utcnow()

        # Generate sequential employee ID (EMP001, EMP002, etc.)
        # Find the highest employee number in the store
        last_employee = await db.Users.find_one(
            {"org_id": org_id, "store_id": store_id, "id": {"$regex": "^EMP"}},
            sort=[("id", -1)]
        )
        
        if last_employee and last_employee.get("id"):
            # Extract number from last employee ID (e.g., EMP005 -> 5)
            try:
                last_num = int(last_employee["id"].replace("EMP", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        # Format as EMP001, EMP002, etc.
        new_id = f"EMP{new_num:03d}"

        # Prepare user document using your Pydantic model
        user_doc = UserModel(
            id=new_id,
            name={
                "first_name": data.first_name,
                "last_name": data.last_name
            },
            email=normalized_email,
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

        # Send welcome email with original password.
        # Do not fail employee creation if email transport fails in production.
        email_sent = False
        try:
            email_sent = send_welcome_email(to_email=normalized_email, password=data.password)
        except Exception as e:
            print(f"Warning: Failed to send welcome email to {normalized_email}: {str(e)}")

        if email_sent:
            message = f"{data.role.capitalize()} employee created and email sent successfully"
        else:
            message = f"{data.role.capitalize()} employee created successfully, but welcome email could not be sent"

        # Return success message
        return {
            "message": message,
            "email": normalized_email,
            "employee_id": new_id,
            "email_sent": email_sent,
        }

    except HTTPException:
        raise
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

        # Format name field for frontend
        if "name" in emp:
            if isinstance(emp["name"], dict):
                first_name = emp["name"].get("first_name", "")
                last_name = emp["name"].get("last_name", "")
                emp["name"] = f"{first_name} {last_name}".strip()
            elif not isinstance(emp["name"], str):
                emp["name"] = "Unknown"
        else:
            emp["name"] = "Unknown"

        # Add department field for frontend compatibility (map from role)
        if "role" in emp:
            emp["department"] = emp["role"]

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

    # Format name field for frontend
    if "name" in employee:
        if isinstance(employee["name"], dict):
            first_name = employee["name"].get("first_name", "")
            last_name = employee["name"].get("last_name", "")
            employee["name"] = f"{first_name} {last_name}".strip()
        elif not isinstance(employee["name"], str):
            employee["name"] = "Unknown"
    else:
        employee["name"] = "Unknown"

    # Add department field for frontend compatibility (map from role)
    if "role" in employee:
        employee["department"] = employee["role"]

    return employee


async def update_employee_by_id(emp_id: str, data, user_info):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    update_data = {}

    # Update name fields together if both are provided
    if getattr(data, "first_name", None) and getattr(data, "last_name", None):
        update_data["name.first_name"] = data.first_name
        update_data["name.last_name"] = data.last_name
    elif getattr(data, "first_name", None):
        update_data["name.first_name"] = data.first_name
    elif getattr(data, "last_name", None):
        update_data["name.last_name"] = data.last_name

    if getattr(data, "email", None):
        normalized_email = data.email.strip().lower()
        existing = await db.Users.find_one(
            {
                "email": normalized_email,
                "id": {"$ne": emp_id},
                "org_id": org_id,
                "store_id": store_id,
            }
        )
        if existing:
            raise HTTPException(status_code=400, detail="Another user with this email already exists in this store")
        update_data["email"] = normalized_email

    if getattr(data, "phone", None):
        update_data["phone"] = data.phone

    if getattr(data, "role", None):
        if data.role not in ["sales", "procurement", "admin"]:
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




async def delete_user_by_objectId(emp_id: str, user_info: dict):
    org_id = user_info.get("org_id")
    store_id = user_info.get("store_id")

    if not org_id or not store_id:
        raise HTTPException(status_code=403, detail="Missing org_id or store_id in token")

    result = await db.Users.delete_one({"_id": ObjectId(emp_id)})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"message": "Employee deleted successfully"}

