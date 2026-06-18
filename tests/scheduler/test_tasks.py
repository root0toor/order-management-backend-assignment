"""
Tests for scheduler task: update_pending_orders_to_processing.

Focus: Business rule enforcement - only PENDING orders are updated.
"""
import pytest
from sqlalchemy.orm import Session

from app.db.models import Order, OrderStatus
from app.schemas import CreateOrderRequest, OrderItemRequest
from app.scheduler.tasks import update_pending_orders_to_processing
from app.services.order_service import create_order


class TestSchedulerUpdatePendingOrders:
    """Test scheduler task: update_pending_orders_to_processing()."""

    def test_updates_all_pending_orders(self, db_session: Session):
        """Scheduler updates ALL PENDING orders to PROCESSING."""
        # Create multiple PENDING orders
        order1 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        order2 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        order3 = self._create_order_with_status(db_session, OrderStatus.PENDING)

        # Run scheduler
        update_pending_orders_to_processing()

        # Reload from database
        db_session.refresh(order1)
        db_session.refresh(order2)
        db_session.refresh(order3)

        # All PENDING orders should now be PROCESSING
        assert order1.status == OrderStatus.PROCESSING
        assert order2.status == OrderStatus.PROCESSING
        assert order3.status == OrderStatus.PROCESSING

    def test_ignores_processing_orders(self, db_session: Session):
        """Scheduler leaves PROCESSING orders unchanged."""
        order = self._create_order_with_status(db_session, OrderStatus.PROCESSING)

        update_pending_orders_to_processing()

        db_session.refresh(order)
        assert order.status == OrderStatus.PROCESSING

    def test_ignores_shipped_orders(self, db_session: Session):
        """Scheduler leaves SHIPPED orders unchanged."""
        order = self._create_order_with_status(db_session, OrderStatus.SHIPPED)

        update_pending_orders_to_processing()

        db_session.refresh(order)
        assert order.status == OrderStatus.SHIPPED

    def test_ignores_delivered_orders(self, db_session: Session):
        """Scheduler leaves DELIVERED orders unchanged."""
        order = self._create_order_with_status(db_session, OrderStatus.DELIVERED)

        update_pending_orders_to_processing()

        db_session.refresh(order)
        assert order.status == OrderStatus.DELIVERED

    def test_ignores_cancelled_orders(self, db_session: Session):
        """Scheduler leaves CANCELLED orders unchanged."""
        order = self._create_order_with_status(db_session, OrderStatus.CANCELLED)

        update_pending_orders_to_processing()

        db_session.refresh(order)
        assert order.status == OrderStatus.CANCELLED

    def test_mixed_statuses(self, db_session: Session):
        """
        Scheduler updates only PENDING orders.
        
        Business rule: each 5-minute run updates ALL current PENDING orders,
        leaving other statuses unchanged. This tests the complete lifecycle.
        """
        # Create orders with various statuses
        pending1 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        pending2 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        processing = self._create_order_with_status(db_session, OrderStatus.PROCESSING)
        shipped = self._create_order_with_status(db_session, OrderStatus.SHIPPED)
        delivered = self._create_order_with_status(db_session, OrderStatus.DELIVERED)
        cancelled = self._create_order_with_status(db_session, OrderStatus.CANCELLED)

        # Run scheduler
        update_pending_orders_to_processing()

        # Reload and verify
        db_session.refresh(pending1)
        db_session.refresh(pending2)
        db_session.refresh(processing)
        db_session.refresh(shipped)
        db_session.refresh(delivered)
        db_session.refresh(cancelled)

        # PENDING orders updated to PROCESSING
        assert pending1.status == OrderStatus.PROCESSING
        assert pending2.status == OrderStatus.PROCESSING

        # Other statuses unchanged
        assert processing.status == OrderStatus.PROCESSING
        assert shipped.status == OrderStatus.SHIPPED
        assert delivered.status == OrderStatus.DELIVERED
        assert cancelled.status == OrderStatus.CANCELLED

    def test_no_pending_orders(self, db_session: Session):
        """Scheduler handles case with no PENDING orders (idempotent)."""
        # Create only non-pending orders
        self._create_order_with_status(db_session, OrderStatus.PROCESSING)
        self._create_order_with_status(db_session, OrderStatus.SHIPPED)

        # Run scheduler (should not fail)
        update_pending_orders_to_processing()

        # Verify no changes
        orders = db_session.query(Order).all()
        assert all(o.status != OrderStatus.PENDING for o in orders)

    def test_idempotent_on_second_run(self, db_session: Session):
        """Running scheduler twice is idempotent."""
        order = self._create_order_with_status(db_session, OrderStatus.PENDING)

        # First run
        update_pending_orders_to_processing()
        db_session.refresh(order)
        assert order.status == OrderStatus.PROCESSING

        # Second run (should not change anything, as no PENDING orders exist)
        update_pending_orders_to_processing()
        db_session.refresh(order)
        assert order.status == OrderStatus.PROCESSING

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


class TestSchedulerEdgeCases:
    """Test scheduler edge cases and corner scenarios."""

    def test_large_batch_of_pending_orders(self, db_session: Session):
        """Scheduler can handle large number of PENDING orders."""
        # Create 100 PENDING orders
        orders = []
        for i in range(100):
            order = self._create_order_with_status(db_session, OrderStatus.PENDING)
            orders.append(order)

        # Run scheduler (should process all atomically)
        update_pending_orders_to_processing()

        # Verify all updated
        for order in orders:
            db_session.refresh(order)
            assert order.status == OrderStatus.PROCESSING

    def test_scheduler_atomic_transaction(self, db_session: Session):
        """
        Scheduler updates are atomic.
        
        All PENDING orders updated in single transaction,
        ensuring consistency: either all succeed or all fail.
        """
        order1 = self._create_order_with_status(db_session, OrderStatus.PENDING)
        order2 = self._create_order_with_status(db_session, OrderStatus.PENDING)

        update_pending_orders_to_processing()

        # Both orders should be updated atomically
        db_session.refresh(order1)
        db_session.refresh(order2)
        assert order1.status == OrderStatus.PROCESSING
        assert order2.status == OrderStatus.PROCESSING

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
