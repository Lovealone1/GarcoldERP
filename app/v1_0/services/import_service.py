import hashlib

from typing import Tuple, Dict, Any
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.helper.io import (
    read_csv, read_xlsx, 
    HeaderMapper, 
    validate_rows,
    CUSTOMER_SCHEMA, 
    SUPPLIER_SCHEMA, 
    PRODUCT_SCHEMA,
    ImportOptions
    )
from app.v1_0.repositories import CustomerRepository,SupplierRepository,ProductRepository

class ImportService:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        supplier_repository: SupplierRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.customer_repository = customer_repository
        self.supplier_repository = supplier_repository
        self.product_repository = product_repository
        self._route = {
            "customers": (CUSTOMER_SCHEMA, self.customer_repository),
            "suppliers": (SUPPLIER_SCHEMA, self.supplier_repository),
            "products":  (PRODUCT_SCHEMA,  self.product_repository),
        }

    async def import_insert(
        self,
        *,
        file: UploadFile,
        opts: ImportOptions,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nombre de archivo ausente")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Archivo vacío")

        rows, meta = await self._read_any(content, file.filename.lower(), opts)

        try:
            schema, repo = self._route[opts.entity]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Entidad no soportada: {opts.entity}")

        mapped, _ = HeaderMapper(schema).apply(rows)
        errors = validate_rows(mapped, schema)

        if errors:
            return {
                "status": "failed",
                "entity": opts.entity,
                "inserted": 0,
                "total_rows": len(mapped),
                "errors": errors,
                "meta": meta,
            }

        if opts.dry_run:
            return {
                "status": "ready",
                "entity": opts.entity,
                "inserted": 0,
                "total_rows": len(mapped),
                "errors": [],
                "meta": meta,
            }

        async with db.begin():
            inserted = await repo.insert_many(mapped, session=db, chunk_size=1000)

        job_id = hashlib.sha1(content).hexdigest()[:12]
        return {
            "job_id": job_id,
            "status": "committed",
            "entity": opts.entity,
            "inserted": inserted,
            "total_rows": len(mapped),
            "errors": [],
            "meta": meta,
        }

    async def _read_any(self, content: bytes, name: str, opts: ImportOptions) -> tuple[list[dict], dict]:
        if name.endswith(".csv"):
            return read_csv(content, delimiter=opts.delimiter)
        if name.endswith(".xlsx"):
            return read_xlsx(content, sheet=opts.sheet, header_row=opts.header_row)  
        raise HTTPException(status_code=415, detail="Solo .csv o .xlsx")
