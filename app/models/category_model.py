from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SubCategory(BaseModel):
    sub_category_id: str
    sub_category_name: str
    tags: List[str]

class CategoryCreate(BaseModel):
    category_id: str
    category_name: str
    description: str
    icon: Optional[str] = None
    sub_categories: List[SubCategory]
    created_at: datetime
    updated_at: datetime

class CategoryUpdate(BaseModel):
    category_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    sub_categories: Optional[List[SubCategory]] = None
    updated_at: Optional[datetime] = None