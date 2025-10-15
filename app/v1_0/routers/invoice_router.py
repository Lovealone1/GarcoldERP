from fastapi import APIRouter, HTTPException, Depends, status, Response, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from dependency_injector.wiring import inject, Provide

from app.storage.database.db_connector import get_db
from app.app_containers import ApplicationContainer
from app.core.logger import logger

from app.utils.pdf_renderer import PdfRenderer
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

def _merge_query(extra_query: str | None, company_id: int | None) -> str | None:
    parts: list[str] = []
    if extra_query:
        parts.append(extra_query.strip("&?"))
    if company_id is not None:
        parts.append(f"company_id={company_id}")
    return "&".join(p for p in parts if p) or None

@router.get(
    "/sales/{sale_id}/pdf",
    summary="Invoice PDF download",
    responses={200: {"content": {"application/pdf": {}}}},
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
@inject
async def get_invoice_pdf(
    sale_id: int = Path(..., ge=1),
    company_id: int | None = Query(None, ge=1),
    pdf_renderer: PdfRenderer = Depends(Provide[ApplicationContainer.api_container.pdf_renderer]),
    db: AsyncSession = Depends(get_db),  # reservado si necesitas validar existencia
):
    try:
        extra_q = _merge_query("print=1", company_id)
        pdf_bytes = await pdf_renderer.render_invoice_pdf(
            sale_id=sale_id,
            pdf_options=None,
            extra_query=extra_q or "print=1",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PDF error: {e}")

    filename = f"invoice_{sale_id}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)