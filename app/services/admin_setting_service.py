
from datetime import datetime
from passlib.context import CryptContext
from app.db import db
from app.models.admin_setting_model import AdminSetupSettingRequest

# 🔐 Setup for password hashing using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# ✅ Hash password if provided
    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])

async def update_admin_setting(admin_id, update_data: dict):
    update_data["updated_at"] = datetime.utcnow()
    result = await db.Users.update_one(
        {"id": admin_id},
        {"$set": update_data}
    )

    if result.modified_count == 1:
        return {"message": "Admin setup updated successfully"}

    return None

# NEW: Get admin setup_setting details by admin_id
async def get_admin_setting(admin_id: str):
    doc = await db.Users.find_one({"id": admin_id}, {"_id": 0})
    if not doc:
        return None
    # Only return fields present in AdminSetupSettingRequest
    allowed_fields = set(AdminSetupSettingRequest.model_fields.keys()) if hasattr(AdminSetupSettingRequest, 'model_fields') else set(AdminSetupSettingRequest.__fields__.keys())
    filtered = {k: v for k, v in doc.items() if k in allowed_fields}
    return {"admin": filtered}
