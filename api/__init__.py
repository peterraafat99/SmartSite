"""SmartSite REST & WebSocket API Routers Package."""
from fastapi import APIRouter
from api.dashboard import router as dashboard_router
from api.streaming import router as streaming_router
from api.incidents import router as incidents_router
from api.workers import router as workers_router
from api.zones import router as zones_router
from api.iot import router as iot_router
from api.regulations import router as regulations_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(streaming_router, prefix="/stream", tags=["Streaming & Vision"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["Safety Incidents"])
api_router.include_router(workers_router, prefix="/workers", tags=["Personnel & Access"])
api_router.include_router(zones_router, prefix="/zones", tags=["Restricted Zones"])
api_router.include_router(iot_router, prefix="/iot", tags=["IoT Environmental Sensors"])
api_router.include_router(regulations_router, prefix="/regulations", tags=["OSHA Regulations"])

__all__ = ["api_router"]
