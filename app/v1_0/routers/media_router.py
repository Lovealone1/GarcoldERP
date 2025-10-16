# app/v1_0/api/media_router.py
from typing import Annotated, List, Tuple
import httpx
from fastapi import (
    APIRouter, HTTPException, Depends, status, Path, Query,
    UploadFile, File
)
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


async def _fetch_image(url: str, *, expect_ct: str) -> Tuple[bytes, str]:
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


async def _read_upload(img: UploadFile) -> Tuple[bytes, str]:
    data = await img.read()
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"file exceeds {MAX_MB}MB")
    ct = (img.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_IMAGE_MIME:
        raise HTTPException(400, f"unsupported content-type: {ct or 'unknown'}")
    return data, ct



@router.post(
    "/product/{product_id}/upload-file",
    response_model=List[MediaOutDTO],
    status_code=status.HTTP_201_CREATED,
    summary="Upload up to 3 product images from local files and persist",
)
@inject
async def upload_product_files(
    product_id: int = Path(..., ge=1),
    files: List[UploadFile] = File(..., description="1 to 3 image files"),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    if not files:
        raise HTTPException(400, "no files")
    if len(files) > 3:
        raise HTTPException(400, "max 3 files per request")

    existing = await repo.count_product_images(db, product_id)
    remaining = max(0, 3 - existing)
    if remaining <= 0:
        raise HTTPException(409, "maximum 3 images per product")
    if len(files) > remaining:
        raise HTTPException(409, f"only {remaining} slots available")

    out: List[MediaOutDTO] = []
    for f in files:
        data, ct = await _read_upload(f)
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
        out.append(MediaOutDTO(id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=row.public_url))
    return out

@router.post(
    "/purchase/{purchase_id}/invoice/upload",
    response_model=MediaOutDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Upload invoice image from local file and persist",
)
@inject
async def upload_invoice_file(
    purchase_id: int = Path(..., ge=1),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    data, ct = await _read_upload(file)
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
