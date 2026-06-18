from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Ensure model metadata is registered before Alembic reads Base.metadata.
from app.db import models  # noqa: E402,F401
