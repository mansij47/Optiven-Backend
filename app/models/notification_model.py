import uuid
from pydantic import BaseModel, Field
from typing import Optional, List

def generate_notification_id():
    return f"NOTIF-{uuid.uuid4().hex[:8].upper()}"

class UserInfo(BaseModel):
    role: str
    id: str
    store_id: Optional[str] = None  # This came from your first model

class NotificationBase(BaseModel):
    notification_id: str = Field(default_factory=generate_notification_id)
    sender: UserInfo
    # receiver: List[UserInfo]  # Allowing multiple receivers
    type_of_notification: Optional[str] = None  # Made optional for flexibility
    title: Optional[str] = None
    message: Optional[str] = None
    emails: Optional[List[str]] = None  # Optional email list for email-type notifications
    status: Optional[int] = 0  # default unread (0 = unread, 1 = read, etc.)

class NotificationUpdate(BaseModel):
    status: Optional[int] = None
    message: Optional[str] = None
    title: Optional[str] = None
    time: Optional[str] = None
    date: Optional[str] = None

class NotificationResponse(NotificationBase):
    id: str
