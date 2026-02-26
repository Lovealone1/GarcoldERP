from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models.company import Company, RegimenCo


async def seed_company(db: AsyncSession) -> Company:

    stmt = (
        insert(Company)
        .values(
            razon_social="Tienda Garcold",
            nombre_completo="Alveiro Antonio Garcia Loaiza",
            cc_nit="71715988-9",
            email_facturacion="agl792@hotmail.com",
            celular="3225711760",
            direccion="Carrera 35 #37-46",
            municipio="Medellín",
            departamento="Antioquia",
            codigo_postal="050016",
            regimen=RegimenCo.SIMPLE,  
        )
        .returning(Company)
    )

    res = await db.execute(stmt)
    company = res.scalar_one()
    await db.commit()
    return company
