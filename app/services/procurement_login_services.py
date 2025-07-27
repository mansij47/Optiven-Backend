# from fastapi import HTTPException
# from typing import Dict, Any, Optional
# from app.models.procurement_models import LoginModel
# from app.utils.auth import verify_password, create_access_token
# from app.db import db  
# from bson.objectid import ObjectId

# async def login(email: str, password: str) -> Optional[Dict[str, Any]]: 
#     procurment = await db.Users.find_one({"email": email})
#     role= procurment.get("role") if procurment else None
#     if not procurment or not verify_password(password, procurment["password"]):
#         return None

#     token = create_access_token({
#         "email": email,
#         "id": str(procurment["_id"]),
#         "role": role,
#         "store_id": procurment.get("store_id", ""),
#         "org_id": procurment.get("org_id", "")
#     })
#     return {"access_token": token, "token_type": "bearer"}


# async def fetch_user(request):
    
#     user = request.state.user

#     user_id = user.get("email")
#     res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
#     if not res:
#         return HTTPException(401, "User not zFound")
    
#     res.pop("password", None) 
#     if not res:
#         return None
#     return res