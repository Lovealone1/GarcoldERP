from .base import EntitySchema, FieldSpec
from .aliases import build_aliases

CUSTOMER_SCHEMA = EntitySchema(
    entity="customers",
    fields=[
        FieldSpec("name", required=True, type="str"),
        FieldSpec("tax_id", type="str"),
        FieldSpec("email", type="email"),
        FieldSpec("phone", type="str"),
        FieldSpec("address", type="str"),
        FieldSpec("city", type="str"),
        FieldSpec("balance", type="number"),
    ],
    unique_keys=["tax_id", "email"],
    aliases=build_aliases([
        ("name", ["nombre", "client_name"]),
        ("tax_id", ["documento", "nit", "dni", "id_number"]),
        ("email", ["correo", "e-mail"]),
        ("phone", ["telefono", "tel"]),
        ("address", ["direccion"]),
        ("city", ["ciudad"]),
        ("balance", ["saldo"]),
    ]),
)
