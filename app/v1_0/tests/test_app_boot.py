"""
Smoke tests that actually build the FastAPI app.

Nothing in the suite imported app.main, so a module-level error anywhere in
the wiring -- a bad import, an unhashable value in a router registration --
produced a green test run and a server that could not start. These tests make
the app itself part of the suite.
"""

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.testclient import TestClient

from app.core.http_cache import NO_STORE


def _app() -> FastAPI:
    from app.main import create_app

    return create_app()


class TestAppConstruction:
    def test_the_app_builds(self):
        assert isinstance(_app(), FastAPI)

    def test_v1_routes_are_mounted_under_the_api_prefix(self):
        paths = [r.path for r in _app().routes if isinstance(r, APIRoute)]
        assert any(p.startswith("/api/v1/") for p in paths)

    def test_the_realtime_websocket_is_mounted(self):
        routes = [getattr(r, "path", "") for r in _app().routes]
        assert "/api/v1/ws/realtime" in routes

    def test_no_duplicate_route_definitions(self):
        seen: set[tuple[str, str]] = set()
        duplicates: list[tuple[str, str]] = []
        for route in _app().routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods:
                key = (method, route.path)
                if key in seen:
                    duplicates.append(key)
                seen.add(key)
        assert duplicates == [], f"duplicate routes: {duplicates}"


class TestHealthEndpoint:
    def test_ready_responds(self):
        with TestClient(_app()) as client:
            res = client.get("/api/ready")
        assert res.status_code == 200
        assert res.json()["message"] == "ready"

    def test_health_is_not_cacheable(self):
        # It reports live state; a cached "ready" would be worse than useless.
        with TestClient(_app()) as client:
            res = client.get("/api/ready")
        assert res.headers["Cache-Control"] == NO_STORE


class TestAuthenticationIsEnforcedEndToEnd:
    def test_a_financial_read_without_a_token_is_rejected(self):
        # The whole point of the router-level dependency: this used to return
        # the full sales ledger to anyone who asked.
        with TestClient(_app()) as client:
            res = client.get("/api/v1/sales")
        assert res.status_code == 401

    def test_bank_balances_without_a_token_are_rejected(self):
        with TestClient(_app()) as client:
            res = client.get("/api/v1/banks")
        assert res.status_code == 401

    def test_a_garbage_token_is_rejected(self):
        with TestClient(_app()) as client:
            res = client.get(
                "/api/v1/transactions", headers={"Authorization": "Bearer nonsense"}
            )
        assert res.status_code == 401

    def test_rejections_are_not_cacheable(self):
        with TestClient(_app()) as client:
            res = client.get("/api/v1/sales")
        assert res.headers["Cache-Control"] == NO_STORE


class TestMultiWorkerGuard:
    # The app logger does not propagate to the root, so caplog cannot see it;
    # assert against the logger call itself.

    def test_more_than_one_worker_is_reported(self, monkeypatch, mocker):
        # In-memory realtime state means a second worker silently drops events.
        monkeypatch.setenv("WEB_CONCURRENCY", "4")
        import app.main as main

        error = mocker.patch.object(main.logger, "error")
        main._warn_if_multi_worker()

        error.assert_called_once()
        assert "WEB_CONCURRENCY" in error.call_args.args[0]

    def test_a_single_worker_is_silent(self, monkeypatch, mocker):
        monkeypatch.setenv("WEB_CONCURRENCY", "1")
        import app.main as main

        error = mocker.patch.object(main.logger, "error")
        main._warn_if_multi_worker()

        error.assert_not_called()

    def test_an_unset_value_is_silent(self, monkeypatch, mocker):
        monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
        import app.main as main

        error = mocker.patch.object(main.logger, "error")
        main._warn_if_multi_worker()

        error.assert_not_called()

    def test_a_malformed_value_does_not_crash_startup(self, monkeypatch, mocker):
        monkeypatch.setenv("WEB_CONCURRENCY", "not-a-number")
        import app.main as main

        mocker.patch.object(main.logger, "error")
        main._warn_if_multi_worker()
