from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Regimen(str, Enum):
    COMUN = "COMUN"
    NO_RESPONSABLE = "NO_RESPONSABLE"
    SIMPLE = "SIMPLE"

@dataclass(slots=True)
class CompanyDTO:
    id: int
    razon_social: str
    nombre_completo: str
    cc_nit: str
    email_facturacion: str
    celular: Optional[str]
    direccion: str
    municipio: str
    departamento: str
    codigo_postal: Optional[str]
    regimen: Regimen