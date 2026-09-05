from fastapi import APIRouter, Depends

from app.core.security.deps import get_auth_context
from app.v1_0.routers import auth_router, defined_routers

v1_router = APIRouter(prefix="/v1", tags=["v1"])

#: Routers that manage their own authentication.
#:
#: auth_router must stay out: it provisions the user row on first sign-in, and
#: get_auth_context rejects a valid token whose user does not exist yet, so
#: applying it here would make first login impossible. It validates the bearer
#: token itself via require_claims.
SELF_AUTHENTICATED = (auth_router,)

# Authentication is applied once, here, rather than annotated on each handler.
#
# Every mutation already required a token but the reads did not, so a bare GET
# could return the full sales ledger, every bank balance, the customer list or
# the dashboard. Worse, several non-GET endpoints were unprotected too --
# admin user creation, deletion and role assignment among them.
#
# Doing it at registration means a new router is protected by default; a new
# endpoint cannot be shipped unauthenticated by forgetting a decorator.
for r in defined_routers:
    if any(r is x for x in SELF_AUTHENTICATED):
        v1_router.include_router(r)
    else:
        v1_router.include_router(r, dependencies=[Depends(get_auth_context)])
