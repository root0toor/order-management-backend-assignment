# Order Management Backend - Project Decisions and Assumptions

## Purpose
This document captures the final scope, assumptions, and acceptance criteria for implementation.
It is intended to keep coding focused, interview-ready, and aligned with assignment intent.

## Assignment Scope (Required)
- Create order
- Retrieve order by ID
- List orders
- Filter orders by status
- Update order status
- Cancel order only when status is PENDING
- Scheduled job updates PENDING orders to PROCESSING every 5 minutes

## Explicitly Out of Scope
- Payments
- Inventory management
- Authentication
- Authorization
- User accounts
- Shipping integrations
- Notifications
- Returns and refunds

## Final Architecture and Stack Decisions
- API style: REST
- Backend framework: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Validation: Pydantic
- API docs: Swagger/OpenAPI
- Deployment target: Local/demo with Docker

## Core Business Rules (Locked)
- Initial status on create is system-controlled: PENDING
- Client cannot set initial status on create
- Strict lifecycle:
  - PENDING -> PROCESSING -> SHIPPED -> DELIVERED
- Cancellation behavior:
  - Soft cancel only (status = CANCELLED)
  - Allowed only from PENDING
- Status update endpoint behavior:
  - Only valid forward transitions are allowed
  - Status cannot be updated once CANCELLED
  - Status cannot transition from DELIVERED to any other state

## Scheduler Behavior (Locked)
Requirement interpretation is fixed as:
- Every run updates ALL currently PENDING orders (not only orders older than 5 minutes)
- Run interval: every 5 minutes
- Scheduler updates only rows currently in PENDING state
- If status already changed by API before scheduler update, scheduler skips that row
- Single-instance scheduler only (distributed scheduling deferred)

## Concurrency Policy
For assignment scope:
- Database transactions ensure atomic updates.
- Last write wins.

Future:
- Optimistic locking.

## Validation Rules (Must Enforce)
Create order payload:
- Required fields:
  - customer_name
  - customer_email
  - items[]
- For each item:
  - product_id
  - product_name
  - quantity
  - unit_price

Validation constraints:
- items cannot be empty
- quantity > 0
- unit_price > 0
- invalid status values are rejected
- invalid pagination inputs are rejected

## API Contract Decisions
Status update endpoint:
- PATCH /orders/{id}/status
- Request body example:
  - { "status": "SHIPPED" }

Structured error contract (global):
- { "code": "...", "message": "...", "details": {} }

Example:
- { "code": "INVALID_STATUS_TRANSITION", "message": "Cannot transition from DELIVERED to PROCESSING", "details": {} }

## HTTP Status Codes
POST /orders
- 201 Created

GET /orders/{id}
- 200 OK
- 404 Not Found

GET /orders
- 200 OK

PATCH /orders/{id}/status
- 200 OK
- 400 Bad Request (invalid transition)
- 404 Not Found

POST /orders/{id}/cancel
- 200 OK
- 400 Bad Request (cannot cancel)
- 404 Not Found

## Data Model (Keep Minimal)
orders
- id (UUID)
- customer_name
- customer_email
- status
- created_at
- updated_at

order_items
- id (UUID)
- order_id
- product_id
- product_name
- quantity
- unit_price

Status enum
- PENDING
- PROCESSING
- SHIPPED
- DELIVERED
- CANCELLED

Do not add unless explicitly asked:
- inventory fields
- payment fields
- shipping fields
- audit tables

## Logging Scope
Keep:
- Structured logging
- Basic scheduler logging

Required log events:
- Order created
- Order updated
- Order cancelled
- Scheduler run started
- Scheduler run completed

## Testing Strategy (Final)
Focus on meaningful coverage, not percentage as a hard gate.

Must cover:
- All business rules
- All API endpoints
- Scheduler behavior
- Critical edge cases

Required edge-case tests:
- Cancel from PROCESSING fails
- Invalid transition fails
- Scheduler updates PENDING only
- Pagination works
- Validation works

Note:
- Coverage can still be reported, but no hard >=80% requirement is enforced in this plan.

## Must Have
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic validation
- Scheduler
- Docker
- Structured errors
- Unit tests
- Integration tests
- Swagger/OpenAPI

## Nice To Have
- Logging
- Pagination
- Seed script

## Future Enhancements
- Idempotency
- Optimistic locking
- Metrics
- Authentication
- Authorization
- Distributed scheduler
- Audit trail

## Important Assumptions to Document in README
Pagination assumption:
- The assignment requests listing all orders.
- Pagination is added for scalability while still allowing complete retrieval via repeated requests.

Concurrency assumption:
- Current implementation uses last-write-wins by design for assignment scope.
- Optimistic locking is intentionally deferred and documented.

## Revised Execution Plan
1. Project skeleton
2. Models + migrations
3. Business rules
4. APIs
5. Validation
6. Scheduler
7. Structured logging
8. Tests
9. Docker + README
10. Future enhancements
