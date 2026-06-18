"""
Integration tests for order API endpoints.

Focus: End-to-end API behavior, status codes, error handling.
"""
import pytest
from starlette.testclient import TestClient

from app.db.models import OrderStatus


class TestCreateOrderEndpoint:
    """Test POST /orders endpoint."""

    def test_create_order_success(self, client: TestClient):
        """POST /orders creates order and returns 201 Created."""
        payload = {
            "customer_name": "Alice",
            "customer_email": "alice@example.com",
            "items": [
                {"quantity": 2, "unit_price": 10.00},
                {"quantity": 1, "unit_price": 25.00},
            ],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["customer_name"] == "Alice"
        assert data["customer_email"] == "alice@example.com"
        assert data["status"] == "PENDING"
        assert data["total"] == 45.00  # (2*10) + (1*25)
        assert len(data["items"]) == 2
        assert "id" in data

    def test_create_order_invalid_email(self, client: TestClient):
        """POST /orders with invalid email returns 422 Unprocessable Entity."""
        payload = {
            "customer_name": "Bob",
            "customer_email": "not-an-email",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 422

    def test_create_order_empty_items(self, client: TestClient):
        """POST /orders with empty items returns 422."""
        payload = {
            "customer_name": "Charlie",
            "customer_email": "charlie@example.com",
            "items": [],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 422

    def test_create_order_zero_quantity(self, client: TestClient):
        """POST /orders with quantity=0 returns 422."""
        payload = {
            "customer_name": "Diana",
            "customer_email": "diana@example.com",
            "items": [{"quantity": 0, "unit_price": 10.00}],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 422

    def test_create_order_negative_price(self, client: TestClient):
        """POST /orders with negative unit_price returns 422."""
        payload = {
            "customer_name": "Eva",
            "customer_email": "eva@example.com",
            "items": [{"quantity": 1, "unit_price": -10.00}],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 422

    def test_create_order_missing_field(self, client: TestClient):
        """POST /orders with missing required field returns 422."""
        payload = {
            "customer_email": "frank@example.com",
            # Missing customer_name
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }

        response = client.post("/orders", json=payload)

        assert response.status_code == 422


class TestGetOrderEndpoint:
    """Test GET /orders/{id} endpoint."""

    def test_get_existing_order(self, client: TestClient):
        """GET /orders/{id} returns order details with 200 OK."""
        # Create order first
        create_payload = {
            "customer_name": "Grace",
            "customer_email": "grace@example.com",
            "items": [{"quantity": 1, "unit_price": 15.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Get order
        response = client.get(f"/orders/{order_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id
        assert data["customer_name"] == "Grace"
        assert data["status"] == "PENDING"

    def test_get_nonexistent_order(self, client: TestClient):
        """GET /orders/{id} with invalid ID returns 404 Not Found."""
        response = client.get("/orders/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        data = response.json()
        assert "code" in data  # ErrorResponse format
        assert "order not found" in data["message"].lower()

    def test_get_order_invalid_uuid(self, client: TestClient):
        """GET /orders/{id} with invalid UUID format returns 422."""
        response = client.get("/orders/not-a-uuid")

        assert response.status_code == 422


class TestListOrdersEndpoint:
    """Test GET /orders endpoint."""

    def test_list_empty_orders(self, client: TestClient):
        """GET /orders with no orders returns empty list."""
        response = client.get("/orders")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 10
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_orders_with_items(self, client: TestClient):
        """GET /orders returns paginated list of orders."""
        # Create 3 orders
        for i in range(3):
            payload = {
                "customer_name": f"Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "items": [{"quantity": 1, "unit_price": 10.00}],
            }
            client.post("/orders", json=payload)

        response = client.get("/orders")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_list_orders_pagination(self, client: TestClient):
        """GET /orders?page=2&size=2 respects pagination parameters."""
        # Create 5 orders
        for i in range(5):
            payload = {
                "customer_name": f"Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "items": [{"quantity": 1, "unit_price": 10.00}],
            }
            client.post("/orders", json=payload)

        # Page 1, size 2
        response = client.get("/orders?page=1&size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["total"] == 5
        assert len(data["items"]) == 2

        # Page 2, size 2
        response = client.get("/orders?page=2&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

        # Page 3, size 2 (only 1 item)
        response = client.get("/orders?page=3&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_list_orders_filter_by_status(self, client: TestClient):
        """GET /orders?status=PENDING filters by status."""
        # Create 3 orders
        order_ids = []
        for i in range(3):
            payload = {
                "customer_name": f"Customer {i}",
                "customer_email": f"customer{i}@example.com",
                "items": [{"quantity": 1, "unit_price": 10.00}],
            }
            response = client.post("/orders", json=payload)
            order_ids.append(response.json()["id"])

        # Update first order to PROCESSING
        client.patch(
            f"/orders/{order_ids[0]}/status",
            json={"status": "PROCESSING"},
        )

        # Filter by PENDING (should return 2)
        response = client.get("/orders?status=PENDING")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Filter by PROCESSING (should return 1)
        response = client.get("/orders?status=PROCESSING")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestUpdateStatusEndpoint:
    """Test PATCH /orders/{id}/status endpoint."""

    def test_update_pending_to_processing(self, client: TestClient):
        """PATCH /orders/{id}/status PENDING→PROCESSING returns 200 OK."""
        # Create order
        create_payload = {
            "customer_name": "Henry",
            "customer_email": "henry@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Update to PROCESSING
        update_payload = {"status": "PROCESSING"}
        response = client.patch(f"/orders/{order_id}/status", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PROCESSING"

    def test_update_processing_to_shipped(self, client: TestClient):
        """PATCH /orders/{id}/status PROCESSING→SHIPPED returns 200 OK."""
        order_id = self._create_and_update_order(client, "PROCESSING")

        response = client.patch(
            f"/orders/{order_id}/status",
            json={"status": "SHIPPED"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "SHIPPED"

    def test_update_shipped_to_delivered(self, client: TestClient):
        """PATCH /orders/{id}/status SHIPPED→DELIVERED returns 200 OK."""
        order_id = self._create_and_update_order(client, "SHIPPED")

        response = client.patch(
            f"/orders/{order_id}/status",
            json={"status": "DELIVERED"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "DELIVERED"

    def test_update_pending_to_shipped_invalid(self, client: TestClient):
        """PATCH /orders/{id}/status PENDING→SHIPPED returns 400 Bad Request."""
        # Create order (status=PENDING)
        create_payload = {
            "customer_name": "Iris",
            "customer_email": "iris@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Try to update to SHIPPED (invalid)
        response = client.patch(
            f"/orders/{order_id}/status",
            json={"status": "SHIPPED"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "code" in data
        assert "invalid" in data["message"].lower()

    def test_update_processing_to_cancelled_invalid(self, client: TestClient):
        """PATCH /orders/{id}/status PROCESSING→CANCELLED returns 400."""
        order_id = self._create_and_update_order(client, "PROCESSING")

        response = client.patch(
            f"/orders/{order_id}/status",
            json={"status": "CANCELLED"},
        )

        assert response.status_code == 400

    def test_update_nonexistent_order(self, client: TestClient):
        """PATCH /orders/{id}/status with invalid ID returns 404."""
        response = client.patch(
            "/orders/00000000-0000-0000-0000-000000000000/status",
            json={"status": "PROCESSING"},
        )

        assert response.status_code == 404

    def test_update_invalid_status(self, client: TestClient):
        """PATCH /orders/{id}/status with invalid status returns 422."""
        # Create order
        create_payload = {
            "customer_name": "Jack",
            "customer_email": "jack@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Try invalid status
        response = client.patch(
            f"/orders/{order_id}/status",
            json={"status": "INVALID"},
        )

        assert response.status_code == 422

    @staticmethod
    def _create_and_update_order(client: TestClient, target_status: str) -> str:
        """Helper: create order and update to target status."""
        create_payload = {
            "customer_name": "Test",
            "customer_email": "test@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Update to target status via intermediate states
        status_sequence = {
            "PROCESSING": ["PROCESSING"],
            "SHIPPED": ["PROCESSING", "SHIPPED"],
            "DELIVERED": ["PROCESSING", "SHIPPED", "DELIVERED"],
        }

        for status in status_sequence[target_status]:
            client.patch(
                f"/orders/{order_id}/status",
                json={"status": status},
            )

        return order_id


class TestCancelOrderEndpoint:
    """Test DELETE /orders/{id} endpoint."""

    def test_cancel_pending_order(self, client: TestClient):
        """DELETE /orders/{id} cancels PENDING order (status→CANCELLED)."""
        # Create order
        create_payload = {
            "customer_name": "Karl",
            "customer_email": "karl@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Cancel order
        response = client.delete(f"/orders/{order_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"

    def test_cancel_processing_order_fails(self, client: TestClient):
        """DELETE /orders/{id} on PROCESSING order returns 400 Bad Request."""
        order_id = self._create_and_update_order(client, "PROCESSING")

        response = client.delete(f"/orders/{order_id}")

        assert response.status_code == 400
        data = response.json()
        assert "cannot cancel" in data["message"].lower()

    def test_cancel_shipped_order_fails(self, client: TestClient):
        """DELETE /orders/{id} on SHIPPED order returns 400."""
        order_id = self._create_and_update_order(client, "SHIPPED")

        response = client.delete(f"/orders/{order_id}")

        assert response.status_code == 400

    def test_cancel_delivered_order_fails(self, client: TestClient):
        """DELETE /orders/{id} on DELIVERED order returns 400."""
        order_id = self._create_and_update_order(client, "DELIVERED")

        response = client.delete(f"/orders/{order_id}")

        assert response.status_code == 400

    def test_cancel_nonexistent_order(self, client: TestClient):
        """DELETE /orders/{id} with invalid ID returns 404."""
        response = client.delete("/orders/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404

    def test_cancel_twice_fails(self, client: TestClient):
        """DELETE /orders/{id} on already-cancelled order returns 400."""
        # Create order
        create_payload = {
            "customer_name": "Lisa",
            "customer_email": "lisa@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Cancel once (succeeds)
        response = client.delete(f"/orders/{order_id}")
        assert response.status_code == 200

        # Cancel again (fails - already cancelled)
        response = client.delete(f"/orders/{order_id}")
        assert response.status_code == 400

    @staticmethod
    def _create_and_update_order(client: TestClient, target_status: str) -> str:
        """Helper: create order and update to target status."""
        create_payload = {
            "customer_name": "Test",
            "customer_email": "test@example.com",
            "items": [{"quantity": 1, "unit_price": 10.00}],
        }
        create_response = client.post("/orders", json=create_payload)
        order_id = create_response.json()["id"]

        # Update to target status
        status_sequence = {
            "PROCESSING": ["PROCESSING"],
            "SHIPPED": ["PROCESSING", "SHIPPED"],
            "DELIVERED": ["PROCESSING", "SHIPPED", "DELIVERED"],
        }

        for status in status_sequence[target_status]:
            client.patch(
                f"/orders/{order_id}/status",
                json={"status": status},
            )

        return order_id
