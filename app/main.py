from contextlib import asynccontextmanager
from inspect import isawaitable
from typing import cast, List

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.core.logger import logger
from app.v1_0.v1_router import v1_router
from app.app_containers import ApplicationContainer
from app.storage.database import async_session, dispose_engine
from app.v1_0.routers import realtime_router
API_PREFIX = getattr(settings, "API_PREFIX", "/api")

@property
def CORS_ORIGINS_LIST(self) -> List[str]:
    return ["*"] if self.CORS_ORIGINS.strip() == "*" else [
        o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()
    ]


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

    origins = settings.CORS_ORIGINS_LIST
    allow_credentials = True

    if "*" in origins:
        # wildcard + credenciales no legal en CORS
        allow_credentials = False

    logger.info("CORS origins=%s allow_credentials=%s", origins, allow_credentials)

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
    app.include_router(realtime_router.router, prefix=API_PREFIX)

    return app


app = create_app()
