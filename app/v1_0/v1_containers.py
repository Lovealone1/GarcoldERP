from dependency_injector import containers, providers
from app.v1_0.repositories import (
    BankRepository,
    SupplierRepository, 
    CustomerRepository,
    ProductRepository, 
    LoanRepository, 
    InvestmentRepository, 
    StatusRepository, 
    TransactionRepository, 
    TransactionTypeRepository, 
    ExpenseRepository, 
    ExpenseCategoryRepository, 
    SaleRepository, 
    SaleItemRepository, 
    ProfitRepository,
    ProfitItemRepository, 
    SalePaymentRepository, 
    PurchaseRepository,
    PurchaseItemRepository, 
    PurchasePaymentRepository, 
    CompanyRepository, 
    MediaRepository
    )
from app.v1_0.services import (
    BankService, 
    SupplierService, 
    CustomerService, 
    ProductService, 
    LoanService, 
    InvestmentService, 
    StatusService, 
    TransactionService, 
    ExpenseService, 
    SaleService,
    SalePaymentService, 
    PurchaseService, 
    PurchasePaymentService,
    ProfitService,
    InvoiceService, 
    DashboardService, 
    MediaService
    )
from app.storage.cloud_storage import CloudStorageService
class APIContainer(containers.DeclarativeContainer):

    bank_repository = providers.Singleton(BankRepository)
    supplier_repository = providers.Singleton(SupplierRepository)
    customer_repository = providers.Singleton(CustomerRepository)
    product_repository = providers.Singleton(ProductRepository)
    loan_repository = providers.Singleton(LoanRepository)
    investment_repository = providers.Singleton(InvestmentRepository)
    status_repository = providers.Singleton(StatusRepository)
    transaction_repository = providers.Singleton(TransactionRepository)
    transaction_type_repository = providers.Singleton(TransactionTypeRepository)
    expense_repository = providers.Singleton(ExpenseRepository)
    expense_category_repository = providers.Singleton(ExpenseCategoryRepository)
    sale_repository = providers.Singleton(SaleRepository)
    sale_item_repository = providers.Singleton(SaleItemRepository)
    profit_repository = providers.Singleton(ProfitRepository)
    profit_item_repository = providers.Singleton(ProfitItemRepository)
    sale_payment_repository = providers.Singleton(SalePaymentRepository)
    purchase_repository = providers.Singleton(PurchaseRepository)
    purchase_item_repository = providers.Singleton(PurchaseItemRepository)
    purchase_payment_repository = providers.Singleton(PurchasePaymentRepository)
    company_repository = providers.Singleton(CompanyRepository)
    media_repository = providers.Singleton(MediaRepository)
    
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
    transaction_service = providers.Singleton(
        TransactionService,
        transaction_repository = transaction_repository, 
        transaction_type_repository = transaction_type_repository,
        bank_repository = bank_repository
    )
    expense_service = providers.Singleton(
        ExpenseService,
        expense_repository = expense_repository, 
        bank_repository = bank_repository, 
        expense_category_repository = expense_category_repository,
        transaction_service = transaction_service
    )
    sale_service = providers.Singleton(
        SaleService,
        sale_repository = sale_repository,
        sale_item_repository = sale_item_repository,
        product_repository = product_repository,
        customer_repository = customer_repository, 
        status_repository = status_repository, 
        profit_repository = profit_repository,
        profit_item_repository = profit_item_repository,
        bank_repository = bank_repository, 
        sale_payment_repository = sale_payment_repository,
        transaction_service = transaction_service
    )
    sale_payment_service = providers.Singleton(
        SalePaymentService,
        sale_repository = sale_repository,
        status_repository = status_repository,
        sale_payment_repository = sale_payment_repository,
        bank_repository = bank_repository,
        customer_repository = customer_repository,
        transaction_service = transaction_service
    )
    purchase_service = providers.Singleton(
        PurchaseService,
        purchase_repository = purchase_repository,
        purchase_item_repository = purchase_item_repository, 
        product_repository = product_repository, 
        supplier_repository = supplier_repository, 
        status_repository = status_repository, 
        bank_repository = bank_repository, 
        purchase_payment_repository = purchase_payment_repository, 
        transaction_service = transaction_service
    )
    purchase_payment_service = providers.Singleton(
        PurchasePaymentService,
        purchase_repository = purchase_repository, 
        status_repository = status_repository, 
        purchase_payment_repository = purchase_payment_repository, 
        bank_repository = bank_repository,
        transaction_service = transaction_service
    )
    profit_service = providers.Singleton(
        ProfitService,
        profit_repository = profit_repository, 
        profit_item_repository = profit_item_repository,
        product_repository = product_repository
    )
    invoice_service = providers.Singleton(
        InvoiceService, 
        customer_repository = customer_repository, 
        company_repository = company_repository, 
        sale_item_repository = sale_item_repository, 
        sale_repository = sale_repository, 
        bank_repository = bank_repository, 
        status_repository = status_repository, 
        product_repository = product_repository, 
    )
    dashboard_service = providers.Singleton(
        DashboardService,
        sale_repository = sale_repository, 
        customer_repository = customer_repository, 
        purchase_repository = purchase_repository, 
        supplier_repository = supplier_repository, 
        bank_repository = bank_repository, 
        expense_repository = expense_repository, 
        profit_repository = profit_repository, 
        sale_item_repository = sale_item_repository, 
        product_repository = product_repository, 
        loan_repository = loan_repository, 
        investment_repository = investment_repository
    )
    cloud_storage_service = providers.Singleton(CloudStorageService)
    media_service = providers.Factory(
        MediaService,
        media_repository=media_repository,
        storage=cloud_storage_service,
    )