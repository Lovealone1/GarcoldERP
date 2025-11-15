from typing import List, Dict, Any, Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Body, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.core.security.deps import AuthContext, get_auth_context
from app.core.security.realtime_auth import build_channel_id_from_auth
from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import ProductUpsert, ProductRangeQuery
from app.v1_0.entities import ProductDTO, ProductPageDTO, SaleProductsDTO
from app.v1_0.services import ProductService

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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
) -> ProductDTO:
    logger.info(
        "[ProductRouter] create payload=%s",
        request.model_dump(),
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.create(
            payload=request,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[ProductRouter] create error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create product",
        )

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
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
) -> ProductDTO:
    logger.info(
        "[ProductRouter] update id=%s",
        product_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.update(
            product_id=product_id,
            payload=data,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[ProductRouter] update error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update product",
        )

@router.delete(
    "/by-id/{product_id}",
    response_model=Dict[str, str],
    summary="Delete product",
)
@inject
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
) -> Dict[str, str]:
    logger.warning(
        "[ProductRouter] delete id=%s",
        product_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        ok = await service.delete(
            product_id=product_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[ProductRouter] delete error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete product",
        )

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return {
        "message": f"Product with ID {product_id} deleted successfully"
    }
    
@router.patch(
    "/by-id/{product_id}/toggle-active",
    response_model=ProductDTO,
    summary="Toggle product active flag",
)
@inject
async def toggle_product_active(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
) -> ProductDTO:
    logger.info(
        "[ProductRouter] toggle_active id=%s",
        product_id,
    )
    channel_id = build_channel_id_from_auth(auth_ctx)

    try:
        return await service.toggle_active(
            product_id=product_id,
            db=db,
            channel_id=channel_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[ProductRouter] toggle_active error: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to toggle product state",
        )

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
    payload: ProductRangeQuery,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    try:
        return await service.sold_products_in_range(
            db=db,
            date_from=payload.date_from,
            date_to=payload.date_to,
            product_ids=payload.product_ids,
        )
    except KeyError:
        raise HTTPException(status_code=400, detail="Fields required: date_from, date_to, product_ids")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] sold_in_range error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch sold products")

@router.get(
    "/by-barcode/{barcode}",
    response_model=ProductDTO,
    summary="Get product by barcode",
)
@inject
async def get_product_by_barcode(
    barcode: str,
    db: AsyncSession = Depends(get_db),
    service: ProductService = Depends(
        Provide[ApplicationContainer.api_container.product_service]
    ),
):
    logger.debug(f"[ProductRouter] get by barcode={barcode}")
    try:
        product = await service.get_by_barcode(barcode, db)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ProductRouter] get_by_barcode error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch product by barcode")
