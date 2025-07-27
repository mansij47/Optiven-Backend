
from fastapi import HTTPException
from app.db import db
from app.utils.auth import create_access_token, verify_password


from fastapi import HTTPException
from app.db import db
from app.utils.auth import create_access_token, verify_password



from fastapi import HTTPException
from app.db import db
from app.utils.auth import create_access_token, verify_password



from fastapi import HTTPException
from app.db import db
from app.utils.auth import create_access_token, verify_password


def example_function() -> dict:
    """This function is an example.
    
    It returns a dictionary with a message.
    
    Returns:
        Dict: A dictionary with a message
    """
    return {"message": "This is an example function"}


async def login(email: str, password: str):
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer", "role": role}



async def fetch_user(request):
    
    user = request.state.user

    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
    if not res:
        return HTTPException(401, "User not zFound")
    
    res.pop("password", None) 
    if not res:
        return None
    return res



async def login(email: str, password: str):
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer", "role": role}



async def fetch_user(request):
    
    user = request.state.user

    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
    if not res:
        return HTTPException(401, "User not zFound")
    
    res.pop("password", None) 
    if not res:
        return None
    return res


async def login(email: str, password: str):
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer", "role": role}



async def fetch_user(request):
    
    user = request.state.user

    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
    if not res:
        return HTTPException(401, "User not zFound")
    
    res.pop("password", None) 
    if not res:
        return None
    return res



async def login(email: str, password: str):
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer", "role": role}



async def fetch_user(request):
    
    user = request.state.user

    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
    if not res:
        return HTTPException(401, "User not zFound")
    
    res.pop("password", None) 
    if not res:
        return None
    return res


async def login(email: str, password: str):
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer", "role": role}



async def fetch_user(request):
    
    user = request.state.user

    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id},{"_id": 0})
    
    if not res:
        return HTTPException(401, "User not zFound")
    
    res.pop("password", None) 
    if not res:
        return None
    return res
