# Schema Validation Decisions

## Overview
This document explains validation rules enforced in Pydantic schemas and the rationale behind each.

## Request Schemas

### CreateOrderRequest

**customer_name**
- **Rule**: Required, 1-255 characters
- **Why**: Identifies customer for order history and shipping; prevents empty values
- **Risk if ignored**: Lost order attribution, unshippable orders

**customer_email**
- **Rule**: Required, valid email format (EmailStr)
- **Why**: Primary contact for order status updates and customer service; email format enforced by Pydantic EmailStr
- **Risk if ignored**: Undeliverable notifications, lost contact with customer

**items**
- **Rule**: Required, non-empty list (min_length=1), each item is OrderItemRequest
- **Why**: Order cannot exist without line items; prevents meaningless zero-item orders
- **Risk if ignored**: Invalid orders in DB, broken order totals, audit confusion

### OrderItemRequest

**product_id**
- **Rule**: Required, 1-255 characters
- **Why**: Uniquely identifies product for fulfillment and inventory systems
- **Risk if ignored**: Unpickable orders, impossible to trace what was ordered

**product_name**
- **Rule**: Required, 1-255 characters
- **Why**: Human-readable product name for invoices, shipping labels, and customer communication
- **Risk if ignored**: Confusing shipping documentation, bad customer experience

**quantity**
- **Rule**: Required, > 0 (integer only)
- **Why**: Prevents zero, negative, or fractional quantities; must be whole units for fulfillment
- **Risk if ignored**: Invalid order fulfillment, negative inventory impact
- **Note**: Validator enforces this twice (via gt=0 and @field_validator) for clarity and fail-fast behavior

**unit_price**
- **Rule**: Required, > 0 (numeric with 2 decimals in DB, float in request)
- **Why**: Prevents zero/negative pricing; must be positive for revenue recognition and invoicing
- **Risk if ignored**: Free/negative price orders, financial reporting errors
- **Note**: Request accepts float; DB stores as Numeric(10,2) for precision

### UpdateStatusRequest

**status**
- **Rule**: Required, valid OrderStatus enum value
- **Why**: Ensures only predefined transitions are sent; prevents arbitrary status strings
- **Risk if ignored**: Invalid order states, broken state machine, audit trail inconsistency
- **Note**: Pydantic enum validation is automatic; @field_validator provides explicit error messages

## Response Schemas

### OrderItemResponse

**All fields from_attributes=True**
- **Why**: Enables automatic ORM attribute mapping (SQLAlchemy model → Pydantic model)
- **Benefit**: Eliminates boilerplate mapping code, keeps sync automatic

**Includes order_id reference**
- **Why**: Allows clients to correlate items back to parent order in nested responses

### OrderResponse

**Nested items list**
- **Why**: Clients get complete order picture in one response; eliminates N+1 query problem in API usage
- **Benefit**: Simple client code, predictable API structure

**Timestamps as datetime with timezone awareness**
- **Why**: UTC timestamps prevent timezone confusion; datetime objects automatically serialize to ISO-8601 in JSON
- **Benefit**: Unambiguous, standards-compliant, parseable by all clients

### ListOrdersResponse

**page, size, total**
- **Why**: Standard pagination metadata; allows clients to iterate large datasets
- **Note**: total is optional (None) to support implementations that skip COUNT for performance

**items as list[OrderResponse]**
- **Why**: Nested orders provide full context without additional calls
- **Benefit**: Predictable API, clients don't need 2+ requests per list call

## Error Response Schema

**code (string)**
- **Format**: UPPER_SNAKE_CASE identifier (e.g., ORDER_NOT_FOUND, INVALID_STATUS_TRANSITION)
- **Why**: Machine-readable for client error handling logic, stable API contract
- **Benefit**: Allows retry logic, fallback behavior, and specific error UX per error type

**message (string)**
- **Format**: Human-readable, actionable description
- **Why**: End users (including developers) read this in logs and error responses
- **Benefit**: Fast debugging, clear problem statement

**details (dict)**
- **Format**: Optional, key-value context
- **Why**: Extra context for specific errors (e.g., current_status, requested_status in transition errors)
- **Benefit**: Rich error information for client-side validation UX

## Validation Strategy Summary

| Field | Check | Reason |
|-------|-------|--------|
| customer_name | Non-empty string | Order attribution |
| customer_email | Valid email format | Contact delivery |
| items | Non-empty list | Order validity |
| quantity | > 0, integer | Fulfillment safety |
| unit_price | > 0, numeric | Financial correctness |
| status | Valid enum | State machine safety |

## Why Pydantic v2 Style

- **Field()** with descriptions: Auto-generates OpenAPI docs
- **from_attributes=True**: ORM integration without manual mapping
- **model_config**: Consolidated configuration; examples included for Swagger/OpenAPI
- **@field_validator**: Explicit, composable, re-raises with context
- **json_schema_extra**: Provides real examples in API docs
