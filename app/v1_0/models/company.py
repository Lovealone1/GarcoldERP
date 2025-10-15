from enum import Enum
from sqlalchemy import String, Text, Enum as PgEnum, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class RegimenCo(str, Enum):
    COMUN = "COMUN"
    NO_RESPONSABLE = "NO_RESPONSABLE"
    SIMPLE = "SIMPLE"

class Company(Base):
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    razon_social: Mapped[str] = mapped_column(Text)
    nombre_completo: Mapped[str] = mapped_column(Text)
    cc_nit: Mapped[str] = mapped_column(String, index=True)
    email_facturacion: Mapped[str] = mapped_column(String)
    celular: Mapped[str] = mapped_column(String)
    direccion: Mapped[str] = mapped_column(Text)
    municipio: Mapped[str] = mapped_column(String)
    departamento: Mapped[str] = mapped_column(String)
    codigo_postal: Mapped[str] = mapped_column(String)
    regimen: Mapped[RegimenCo] = mapped_column(PgEnum(RegimenCo, name="regimen_co"), default="SIMPLE")