from typing import Tuple, List
import httpx
from fastapi import (
    APIRouter, HTTPException, Depends, status, Path,
    UploadFile, File, Response
)
from dependency_injector.wiring import inject, Provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger
from app.v1_0.schemas import MediaOutDTO, MediaKindDTO
from app.v1_0.services.media_service import MediaService
from app.v1_0.repositories import MediaRepository
from app.storage.cloud_storage.types import ALLOWED_IMAGE_MIME
from app.storage.cloud_storage.service import CloudStorageService

router = APIRouter(prefix="/media", tags=["Media"])

MAX_MB = 5
MAX_BYTES = MAX_MB * 1024 * 1024


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
    "/product/{product_id}/upload-files",
    response_model=list[MediaOutDTO],
    status_code=status.HTTP_201_CREATED,
    summary="Upload up to 3 images for a product in one request",
)
@inject
async def upload_product_files(
    product_id: int = Path(..., ge=1),
    files: List[UploadFile] = File(..., description="1-3 image files"),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    cnt = await repo.count_product_images(db, product_id)
    remaining = max(0, 3 - cnt)
    if remaining <= 0:
        raise HTTPException(409, "maximum 3 images per product")
    if not files:
        raise HTTPException(400, "no files provided")

    results: list[MediaOutDTO] = []

    for f in files[:remaining]:
        data = await f.read()
        if not data:
            raise HTTPException(400, "empty file")
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"file exceeds {MAX_MB}MB")

        ct = (f.content_type or "").split(";")[0].strip().lower()
        if ct not in ALLOWED_IMAGE_MIME:
            from app.storage.cloud_storage.types import sniff_mime
            sniffed = sniff_mime(data) or ""
            if sniffed in ALLOWED_IMAGE_MIME:
                ct = sniffed
            else:
                raise HTTPException(400, f"unsupported content-type: {ct or sniffed or 'unknown'}")

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
            content_type=ct,
            bytes=len(data),
            checksum=None,
        )
        results.append(
            MediaOutDTO(
                id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=storage.view_url(row.key)
            )
        )

    return results


@router.get(
    "/product/{product_id}",
    response_model=list[MediaOutDTO],
    summary="List product images",
)
@inject
async def list_product_media(
    product_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
):
    rows = await repo.list_by_product(db, product_id)
    return [
        MediaOutDTO(id=r.id, kind=MediaKindDTO(r.kind), key=r.key, public_url=storage.view_url(r.key))
        for r in rows
    ]


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
        content_type=ct,
        bytes=len(data),
        checksum=None,
    )
    return MediaOutDTO(id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=storage.view_url(row.key))


@router.post(
    "/purchase/{purchase_id}/upload-files",
    response_model=list[MediaOutDTO],
    status_code=status.HTTP_201_CREATED,
    summary="Upload up to 10 invoice images for a purchase in one request",
)
@inject
async def upload_purchase_files(
    purchase_id: int = Path(..., ge=1),
    files: List[UploadFile] = File(..., description="1-10 image files"),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    existing = await repo.list_by_purchase(db, purchase_id)
    remaining = max(0, 10 - len(existing))
    if remaining <= 0:
        raise HTTPException(409, "maximum 10 images per purchase")
    if not files:
        raise HTTPException(400, "no files provided")

    results: list[MediaOutDTO] = []

    for f in files[:remaining]:
        data = await f.read()
        if not data:
            raise HTTPException(400, "empty file")
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"file exceeds {MAX_MB}MB")

        ct = (f.content_type or "").split(";")[0].strip().lower()
        if ct not in ALLOWED_IMAGE_MIME:
            from app.storage.cloud_storage.types import sniff_mime
            sniffed = sniff_mime(data) or ""
            if sniffed in ALLOWED_IMAGE_MIME:
                ct = sniffed
            else:
                raise HTTPException(400, f"unsupported content-type: {ct or sniffed or 'unknown'}")

        try:
            key, put_url, headers = storage.presign_put(prefix=f"invoices/{purchase_id}", content_type=ct)
            async with httpx.AsyncClient(timeout=60) as client:
                r2 = await client.put(put_url, content=data, headers=headers)
            if r2.status_code != 200:
                raise HTTPException(502, detail={"r2_status": r2.status_code, "r2_text": r2.text[:500], "ct": ct})
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[MediaRouter] R2 PUT purchase error: %s", e, exc_info=True)
            raise HTTPException(502, "R2 upload failed")

        row = await service.confirm_purchase_invoice(
            db,
            purchase_id=purchase_id,
            key=key,
            content_type=ct,
            bytes=len(data),
            checksum=None,
        )
        results.append(
            MediaOutDTO(
                id=row.id, kind=MediaKindDTO(row.kind), key=row.key, public_url=storage.view_url(row.key)
            )
        )

    return results


@router.get(
    "/purchase/{purchase_id}",
    response_model=list[MediaOutDTO],
    summary="List purchase invoice images",
)
@inject
async def list_purchase_media(
    purchase_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    repo: MediaRepository = Depends(Provide[ApplicationContainer.api_container.media_repository]),
    storage: CloudStorageService = Depends(Provide[ApplicationContainer.api_container.cloud_storage_service]),
):
    rows = await repo.list_by_purchase(db, purchase_id)
    return [
        MediaOutDTO(id=r.id, kind=MediaKindDTO(r.kind), key=r.key, public_url=storage.view_url(r.key))
        for r in rows
    ]


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media by id (DB + R2)",
)
@inject
async def delete_media_endpoint(
    media_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    service: MediaService = Depends(Provide[ApplicationContainer.api_container.media_service]),
):
    await service.delete_media(db, media_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)