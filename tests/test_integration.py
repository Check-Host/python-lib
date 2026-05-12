"""Integration tests that hit the live Check-Host API.

These tests are marked ``live`` and skipped by default. Run them with::

    pytest -m live

They are gentle: a single ping check, a single locations fetch, etc.,
respecting the public rate limits documented in the API.
"""

from __future__ import annotations

import time

import pytest

from checkhost import CheckHost
from checkhost.regions import Continent

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def client() -> CheckHost:
    return CheckHost()


def test_live_myip(client: CheckHost) -> None:
    ip = client.myip()
    assert isinstance(ip, str)
    assert ip


def test_live_locations(client: CheckHost) -> None:
    locs = client.locations()
    assert isinstance(locs, dict)
    assert locs, "live API returned no locations"


def test_live_info(client: CheckHost) -> None:
    info = client.info("check-host.cc")
    assert info.ip
    # Swagger 2.0.0 fields - allowed to be empty but should exist as attributes
    assert isinstance(info.country_code, str)
    assert isinstance(info.privacy, dict)


def test_live_myinfo(client: CheckHost) -> None:
    info = client.myinfo()
    assert info.ip
    assert info.country
    assert isinstance(info.is_eu, bool)


def test_live_ping_and_poll(client: CheckHost) -> None:
    task = client.ping("1.1.1.1", region=[Continent.EUROPE], repeat_checks=1)
    assert task.uuid
    # API caps polling on /report at ~1Hz, so the minimum interval is
    # clamped to 1.0s by wait_for_report regardless of what we ask.
    time.sleep(1.0)
    report = client.wait_for_report(
        task.uuid,
        interval=1.0,
        max_wait=20.0,
        require_complete=False,
    )
    assert report.uuid == task.uuid
    # We always get at least one node back even on the public tier
    assert report.completed_nodes or report.pending_nodes


def test_live_og_image(client: CheckHost) -> None:
    task = client.ping("1.1.1.1", region=[Continent.EUROPE])
    time.sleep(1.0)
    image = client.og_image(task.uuid)
    assert image.startswith(b"\x89PNG"), "expected PNG magic header"


def test_live_country_map_svg(client: CheckHost) -> None:
    task = client.ping("1.1.1.1", region=[Continent.EUROPE])
    time.sleep(1.0)
    svg = client.country_map(task.uuid)
    assert b"<svg" in svg[:200]
