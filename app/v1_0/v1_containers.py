from dependency_injector import containers, providers

class APIContainer(containers.DeclarativeContainer):
    """Base DI container for v1. Override `db_session` from main."""
    wiring_config = containers.WiringConfiguration(packages=["app.v1_0"])
    db_session = providers.Dependency()
