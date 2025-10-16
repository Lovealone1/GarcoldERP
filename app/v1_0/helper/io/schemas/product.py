from .base import EntitySchema, FieldSpec
from .aliases import build_aliases

PRODUCT_SCHEMA = EntitySchema(
    entity="products",
    fields=[
        FieldSpec("reference", required=True, type="str"),
        FieldSpec("description", type="str"),
        FieldSpec("quantity", type="int"),
        FieldSpec("purchase_price", type="number"),
        FieldSpec("sale_price", type="number"),
        FieldSpec("is_active", type="str"),
    ],
    unique_keys=["reference"],
    aliases=build_aliases([
        ("reference", ["sku", "codigo", "code", "referencia"]),
        ("description", ["descripcion", "product_name", "nombre"]),
        ("quantity", ["qty", "cantidad", "stock"]),
        ("purchase_price", ["precio_compra", "costo", "cost"]),
        ("sale_price", ["precio_venta", "precio", "price"]),
        ("is_active", ["activo", "habilitado"]),
    ]),
)
