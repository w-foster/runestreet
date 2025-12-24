from __future__ import annotations

from fastapi import APIRouter

from app.api.routes_health import router as health_router
from app.api.routes_scan import router as scan_router
from app.api.routes_series import router as series_router

router = APIRouter()
router.include_router(health_router)
router.include_router(scan_router)
router.include_router(series_router)


