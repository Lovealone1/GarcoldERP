from dependency_injector import containers, providers
from app.v1_0.v1_containers import APIContainer
from app.storage.database import async_session

class ApplicationContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
                "app.v1_0.routers.bank_router",
                "app.v1_0.routers.supplier_router",
                "app.v1_0.routers.customer_router", 
                "app.v1_0.routers.product_router",
                "app.v1_0.routers.loan_router",
                "app.v1_0.routers.investment_router",
                "app.v1_0.routers.status_router",
                "app.v1_0.routers.transaction_router", 
                "app.v1_0.routers.expense_router",
                "app.v1_0.routers.expense_category_router",
                "app.v1_0.routers.sale_router",
                "app.v1_0.routers.sale_payment_router", 
                "app.v1_0.routers.purchase_router", 
                "app.v1_0.routers.purchase_payment_router", 
                "app.v1_0.routers.profit_router", 
                "app.v1_0.routers.invoice_router", 
                "app.v1_0.routers.dashboard_router",
                "app.v1_0.routers.media_router",
                "app.v1_0.routers.import_router",
                "app.v1_0.routers.export_router",
            ]
    )
    db_session = providers.Object(async_session)

    api_container = providers.Container(
        APIContainer
    )
