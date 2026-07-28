import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import ProxyHubException
from app.scheduler.jobs import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxyhub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ProxyHub API...")
    start_scheduler()
    yield
    logger.info("Shutting down ProxyHub API...")
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="Plataforma para gerenciamento de proxies, filas de scraping e monitoramento em tempo real.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProxyHubException)
async def proxyhub_exception_handler(request: Request, exc: ProxyHubException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(api_router)
