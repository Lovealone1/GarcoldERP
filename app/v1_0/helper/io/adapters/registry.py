from .customers import CustomerAdapter
from .suppliers import SupplierAdapter
from .products import ProductAdapter

REGISTRY = {
    "customers": CustomerAdapter(),
    "suppliers": SupplierAdapter(),
    "products": ProductAdapter(),
}

def get_adapter(entity: str):
    try:
        return REGISTRY[entity]
    except KeyError:
        raise ValueError(f"Entidad no soportada: {entity}")
