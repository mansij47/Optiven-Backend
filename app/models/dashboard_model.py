from pydantic import BaseModel
from typing import List

class ChartData(BaseModel):
    labels: List[str]
    data: List[int]

class TopProduct(BaseModel):
    product_name: str
    quantity: int

class DashboardResponse(BaseModel):
    total_items: int
    low_stock_items: int
    out_of_stock: int
    unique_visits: int
    inventory_status_chart: ChartData
    finance_report_chart: ChartData
    top_selling_products: List[TopProduct]