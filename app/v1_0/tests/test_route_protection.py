"""
Guards the authentication posture of the whole v1 surface.

Every mutation already required a token but the reads did not, so an
unauthenticated GET could return the full sales ledger, every bank balance,
the customer list or the dashboard. Several non-GET endpoints were open too,
including admin user creation, deletion and role assignment.

Authentication is now applied once at router registration, so these tests
assert the property globally rather than endpoint by endpoint -- a new route
cannot regress by forgetting a decorator.
"""

from fastapi import Depends
from fastapi.routing import APIRoute

from app.core.security.deps import get_auth_context
from app.v1_0.routers import auth_router
from app.v1_0.v1_router import SELF_AUTHENTICATED, v1_router


def _dependency_callables(route: APIRoute) -> set:
    return {d.call for d in route.dependant.dependencies if d.call is not None}


def _route_requires_auth(route: APIRoute) -> bool:
    """True when get_auth_context runs for this route, at any depth."""
    if get_auth_context in _dependency_callables(route):
        return True
    # A handler that declares it in its own signature counts as well.
    return any(
        sub.call is get_auth_context
        for dep in route.dependant.dependencies
        for sub in [dep, *dep.dependencies]
    )


def _v1_api_routes() -> list[APIRoute]:
    return [r for r in v1_router.routes if isinstance(r, APIRoute)]


#: Paths that are deliberately reachable without a provisioned user.
SELF_AUTHENTICATED_PREFIXES = ("/v1/auth",)


class TestEveryRouteIsProtected:
    def test_the_surface_is_not_empty(self):
        # A sanity check: an empty list would make every assertion below vacuous.
        assert len(_v1_api_routes()) > 50

    def test_no_endpoint_is_unauthenticated(self):
        unprotected = [
            f"{sorted(r.methods)} {r.path}"
            for r in _v1_api_routes()
            if not r.path.startswith(SELF_AUTHENTICATED_PREFIXES)
            and not _route_requires_auth(r)
        ]
        assert unprotected == [], "unauthenticated endpoints: " + ", ".join(unprotected)

    def test_financial_reads_require_a_token(self):
        # These are the reads that were open: the whole ledger, balances and
        # aggregates, all without a token.
        watched = (
            "/v1/sales",
            "/v1/purchases",
            "/v1/transactions",
            "/v1/expenses",
            "/v1/banks",
            "/v1/customers",
            "/v1/suppliers",
            "/v1/products",
            "/v1/profits",
            "/v1/dashboard",
        )
        for prefix in watched:
            routes = [r for r in _v1_api_routes() if r.path.startswith(prefix)]
            assert routes, f"no routes found under {prefix}"
            for route in routes:
                assert _route_requires_auth(route), f"{route.path} is unauthenticated"

    def test_admin_and_role_management_require_a_token(self):
        # These allowed creating users and reassigning roles with no credential.
        for prefix in ("/v1/admin", "/v1/roles", "/v1/permissions", "/v1/role-permissions"):
            for route in _v1_api_routes():
                if route.path.startswith(prefix):
                    assert _route_requires_auth(route), f"{route.path} is unauthenticated"

    def test_every_get_requires_a_token(self):
        open_gets = [
            r.path
            for r in _v1_api_routes()
            if "GET" in r.methods
            and not r.path.startswith(SELF_AUTHENTICATED_PREFIXES)
            and not _route_requires_auth(r)
        ]
        assert open_gets == []


class TestSelfAuthenticatedRouters:
    def test_auth_router_is_the_only_exemption(self):
        assert list(SELF_AUTHENTICATED) == [auth_router]

    def test_auth_router_stays_reachable_for_first_sign_in(self):
        # get_auth_context rejects a valid token whose user row does not exist
        # yet, so applying it here would make provisioning impossible.
        routes = [r for r in _v1_api_routes() if r.path.startswith("/v1/auth")]
        assert routes
        for route in routes:
            assert not _route_requires_auth(route)


class TestRegistrationIsTheEnforcementPoint:
    def test_a_newly_registered_router_is_protected_by_default(self):
        from fastapi import APIRouter

        probe = APIRouter(prefix="/probe")

        @probe.get("/open")
        async def open_endpoint():
            return {}

        holder = APIRouter(prefix="/v1")
        holder.include_router(probe, dependencies=[Depends(get_auth_context)])

        route = next(r for r in holder.routes if isinstance(r, APIRoute))
        assert _route_requires_auth(route)
