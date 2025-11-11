from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timezone, datetime 
from zoneinfo import ZoneInfo

from app.v1_0.entities import (
    SaleInvoiceDTO,
    CompanyDTO,
    CustomerDTO,
    SaleItemViewDescDTO,
    Regimen
)

from app.v1_0.repositories import (
    CustomerRepository,
    CompanyRepository,
    SaleItemRepository,
    SaleRepository,
    BankRepository,
    StatusRepository,
    ProductRepository,
)

class InvoiceService:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        company_repository: CompanyRepository,
        sale_item_repository: SaleItemRepository,
        sale_repository: SaleRepository,
        bank_repository: BankRepository,
        status_repository: StatusRepository,
        product_repository: ProductRepository
    ) -> None:
        self.customer_repository = customer_repository
        self.company_repository = company_repository
        self.sale_item_repository = sale_item_repository
        self.sale_repository = sale_repository
        self.bank_repository = bank_repository
        self.status_repository = status_repository
        self.product_repository = product_repository
        self.company_id = 1
        
    def fmt_dt(self,dt: datetime | None,
           fmt: str = "%Y-%m-%d %H:%M",
           tz: str = "America/Bogota") -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)  
        return dt.astimezone(ZoneInfo(tz)).strftime(fmt)

    async def generate_from_sale(self, sale_id: int, db: AsyncSession) -> SaleInvoiceDTO:
        sale = await self.sale_repository.get_by_id(sale_id, session=db)
        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found")

        customer = await self.customer_repository.get_by_id(sale.customer_id, session=db)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer_dto = CustomerDTO(
            id=customer.id,
            name=customer.name,
            tax_id=customer.tax_id,
            email=customer.email,
            phone=customer.phone,
            address=customer.address,
            city=customer.city,
            balance=customer.balance,
            created_at=customer.created_at
        )

        bank = await self.bank_repository.get_by_id(sale.bank_id, session=db)
        account_number = getattr(bank, "account_number", None) if bank else None

        status_row = await self.status_repository.get_by_id(sale.status_id, session=db)
        status_name = getattr(status_row, "name", "Desconocido") if status_row else "Desconocido"

        items_model = await self.sale_item_repository.get_by_sale_id(sale.id, session=db)
        items: List[SaleItemViewDescDTO] = []
        for it in items_model:
            prod = await self.product_repository.get_by_id(it.product_id, session=db)
            reference = getattr(prod, "reference", "Desconocido") if prod else "Desconocido"
            description = (
                getattr(prod, "description", None)
                or getattr(prod, "name", None)
                or reference
            )
            items.append(
                SaleItemViewDescDTO(
                    sale_id=sale.id,
                    product_reference=reference,
                    product_description=description,
                    quantity=int(getattr(it, "quantity", 0)),
                    unit_price=float(getattr(it, "unit_price", 0.0) or 0.0),
                    total=float(getattr(it, "total", 0.0) or 0.0),
                )
            )

        company = await self.company_repository.get_by_id(self.company_id, session=db)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        raw = (company.regimen or "").strip().upper().replace(" ", "_")
        try:
            regimen_enum = Regimen(raw)  
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid regimen: {company.regimen!r}")
        company_dto = CompanyDTO(
            id=company.id,
            razon_social=company.razon_social,
            nombre_completo=company.nombre_completo,
            cc_nit=company.cc_nit,
            email_facturacion=company.email_facturacion,
            celular=company.celular,
            direccion=company.direccion,
            municipio=company.municipio,
            departamento=company.departamento,
            codigo_postal=company.codigo_postal,
            regimen=regimen_enum,  
        )

        return SaleInvoiceDTO(
            sale_id=sale.id,
            date=sale.created_at,
            status=status_name,
            total=float(sale.total or 0.0),
            remaining_balance=float(sale.remaining_balance or 0.0),
            account_number=account_number,
            customer=customer_dto,
            company=company_dto,
            items=items,
        )