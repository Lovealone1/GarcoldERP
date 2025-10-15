from typing import Annotated
import httpx

from fastapi import APIRouter, HTTPException, Depends, status, Path, Query
from pydantic import AnyHttpUrl
from dependency_injector.wiring import inject, Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.schemas import MediaOutDTO, MediaKindDTO, ContentTypeImage
from app.v1_0.services.media_service import MediaService
from app.v1_0.repositories import MediaRepository
from app.storage.cloud_storage.types import ALLOWED_IMAGE_MIME
from app.storage.cloud_storage.service import CloudStorageService

router = APIRouter(prefix="/media", tags=["Media"])

MAX_MB = 5
MAX_BYTES = MAX_MB * 1024 * 1024


async def _fetch_image(url: str, *, expect_ct: str) -> tuple[bytes, str]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            data = resp.content
            if not data:
                raise HTTPException(400, "empty image")
            if len(data) > MAX_BYTES:
                raise HTTPException(413, f"file exceeds {MAX_MB}MB")
            ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ct in ALLOWED_IMAGE_MIME:
                return data, ct
            if expect_ct in ALLOWED_IMAGE_MIME:
                return data, expect_ct
            raise HTTPException(400, f"unsupported content-type: {ct or expect_ct}")
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error("[MediaRouter] fetch status error: %s", e, exc_info=True)
        raise HTTPException(502, f"fetch failed: {e.response.status_code}")
    except Exception as e:
        logger.error("[MediaRouter] fetch error: %s", e, exc_info=True)
        raise HTTPException(502, "fetch failed")


@router.post(
    "/avatar/upload-from-url",
    response_model=MediaOutDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Download avatar by URL, upload to R2 with presigned PUT, and persist",
)
@inject
async def upload_avatar_from_url(
    image_url: Annotated[AnyHttpUrl, Query(..., description="Direct image URL")],
    user_id: Annotated[int, Query(ge=1)],
    content_type: ContentTypeImage = Query("image/jpeg"),
    db: AsyncSession = Depends(get_db),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    data, ct = await _fetch_image(str(image_url), expect_ct=content_type)
    try:
        key, put_url, headers = storage.presign_put(prefix=f"avatars/{user_id}", content_type=ct)
        async with httpx.AsyncClient(timeout=60) as client:
            r2 = await client.put(put_url, content=data, headers=headers)
        if r2.status_code != 200:
            raise HTTPException(502, detail={"r2_status": r2.status_code, "r2_text": r2.text[:500], "ct": ct})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MediaRouter] R2 PUT avatar error: %s", e, exc_info=True)
        raise HTTPException(502, "R2 upload failed")

    row = await service.confirm_user_avatar(
        db,
        user_id=user_id,
        key=key,
        public_url=storage.build_public_url(key),
        content_type=ct,
        bytes=len(data),
        checksum=None,
    )
    return MediaOutDTO(id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=row.public_url)


@router.post(
    "/product/{product_id}/upload-from-url",
    response_model=MediaOutDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Download image by URL, upload to R2 with presigned PUT, and persist (max 3 per product)",
)
@inject
async def upload_product_from_url(
    image_url: Annotated[AnyHttpUrl, Query(..., description="Direct image URL")],
    product_id: int = Path(..., ge=1),
    content_type: ContentTypeImage = Query("image/jpeg"),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    cnt = await repo.count_product_images(db, product_id)
    if cnt >= 3:
        raise HTTPException(409, "maximum 3 images per product")

    data, ct = await _fetch_image(str(image_url), expect_ct=content_type)
    try:
        key, put_url, headers = storage.presign_put(prefix=f"products/{product_id}", content_type=ct)
        async with httpx.AsyncClient(timeout=60) as client:
            r2 = await client.put(put_url, content=data, headers=headers)
        if r2.status_code != 200:
            raise HTTPException(502, detail={"r2_status": r2.status_code, "r2_text": r2.text[:500], "ct": ct})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MediaRouter] R2 PUT product error: %s", e, exc_info=True)
        raise HTTPException(502, "R2 upload failed")

    row = await service.confirm_product_image(
        db,
        product_id=product_id,
        key=key,
        public_url=storage.build_public_url(key),
        content_type=ct,
        bytes=len(data),
        checksum=None,
    )
    return MediaOutDTO(id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=row.public_url)


@router.post(
    "/purchase/{purchase_id}/invoice/upload-from-url",
    response_model=MediaOutDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Download invoice by URL, upload to R2 with presigned PUT, and persist",
)
@inject
async def upload_invoice_from_url(
    image_url: Annotated[AnyHttpUrl, Query(..., description="Direct image URL")],
    purchase_id: int = Path(..., ge=1),
    content_type: ContentTypeImage = Query("image/jpeg"),
    db: AsyncSession = Depends(get_db),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    data, ct = await _fetch_image(str(image_url), expect_ct=content_type)
    try:
        key, put_url, headers = storage.presign_put(prefix=f"invoices/{purchase_id}", content_type=ct)
        async with httpx.AsyncClient(timeout=60) as client:
            r2 = await client.put(put_url, content=data, headers=headers)
        if r2.status_code != 200:
            raise HTTPException(502, detail={"r2_status": r2.status_code, "r2_text": r2.text[:500], "ct": ct})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[MediaRouter] R2 PUT invoice error: %s", e, exc_info=True)
        raise HTTPException(502, "R2 upload failed")

    row = await service.confirm_purchase_invoice(
        db,
        purchase_id=purchase_id,
        key=key,
        public_url=storage.build_public_url(key),
        content_type=ct,
        bytes=len(data),
        checksum=None,
    )
    return MediaOutDTO(id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=row.public_url)