from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.helper.io import (
    write_csv, write_xlsx,
    rows_from_dtos,
    CUSTOMER_FIELDS, PRODUCT_FIELDS, SUPPLIER_FIELDS, FileFmt
)
from app.v1_0.services import CustomerService, ProductService, SupplierService

class ExportService:
    def __init__(self, customer_service: CustomerService, product_service: ProductService, supplier_service: SupplierService) -> None:
        self.cs = customer_service
        self.ps = product_service
        self.ss = supplier_service

    async def export_customers(self, db: AsyncSession, fmt: FileFmt) -> Response:
        dtos = await self.cs.list_all(db)
        rows = rows_from_dtos(dtos, CUSTOMER_FIELDS, entity="customers")
        fname = f"customers.{fmt}"
        return write_csv(rows, fname) if fmt == "csv" else write_xlsx(rows, fname)

    async def export_products(self, db: AsyncSession, fmt: FileFmt) -> Response:
        dtos = await self.ps.list_all(db)
        rows = rows_from_dtos(dtos, PRODUCT_FIELDS, entity="products")
        fname = f"products.{fmt}"
        return write_csv(rows, fname) if fmt == "csv" else write_xlsx(rows, fname)

    async def export_suppliers(self, db: AsyncSession, fmt: FileFmt) -> Response:
        dtos = await self.ss.list_all(db)
        rows = rows_from_dtos(dtos, SUPPLIER_FIELDS, entity="suppliers")
        fname = f"suppliers.{fmt}"
        return write_csv(rows, fname) if fmt == "csv" else write_xlsx(rows, fname)
