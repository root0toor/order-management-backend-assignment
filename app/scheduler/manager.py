from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import get_logger
from app.scheduler.tasks import update_pending_orders_to_processing

logger = get_logger(__name__)

scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    """
    Start the background scheduler.
    
    Configures and starts APScheduler with:
    - Update PENDING orders to PROCESSING task
    - Runs every 5 minutes
    - Single-instance (no distributed locking)
    """
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.warning("Scheduler is already running")
        return

    try:
        scheduler = BackgroundScheduler()
        
        # Add job: update PENDING orders to PROCESSING every 5 minutes
        scheduler.add_job(
            update_pending_orders_to_processing,
            "interval",
            minutes=5,
            id="update_pending_orders",
            name="Update PENDING orders to PROCESSING",
            replace_existing=True,
        )

        scheduler.start()
        logger.info(
            "scheduler_started",
            extra={
                "jobs": len(scheduler.get_jobs()),
            },
        )

    except Exception as e:
        logger.error(
            "scheduler_startup_failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise


def stop_scheduler() -> None:
    """
    Stop the background scheduler gracefully.
    
    Ensures all pending jobs are completed before shutdown.
    """
    global scheduler

    if scheduler is None or not scheduler.running:
        logger.warning("Scheduler is not running")
        return

    try:
        scheduler.shutdown(wait=True)
        logger.info("scheduler_stopped")
    except Exception as e:
        logger.error(
            "scheduler_shutdown_failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise
