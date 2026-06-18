"""
Unit tests for order service business logic.

Focus: Status transitions, cancellation rules, validation.
"""
import pytest
from sqlalchemy.orm import Session

from app.db.models import Order, OrderStatus
from app.exceptions import (
    CannotCancelOrderError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
)
from app.schemas import CreateOrderRequest, OrderItemRequest, UpdateStatusRequest
from app.services.order_service import (
    cancel_order,
    create_order,
    get_order,
    list_orders,
    update_order_status,
)


class TestCreateOrder:
    """Test order creation with business rule enforcement."""

    def test_create_order_forces_pending_status(self, db_session: Session):
        """Created orders must have PENDING status (enforced, not user-chosen)."""
        request = CreateOrderRequest(
            customer_name="Alice",
            customer_email="alice@example.com",
            items=[OrderItemRequest(quantity=2, unit_price=10.00)],
        )

        order = create_order(db_session, request)

        assert order.status == OrderStatus.PENDING
        assert order.customer_name == "Alice"
        assert order.customer_email == "alice@example.com"
        assert len(order.items) == 1
        assert order.items[0].quantity == 2
        assert order.items[0].unit_price == 10.00

    def test_create_order_calculates_total_correctly(self, db_session: Session):
        """Order total should be sum of (quantity * unit_price) for all items."""
        request = CreateOrderRequest(
            customer_name="Bob",
            customer_email="bob@example.com",
            items=[
                OrderItemRequest(quantity=2, unit_price=10.00),
                OrderItemRequest(quantity=1, unit_price=25.00),
            ],
        )

        order = create_order(db_session, request)

        # Total: (2 * 10) + (1 * 25) = 45
        assert order.total == 45.00

    def test_create_order_with_multiple_items(self, db_session: Session):
        """Orders can contain multiple items."""
        request = CreateOrderRequest(
            customer_name="Charlie",
            customer_email="charlie@example.com",
            items=[
                OrderItemRequest(quantity=3, unit_price=5.00),
                OrderItemRequest(quantity=2, unit_price=7.50),
                OrderItemRequest(quantity=1, unit_price=20.00),
            ],
        )

        order = create_order(db_session, request)

        assert len(order.items) == 3
        # Total: (3*5) + (2*7.5) + (1*20) = 15 + 15 + 20 = 50
        assert order.total == 50.00

    def test_create_order_creates_order_items(self, db_session: Session):
        """Order items are created and linked to order."""
        request = CreateOrderRequest(
            customer_name="Diana",
            customer_email="diana@example.com",
            items=[
                OrderItemRequest(quantity=5, unit_price=9.99),
            ],
        )

        order = create_order(db_session, request)

        assert len(order.items) == 1
        item = order.items[0]
        assert item.order_id == order.id
        assert item.quantity == 5
        assert item.unit_price == 9.99


