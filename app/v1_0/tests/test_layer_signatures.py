"""
Every router -> service and service -> repository call must actually bind.

The unit tests mock the layer below, so a call that passes a keyword the
callee does not accept still passes: the mock accepts anything. That is how
`ProductRepository.list_paginated() got an unexpected keyword argument 'q'`
reached production -- the services and routers were updated to pass the new
filters, three repositories were not, and 382 green tests said nothing.

These assertions walk the real call sites with `ast` and bind them against the
real signatures, so a half-applied change across layers fails here instead of
as a 500 on the first request.
"""

import ast
import glob
import importlib
import inspect
from typing import Optional

import pytest

SERVICE_GLOB = "app/v1_0/services/*.py"
ROUTER_GLOB = "app/v1_0/routers/*.py"


def _snake(class_name: str) -> str:
    return "".join(
        "_" + c.lower() if c.isupper() else c for c in class_name
    ).lstrip("_")


def _load(module: str, class_name: str):
    try:
        return getattr(importlib.import_module(module), class_name, None)
    except ImportError:
        return None


def _binds(method, call: ast.Call) -> Optional[str]:
    """Return the TypeError message if the call cannot bind, else None."""
    kwargs = {kw.arg: None for kw in call.keywords if kw.arg}
    positional = [None] * len(call.args)
    try:
        # A leading None stands in for `self`.
        inspect.signature(method).bind_partial(None, *positional, **kwargs)
    except TypeError as exc:
        return str(exc)
    return None


def _tree(path: str) -> ast.Module:
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), path)


# --------------------------------------------------------------------------
# service -> repository
# --------------------------------------------------------------------------


def _repository_calls():
    """Yield (location, repository class, method name, call node)."""
    for path in sorted(glob.glob(SERVICE_GLOB)):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "self"
                and func.value.attr.endswith("_repository")
            ):
                continue

            base = func.value.attr[: -len("_repository")]
            cls = _load(
                f"app.v1_0.repositories.{base}_repository",
                "".join(w.capitalize() for w in base.split("_")) + "Repository",
            )
            if cls is None:
                continue
            yield f"{path}:{node.lineno}", cls, func.attr, node


def test_every_service_to_repository_call_binds():
    failures = []
    for loc, cls, method_name, call in _repository_calls():
        method = getattr(cls, method_name, None)
        if method is None:
            failures.append(f"{loc}: {cls.__name__} has no {method_name}()")
            continue
        problem = _binds(method, call)
        if problem:
            failures.append(f"{loc}: {cls.__name__}.{method_name}() {problem}")

    assert not failures, "service -> repository calls that would raise:\n" + "\n".join(
        failures
    )


def test_the_repository_scan_finds_call_sites():
    """Guard against the scan silently matching nothing and passing vacuously."""
    assert len(list(_repository_calls())) > 100


# --------------------------------------------------------------------------
# router -> service
# --------------------------------------------------------------------------


def _service_calls():
    """Yield (location, service class, method name, call node)."""
    for path in sorted(glob.glob(ROUTER_GLOB)):
        for fn in ast.walk(_tree(path)):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Depends(...) parameters annotated with a *Service class.
            bound = {
                arg.arg: arg.annotation.id
                for arg in list(fn.args.args) + list(fn.args.kwonlyargs)
                if isinstance(arg.annotation, ast.Name)
                and arg.annotation.id.endswith("Service")
            }
            if not bound:
                continue

            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id in bound
                ):
                    continue

                class_name = bound[func.value.id]
                cls = _load(
                    f"app.v1_0.services.{_snake(class_name)}", class_name
                )
                if cls is None:
                    continue
                yield f"{path}:{node.lineno}", cls, func.attr, node


def test_every_router_to_service_call_binds():
    failures = []
    for loc, cls, method_name, call in _service_calls():
        method = getattr(cls, method_name, None)
        if method is None:
            failures.append(f"{loc}: {cls.__name__} has no {method_name}()")
            continue
        problem = _binds(method, call)
        if problem:
            failures.append(f"{loc}: {cls.__name__}.{method_name}() {problem}")

    assert not failures, "router -> service calls that would raise:\n" + "\n".join(
        failures
    )


def test_the_service_scan_finds_call_sites():
    assert len(list(_service_calls())) > 50
