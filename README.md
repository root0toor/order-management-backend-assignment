# Order Management Backend Skeleton

Minimal project skeleton with FastAPI, SQLAlchemy, Alembic, PostgreSQL, Docker, and structured logging.

## Quick Start
1. Copy environment template:
   - `cp .env.example .env`
2. Start services:
   - `docker compose up --build`
3. Open API docs:
   - `http://localhost:8000/docs`
4. Health check:
   - `http://localhost:8000/health`

## Migrations
- Generate revision:
  - `alembic revision -m "init"`
- Apply migrations:
  - `alembic upgrade head`

## Notes
- This skeleton intentionally excludes business/domain logic.
- It provides only app bootstrapping, infrastructure wiring, and health endpoint.
