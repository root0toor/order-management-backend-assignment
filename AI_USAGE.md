# AI Usage Strategy

## 1. Tools Used
- Cursor
- ChatGPT

## 2. What AI Assisted With
- Requirement analysis
- Architecture decisions
- API design
- Test strategy
- Boilerplate generation

## 3. Issues Found
- Suggested optimistic locking beyond assignment scope.
- Added unnecessary production features for current assignment stage.

## 4. Corrections Made
- Simplified concurrency model.
- Deferred idempotency.
- Removed unnecessary complexity.

## 5. Final Human Decisions
- FastAPI selected.
- PostgreSQL selected.
- Strict lifecycle selected.
- Single-instance scheduler selected.
