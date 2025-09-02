from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class SpecificationModel(BaseModel):
    processor: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    graphics: Optional[str] = None
    display: Optional[str] = None
    os: Optional[str] = None


class VariantModel(BaseModel):
    specifications: SpecificationModel
    quantity: int
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    price: Optional[float] = None


class InventoryModel(BaseModel):
    product_name: str
    brand: str
    category: str
    sub_category: str
    description: Optional[str] = None
    variants: List[VariantModel] = []
