# from fastapi import HTTPException
# from app.db import db
# from typing import Optional, Dict, Any
# from motor.motor_asyncio import AsyncIOMotorClient
# from app.models.admin_login_model import LoginModel
# from app.utils.auth import verify_password, create_access_token

# async def login(email: str, password: str) -> Optional[Dict[str, Any]]:
#     admin = await db.Users.find_one({"email": email})
#     role= admin.get("role") if admin else None
#     if not admin or not verify_password(password, admin["password"]):
#         return None

#     token = create_access_token({
#         "email": email,
#         "id": admin["id"],
#         "role": role,
#         "store_id": admin.get("store_id", ""),
#         "org_id": admin.get("org_id", "")
#     })
#     return {"access_token": token, "token_type": "bearer"}