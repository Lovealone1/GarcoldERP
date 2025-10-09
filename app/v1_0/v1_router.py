from fastapi import APIRouter
from app.v1_0.routers import defined_routers

v1_router = APIRouter(prefix="/v1", tags=["v1"])

for r in defined_routers:
    v1_router.include_router(r)