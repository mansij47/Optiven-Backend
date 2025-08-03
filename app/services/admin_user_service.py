import uuid
from bson import ObjectId
from fastapi import HTTPException, Request
from datetime import datetime
import bcrypt
from pymongo import DESCENDING

from app.db import db
from app.models.super_admin_models import UserModel
# from app.services.admin_setup_service import hash_password
from app.utils.auth import hash_password
from app.utils.email_utils import send_welcome_email
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

        # Auto-generate custom user

        # Hash password
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        today = datetime.utcnow()

        new_id = str(uuid.uuid4())  # Generate a new UUID for the employee_id

        # Prepare user document
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



        # Insert into Users collection
        await db.Users.insert_one(user_doc.model_dump())

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
#         res = send_welcome_email(to_email=doc.get("email"), password=doc.get("password"))
#         print("Email sent status:", res)
#         if not res:
#             raise HTTPException(status_code=500, detail="Failed to send welcome email")
#         return {
#             "message": f"{data.role.capitalize()} employee created successfully",
#             "employee_id": new_id,
#             "store_id": store_id,
#             "email": doc.get("email"),
#             "password": password
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")
    
     
#     try:
#         res = send_welcome_email(to_email=doc.get("email"), password=doc.get("password"))
#         print("Email sent status:", res)
#         if not res:
#             raise HTTPException(status_code=500, detail="Failed to send welcome email")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to send credentials: {str(e)}")

# return {
#     "store_id": store_id,
#     "store_email": doc.get("store_email"),
#     "password": password
# }
        print("User created successfully:", user_doc)
        try:
            res = send_welcome_email(
                to_email=data.email,
                password=data.password  # original (non-hashed) password
                # employee_id=new_id
            )
            print("Email sent status:", res)
            if not res:
                raise HTTPException(status_code=500, detail="Failed to send welcome email")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send credentials: {str(e)}")

        return {
            "message": f"{data.role.capitalize()} employee created and email sent successfully",
            # "employee_id": new_id,
            "email": data.email
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {str(e)}")




async def delete_user_by_id(employee_id: str, request: Request):
    # try:
    #     # User_id = ObjectId(user_id)
    # except:    
    #     raise HTTPException(status_code=400, detail="Invalid ObjectID format")

    # user_token_data = request.state.user
    # if not user_token_data or not all(k in user_token_data for k in ["org_id", "store_id", "role"]):
    #     raise HTTPException(status_code=403, detail="Invalid or missing token data")

    # org_id = user_token_data["org_id"]
    # store_id = user_token_data["store_id"]

    # # Step 1: Find the user first
    # user = await db.Users.find_one({"_id": User_id}, {"_id": 0})
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")

    # # Step 2: Delete user
    # result = await db.Users.delete_one({"_id": User_id})


    # # user_role = user.get("role")
    # # await db.Users.delete_one({"_id": User_id})


    # # Step 3: Remove from store's departments array
    # await db.Stores.update_one(
    #     {"org_id": org_id, "store_id": store_id},
    #     {
    #         "$pull": {
    #             "departments": {
    #                 "department": user["role"],
    #                 "employee_id": str(User_id)
    #             }
    #         }
    #     }
    # )

    # return {"message": "User and department reference deleted successfully"}

    try:
        user_token_data = request.state.user
        if not user_token_data or not all(k in user_token_data for k in ["org_id", "store_id", "role"]):
            raise HTTPException(status_code=403, detail="Invalid or missing token data")

        org_id = user_token_data["org_id"]
        store_id = user_token_data["store_id"]

        # Step 1: Find the user using employee_id (not _id)
        user = await db.Users.find_one({"employee_id": employee_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["_id"]  # ObjectId
        user_role = user.get("role")

        # Step 2: Delete user
        delete_result = await db.Users.delete_one({"_id": user_id})
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=500, detail="Failed to delete user")

        # Step 3: Remove employee from store's departments array
        update_result = await db.Stores.update_one(
            {"org_id": org_id, "store_id": store_id},
            {
                "$pull": {
                    "departments": {
                        "department": user_role,
                        "employee_id": employee_id
                    }
                }
            }
        )

        return {"message": "User and department reference deleted successfully"}

    except HTTPException as e:
        raise e  # Reraise handled exceptions

    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


#forgot password handler

async def reset_password(email: str, user_id: str, new_password: str):
    # Validate ObjectId
    try:
        obj_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.Users.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found by ID")

    if user["email"].lower() != email.lower():
        raise HTTPException(status_code=400, detail="Email does not match the user")

    hashed_pw = hash_password(new_password)
    await db.Users.update_one(
        {"_id": obj_id},
        {"$set": {"password": hashed_pw}}
    )

    return {"message": "Password updated successfully"}