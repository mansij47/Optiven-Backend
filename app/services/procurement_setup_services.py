from datetime import datetime
from passlib.context import CryptContext
from app.db import db

# 🔐 Setup for password hashing using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# ✅ Hash password if provided
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])

async def update_admin_setup(admin_id, update_data: dict):
    update_data["updated_at"] = datetime.utcnow()
    result = await db["Admins"].update_one(
        {"id": admin_id},
        {"$set": update_data}
    )

    if result.modified_count == 1:
        return await db["Admins"].find_one({"id": admin_id}, {"_id": 0})

    return None