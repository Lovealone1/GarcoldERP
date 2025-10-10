from dependency_injector import containers, providers
from app.core.settings import settings
from app.v1_0.repositories import (
    BankRepository
    )
from app.v1_0.services import (
    BankService
)
class APIContainer(containers.DeclarativeContainer):
    bank_repository = providers.Singleton(BankRepository)
    bank_service = providers.Singleton(
        BankService, 
        bank_repository=bank_repository
    )