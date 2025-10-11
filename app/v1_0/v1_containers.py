from dependency_injector import containers, providers
from app.v1_0.repositories import (
    BankRepository,
    SupplierRepository, 
    CustomerRepository,
    ProductRepository, 
    LoanRepository, 
    InvestmentRepository, 
    StatusRepository
    )
from app.v1_0.services import (
    BankService, 
    SupplierService, 
    CustomerService, 
    ProductService, 
    LoanService, 
    InvestmentService, 
    StatusService
)
class APIContainer(containers.DeclarativeContainer):
    bank_repository = providers.Singleton(BankRepository)
    supplier_repository = providers.Singleton(SupplierRepository)
    customer_repository = providers.Singleton(CustomerRepository)
    product_repository = providers.Singleton(ProductRepository)
    loan_repository = providers.Singleton(LoanRepository)
    investment_repository = providers.Singleton(InvestmentRepository)
    status_repository = providers.Singleton(StatusRepository)
    
    bank_service = providers.Singleton(
        BankService, 
        bank_repository=bank_repository
    )
    supplier_service = providers.Singleton(
        SupplierService,
        supplier_repository = supplier_repository
    )
    customer_service = providers.Singleton(
        CustomerService, 
        customer_repository = customer_repository
    )
    product_service = providers.Singleton(
        ProductService,
        product_repository = product_repository
    )
    loan_service = providers.Singleton(
        LoanService,
        loan_repository = loan_repository
    )
    investment_service = providers.Singleton(
        InvestmentService, 
        investment_repository = investment_repository
    )
    status_service = providers.Singleton(
        StatusService,
        status_repository = status_repository
    )