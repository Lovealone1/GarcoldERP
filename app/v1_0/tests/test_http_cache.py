import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.core.http_cache import NO_STORE, NoStoreCacheMiddleware


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(NoStoreCacheMiddleware)

    @app.get("/api/v1/banks")
    async def banks():
        return [{"id": 1, "balance": 100.0}]

    @app.get("/api/v1/sales")
    async def sales():
        return {"items": []}

    @app.post("/api/dashboard")
    async def dashboard():
        return {"total": 1}

    @app.get("/api/docs")
    async def docs():
        return {"docs": True}

    @app.get("/api/openapi.json")
    async def openapi():
        return {"openapi": "3.1.0"}

    @app.get("/api/v1/media/signed")
    async def media():
        # A handler with a deliberate policy of its own.
        return JSONResponse(
            {"url": "https://cdn/x.png"},
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    @app.get("/api/v1/varying")
    async def varying():
        return JSONResponse({"ok": True}, headers={"Vary": "Accept-Encoding"})

    @app.get("/api/v1/boom")
    async def boom():
        raise ValueError("kaboom")

    @app.get("/api/v1/missing")
    async def missing():
        return JSONResponse({"detail": "not found"}, status_code=404)

    return TestClient(app, raise_server_exceptions=False)


class TestFinancialResponses:
    # Without an explicit policy, a browser may heuristically cache a 200 and
    # serve a balance from disk with no request reaching the API at all.
    @pytest.mark.parametrize("path", ["/api/v1/banks", "/api/v1/sales"])
    def test_financial_gets_are_no_store(self, client, path):
        res = client.get(path)
        assert res.headers["Cache-Control"] == NO_STORE
        assert res.headers["Pragma"] == "no-cache"

    def test_no_store_forbids_disk_and_memory_cache(self, client):
        cache_control = client.get("/api/v1/banks").headers["Cache-Control"]
        assert "no-store" in cache_control
        assert "private" in cache_control
        assert "max-age=0" in cache_control

    def test_posts_are_covered_too(self, client):
        res = client.post("/api/dashboard")
        assert res.headers["Cache-Control"] == NO_STORE

    def test_vary_on_authorization(self, client):
        # Stops a shared cache handing one user's response to another if
        # anything upstream ignores `private`.
        assert client.get("/api/v1/banks").headers["Vary"] == "Authorization"

    def test_existing_vary_is_extended_not_replaced(self, client):
        vary = client.get("/api/v1/varying").headers["Vary"]
        assert "Accept-Encoding" in vary
        assert "Authorization" in vary

    def test_error_responses_are_not_cacheable(self, client):
        assert client.get("/api/v1/missing").headers["Cache-Control"] == NO_STORE

    def test_unhandled_500s_bypass_the_middleware(self, client):
        # Starlette builds this response in ServerErrorMiddleware, which sits
        # outside the user middleware stack, so our header never lands. That is
        # acceptable: 500 is not in the set of heuristically cacheable statuses
        # (RFC 9111), unlike 404, which is covered by the test above.
        res = client.get("/api/v1/boom")
        assert res.status_code == 500
        assert "Cache-Control" not in res.headers


class TestExemptions:
    @pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json"])
    def test_documentation_is_left_alone(self, client, path):
        assert "Cache-Control" not in client.get(path).headers

    def test_a_handlers_own_policy_wins(self, client):
        # Signed media URLs are deliberately cacheable.
        res = client.get("/api/v1/media/signed")
        assert res.headers["Cache-Control"] == "public, max-age=604800, immutable"


class TestCorsOriginsAlias:
    def _settings(self, monkeypatch, **env):
        for key in ("CORS_ORIGINS", "CORS_ORIGIN"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        from app.core.settings import Settings

        return Settings(_env_file=None)

    def test_plural_name_is_read(self, monkeypatch):
        s = self._settings(monkeypatch, CORS_ORIGINS="http://a.test")
        assert s.CORS_ORIGINS_LIST == ["http://a.test"]

    # The deployed .env spells it CORS_ORIGIN, so the plural-only name fell
    # back to "*" and allowed every origin.
    def test_singular_name_is_accepted(self, monkeypatch):
        s = self._settings(monkeypatch, CORS_ORIGIN="http://b.test")
        assert s.CORS_ORIGINS_LIST == ["http://b.test"]

    def test_plural_wins_when_both_are_set(self, monkeypatch):
        s = self._settings(
            monkeypatch, CORS_ORIGINS="http://a.test", CORS_ORIGIN="http://b.test"
        )
        assert s.CORS_ORIGINS_LIST == ["http://a.test"]

    def test_comma_separated_list_is_split_and_trimmed(self, monkeypatch):
        s = self._settings(monkeypatch, CORS_ORIGIN="http://a.test, http://b.test")
        assert s.CORS_ORIGINS_LIST == ["http://a.test", "http://b.test"]

    def test_wildcard_still_allowed_locally(self, monkeypatch):
        s = self._settings(monkeypatch, CORS_ORIGINS="*", APP_ENV="local")
        assert s.CORS_ORIGINS_LIST == ["*"]

    @pytest.mark.parametrize("env", ["staging", "prod"])
    def test_wildcard_is_rejected_in_deployed_environments(self, monkeypatch, env):
        # "*" also silently forces allow_credentials off in main.create_app.
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            self._settings(monkeypatch, CORS_ORIGINS="*", APP_ENV=env)
