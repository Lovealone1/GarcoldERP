from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

#: Paths that are allowed to be cached, matched as prefixes against the full path.
#:
#: Everything else in this API returns account-specific financial data and must
#: never be stored by a browser, proxy or CDN.
CACHEABLE_PREFIXES: tuple[str, ...] = (
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)

NO_STORE = "private, no-store, max-age=0, must-revalidate"


class NoStoreCacheMiddleware(BaseHTTPMiddleware):
    """
    Declare dynamic API responses uncacheable.

    Without an explicit policy a browser or intermediary is free to apply
    heuristic caching to a 200 with no Cache-Control, which for a balance or a
    transaction list means serving yesterday's figure from disk with no request
    reaching the API at all.

    The frontend had been working around this per call site, with a `_ts`
    cache-busting parameter and a `Cache-Control: no-cache` *request* header.
    That only covered the endpoints someone remembered, and the request header
    is not CORS-safelisted, so it forced a preflight OPTIONS round trip on every
    one of those GETs. Declaring the policy on the response removes both the
    gap and the extra round trip.

    `Vary: Authorization` keeps a shared cache from serving one user's response
    to another, in the event anything upstream ignores `private`.
    """

    def __init__(self, app: ASGIApp, cacheable_prefixes: tuple[str, ...] = CACHEABLE_PREFIXES):
        super().__init__(app)
        self._cacheable_prefixes = cacheable_prefixes

    def _is_cacheable(self, path: str) -> bool:
        return path.startswith(self._cacheable_prefixes)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if self._is_cacheable(request.url.path):
            return response

        # A handler that deliberately set its own policy (a signed media
        # redirect, say) keeps it.
        if "cache-control" not in response.headers:
            response.headers["Cache-Control"] = NO_STORE
            response.headers["Pragma"] = "no-cache"

        existing_vary = response.headers.get("Vary")
        if not existing_vary:
            response.headers["Vary"] = "Authorization"
        elif "authorization" not in existing_vary.lower():
            response.headers["Vary"] = existing_vary + ", Authorization"

        return response
