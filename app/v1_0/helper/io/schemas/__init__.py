from .base import EntitySchema, FieldSpec
from .aliases import build_aliases

from .product import PRODUCT_SCHEMA
from .customer import CUSTOMER_SCHEMA
from .supplier import SUPPLIER_SCHEMA

__all__ = [
    "EntitySchema",
    "FieldSpec",
    "build_aliases",
    "PRODUCT_SCHEMA",
    "CUSTOMER_SCHEMA",
    "SUPPLIER_SCHEMA",
]
