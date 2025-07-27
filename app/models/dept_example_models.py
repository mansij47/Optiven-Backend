from typing import List
from pydantic import BaseModel, EmailStr

class ModelNameSchema(BaseModel):
    entity1: List[str]
    entity2: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str