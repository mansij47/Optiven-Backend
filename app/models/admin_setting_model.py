from typing import Optional
from pydantic import BaseModel

class AdminSetupSettingRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None
