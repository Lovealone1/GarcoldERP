"""
Static routes must not be shadowed by parameterised ones.

FastAPI matches routes in registration order, so declaring GET /{purchase_id}
before GET /filter-options makes the literal path unreachable: it binds as a
purchase id and fails validation with a 422. This is silent at import time and
only shows up when the endpoint is called, so it is asserted here across the
whole surface rather than left to be discovered per endpoint.
"""

import re

import pytest
from fastapi.routing import APIRoute

from app.v1_0.v1_router import v1_router

PARAM = re.compile(r"\{[^}]+\}")


def _segments(path: str) -> list[str]:
    return [seg for seg in path.strip("/").split("/") if seg]


def _is_param(segment: str) -> bool:
    return bool(PARAM.fullmatch(segment))


def _routes() -> list[APIRoute]:
    return [r for r in v1_router.routes if isinstance(r, APIRoute)]


def _captures(param_path: str, literal_path: str) -> bool:
    """True when a request for `literal_path` would match `param_path`."""
    a, b = _segments(param_path), _segments(literal_path)
    if len(a) != len(b):
        return False
    for pattern, actual in zip(a, b):
        if _is_param(pattern):
            continue
        if pattern != actual:
            return False
    return True


def test_no_literal_route_is_shadowed_by_an_earlier_parameterised_route():
    routes = _routes()
    shadowed: list[str] = []

    for i, literal in enumerate(routes):
        if any(_is_param(s) for s in _segments(literal.path)):
            continue  # only literal paths can be shadowed

        for earlier in routes[:i]:
            if not any(_is_param(s) for s in _segments(earlier.path)):
                continue
            if not (literal.methods & earlier.methods):
                continue
            if _captures(earlier.path, literal.path):
                shadowed.append(
                    f"{sorted(literal.methods)} {literal.path} "
                    f"is captured by earlier {earlier.path}"
                )

    assert shadowed == [], "shadowed routes:\n" + "\n".join(shadowed)


@pytest.mark.parametrize(
    "path",
    [
        "/v1/purchases/filter-options",
        "/v1/purchases/summary",
        "/v1/sales/filter-options",
        "/v1/sales/summary",
        "/v1/expenses/filter-options",
        "/v1/expenses/summary",
        "/v1/transactions/filter-options",
        "/v1/transactions/summary",
    ],
)
def test_the_new_sibling_endpoints_are_registered(path):
    paths = {r.path for r in _routes()}
    assert path in paths


class TestHelper:
    def test_a_parameterised_path_captures_a_matching_literal(self):
        assert _captures("/v1/purchases/{purchase_id}", "/v1/purchases/summary")

    def test_different_lengths_do_not_capture(self):
        assert not _captures("/v1/purchases/{id}/items", "/v1/purchases/summary")

    def test_a_differing_literal_segment_does_not_capture(self):
        assert not _captures("/v1/sales/{id}", "/v1/purchases/summary")
