import hashlib
from typing import Dict, Any, List, Tuple, Set
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.helper.io import (
    read_csv, read_xlsx,
    HeaderMapper,
    validate_rows,
    CUSTOMER_SCHEMA,
    SUPPLIER_SCHEMA,
    PRODUCT_SCHEMA,
    ImportOptions,
)
from app.v1_0.repositories import CustomerRepository, SupplierRepository, ProductRepository


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

        key_field = (
            "tax_id" if opts.entity in ("customers", "suppliers")
            else "reference"
        )
        mapped, dd_stats = self._dedupe_in_file(mapped, key_field)

        errors = validate_rows(mapped, schema)
        if errors:
            return {
                "status": "failed",
                "entity": opts.entity,
                "inserted": 0,
                "total_rows": len(mapped),
                "errors": errors,
                "dedupe_in_file": dd_stats,
                "meta": meta,
            }

        if opts.dry_run:
            return {
                "status": "ready",
                "entity": opts.entity,
                "inserted": 0,
                "total_rows": len(mapped),
                "errors": [],
                "dedupe_in_file": dd_stats,
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
            "dedupe_in_file": dd_stats,
            "meta": meta,
        }

    async def _read_any(self, content: bytes, name: str, opts: ImportOptions) -> tuple[list[dict], dict]:
        if name.endswith(".csv"):
            return read_csv(content, delimiter=opts.delimiter)
        if name.endswith(".xlsx"):
            return read_xlsx(content, sheet=opts.sheet, header_row=opts.header_row)
        raise HTTPException(status_code=415, detail="Solo .csv o .xlsx")

    def _dedupe_in_file(self, rows: List[Dict[str, Any]], key_field: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Mantiene la primera fila por cada valor no vacío de `key_field`.
        Filas con `key_field` vacío no se deduplican entre sí.
        Normaliza por strip().lower() para comparar.
        """
        seen: Set[str] = set()
        out: List[Dict[str, Any]] = []
        removed = 0
        empty_keys = 0

        for r in rows:
            raw = r.get(key_field)
            key = None if raw is None else str(raw).strip()
            if not key:
                empty_keys += 1
                out.append(r)          
                continue
            norm = key.lower()
            if norm in seen:
                removed += 1
                continue
            seen.add(norm)
            out.append(r)

        return out, {
            "key_field": key_field,
            "input_rows": len(rows),
            "kept_rows": len(out),
            "removed_duplicates": removed,
            "rows_with_empty_key": empty_keys,
        }
