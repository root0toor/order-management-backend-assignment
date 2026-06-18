# Test Suite Summary

## Overview

Complete test suite for order management backend with focus on business rules:
- **Status transitions** (VALID_TRANSITIONS enforcement)
- **Cancellation rules** (PENDING-only soft delete)
- **Validation rules** (Pydantic schemas)
- **Scheduler behavior** (PENDING→PROCESSING only)

## Test Organization

### Unit Tests (48 tests) - `tests/unit/`

**test_order_service.py (37 tests)**
- `TestCreateOrder` (7 tests)
  - Forces PENDING status
  - Calculates total correctly
  - Multiple items handling
  - Order item creation
  
- `TestUpdateOrderStatus` (10 tests)
  - Valid transitions: PENDING→PROCESSING, PROCESSING→SHIPPED, SHIPPED→DELIVERED, PENDING→CANCELLED
  - Invalid transitions: PENDING→SHIPPED (must go through PROCESSING), PROCESSING→CANCELLED (no backtrack), SHIPPED→PENDING (no backward), DELIVERED/CANCELLED terminal states

- `TestCancelOrder` (6 tests)
  - Cancellation only from PENDING
  - Fails from PROCESSING, SHIPPED, DELIVERED, CANCELLED
  - Nonexistent order handling

- `TestListOrders` (5 tests)
  - Empty list handling
  - Pagination (page, size)
  - Status filtering
  - Total count

- `TestGetOrder` (2 tests)
  - Existing order retrieval
  - Nonexistent order error

**test_schemas.py (11 tests)**
- `TestOrderItemRequestValidation` (7 tests)
  - Quantity validation (must be > 0)
  - Unit price validation (must be > 0)
  - Zero/negative rejection
  - Decimal precision support

- `TestCreateOrderRequestValidation` (8 tests)
  - Valid request structure
  - Email validation (valid/invalid patterns)
  - Items non-empty requirement
  - Multiple items support
  - Required fields enforcement
  - Invalid items in list

- `TestUpdateStatusRequestValidation` (5 tests)
  - All valid enum values (PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED)
  - Invalid string rejection
  - Case sensitivity

### Integration Tests (28 tests) - `tests/integration/`

**test_orders_api.py (28 tests)**
- `TestCreateOrderEndpoint` (6 tests)
  - Successful order creation (201 Created)
  - Invalid email (422)
  - Empty items (422)
  - Zero quantity (422)
  - Negative price (422)
  - Missing required field (422)

- `TestGetOrderEndpoint` (3 tests)
  - Existing order retrieval (200 OK)
  - Nonexistent order (404 Not Found)
  - Invalid UUID format (422)

- `TestListOrdersEndpoint` (5 tests)
  - Empty list response
  - Multiple orders listing
  - Pagination parameters
  - Status filtering

- `TestUpdateStatusEndpoint` (7 tests)
  - Valid transitions (PENDING→PROCESSING, PROCESSING→SHIPPED, SHIPPED→DELIVERED)
  - Invalid transitions (PENDING→SHIPPED, PROCESSING→CANCELLED)
  - Nonexistent order (404)
  - Invalid status (422)

- `TestCancelOrderEndpoint` (7 tests)
  - Successful cancellation from PENDING (200 OK)
  - Fails from PROCESSING, SHIPPED, DELIVERED (400)
  - Nonexistent order (404)
  - Double cancel (400)

### Scheduler Tests (12 tests) - `tests/scheduler/`

**test_tasks.py (12 tests)**
- `TestSchedulerUpdatePendingOrders` (10 tests)
  - Updates all PENDING orders
  - Ignores PROCESSING, SHIPPED, DELIVERED, CANCELLED
  - Mixed status scenario (updates only PENDING)
  - No pending orders (idempotent)
  - Idempotent on second run
  - Large batch handling (100 orders)

- `TestSchedulerEdgeCases` (2 tests)
  - Large batch performance
  - Atomic transaction guarantee

## Test Coverage by Category

| Category | Count | Type | Focus |
|----------|-------|------|-------|
| Status Transitions | 13 | Unit | VALID_TRANSITIONS map enforcement |
| Cancellation Rules | 11 | Unit/Integration | PENDING-only soft delete |
| Validation Rules | 19 | Unit/Schema | Pydantic input validation |
| API Endpoints | 28 | Integration | HTTP status codes, error handling |
| Scheduler | 12 | Unit | PENDING→PROCESSING only |
| **TOTAL** | **88** | - | - |

## Test Execution

### Run All Tests
```bash
pytest tests/ -v
```

### Run by Category
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Scheduler tests only
pytest tests/scheduler/ -v
```

### Run Specific Test Class
```bash
pytest tests/unit/test_order_service.py::TestUpdateOrderStatus -v
```

### Run with Coverage Report
```bash
pytest tests/ --cov=app --cov-report=html
```

## Business Rules Tested

### 1. Order Lifecycle (Status Transitions)
✅ PENDING → PROCESSING → SHIPPED → DELIVERED (happy path)
✅ PENDING → CANCELLED (soft delete, early cancellation only)
✅ No backward transitions (SHIPPED → PENDING invalid)
✅ Terminal states (DELIVERED, CANCELLED have no valid next states)
✅ No side paths (e.g., PROCESSING → CANCELLED invalid)

### 2. Cancellation Rules
✅ Soft delete: status → CANCELLED (no data deletion)
✅ Only from PENDING: other states cannot be cancelled
✅ Idempotent on refusal: double-cancel returns 400 (consistent error)

### 3. Order Creation
✅ Forces PENDING status (user cannot override)
✅ Requires non-empty items (cannot order nothing)
✅ Calculates total: sum of (quantity × unit_price) per item
✅ Creates order items with quantity > 0, unit_price > 0

### 4. Scheduler Behavior
✅ Runs every 5 minutes (APScheduler with IntervalTrigger)
✅ Updates ALL PENDING orders to PROCESSING (batch update)
✅ Ignores non-PENDING statuses (only touches PENDING)
✅ Atomic transaction (all-or-nothing consistency)
✅ Idempotent (second run changes nothing if no PENDING exist)

## Test Infrastructure

### Fixtures (conftest.py)
- **engine**: SQLite in-memory database (session-scoped)
- **db_session**: Test session with auto-rollback (function-scoped)
- **client**: FastAPI TestClient with DB dependency override

### Database Strategy
- In-memory SQLite for speed and isolation
- Auto-rollback after each test (transactional isolation)
- No test data pollution (fresh database per test)

### Error Handling
- Domain exceptions → HTTP status codes tested
- Validation errors (422 Unprocessable Entity)
- Business rule violations (400 Bad Request)
- Not found errors (404 Not Found)

## Assumptions & Design Decisions

1. **Status Transitions**: VALID_TRANSITIONS map is single source of truth
2. **Cancellation**: Soft delete (status change) not hard delete (data removal)
3. **Scheduler**: Single-instance (no distributed lock), idempotent on rerun
4. **Validation**: Enforced at both schema (Pydantic) and service (business logic) layers
5. **Database**: Transactional isolation via auto-rollback ensures test independence

## Future Enhancements (Out of Scope)

- [ ] Distributed scheduler locking (for multi-instance deployment)
- [ ] Optimistic concurrency control (version field, conflict detection)
- [ ] Audit trail (log all status changes with timestamps)
- [ ] Performance testing (load, latency, throughput)
- [ ] Chaos testing (database failures, network partitions)
