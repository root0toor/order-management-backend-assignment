import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from app.db.models import OrderStatus


# Request schemas
class OrderItemRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=255)
    product_name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("unit_price must be greater than 0")
        return v


class CreateOrderRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_email: EmailStr
    items: list[OrderItemRequest] = Field(..., min_length=1)

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list) -> list:
        if not v or len(v) == 0:
            raise ValueError("items cannot be empty")
        return v


class UpdateStatusRequest(BaseModel):
    status: OrderStatus

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: OrderStatus) -> OrderStatus:
        valid_statuses = {s.value for s in OrderStatus}
        if v.value not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


# Response schemas
class OrderItemResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    product_id: str
    product_name: str
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    customer_name: str
    customer_email: str
    status: OrderStatus
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListOrdersResponse(BaseModel):
    items: list[OrderResponse]
    page: int
    size: int
    total: int | None = None


# Error response schema
class ErrorResponse(BaseModel):
    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error details")

    model_config = {"from_attributes": False}
