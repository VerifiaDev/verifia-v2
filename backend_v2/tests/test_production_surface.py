"""Exercise real app construction without lifespan, credentials, or upstream calls."""

import importlib.util
import sys

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


@pytest.fixture(params=[False, True], ids=["local", "render"])
def surface(request, monkeypatch):
    from app import main

    if request.param:
        monkeypatch.setenv("RENDER", "true")
    else:
        monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings.from_env()
    assert settings.production is request.param
    # Keep .env loading from changing the settings under test. Import separately
    # so the shared main module and other tests' fixtures remain intact.
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    spec = importlib.util.spec_from_file_location("app._surface_test", main.__file__)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    # No context manager: do not run the lifespan that creates provider clients.
    return module, TestClient(module.app)


def test_documentation_routes_follow_deployment(surface):
    module, client = surface
    expected = 404 if module.settings.production else 200
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path)
        assert response.status_code == expected, path
    if not module.settings.production:
        assert "/health" in client.get("/openapi.json").json()["paths"]
    else:
        assert module.app.openapi_url is None
        assert module.app.docs_url is None
        assert module.app.redoc_url is None


@pytest.mark.parametrize("expose_detail", [False, True], ids=["debug-off", "debug-on"])
@pytest.mark.parametrize("init_error", [None, "internal startup diagnostic"])
def test_health_visibility_and_readiness(surface, expose_detail, init_error):
    module, client = surface
    module.settings.pipeline.expose_detail = expose_detail
    module.state["init_error"] = init_error
    status = "degraded" if init_error else "ok"
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    if module.settings.production:
        # Exact body excludes model, configuration, quotas and debug errors.
        assert body == {"status": status}
    else:
        assert body["status"] == status
        assert body["init_error"] == (init_error if expose_detail else None)
        assert body["config"]["model"] == module.settings.model_name
        assert body["config"]["upstream_concurrency"] == module.upstream.max_concurrency


@pytest.mark.parametrize("value,expected", [("false", False), ("true", True), (" TRUE ", True)])
def test_render_setting_uses_existing_boolean_parser(monkeypatch, value, expected):
    monkeypatch.setenv("RENDER", value)
    assert Settings.from_env().production is expected
