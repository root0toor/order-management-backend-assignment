"""
Unit tests for schema validation.

Focus: Input validation, business rule enforcement at schema level.
"""
import pytest
from pydantic import ValidationError

from app.db.models import OrderStatus
from app.schemas import (
    CreateOrderRequest,
    OrderItemRequest,
    UpdateStatusRequest,
)


class TestOrderItemRequestValidation:
    """Test OrderItemRequest validation rules."""

    def test_valid_item(self):
        """Valid item with quantity > 0 and unit_price > 0."""
        item = OrderItemRequest(quantity=5, unit_price=9.99)
        assert item.quantity == 5
        assert item.unit_price == 9.99

    def test_quantity_zero_invalid(self):
        """Quantity must be > 0 (zero is invalid)."""
        with pytest.raises(ValidationError) as exc_info:
            OrderItemRequest(quantity=0, unit_price=10.00)

        errors = exc_info.value.errors()
        assert any("greater than 0" in str(e) for e in errors)

    def test_quantity_negative_invalid(self):
        """Quantity must be > 0 (negative is invalid)."""
        with pytest.raises(ValidationError) as exc_info:
            OrderItemRequest(quantity=-5, unit_price=10.00)

        errors = exc_info.value.errors()
        assert any("greater than 0" in str(e) for e in errors)

    def test_unit_price_zero_invalid(self):
        """Unit price must be > 0 (zero is invalid)."""
        with pytest.raises(ValidationError) as exc_info:
            OrderItemRequest(quantity=5, unit_price=0.0)

        errors = exc_info.value.errors()
        assert any("greater than 0" in str(e) for e in errors)

    def test_unit_price_negative_invalid(self):
        """Unit price must be > 0 (negative is invalid)."""
        with pytest.raises(ValidationError) as exc_info:
            OrderItemRequest(quantity=5, unit_price=-9.99)

        errors = exc_info.value.errors()
        assert any("greater than 0" in str(e) for e in errors)

    def test_unit_price_decimal_precision(self):
        """Unit price supports decimal places (e.g., $9.99)."""
        item = OrderItemRequest(quantity=2, unit_price=12.99)
        assert item.unit_price == 12.99

    def test_large_quantity(self):
        """Quantity can be large (e.g., bulk orders)."""
        item = OrderItemRequest(quantity=1000000, unit_price=0.01)
        assert item.quantity == 1000000


class TestCreateOrderRequestValidation:
    """Test CreateOrderRequest validation rules."""

    def test_valid_request(self):
        """Valid request with all required fields."""
        request = CreateOrderRequest(
            customer_name="Alice",
            customer_email="alice@example.com",
            items=[OrderItemRequest(quantity=2, unit_price=10.00)],
        )
        assert request.customer_name == "Alice"
        assert request.customer_email == "alice@example.com"
        assert len(request.items) == 1

    def test_email_validation_valid(self):
        """Valid email addresses are accepted."""
        valid_emails = [
            "user@example.com",
            "john.doe@example.co.uk",
            "user+tag@example.com",
        ]
        for email in valid_emails:
            request = CreateOrderRequest(
                customer_name="Test",
                customer_email=email,
                items=[OrderItemRequest(quantity=1, unit_price=1.00)],
            )
            assert request.customer_email == email

    def test_email_validation_invalid(self):
        """Invalid email addresses are rejected."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
        ]
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                CreateOrderRequest(
                    customer_name="Test",
                    customer_email=email,
                    items=[OrderItemRequest(quantity=1, unit_price=1.00)],
                )

    def test_items_empty_invalid(self):
        """Items list must be non-empty (cannot order nothing)."""
        with pytest.raises(ValidationError) as exc_info:
            CreateOrderRequest(
                customer_name="Bob",
                customer_email="bob@example.com",
                items=[],
            )

        errors = exc_info.value.errors()
        assert any("at least 1" in str(e) for e in errors)

    def test_items_multiple_valid(self):
        """Orders can have multiple items."""
        request = CreateOrderRequest(
            customer_name="Charlie",
            customer_email="charlie@example.com",
            items=[
                OrderItemRequest(quantity=1, unit_price=10.00),
                OrderItemRequest(quantity=2, unit_price=5.00),
                OrderItemRequest(quantity=3, unit_price=2.50),
            ],
        )
        assert len(request.items) == 3

    def test_customer_name_required(self):
        """Customer name is required."""
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                customer_name="",
                customer_email="test@example.com",
                items=[OrderItemRequest(quantity=1, unit_price=1.00)],
            )

    def test_item_with_invalid_quantity(self):
        """Invalid item in list causes validation failure."""
        with pytest.raises(ValidationError):
            CreateOrderRequest(
                customer_name="Diana",
                customer_email="diana@example.com",
                items=[
                    OrderItemRequest(quantity=1, unit_price=10.00),
                    OrderItemRequest(quantity=0, unit_price=5.00),  # Invalid
                ],
            )


class TestUpdateStatusRequestValidation:
    """Test UpdateStatusRequest validation rules."""

    def test_valid_status_pending(self):
        """Valid status: PENDING."""
        request = UpdateStatusRequest(status=OrderStatus.PENDING)
        assert request.status == OrderStatus.PENDING

    def test_valid_status_processing(self):
        """Valid status: PROCESSING."""
        request = UpdateStatusRequest(status=OrderStatus.PROCESSING)
        assert request.status == OrderStatus.PROCESSING

    def test_valid_status_shipped(self):
        """Valid status: SHIPPED."""
        request = UpdateStatusRequest(status=OrderStatus.SHIPPED)
        assert request.status == OrderStatus.SHIPPED

    def test_valid_status_delivered(self):
        """Valid status: DELIVERED."""
        request = UpdateStatusRequest(status=OrderStatus.DELIVERED)
        assert request.status == OrderStatus.DELIVERED

    def test_valid_status_cancelled(self):
        """Valid status: CANCELLED."""
        request = UpdateStatusRequest(status=OrderStatus.CANCELLED)
        assert request.status == OrderStatus.CANCELLED

    def test_invalid_status_string(self):
        """Invalid status string is rejected."""
        with pytest.raises(ValidationError):
            UpdateStatusRequest(status="INVALID_STATUS")

    def test_status_enum_case_sensitive(self):
        """Status enum values are case-sensitive."""
        with pytest.raises(ValidationError):
            UpdateStatusRequest(status="pending")  # lowercase invalid
