from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.v1_0.models import Company
from app.v1_0.repositories import CompanyRepository
from app.v1_0.entities import CompanyDTO, Regimen

class CompanyService:
    def __init__(self, company_repository: CompanyRepository):
        self.company_repository = company_repository

    async def patch_company(self, session: AsyncSession, **fields: Any) -> CompanyDTO:
        async with session.begin():
            c: Company = await self.company_repository.patch_single(session, **fields)
        return CompanyDTO(
            id=c.id,
            razon_social=c.razon_social,
            nombre_completo=c.nombre_completo,
            cc_nit=c.cc_nit,
            email_facturacion=c.email_facturacion,
            celular=c.celular,
            direccion=c.direccion,
            municipio=c.municipio,
            departamento=c.departamento,
            codigo_postal=c.codigo_postal,
            regimen=c.regimen if isinstance(c.regimen, Regimen) else Regimen(c.regimen),
        )

    async def get_company(self, session: AsyncSession) -> Optional[CompanyDTO]:
        c = await self.company_repository.get_single(session)
        if not c:
            return None
        return CompanyDTO(
            id=c.id,
            razon_social=c.razon_social,
            nombre_completo=c.nombre_completo,
            cc_nit=c.cc_nit,
            email_facturacion=c.email_facturacion,
            celular=c.celular,
            direccion=c.direccion,
            municipio=c.municipio,
            departamento=c.departamento,
            codigo_postal=c.codigo_postal,
            regimen=c.regimen if isinstance(c.regimen, Regimen) else Regimen(c.regimen),
        )