class TestUpdateOrderStatus:
    """Test status transitions with VALID_TRANSITIONS enforcement."""

    def test_transition_pending_to_processing(self, db_session: Session):
        """PENDING → PROCESSING is valid."""
        order = self._create_test_order(db_session, OrderStatus.PENDING)

        updated = update_order_status(
            db_session,
            order.id,
            UpdateStatusRequest(status=OrderStatus.PROCESSING),
        )

        assert updated.status == OrderStatus.PROCESSING

    def test_transition_pending_to_cancelled(self, db_session: Session):
        """PENDING → CANCELLED is valid."""
        order = self._create_test_order(db_session, OrderStatus.PENDING)

        updated = update_order_status(
            db_session,
            order.id,
            UpdateStatusRequest(status=OrderStatus.CANCELLED),
        )

        assert updated.status == OrderStatus.CANCELLED

    def test_transition_processing_to_shipped(self, db_session: Session):
        """PROCESSING → SHIPPED is valid."""
        order = self._create_test_order(db_session, OrderStatus.PROCESSING)

        updated = update_order_status(
            db_session,
            order.id,
            UpdateStatusRequest(status=OrderStatus.SHIPPED),
        )

        assert updated.status == OrderStatus.SHIPPED

    def test_transition_shipped_to_delivered(self, db_session: Session):
        """SHIPPED → DELIVERED is valid."""
        order = self._create_test_order(db_session, OrderStatus.SHIPPED)

        updated = update_order_status(
            db_session,
            order.id,
            UpdateStatusRequest(status=OrderStatus.DELIVERED),
        )

        assert updated.status == OrderStatus.DELIVERED

    def test_transition_pending_to_shipped_invalid(self, db_session: Session):
        """PENDING → SHIPPED is invalid (must go through PROCESSING)."""
        order = self._create_test_order(db_session, OrderStatus.PENDING)

        with pytest.raises(InvalidStatusTransitionError):
            update_order_status(
                db_session,
                order.id,
                UpdateStatusRequest(status=OrderStatus.SHIPPED),
            )

    def test_transition_processing_to_cancelled_invalid(self, db_session: Session):
        """PROCESSING → CANCELLED is invalid (cannot cancel after processing)."""
        order = self._create_test_order(db_session, OrderStatus.PROCESSING)

        with pytest.raises(InvalidStatusTransitionError):
            update_order_status(
                db_session,
                order.id,
                UpdateStatusRequest(status=OrderStatus.CANCELLED),
            )

    def test_transition_shipped_to_pending_invalid(self, db_session: Session):
        """SHIPPED → PENDING is invalid (no backward transitions)."""
        order = self._create_test_order(db_session, OrderStatus.SHIPPED)

        with pytest.raises(InvalidStatusTransitionError):
            update_order_status(
                db_session,
                order.id,
                UpdateStatusRequest(status=OrderStatus.PENDING),
            )

    def test_transition_delivered_terminal_invalid(self, db_session: Session):
        """DELIVERED has no valid next state (terminal state)."""
        order = self._create_test_order(db_session, OrderStatus.DELIVERED)

        with pytest.raises(InvalidStatusTransitionError):
            update_order_status(
                db_session,
                order.id,
                UpdateStatusRequest(status=OrderStatus.SHIPPED),
            )

    def test_transition_cancelled_terminal_invalid(self, db_session: Session):
        """CANCELLED has no valid next state (terminal state)."""
        order = self._create_test_order(db_session, OrderStatus.CANCELLED)

        with pytest.raises(InvalidStatusTransitionError):
            update_order_status(
                db_session,
                order.id,
                UpdateStatusRequest(status=OrderStatus.PENDING),
            )

    def test_transition_nonexistent_order(self, db_session: Session):
        """Updating nonexistent order raises OrderNotFoundError."""
        with pytest.raises(OrderNotFoundError):
            update_order_status(
                db_session,
                "00000000-0000-0000-0000-000000000000",
                UpdateStatusRequest(status=OrderStatus.PROCESSING),
            )

    @staticmethod
    def _create_test_order(
        db_session: Session, status: OrderStatus
    ) -> Order:
        """Helper: create test order with specific status."""
        request = CreateOrderRequest(
            customer_name="Test",
            customer_email="test@example.com",
            items=[OrderItemRequest(quantity=1, unit_price=1.00)],
        )
        order = create_order(db_session, request)
        # Force status for testing (bypass PENDING requirement)
        order.status = status
        db_session.commit()
        return order


