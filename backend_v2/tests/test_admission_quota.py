"""Offline admission-before-quota regressions for both verification endpoints."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest

from app import main, security
from app.resources import current_lease

PATHS = ["/verify", "/verify/stream"]
IP = "offline-client"


@pytest.fixture(autouse=True)
def admission_environment(monkeypatch):
    monkeypatch.setattr(security, "memory_mb", lambda: (100, 120))
    monkeypatch.setattr(security, "time", SimpleNamespace(time=lambda: 100000))
    monkeypatch.setattr(main.guard, "client_ip", lambda scope: IP)


def quota_state():
    return deepcopy((main.guard.clients, main.guard.global_count))


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("reason", ["busy", "memory-at-limit", "memory-over-limit", "probe-error"])
def test_capacity_rejections_preserve_all_quota_counters(client, fake, monkeypatch, path, reason):
    assert main.guard.quota(IP) == 0  # Also protect existing counters, not just an empty table.
    before = quota_state()

    def measure():
        if reason == "probe-error":
            raise OSError("synthetic probe failure")
        rss = main.guard.memory_limit + (reason == "memory-over-limit")
        return rss, rss

    # Restore synthetic occupancy before the shared no-leak fixture tears down.
    with monkeypatch.context() as patch:
        if reason == "busy":
            patch.setattr(main.guard, "active", main.guard.maximum)
        else:
            patch.setattr(security, "memory_mb", measure)
        expected_active = main.guard.active
        for _ in range(12):  # More than the default per-minute quota.
            response = client.post(path, json={"text": "offline"})
            assert response.status_code == (429 if reason == "busy" else 503)
            assert response.json()["error"] == ("BUSY" if reason == "busy" else "LOW_MEMORY")
            assert quota_state() == before
            assert main.guard.active == expected_active
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("exhausted", [60, 3600, 86400, "global", "client-table"])
def test_quota_rejection_releases_reserved_slot(client, fake, monkeypatch, path, exhausted):
    if isinstance(exhausted, int):
        monkeypatch.setattr(main.guard, "limits", [
            (seconds, 1 if seconds == exhausted else limit)
            for seconds, limit in main.guard.limits
        ])
    elif exhausted == "global":
        monkeypatch.setattr(main.guard, "global_daily", 1)
    else:
        monkeypatch.setattr(main.guard, "client_limit", 1)
    assert main.guard.quota("other-client" if exhausted == "client-table" else IP) == 0
    before = quota_state()
    quota = main.guard.quota
    reservations = []

    def checked_quota(ip):
        reservations.append(main.guard.active)
        assert current_lease.get().guard is main.guard
        return quota(ip)

    monkeypatch.setattr(main.guard, "quota", checked_quota)
    for _ in range(3):
        response = client.post(path, json={"text": "offline"})
        assert response.status_code == 429 and response.json()["error"] == "RATE_LIMITED"
        assert int(response.headers["retry-after"]) > 0
        assert main.guard.active == 0
        assert quota_state() == before
    assert reservations == [1, 1, 1]
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("stage", ["client_ip", "quota"])
def test_quota_control_failure_releases_reserved_slot(client, fake, monkeypatch, path, stage):
    before = quota_state()

    def fail(*args):
        assert main.guard.active == 1
        assert current_lease.get().guard is main.guard
        raise RuntimeError("synthetic control failure")

    monkeypatch.setattr(main.guard, stage, fail)
    response = client.post(path, json={"text": "offline"})
    assert response.status_code == 500 and response.json()["error"] == "INTERNAL_ERROR"
    assert main.guard.active == 0 and quota_state() == before
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}


@pytest.mark.parametrize("path", PATHS)
def test_cancellation_during_quota_control_releases_slot(fake, monkeypatch, path):
    before = quota_state()

    def cancel(ip):
        assert main.guard.active == 1
        raise asyncio.CancelledError()

    monkeypatch.setattr(main.guard, "quota", cancel)

    async def run():
        assert current_lease.get() is None
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            with pytest.raises(asyncio.CancelledError):
                await client.post(path, json={"text": "offline"})
        assert current_lease.get() is None
        assert main.guard.active == 0 and quota_state() == before

    asyncio.run(run())
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}


@pytest.mark.parametrize("path", PATHS)
def test_admitted_request_spends_each_quota_once(client, fake, path):
    response = client.post(path, json={"text": "offline"})
    assert response.status_code == 200
    counters = main.guard.clients[IP][1]
    assert [counters[seconds][1] for seconds in (60, 3600, 86400)] == [1, 1, 1]
    assert main.guard.global_count[1] == 1 and main.guard.active == 0
    assert fake.calls["extract"] == 1


def test_mixed_endpoint_burst_keeps_capacity_and_only_charges_admitted_requests(fake, monkeypatch):
    async def run():
        occupied, release = asyncio.Event(), asyncio.Event()
        extract = fake.extract
        reservations = []

        async def blocked_extract(text):
            reservations.append(main.guard.active)
            if len(reservations) == main.guard.maximum:
                occupied.set()
            await release.wait()
            return await extract(text)

        monkeypatch.setattr(main.state["llm"], "extract", blocked_extract)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            admitted = [asyncio.create_task(client.post(path, json={"text": "offline"})) for path in PATHS]
            try:
                await asyncio.wait_for(occupied.wait(), 2)
                assert main.guard.active == main.guard.maximum == 2
                before = quota_state()
                rejected = await asyncio.gather(*[
                    client.post(PATHS[index % 2], json={"text": "rejected"}) for index in range(12)
                ])
                assert all(r.status_code == 429 and r.json()["error"] == "BUSY" for r in rejected)
                assert main.guard.active == 2 and quota_state() == before
            finally:
                release.set()
                results = await asyncio.gather(*admitted)
            assert all(r.status_code == 200 for r in results)
            assert main.guard.active == 0
            assert max(reservations) == 2
            counters = main.guard.clients[IP][1]
            assert [counters[seconds][1] for seconds in (60, 3600, 86400)] == [2, 2, 2]
            assert main.guard.global_count[1] == 2
            # Capacity remains reusable after the rejected burst.
            assert (await client.post("/verify", json={"text": "next"})).status_code == 200
            assert main.guard.active == 0 and main.guard.global_count[1] == 3

    asyncio.run(run())


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("pressure", ["busy", "memory"])
def test_capacity_rejection_takes_priority_over_exhausted_quota(client, fake, monkeypatch, path, pressure):
    monkeypatch.setattr(main.guard, "global_daily", 1)
    assert main.guard.quota(IP) == 0
    before = quota_state()
    with monkeypatch.context() as patch:
        patch.setattr(main.guard, "active", main.guard.maximum)
        if pressure == "memory":
            patch.setattr(security, "memory_mb", lambda: (main.guard.memory_limit, main.guard.memory_limit))
        response = client.post(path, json={"text": "offline"})
        expected = "BUSY" if pressure == "busy" else "LOW_MEMORY"
        assert response.json()["error"] == expected
        assert response.status_code == (429 if pressure == "busy" else 503)
        assert quota_state() == before
    assert fake.calls == {"extract": 0, "retrieve": 0, "verify": 0}
