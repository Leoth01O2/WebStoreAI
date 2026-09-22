from pydantic import BaseModel
from typing import List, Optional

class DashboardSummaryResponse(BaseModel):
    total_revenue: float
    today_revenue: float
    week_revenue: float
    month_revenue: float
    total_orders: int
    today_orders: int
    completed_orders: int
    cancelled_orders: int
    total_products: int
    low_stock_count: int
    total_customers: int

class RevenueTrendItem(BaseModel):
    date: str
    revenue: float
    order_count: int

class TopProductItem(BaseModel):
    product_id: int
    sku: str
    name: str
    category_name: Optional[str] = None
    total_quantity_sold: int
    total_revenue: float

class LowStockAlertItem(BaseModel):
    product_id: int
    sku: str
    name: str
    category_name: Optional[str] = None
    stock_quantity: int
    min_stock_alert: int
    unit: str

class InventoryLogResponse(BaseModel):
    id: int
    product_id: int
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    change_type: str
    reference_code: Optional[str] = None
    quantity_before: int
    change_quantity: int
    quantity_after: int
    note: Optional[str] = None
    created_at: Optional[str] = None
