"""Offline checks: no lifespan and no real provider clients."""
import logging
import secrets
import time

import pytest

from app import main
from app.ip_diagnostics import IPDiagnostics


@pytest.fixture
def diagnostics(monkeypatch):
    monkeypatch.setenv("IP_DIAGNOSTICS_ENABLED", "1")
    monkeypatch.setenv("IP_DIAGNOSTICS_TOKEN", secrets.token_hex(32))
    monkeypatch.setenv("IP_DIAGNOSTICS_HMAC_KEY", secrets.token_hex(32))
    monkeypatch.setenv("IP_DIAGNOSTICS_EXPIRES_AT", str(int(time.time()) + 900))
    diagnostic = IPDiagnostics()
    monkeypatch.setattr(main, "ip_diagnostics", diagnostic)
    return diagnostic


def test_default_disabled(client, monkeypatch):
    monkeypatch.delenv("IP_DIAGNOSTICS_ENABLED", raising=False)
    monkeypatch.setattr(main, "ip_diagnostics", IPDiagnostics())
    assert client.get("/").json() == {"status": "ok", "message": "Backend çalışıyor!"}


def test_auth_expiry_and_missing_secrets(client, diagnostics, monkeypatch):
    normal = client.get("/").json()
    assert client.get("/", headers={"X-Verifia-IP-Diagnostics": "wrong"}).json() == normal
    token = diagnostics.token.decode()
    assert client.get("/", headers=[("X-Verifia-IP-Diagnostics", token)] * 2).json() == normal
    diagnostics.deadline = 0
    assert client.get("/", headers={"X-Verifia-IP-Diagnostics": token}).json() == normal
    assert not diagnostics.enabled and not diagnostics.token and not diagnostics.key
    monkeypatch.delenv("IP_DIAGNOSTICS_HMAC_KEY")
    assert not IPDiagnostics().enabled


def test_tags_and_no_logs_or_provider_calls(client, fake, diagnostics, caplog, monkeypatch):
    monkeypatch.setattr(main.guard, "trusted", [])
    before = dict(fake.calls)
    caplog.set_level(logging.INFO)
    token, key = diagnostics.token.decode(), diagnostics.key.decode()
    response = client.get("/", headers={
        "X-Verifia-IP-Diagnostics": token,
        "X-Request-ID": token,
        "X-Forwarded-For": "198.51.100.12, invalid-secret, 2001:db8::1",
    })
    data = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert data["peer"] == data["selected"]
    assert data["xff_header_count"] == 1
    assert data["xff_hops"][0] == diagnostics.address("198.51.100.12")
    assert data["xff_hops"][1] == {"family": "invalid"}
    assert data["xff_hops"][2] == diagnostics.address("2001:0db8:0:0::1")
    assert fake.calls == before
    assert main.guard.clients == {} and main.guard.global_count == (0, 0)
    for secret in ("198.51.100.12", "2001:db8::1", "invalid-secret", token, key):
        # Boolean assertions avoid including secret values in pytest failure output.
        assert (secret not in response.text) is True
        assert (secret not in str(response.headers)) is True
        assert (secret not in caplog.text) is True
    old = diagnostics.address("198.51.100.12")
    diagnostics.key = b"different-session-key"
    assert diagnostics.address("198.51.100.12") != old


def test_bounds_and_duplicate_xff(client, diagnostics, monkeypatch):
    auth = ("X-Verifia-IP-Diagnostics", diagnostics.token.decode())
    data = client.get("/", headers=[auth, ("X-Forwarded-For", "192.0.2.1"),
                                           ("X-Forwarded-For", "192.0.2.2")]).json()
    assert data["xff_header_count"] == 2
    assert len(data["xff_hops"]) == 2
    def forbidden_selector(scope):
        raise AssertionError("Oversized XFF reached client selector")
    monkeypatch.setattr(main.guard, "client_ip", forbidden_selector)
    for value in (",".join(["192.0.2.1"] * 20), "x" * 4097):
        data = client.get("/", headers=[auth, ("X-Forwarded-For", value)]).json()
        assert data["xff_truncated"]
        assert data["xff_hops"] == [] and data["selected"] is None


@pytest.mark.parametrize("expiry", ["0", "-1", "invalid", "999999999999"])
def test_invalid_expiry_disables(diagnostics, monkeypatch, expiry):
    monkeypatch.setenv("IP_DIAGNOSTICS_EXPIRES_AT", expiry)
    assert not IPDiagnostics().enabled


def test_absolute_expiry_survives_restart(diagnostics, monkeypatch):
    expires = diagnostics.expires_at
    monkeypatch.setattr("app.ip_diagnostics.time.time", lambda: expires + 1)
    assert diagnostics.response({"headers": []}, main.guard) is None
    assert not IPDiagnostics().enabled
    assert not diagnostics.enabled


def test_expiry_binds_tags_to_session(diagnostics, monkeypatch):
    old = diagnostics.address("192.0.2.1")
    monkeypatch.setenv("IP_DIAGNOSTICS_EXPIRES_AT", str(diagnostics.expires_at + 1))
    assert IPDiagnostics().address("192.0.2.1") != old


def test_equal_or_malformed_secrets_disabled(diagnostics, monkeypatch):
    monkeypatch.setenv("IP_DIAGNOSTICS_HMAC_KEY", diagnostics.token.decode())
    assert not IPDiagnostics().enabled
    monkeypatch.setenv("IP_DIAGNOSTICS_HMAC_KEY", "not-a-generated-key")
    assert not IPDiagnostics().enabled


def test_generator_private_file_and_no_output(tmp_path, capsys, monkeypatch):
    from tools.create_ip_diagnostics_session import create_session
    path = tmp_path / ".env.ip-diagnostics"
    create_session(path)
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    diagnostic = IPDiagnostics()
    assert diagnostic.enabled
    assert (diagnostic.token != diagnostic.key) is True
    assert capsys.readouterr().out == ""
    with pytest.raises(FileExistsError):
        create_session(path)
