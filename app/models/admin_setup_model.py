from pydantic import BaseModel
from typing import Optional


class AdminSetupRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None
