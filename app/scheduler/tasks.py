from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.session import SessionLocal

logger = get_logger(__name__)


def update_pending_orders_to_processing() -> None:
    """
    Scheduler task: Update all PENDING orders to PROCESSING.
    
    Business rules:
    - Only PENDING orders are updated
    - Status transitions to PROCESSING
    - All other statuses are left unchanged
    - Runs every 5 minutes
    - Single-instance deployment (no distributed lock)
    
    Logging:
    - Logs run start and end
    - Logs count of orders scanned and updated
    - Logs any errors
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        run_started_at = datetime.utcnow().isoformat()
        
        logger.info(
            "scheduler_run_started",
            extra={
                "task": "update_pending_orders_to_processing",
                "timestamp": run_started_at,
            },
        )

        # Query all PENDING orders
        pending_orders = db.query(Order).filter(Order.status == OrderStatus.PENDING).all()
        scanned_count = len(pending_orders)

        # Update each PENDING order to PROCESSING
        updated_count = 0
        for order in pending_orders:
            order.status = OrderStatus.PROCESSING
            updated_count += 1

        # Commit all updates atomically
        db.commit()

        run_ended_at = datetime.utcnow().isoformat()
        logger.info(
            "scheduler_run_completed",
            extra={
                "task": "update_pending_orders_to_processing",
                "scanned_count": scanned_count,
                "updated_count": updated_count,
                "timestamp": run_ended_at,
            },
        )

    except Exception as e:
        logger.error(
            "scheduler_run_failed",
            extra={
                "task": "update_pending_orders_to_processing",
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        if db:
            db.rollback()
        raise

    finally:
        if db:
            db.close()
