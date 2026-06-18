# Order Service Layer - Business Rules Implementation

## Overview
The `app/services/order_service.py` module implements five core business functions with strict enforcement of order lifecycle rules, cancellation constraints, and data integrity.

---

## Business Rules by Function

### 1. create_order(db, request) → OrderResponse

**Rule: Initial Status is System-Controlled**
- Implementation: Status is hardcoded to `OrderStatus.PENDING`
- Why: Prevents clients from creating orders in arbitrary states (e.g., already SHIPPED)
- Enforcement: No status field in CreateOrderRequest; client cannot override
- Risk if ignored: Orders could bypass fulfillment pipelines

**Rule: Items are Required and Non-Empty**
- Implementation: Schema validation requires min_length=1; service iterates over request.items
- Why: Order without items is meaningless; prevents zero-item orders
- Enforcement: Pydantic validator rejects empty list; service expects non-empty list
- Risk if ignored: Invalid orders in DB, broken totals, audit confusion

**Rule: Create Uses DB Transaction**
- Implementation: `db.add()`, `db.commit()`, `db.refresh()`
- Why: Ensures order and all items are persisted atomically; if items fail, entire order rolls back
- Enforcement: SQLAlchemy session transaction boundary
- Risk if ignored: Orphaned orders without items, inconsistent state

---

### 2. get_order(db, order_id) → OrderResponse

**Rule: Return Full Order with Items**
- Implementation: Query loads Order (ORM auto-loads items via relationship)
- Why: Clients get complete context in one response
- Enforcement: Relationship defined in models with eager loading
- Risk if ignored: Client needs N+1 queries, API response incomplete

**Rule: Raise OrderNotFoundError if Not Found**
- Implementation: `if not order: raise OrderNotFoundError`
- Why: Explicit error contract; allows API handler to map to 404
- Enforcement: Domain exception, not generic DB exception
- Risk if ignored: Ambiguous API behavior, hard to debug

---

### 3. list_orders(db, page=1, size=20, status=None) → ListOrdersResponse

**Rule: Default Pagination (page=1, size=20)**
- Implementation: Default parameter values; offset = (page - 1) * size
- Why: Prevents accidental large queries; provides predictable API contract
- Enforcement: Function signature with defaults
- Risk if ignored: Client can request entire DB in one call; memory/perf issues

**Rule: Optional Status Filter**
- Implementation: `if status: query = query.filter(Order.status == status)`
- Why: Allows efficient filtering without multiple API calls
- Enforcement: Parameter is optional; only applies filter if provided
- Risk if ignored: Cannot efficiently query orders by status; full table scans

**Rule: Return Total Count**
- Implementation: `total = query.count()` before pagination
- Why: Clients know total result size; enables pagination UX
- Enforcement: Count executed at DB layer
- Risk if ignored: Pagination UX broken; client can't know if more pages exist

---

### 4. update_order_status(db, order_id, request) → OrderResponse

**Rule: Strict Forward-Only Transitions**
- Implementation: `VALID_TRANSITIONS` map defines allowed transitions per state
  ```
  PENDING → {PROCESSING, CANCELLED}
  PROCESSING → {SHIPPED}
  SHIPPED → {DELIVERED}
  DELIVERED → {} (terminal, no transitions)
  CANCELLED → {} (terminal, no transitions)
  ```
- Why: Enforces business process; prevents invalid states (e.g., DELIVERED → PENDING)
- Enforcement: Pre-computed transition map checked before update
- Risk if ignored: Orders can regress (SHIPPED → PENDING); audit trail broken; fulfillment chaos

**Rule: No Transitions from CANCELLED**
- Implementation: CANCELLED maps to empty set in VALID_TRANSITIONS
- Why: Cancelled orders are final; prevents "uncancel" semantics
- Enforcement: Empty set means no transitions allowed
- Risk if ignored: Cancelled orders resurface; customer confusion; double fulfillment

**Rule: No Transitions from DELIVERED**
- Implementation: DELIVERED maps to empty set in VALID_TRANSITIONS
- Why: Delivered orders are final; prevents post-delivery state changes
- Enforcement: Empty set means no transitions allowed
- Risk if ignored: Can change shipped orders back to processing; fulfillment logic breaks

