from pydantic import BaseModel
from typing import Literal

class RequestedBy(BaseModel):
    role: str  # Can also be Literal["admin", "user", etc.]
    id: str

class HelpRequest(BaseModel):
    requested_by: RequestedBy
    title: str
    message: str