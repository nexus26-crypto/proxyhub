from fastapi import APIRouter

from app.api.v1 import auth, dashboard, gateway, logs, proxies, ws

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(proxies.router)
api_router.include_router(logs.router)
api_router.include_router(dashboard.router)
api_router.include_router(gateway.router)
api_router.include_router(ws.router)