**Rule: Raise InvalidStatusTransitionError on Invalid Transition**
- Implementation: `if new_status not in VALID_TRANSITIONS.get(current_status, set()): raise`
- Why: Explicit domain error; API handler maps to 400 Bad Request
- Enforcement: Custom exception with current/new status in message
- Risk if ignored: Silent failures, hard-to-debug order state issues

**Rule: Use DB Transaction for Update**
- Implementation: `db.commit()` after status change
- Why: Ensures atomic update; no partial writes
- Enforcement: SQLAlchemy session transaction
- Risk if ignored: Race conditions; concurrent updates may overwrite

---

### 5. cancel_order(db, order_id) → OrderResponse

**Rule: Cancellation Only Allowed from PENDING**
- Implementation: `if order.status != OrderStatus.PENDING: raise CannotCancelOrderError`
- Why: Only pre-processing orders can be safely cancelled; prevents cancelling already-shipped orders
- Enforcement: Explicit status check before update
- Risk if ignored: Customers cancel orders already in transit; logistics chaos

**Rule: Soft Cancel (Status = CANCELLED, Not Deletion)**
- Implementation: Sets `order.status = OrderStatus.CANCELLED`, does NOT delete row
- Why: Preserves audit history; order remains queryable for reporting
- Enforcement: Update operation, not delete
- Risk if ignored: Lost order history; can't track what was cancelled; reporting broken

**Rule: Raise CannotCancelOrderError if Not in PENDING**
- Implementation: Custom exception with current status in message
- Why: Explicit error contract; API handler maps to 400
- Enforcement: Domain-specific exception, not generic error
- Risk if ignored: Ambiguous API errors, client can't distinguish root cause

---

## Exception Hierarchy

| Exception | Raised By | HTTP Code | Reason |
|-----------|-----------|-----------|--------|
| OrderNotFoundError | get_order, update_order_status, cancel_order | 404 | Resource not found |
| InvalidStatusTransitionError | update_order_status | 400 | Business rule violation (invalid transition) |
| CannotCancelOrderError | cancel_order | 400 | Business rule violation (cancel from non-PENDING) |

---

## Transaction Boundaries

| Function | Transaction Scope | Commits | Why |
|----------|-------------------|---------|-----|
| create_order | Order + OrderItems | Yes | Atomicity: all-or-nothing |
| get_order | Query only | No | Read-only; no state change |
| list_orders | Query only | No | Read-only; no state change |
| update_order_status | Status update | Yes | Atomicity: single state change |
| cancel_order | Status update | Yes | Atomicity: single state change |

---

## Lifecycle Diagram

```
CREATE (auto PENDING)
    ↓
[PENDING]  ← Can transition to PROCESSING or CANCELLED
    ↓              ↓
    ↓         [CANCELLED] ← Terminal, no transitions
    ↓
[PROCESSING] ← Can transition to SHIPPED
    ↓
[SHIPPED] ← Can transition to DELIVERED
    ↓
[DELIVERED] ← Terminal, no transitions
```

---

## Why No Repository Layer?

- Service layer directly uses SQLAlchemy Session
- Query logic is simple and tied to specific operations
- No shared query methods to abstract
- If needed later: can extract Query builders into separate module without breaking API

## Why Transactions Matter

**Last-write-wins concurrency model** (as per PROJECT_DECISIONS.md):
- If scheduler and manual API update hit same order simultaneously:
  - Both execute in transactions
  - Last one to commit wins
  - Previous update is overwritten
- **No optimistic locking** (deferred to future enhancement)
- Transactions ensure each update is atomic within its own scope

---

## Testing Strategy

To verify these rules are enforced:

1. **create_order**
   - ✓ Status is always PENDING
   - ✓ Empty items rejected
   - ✓ Items are persisted with order

2. **update_order_status**
   - ✓ Invalid transitions raise InvalidStatusTransitionError
   - ✓ PENDING → PROCESSING succeeds
   - ✓ PENDING → INVALID_STATUS fails
   - ✓ DELIVERED → any status fails

3. **cancel_order**
   - ✓ Cancel from PENDING succeeds
   - ✓ Cancel from PROCESSING fails with CannotCancelOrderError
   - ✓ Cancel from DELIVERED fails
   - ✓ Status is CANCELLED, not deleted

