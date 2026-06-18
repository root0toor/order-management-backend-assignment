import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from app.db.models import OrderStatus


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class OrderItemRequest(BaseModel):
    """Order item request payload.
    
    Validation rules:
    - quantity must be > 0
    - unit_price must be > 0
    - product_id and product_name required and non-empty
    """
    product_id: str = Field(..., min_length=1, max_length=255, description="Product identifier")
    product_name: str = Field(..., min_length=1, max_length=255, description="Product display name")
    quantity: int = Field(..., gt=0, description="Quantity ordered (must be > 0)")
    unit_price: float = Field(..., gt=0, description="Price per unit (must be > 0)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_id": "SKU-12345",
                "product_name": "Yoga Mat",
                "quantity": 2,
                "unit_price": 49.99,
            }
        }
    }

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
    """Create order request payload.
    
    Validation rules:
    - customer_name required, non-empty, max 255 chars
    - customer_email required and valid email format
    - items required, must contain at least 1 item
    """
    customer_name: str = Field(..., min_length=1, max_length=255, description="Customer full name")
    customer_email: EmailStr = Field(..., description="Customer email (must be valid email)")
    items: list[OrderItemRequest] = Field(..., min_length=1, description="Order items (required, min 1)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_name": "Jane Doe",
                "customer_email": "jane@example.com",
                "items": [
                    {
                        "product_id": "SKU-12345",
                        "product_name": "Yoga Mat",
                        "quantity": 2,
                        "unit_price": 49.99,
                    }
                ],
            }
        }
    }

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list) -> list:
        if not v or len(v) == 0:
            raise ValueError("items cannot be empty")
        return v


class UpdateStatusRequest(BaseModel):
    """Update order status request payload.
    
    Validation rules:
    - status must be a valid OrderStatus enum value
    """
    status: OrderStatus = Field(..., description="New order status")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "PROCESSING",
            }
        }
    }

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: OrderStatus) -> OrderStatus:
        valid_statuses = {s.value for s in OrderStatus}
        if v.value not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v



# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class OrderItemResponse(BaseModel):
    """Order item response payload.
    
    Returns the full order item details with ID and parent order reference.
    """
    id: uuid.UUID = Field(..., description="Unique item identifier (UUID)")
    order_id: uuid.UUID = Field(..., description="Parent order identifier")
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product display name")
    quantity: int = Field(..., description="Quantity ordered")
    unit_price: float = Field(..., description="Price per unit")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "order_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "product_id": "SKU-12345",
                "product_name": "Yoga Mat",
                "quantity": 2,
                "unit_price": 49.99,
            }
        }
    }


class OrderResponse(BaseModel):
    """Order response payload with nested items.
    
    Returns full order details including status, customer info, timestamps, and items.
    """
    id: uuid.UUID = Field(..., description="Unique order identifier (UUID)")
    customer_name: str = Field(..., description="Customer full name")
    customer_email: str = Field(..., description="Customer email address")
    status: OrderStatus = Field(..., description="Current order status")
    items: list[OrderItemResponse] = Field(..., description="Order items")
    created_at: datetime = Field(..., description="Order creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Order last update timestamp (UTC)")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                "customer_name": "Jane Doe",
                "customer_email": "jane@example.com",
                "status": "PENDING",
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "order_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                        "product_id": "SKU-12345",
                        "product_name": "Yoga Mat",
                        "quantity": 2,
                        "unit_price": 49.99,
                    }
                ],
                "created_at": "2026-06-19T10:30:00+00:00",
                "updated_at": "2026-06-19T10:30:00+00:00",
            }
        }
    }


class ListOrdersResponse(BaseModel):
    """Paginated list of orders.
    
    Returns orders with pagination metadata.
    """
    items: list[OrderResponse] = Field(..., description="Orders in current page")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    size: int = Field(..., ge=1, description="Items per page")
    total: int | None = Field(None, description="Total count of all orders (optional)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
                        "customer_name": "Jane Doe",
                        "customer_email": "jane@example.com",
                        "status": "PENDING",
                        "items": [],
                        "created_at": "2026-06-19T10:30:00+00:00",
                        "updated_at": "2026-06-19T10:30:00+00:00",
                    }
                ],
                "page": 1,
                "size": 20,
                "total": 42,
            }
        }
    }


# ============================================================================
# ERROR RESPONSE SCHEMA
# ============================================================================

class ErrorResponse(BaseModel):
    """Structured error response.
    
    All API errors follow this contract with:
    - code: machine-readable error identifier
    - message: human-readable error description
    - details: optional additional context
    """
    code: str = Field(..., description="Error code identifier (e.g., ORDER_NOT_FOUND)")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error context")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "INVALID_STATUS_TRANSITION",
                "message": "Cannot transition from DELIVERED to PROCESSING",
                "details": {
                    "current_status": "DELIVERED",
                    "requested_status": "PROCESSING",
                },
            }
        }
    }
