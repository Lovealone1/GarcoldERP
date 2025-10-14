from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.utils.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.v1_0.entities import SaleInvoiceDTO
from app.v1_0.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])

@router.get(
    "/from-sale/{sale_id}",
    response_model=SaleInvoiceDTO,
    status_code=status.HTTP_200_OK,
    summary="Generate an invoice from a sale",
)
@inject
async def generate_invoice_from_sale(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    invoice_service: InvoiceService = Depends(
        Provide[ApplicationContainer.api_container.invoice_service]
    ),
) -> SaleInvoiceDTO:
    logger.info(f"[InvoiceRouter] generate_invoice_from_sale sale_id={sale_id}")
    try:
        invoice = await invoice_service.generate_from_sale(sale_id, db)
        return invoice
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[InvoiceRouter] generate_invoice_from_sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate invoice")
