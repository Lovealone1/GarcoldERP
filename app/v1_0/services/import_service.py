import hashlib
from typing import Any, Dict, List, Set, Tuple

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.helper.io import (
    HeaderMapper,
    ImportOptions,
    PRODUCT_SCHEMA,
    SUPPLIER_SCHEMA,
    CUSTOMER_SCHEMA,
    read_csv,
    read_xlsx,
    validate_rows,
)
from app.v1_0.repositories import (
    CustomerRepository,
    ProductRepository,
    SupplierRepository,
)


class ImportService:
    """Bulk import for customers, suppliers, and products with header mapping and validation."""

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
            "products": (PRODUCT_SCHEMA, self.product_repository),
        }

    async def import_insert(
        self,
        *,
        file: UploadFile,
        opts: ImportOptions,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Read, validate, and insert rows in bulk.

        Steps:
          1) Read CSV/XLSX into rows and collect simple metadata.
          2) Resolve target schema and repository based on `opts.entity`.
          3) Apply header mapping and de-duplicate in-file by key field.
          4) Validate rows against the entity schema.
          5) Insert in chunks unless `dry_run` is set.

        Args:
            file: Uploaded CSV or XLSX file.
            opts: Import options including entity, mapping options, and dry_run.
            db: Active async DB session.

        Returns:
            A dict with status, counters, optional errors, and metadata.

        Raises:
            HTTPException: 400 for missing filename or empty content.
                           400 for unsupported entity.
                           415 for unsupported file type.
        """
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

        key_field = "tax_id" if opts.entity in ("customers", "suppliers") else "reference"
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

    async def _read_any(
        self,
        content: bytes,
        name: str,
        opts: ImportOptions,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Read CSV or XLSX into a list of dict rows plus simple metadata.

        Args:
            content: Raw file bytes.
            name: Lowercased filename to infer type.
            opts: Import options used for delimiter/sheet/header row.

        Returns:
            (rows, meta) where rows is a list of dictionaries and meta is a dict.

        Raises:
            HTTPException: 415 if extension is not .csv or .xlsx.
        """
        if name.endswith(".csv"):
            return read_csv(content, delimiter=opts.delimiter)
        if name.endswith(".xlsx"):
            return read_xlsx(content, sheet=opts.sheet, header_row=opts.header_row)
        raise HTTPException(status_code=415, detail="Solo .csv o .xlsx")

    def _dedupe_in_file(
        self,
        rows: List[Dict[str, Any]],
        key_field: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Keep the first row for each non-empty `key_field` value.

        Comparison uses `strip().lower()`. Rows with empty key are never
        considered duplicates among themselves.

        Args:
            rows: Parsed and header-mapped rows.
            key_field: Field used to identify duplicates.

        Returns:
            (filtered_rows, stats) with basic de-duplication metrics.
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
