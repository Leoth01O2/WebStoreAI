from pydantic import BaseModel, Field
from typing import Optional

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tên danh mục")
    code: str = Field(..., min_length=1, max_length=50, description="Mã danh mục duy nhất")
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None

class CategoryResponse(CategoryBase):
    id: int
    created_at: Optional[str] = None
