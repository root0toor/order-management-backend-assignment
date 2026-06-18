import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.exceptions import CannotCancelOrderError
from app.exceptions import InvalidStatusTransitionError
from app.exceptions import OrderNotFoundError
from app.schemas import CreateOrderRequest
from app.schemas import OrderResponse
from app.schemas import ListOrdersResponse
from app.schemas import UpdateStatusRequest


# Valid status transitions
VALID_TRANSITIONS = {
    OrderStatus.PENDING: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def create_order(db: Session, request: CreateOrderRequest) -> OrderResponse:
    """
    Create a new order with items.
    
    Business rules:
    - Initial status is system-controlled: PENDING
    - Client cannot set initial status
    - Items are required and non-empty
    """
    order = Order(
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        status=OrderStatus.PENDING,
    )

    for item in request.items:
        order_item = OrderItem(
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        order.items.append(order_item)

    db.add(order)
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)


def get_order(db: Session, order_id: uuid.UUID) -> OrderResponse:
    """
    Retrieve order by ID.
    
    Raises:
    - OrderNotFoundError if order not found
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise OrderNotFoundError(f"Order {order_id} not found")
    return OrderResponse.model_validate(order)


def list_orders(
    db: Session,
    page: int = 1,
    size: int = 20,
    status: Optional[OrderStatus] = None,
) -> ListOrdersResponse:
    """
    List orders with pagination and optional status filtering.
    
    Defaults: page=1, size=20
    """
    query = db.query(Order)

    if status:
        query = query.filter(Order.status == status)

    total = query.count()
    offset = (page - 1) * size
    orders = query.offset(offset).limit(size).all()

    return ListOrdersResponse(
        items=[OrderResponse.model_validate(order) for order in orders],
        page=page,
        size=size,
        total=total,
    )


def update_order_status(
    db: Session,
    order_id: uuid.UUID,
    request: UpdateStatusRequest,
) -> OrderResponse:
    """
    Update order status with strict transition validation.
    
    Business rules:
    - Only valid forward transitions are allowed
    - Status cannot be updated once CANCELLED
    - Status cannot transition from DELIVERED to any other state
    - Transitions: PENDING -> PROCESSING -> SHIPPED -> DELIVERED
    - CANCELLED only from PENDING
    
    Raises:
    - OrderNotFoundError if order not found
    - InvalidStatusTransitionError if transition is not allowed
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise OrderNotFoundError(f"Order {order_id} not found")

    current_status = order.status
    new_status = request.status

    # Check if transition is valid
    if new_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise InvalidStatusTransitionError(
            f"Cannot transition from {current_status.value} to {new_status.value}"
        )

    order.status = new_status
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)


def cancel_order(db: Session, order_id: uuid.UUID) -> OrderResponse:
    """
    Cancel an order (soft cancel via status update).
    
    Business rules:
    - Cancellation is only allowed when status is PENDING
    - Cancellation sets status to CANCELLED (not a delete)
    
    Raises:
    - OrderNotFoundError if order not found
    - CannotCancelOrderError if order status is not PENDING
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise OrderNotFoundError(f"Order {order_id} not found")

    if order.status != OrderStatus.PENDING:
        raise CannotCancelOrderError(
            f"Cannot cancel order with status {order.status.value}. Only PENDING orders can be cancelled."
        )

    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    return OrderResponse.model_validate(order)