class TestCancelOrder:
    """Test cancellation with business rule enforcement."""

    def test_cancel_from_pending_succeeds(self, db_session: Session):
        """Orders in PENDING status can be cancelled."""
        request = CreateOrderRequest(
            customer_name="Eva",
            customer_email="eva@example.com",
            items=[OrderItemRequest(quantity=1, unit_price=10.00)],
        )
        order = create_order(db_session, request)

        cancelled = cancel_order(db_session, order.id)

        assert cancelled.status == OrderStatus.CANCELLED

    def test_cancel_from_processing_fails(self, db_session: Session):
        """Orders in PROCESSING status cannot be cancelled."""
        order = self._create_order_with_status(db_session, OrderStatus.PROCESSING)

        with pytest.raises(CannotCancelOrderError):
            cancel_order(db_session, order.id)

    def test_cancel_from_shipped_fails(self, db_session: Session):
        """Orders in SHIPPED status cannot be cancelled."""
        order = self._create_order_with_status(db_session, OrderStatus.SHIPPED)

        with pytest.raises(CannotCancelOrderError):
            cancel_order(db_session, order.id)

    def test_cancel_from_delivered_fails(self, db_session: Session):
        """Orders in DELIVERED status cannot be cancelled."""
        order = self._create_order_with_status(db_session, OrderStatus.DELIVERED)

        with pytest.raises(CannotCancelOrderError):
            cancel_order(db_session, order.id)

    def test_cancel_from_cancelled_fails(self, db_session: Session):
        """Already-cancelled orders cannot be cancelled again."""
        order = self._create_order_with_status(db_session, OrderStatus.CANCELLED)

        with pytest.raises(CannotCancelOrderError):
            cancel_order(db_session, order.id)

    def test_cancel_nonexistent_order(self, db_session: Session):
        """Cancelling nonexistent order raises OrderNotFoundError."""
        with pytest.raises(OrderNotFoundError):
            cancel_order(db_session, "00000000-0000-0000-0000-000000000000")

    @staticmethod
    def _create_order_with_status(
        db_session: Session, status: OrderStatus
    ) -> Order:
        """Helper: create test order with specific status."""
        request = CreateOrderRequest(
            customer_name="Test",
            customer_email="test@example.com",
            items=[OrderItemRequest(quantity=1, unit_price=1.00)],
        )
        order = create_order(db_session, request)
        order.status = status
        db_session.commit()
        return order


class TestListOrders:
    """Test pagination and filtering."""

    def test_list_orders_empty(self, db_session: Session):
        """Empty database returns empty list."""
        result = list_orders(db_session, page=1, size=10)

        assert result.total == 0
        assert result.page == 1
        assert result.size == 10
        assert result.items == []

    def test_list_orders_pagination(self, db_session: Session):
        """Pagination respects page and size parameters."""
        # Create 5 orders
        for i in range(5):
            request = CreateOrderRequest(
                customer_name=f"Customer {i}",
                customer_email=f"customer{i}@example.com",
                items=[OrderItemRequest(quantity=1, unit_price=10.00)],
            )
            create_order(db_session, request)

        # Page 1, size 2
        result = list_orders(db_session, page=1, size=2)
        assert result.total == 5
        assert len(result.items) == 2

        # Page 2, size 2
        result = list_orders(db_session, page=2, size=2)
        assert result.total == 5
        assert len(result.items) == 2

        # Page 3, size 2 (only 1 item left)
        result = list_orders(db_session, page=3, size=2)
        assert result.total == 5
        assert len(result.items) == 1

    def test_list_orders_filter_by_status(self, db_session: Session):
        """Filter parameter limits results to specific status."""
        # Create orders with different statuses
        order1 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        order2 = self._create_order_with_status(db_session, OrderStatus.PROCESSING)
        order3 = self._create_order_with_status(db_session, OrderStatus.PENDING)

        # Filter by PENDING
        result = list_orders(db_session, page=1, size=10, status=OrderStatus.PENDING)
        assert result.total == 2

        # Filter by PROCESSING
        result = list_orders(
            db_session, page=1, size=10, status=OrderStatus.PROCESSING
        )
        assert result.total == 1

    @staticmethod
    def _create_order_with_status(
        db_session: Session, status: OrderStatus
    ) -> Order:
        """Helper: create test order with specific status."""
        request = CreateOrderRequest(
            customer_name="Test",
            customer_email="test@example.com",
            items=[OrderItemRequest(quantity=1, unit_price=1.00)],
        )
        order = create_order(db_session, request)
        order.status = status
        db_session.commit()
        return order


class TestGetOrder:
    """Test order retrieval."""

    def test_get_existing_order(self, db_session: Session):
        """Get existing order returns order details."""
        request = CreateOrderRequest(
            customer_name="Frank",
            customer_email="frank@example.com",
            items=[OrderItemRequest(quantity=3, unit_price=7.50)],
        )
        created = create_order(db_session, request)

        retrieved = get_order(db_session, created.id)

        assert retrieved.id == created.id
        assert retrieved.customer_name == "Frank"
        assert retrieved.status == OrderStatus.PENDING

    def test_get_nonexistent_order(self, db_session: Session):
        """Get nonexistent order raises OrderNotFoundError."""
        with pytest.raises(OrderNotFoundError):
            get_order(db_session, "00000000-0000-0000-0000-000000000000")
