from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
