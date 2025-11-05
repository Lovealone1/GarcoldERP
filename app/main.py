from contextlib import asynccontextmanager
from inspect import isawaitable
from typing import cast

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.core.logger import logger
from app.v1_0.v1_router import v1_router
from app.app_containers import ApplicationContainer
from app.storage.database import async_session, dispose_engine

API_PREFIX = getattr(settings, "API_PREFIX", "/api")


def _cors_origins() -> list[str]:
    v = getattr(settings, "CORS_ORIGINS", ["*"])
    if isinstance(v, str):
        if v.strip() == "*":
            return ["*"]
        return [s.strip() for s in v.split(",") if s.strip()]
    return list(v)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = cast(ApplicationContainer, app.state.container)
    ret = container.init_resources()
    if isawaitable(ret):
        await ret
    logger.info(f"{settings.APP_NAME} starting in {settings.APP_ENV}")
    try:
        yield
    finally:
        logger.info(f"{settings.APP_NAME} shutdown")
        shut = getattr(container, "shutdown_resources", None)
        if callable(shut):
            r = shut()
            if isawaitable(r):
                await r
        await dispose_engine()


def create_app() -> FastAPI:
    container = ApplicationContainer()
    container.db_session.override(async_session)
    # cablea Provide[...] si aplican
    try:
        container.wire(packages=["app.v1_0"])
    except Exception:
        pass

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        lifespan=lifespan,
    )

    app.state.container = container

    origins = _cors_origins()
    allow_credentials = getattr(settings, "CORS_ALLOW_CREDENTIALS", True)
    if "*" in origins:
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
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
