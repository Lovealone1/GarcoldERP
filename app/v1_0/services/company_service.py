# Third-party
from sqlalchemy.ext.asyncio import AsyncSession

# Internal
from typing import Any, Optional
from app.v1_0.entities import CompanyDTO, Regimen
from app.v1_0.models import Company
from app.v1_0.repositories import CompanyRepository


class CompanyService:
    """
    Service layer for company profile read and update operations.
    """

    def __init__(self, company_repository: CompanyRepository) -> None:
        """
        Initialize the service with its repository.

        Args:
            company_repository: Repository for company persistence.
        """
        self.company_repository = company_repository

    async def patch_company(self, session: AsyncSession, **fields: Any) -> CompanyDTO:
        """
        Partially update the single company record and return the updated DTO.

        Args:
            session: Active async database session.
            **fields: Arbitrary fields to patch on the company model.

        Returns:
            CompanyDTO: The updated company view.

        Raises:
            ValueError: If `regimen` stored cannot be mapped to the Regimen enum.
        """
        async with session.begin():
            c: Company = await self.company_repository.patch_single(session, **fields)

        regimen = c.regimen if isinstance(c.regimen, Regimen) else Regimen(c.regimen)

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
            regimen=regimen,
        )

    async def get_company(self, session: AsyncSession) -> Optional[CompanyDTO]:
        """
        Retrieve the single company record as DTO.

        Args:
            session: Active async database session.

        Returns:
            CompanyDTO | None: Company data if present, otherwise None.

        Raises:
            ValueError: If `regimen` stored cannot be mapped to the Regimen enum.
        """
        c = await self.company_repository.get_single(session)
        if not c:
            return None

        regimen = c.regimen if isinstance(c.regimen, Regimen) else Regimen(c.regimen)

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
            regimen=regimen,
        )
