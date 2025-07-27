from typing import Any, Dict, Optional
from app.db import db
from app.utils.auth import verify_password, create_access_token

async def login(email: str, password: str) -> Optional[Dict[str, Any]]:
    sales  = await db.Users.find_one({"email": email})
    role= sales .get("role") if sales  else None
    if not sales  or not verify_password(password, sales ["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(sales ["id"]),
        "role": role,
        "store_id": sales.get("store_id", ""),
        "org_id": sales.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer"}

