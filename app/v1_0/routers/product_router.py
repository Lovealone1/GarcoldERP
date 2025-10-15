from typing import List, Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import ProductUpsert
from app.v1_0.entities import ProductDTO, ProductPageDTO, SaleProductsDTO
from app.v1_0.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/create",
    response_model=ProductDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create product",
)
@inject
async def create_product(
    request: ProductUpsert,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.info(f"[ProductRouter] create payload={request.model_dump()}")
    try:
        return await service.create(request, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] create error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create product")


@router.get(
    "/by-id/{product_id}",
    response_model=ProductDTO,
    summary="Get product by ID",
)
@inject
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.debug(f"[ProductRouter] get id={product_id}")
    try:
        return await service.get(product_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch product")


@router.get(
    "",
    response_model=List[ProductDTO],
    summary="List all products",
)
@inject
async def list_products(
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.debug("[ProductRouter] list_all")
    try:
        return await service.list_all(db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] list_all error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list products")


@router.get(
    "/page",
    response_model=ProductPageDTO,
    summary="List products paginated",
)
@inject
async def list_products_paginated(
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.debug(f"[ProductRouter] list_paginated page={page}")
    try:
        return await service.list_paginated(page, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] list_paginated error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list products")


@router.patch(
    "/by-id/{product_id}",
    response_model=ProductDTO,
    summary="Update product",
)
@inject
async def update_product(
    product_id: int,
    data: ProductUpsert,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.info(f"[ProductRouter] update id={product_id}")
    try:
        return await service.update(product_id, data, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] update error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update product")


@router.delete(
    "/by-id/{product_id}",
    response_model=Dict[str, str],
    summary="Delete product",
)
@inject
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.warning(f"[ProductRouter] delete id={product_id}")
    try:
        ok = await service.delete(product_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete product")

    if not ok:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": f"Product with ID {product_id} deleted successfully"}


@router.patch(
    "/by-id/{product_id}/increase",
    response_model=ProductDTO,
    summary="Increase quantity",
)
@inject
async def increase_quantity(
    product_id: int,
    amount: int = Body(..., embed=True, ge=1),
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.info(f"[ProductRouter] increase id={product_id} amount={amount}")
    try:
        return await service.increase_quantity(product_id, amount, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] increase error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to increase quantity")


@router.patch(
    "/by-id/{product_id}/decrease",
    response_model=ProductDTO,
    summary="Decrease quantity",
)
@inject
async def decrease_quantity(
    product_id: int,
    amount: int = Body(..., embed=True, ge=1),
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.info(f"[ProductRouter] decrease id={product_id} amount={amount}")
    try:
        return await service.decrease_quantity(product_id, amount, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] decrease error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to decrease quantity")


@router.get(
    "/top",
    response_model=List[Dict[str, Any]],
    summary="Top products by quantity in range",
)
@inject
async def top_products(
    date_from: date = Query(...),
    date_to: date = Query(...),
    limit: Optional[int] = Query(None, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.debug(f"[ProductRouter] top date_from={date_from} date_to={date_to} limit={limit}")
    try:
        return await service.top_products_by_quantity(
            date_from=date_from, date_to=date_to, db=db, limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] top error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compute top products")


@router.post(
    "/sold-in-range",
    response_model=List[SaleProductsDTO],
    summary="Sold products for given IDs in range",
)
@inject
async def sold_in_range(
    payload: Dict[str, Any] = Body(..., example={
        "date_from": "2025-01-01",
        "date_to": "2025-01-31",
        "product_ids": [1, 2, 3]
    }),
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    try:
        return await service.sold_products_in_range(
            db=db,
            date_from=payload["date_from"],
            date_to=payload["date_to"],
            product_ids=payload["product_ids"],
        )
    except KeyError:
        raise HTTPException(status_code=400, detail="Fields required: date_from, date_to, product_ids")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] sold_in_range error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch sold products")
