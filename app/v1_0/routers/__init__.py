from .bank_router import router as bank_router
from .supplier_router import router as supplier_router
from .customer_router import router as customer_router
from .product_router import router as product_router 
from .loan_router import router as loan_router
from .investment_router import router as investment_router
from .status_router import router as status_router
from .transaction_router import router as transaction_router
from .expense_router import router as expense_router
from .expense_category_router import router as expense_category_router
from .sale_router import router as sale_router
from .sale_payment_router import router as sale_payment_router
from .purchase_router import router as purchase_router
from .purchase_payment_router import router as purchase_payment_router
from .profit_router import router as profit_router
from .invoice_router import router as invoice_router
from .dashboard_router import router as dashboard_router
from .media_router import router as media_router
from .import_router import router as import_router
from .export_router import router as export_router
from .auth_router import router as auth_router
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
    expense_category_router,
    sale_router,
    sale_payment_router,
    purchase_router,
    purchase_payment_router,
    profit_router,
    invoice_router,
    dashboard_router,
    media_router,
    import_router,
    export_router,
    auth_router
    ]