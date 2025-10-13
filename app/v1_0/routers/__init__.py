from .bank_router import router as bank_router
from .supplier_router import router as supplier_router
from .customer_router import router as customer_router
from .product_router import router as product_router 
from .loan_router import router as loan_router
from .investment_router import router as investment_router
from .status_router import router as status_router
from .transaction_router import router as transaction_router
from .expense_router import router as expense_router
from .sale_router import router as sale_router
defined_routers = [
    bank_router,
    supplier_router,
    customer_router,
    product_router,
    loan_router,
    investment_router,
    status_router,
    transaction_router,
    expense_router,
    sale_router
    ]