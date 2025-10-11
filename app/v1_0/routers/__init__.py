from .bank_router import router as bank_router
from .supplier_router import router as supplier_router
from .customer_router import router as customer_router
from .product_router import router as product_router 
defined_routers = [
    bank_router,
    supplier_router,
    customer_router,
    product_router
    ]