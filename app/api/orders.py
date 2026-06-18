import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.exceptions import CannotCancelOrderError
from app.exceptions import InvalidStatusTransitionError
from app.exceptions import OrderNotFoundError
from app.schemas import CreateOrderRequest
from app.schemas import ErrorResponse
from app.schemas import ListOrdersResponse
from app.schemas import OrderResponse
from app.schemas import UpdateStatusRequest
from app.services.order_service import cancel_order
from app.services.order_service import create_order
from app.services.order_service import get_order
from app.services.order_service import list_orders
from app.services.order_service import update_order_status
from app.db.models import OrderStatus

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    responses={
        201: {"description": "Order created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request (validation error)"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def create_order_endpoint(
    request: CreateOrderRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Create a new order with items.
    
    - **customer_name**: Customer full name (required, 1-255 chars)
    - **customer_email**: Valid email address (required)
    - **items**: At least 1 item with product_id, product_name, quantity > 0, unit_price > 0
    
    Returns:
    - 201 Created: Order created with status=PENDING
    - 400 Bad Request: Validation error (empty items, invalid email, etc.)
    - 500 Internal Server Error: Database or unexpected error
    """
    try:
        return create_order(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Failed to create order",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
    responses={
        200: {"description": "Order found"},
        404: {"model": ErrorResponse, "description": "Order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def get_order_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Retrieve a specific order by ID with all its items.
    
    Returns:
    - 200 OK: Full order details with items
    - 404 Not Found: Order does not exist
    - 500 Internal Server Error: Database error
    """
    try:
        return get_order(db, order_id)
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found",
                details={},
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Failed to retrieve order",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.get(
    "",
    response_model=ListOrdersResponse,
    summary="List orders with pagination",
    responses={
        200: {"description": "Orders retrieved"},
        400: {"model": ErrorResponse, "description": "Invalid pagination parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def list_orders_endpoint(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: str | None = Query(None, description="Filter by status (PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)"),
    db: Session = Depends(get_db),
) -> ListOrdersResponse:
    """
    List all orders with pagination and optional status filter.
    
    Query parameters:
    - **page**: Page number (default 1)
    - **size**: Items per page (default 20, max 100)
    - **status**: Optional status filter (PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)
    
    Returns:
    - 200 OK: Paginated list with items, page, size, total
    - 400 Bad Request: Invalid pagination or status
    - 500 Internal Server Error: Database error
    """
    try:
        # Convert string status to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = OrderStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorResponse(
                        code="INVALID_STATUS",
                        message=f"Invalid status: {status}. Must be one of PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED",
                        details={"provided_status": status},
                    ).model_dump(),
                )

        return list_orders(db, page=page, size=size, status=status_enum)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Failed to list orders",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
    responses={
        200: {"description": "Status updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid transition or status"},
        404: {"model": ErrorResponse, "description": "Order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def update_order_status_endpoint(
    order_id: uuid.UUID,
    request: UpdateStatusRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Update order status with strict transition validation.
    
    Valid transitions:
    - PENDING → PROCESSING or CANCELLED
    - PROCESSING → SHIPPED
    - SHIPPED → DELIVERED
    - DELIVERED → (no transitions, terminal state)
    - CANCELLED → (no transitions, terminal state)
    
    Request body:
    - **status**: New status (must be valid enum value)
    
    Returns:
    - 200 OK: Order with updated status
    - 400 Bad Request: Invalid transition (e.g., DELIVERED → PROCESSING)
    - 404 Not Found: Order does not exist
    - 500 Internal Server Error: Database error
    """
    try:
        return update_order_status(db, order_id, request)
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found",
                details={},
            ).model_dump(),
        )
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="INVALID_STATUS_TRANSITION",
                message=str(e),
                details={},
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Failed to update order status",
                details={"error": str(e)},
            ).model_dump(),
        )


@router.delete(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Cancel an order",
    responses={
        200: {"description": "Order cancelled successfully"},
        400: {"model": ErrorResponse, "description": "Cannot cancel order (not in PENDING state)"},
        404: {"model": ErrorResponse, "description": "Order not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
def cancel_order_endpoint(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Cancel an order (soft delete via status update).
    
    Business rule:
    - Cancellation is only allowed for orders in PENDING status
    - Cancellation sets status to CANCELLED (does not delete the order)
    - Cancelled orders can be queried for history and auditing
    
    Returns:
    - 200 OK: Order with status=CANCELLED
    - 400 Bad Request: Cannot cancel (order not in PENDING state)
    - 404 Not Found: Order does not exist
    - 500 Internal Server Error: Database error
    """
    try:
        return cancel_order(db, order_id)
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found",
                details={},
            ).model_dump(),
        )
    except CannotCancelOrderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                code="CANNOT_CANCEL_ORDER",
                message=str(e),
                details={},
            ).model_dump(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Failed to cancel order",
                details={"error": str(e)},
            ).model_dump(),
        )
