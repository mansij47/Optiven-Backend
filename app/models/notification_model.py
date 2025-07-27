from pydantic import BaseModel
from typing import Optional, List

class UserInfo(BaseModel):
    role: str
    id: str

class NotificationBase(BaseModel):
    sender: UserInfo
    receiver: List[UserInfo]  # Multiple receivers
    type_of_notification: str
    title: str
    message: str
    status: int
    time: str
    date: str

class NotificationUpdate(BaseModel):
    status: Optional[int] = None
    message: Optional[str] = None
    title: Optional[str] = None

class NotificationResponse(NotificationBase):
    id: str