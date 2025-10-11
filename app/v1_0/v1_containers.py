from dependency_injector import containers, providers
from app.v1_0.repositories import (
    BankRepository,
    SupplierRepository
    )
from app.v1_0.services import (
    BankService, 
    SupplierService
)
class APIContainer(containers.DeclarativeContainer):
    bank_repository = providers.Singleton(BankRepository)
    supplier_repository = providers.Singleton(SupplierRepository)
    bank_service = providers.Singleton(
        BankService, 
        bank_repository=bank_repository
    )
    supplier_service = providers.Singleton(
        SupplierService,
        supplier_repository = supplier_repository
    )