from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.v1_0.models import Product


MOCK_PRODUCTS = [
    {
        "reference": "COCA400",
        "description": "Coca-Cola 400ml",
        "quantity": 50,
        "purchase_price": 1500.00,
        "sale_price": 2500.00,
        "is_active": True,
        "barcode": "7701234560001",
        "barcode_type": "EAN13",
    },
    {
        "reference": "COCA1750",
        "description": "Coca-Cola 1.75L",
        "quantity": 30,
        "purchase_price": 3500.00,
        "sale_price": 5500.00,
        "is_active": True,
        "barcode": "7701234560002",
        "barcode_type": "EAN13",
    },
    {
        "reference": "PEPSI400",
        "description": "Pepsi 400ml",
        "quantity": 40,
        "purchase_price": 1400.00,
        "sale_price": 2400.00,
        "is_active": True,
        "barcode": "7701234560003",
        "barcode_type": "EAN13",
    },
    {
        "reference": "AGUA600",
        "description": "Agua pura 600ml",
        "quantity": 60,
        "purchase_price": 800.00,
        "sale_price": 1500.00,
        "is_active": True,
        "barcode": "7701234560004",
        "barcode_type": "EAN13",
    },
    {
        "reference": "GALLETASCHOC",
        "description": "Galletas de chocolate 6 und",
        "quantity": 25,
        "purchase_price": 1200.00,
        "sale_price": 2200.00,
        "is_active": True,
        "barcode": "7701234560005",
        "barcode_type": "EAN13",
    },
    {
        "reference": "ARROZ500",
        "description": "Arroz 500g",
        "quantity": 80,
        "purchase_price": 2000.00,
        "sale_price": 2800.00,
        "is_active": True,
        "barcode": "7701234560006",
        "barcode_type": "EAN13",
    },
    {
        "reference": "AZUCAR1000",
        "description": "Azúcar 1kg",
        "quantity": 70,
        "purchase_price": 2500.00,
        "sale_price": 3400.00,
        "is_active": True,
        "barcode": "7701234560007",
        "barcode_type": "EAN13",
    },
    {
        "reference": "ACEITE900",
        "description": "Aceite vegetal 900ml",
        "quantity": 45,
        "purchase_price": 6000.00,
        "sale_price": 7800.00,
        "is_active": True,
        "barcode": "7701234560008",
        "barcode_type": "EAN13",
    },
    {
        "reference": "LECHE1000",
        "description": "Leche entera 1L",
        "quantity": 55,
        "purchase_price": 3200.00,
        "sale_price": 4200.00,
        "is_active": True,
        "barcode": "7701234560009",
        "barcode_type": "EAN13",
    },
    {
        "reference": "PANBLANCO",
        "description": "Pan blanco tajado",
        "quantity": 35,
        "purchase_price": 2800.00,
        "sale_price": 3800.00,
        "is_active": True,
        "barcode": "7701234560010",
        "barcode_type": "EAN13",
    },
]


async def seed_products(db: AsyncSession):
    products = []

    for data in MOCK_PRODUCTS:
        stmt = insert(Product).values(**data).returning(Product)
        res = await db.execute(stmt)
        products.append(res.scalar_one())

    await db.commit()
    return products
