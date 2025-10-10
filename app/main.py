from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.core.logger import logger
from app.v1_0.v1_router import v1_router
from app.app_containers import ApplicationContainer
from app.utils.database import async_session, dispose_engine

API_PREFIX = getattr(settings, "API_PREFIX", "/api/v1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.container.init_resources()
    logger.info(f"{settings.APP_NAME} starting in {settings.APP_ENV}")
    
    try:
        yield
    finally:
        logger.info(f"{settings.APP_NAME} shutdown")
        await dispose_engine()  


def create_app() -> FastAPI:
    container = ApplicationContainer()
    container.db_session.override(async_session)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        lifespan=lifespan,
    )

    app.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    base_router = APIRouter(prefix=API_PREFIX)
    base_router.include_router(v1_router)

    @base_router.get("/", tags=["health"])
    @base_router.get("/ready", tags=["health"])
    async def ready():
        return {
            "message": "ready",
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "prefix": API_PREFIX,
        }

    app.include_router(base_router)
    return app


app = create_app()