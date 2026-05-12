"""End-to-end tests for the public :class:`CheckHost` class.

Every test stubs the HTTP layer via ``conftest.transport`` so no live
network is required.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from checkhost import CheckHost
from checkhost._exceptions import (
    CheckHostBadRequestError,
    CheckHostRateLimitError,
    CheckHostTimeoutError,
    CheckHostValidationError,
)
from checkhost._models import CheckCreated, MinResponseINFO, Report
from checkhost.regions import Continent, DNSType, IPVersion, MTRProtocol
from tests.conftest import FakeTransport


def _check_created_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": 200,
        "target": "1.1.1.1",
        "method": "ping",
        "repeatchecks": 0,
        "uuid": "uuid-1",
        "reportURL": "https://check-host.cc/report/uuid-1",
        "apiURL": "https://api.check-host.cc/report/uuid-1",
        "autodelete": "01-01-2039",
        "message": "queued",
        "success": "success",
    }
    payload.update(overrides)
    return payload


class TestUtilityMethods:
    def test_myip_returns_string(self, transport: FakeTransport) -> None:
        transport.queue_json("1.2.3.4")
        with CheckHost() as ch:
            assert ch.myip() == "1.2.3.4"
        assert transport.last_call["url"].endswith("/myip")
        assert transport.last_call["method"] == "GET"

    def test_myip_handles_dict_response(self, transport: FakeTransport) -> None:
        transport.queue_json({"ip": "9.9.9.9", "extra": "data"})
        with CheckHost() as ch:
            assert ch.myip() == "9.9.9.9"

    def test_locations_returns_dict(self, transport: FakeTransport) -> None:
        transport.queue_json({"de1": {"country": "DE"}, "us1": {"country": "US"}})
        with CheckHost() as ch:
            locs = ch.locations()
        assert "de1" in locs
        assert locs["us1"]["country"] == "US"

    def test_info_parses_and_validates(self, transport: FakeTransport) -> None:
        transport.queue_json(
            {
                "ip": "1.2.3.4",
                "reverse": "host",
                "iprange": "1.2.3.0-1.2.3.255",
                "country": "DE",
                "city": "Berlin",
                "zipcode": "10115",
            }
        )
        with CheckHost() as ch:
            info = ch.info("check-host.cc")
        assert isinstance(info, MinResponseINFO)
        assert info.ip == "1.2.3.4"
        assert transport.last_body_json["target"] == "check-host.cc"

    def test_info_rejects_empty_target(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.info("  ")

    def test_whois_returns_dict_even_for_non_dict_response(self, transport: FakeTransport) -> None:
        transport.queue_json(["raw", "lines"])
        with CheckHost() as ch:
            result = ch.whois("example.com")
        assert result == {"raw": ["raw", "lines"]}

    def test_myinfo_endpoint(self, transport: FakeTransport) -> None:
        transport.queue_json(
            {
                "ip": "45.95.55.230",
                "country": "Germany",
                "countryCode": "DE",
                "city": "Berlin",
                "isEu": True,
                "success": True,
            }
        )
        with CheckHost() as ch:
            info = ch.myinfo()
        assert info.ip == "45.95.55.230"
        assert info.country_code == "DE"
        assert info.is_eu is True
        assert transport.last_call["url"].endswith("/myinfo")
        assert transport.last_call["method"] == "GET"

    def test_info_force_endpoint(self, transport: FakeTransport) -> None:
        transport.queue_json(
            {"ip": "1.1.1.1", "country": "USA", "countryCode": "US", "success": True}
        )
        with CheckHost() as ch:
            info = ch.info_force("1.1.1.1")
        assert info.ip == "1.1.1.1"
        assert info.country_code == "US"
        assert transport.last_call["url"].endswith("/infoforce/1.1.1.1")
        assert transport.last_call["method"] == "GET"

    def test_info_force_url_encodes_target(self, transport: FakeTransport) -> None:
        transport.queue_json({"ip": "1.2.3.4", "success": True})
        with CheckHost() as ch:
            ch.info_force("host with space")
        # Space encoded as %20 (urllib's quote with safe='') keeps non-reserved chars.
        assert "%20" in transport.last_call["url"]


class TestMonitoringMethods:
    def test_ping_serialises_options(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload())
        with CheckHost() as ch:
            task = ch.ping(
                "1.1.1.1",
                region=[Continent.EUROPE, "DE"],
                repeat_checks=2,
                timeout=5,
            )
        assert isinstance(task, CheckCreated)
        assert task.uuid == "uuid-1"
        body = transport.last_body_json
        assert body == {
            "target": "1.1.1.1",
            "repeatchecks": 2,
            "region": ["EU", "DE"],
            "timeout": 5,
        }

    def test_ping_minimal(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload())
        with CheckHost() as ch:
            ch.ping("1.1.1.1")
        body = transport.last_body_json
        assert body == {"target": "1.1.1.1", "repeatchecks": 0}

    def test_dns_uses_querymethod(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="dns"))
        with CheckHost() as ch:
            ch.dns(
                "check-host.cc",
                query_method=DNSType.MX,
                region=[Continent.EUROPE],
            )
        body = transport.last_body_json
        assert body["querymethod"] == "MX"
        assert body["region"] == ["EU"]
        assert "repeatchecks" not in body  # DNS endpoint has no repeat_checks

    def test_dns_rejects_invalid_record_type(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.dns("example.com", query_method="ZZZ")

    def test_tcp_includes_port(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="tcp"))
        with CheckHost() as ch:
            ch.tcp("example.com", 443, repeat_checks=1)
        body = transport.last_body_json
        assert body["port"] == 443
        assert body["repeatchecks"] == 1

    def test_tcp_rejects_invalid_port(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.tcp("example.com", 70000)

    def test_udp_with_payload(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="udp"))
        with CheckHost() as ch:
            ch.udp("1.1.1.1", 53, payload="\\x00", region=["EU"])
        body = transport.last_body_json
        assert body["payload"] == "\\x00"
        assert body["port"] == 53

    def test_udp_without_payload_omits_field(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="udp"))
        with CheckHost() as ch:
            ch.udp("1.1.1.1", 53)
        assert "payload" not in transport.last_body_json

    def test_http_endpoint(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="http"))
        with CheckHost() as ch:
            ch.http("https://check-host.cc", region=[Continent.NORTH_AMERICA])
        body = transport.last_body_json
        assert body["target"] == "https://check-host.cc"
        assert body["region"] == ["NA"]

    def test_mtr_defaults(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="mtr"))
        with CheckHost() as ch:
            ch.mtr("1.1.1.1")
        body = transport.last_body_json
        assert body["target"] == "1.1.1.1"
        assert body["repeatchecks"] == 10
        assert "forceIPversion" not in body
        assert "forceProtocol" not in body

    def test_mtr_force_protocol_and_ip(self, transport: FakeTransport) -> None:
        transport.queue_json(_check_created_payload(method="mtr"))
        with CheckHost() as ch:
            ch.mtr(
                "1.1.1.1",
                repeat_checks=5,
                force_ip_version=IPVersion.V4,
                force_protocol=MTRProtocol.TCP,
            )
        body = transport.last_body_json
        assert body["repeatchecks"] == 5
        assert body["forceIPversion"] == 4
        assert body["forceProtocol"] == "tcp"

    def test_mtr_rejects_below_minimum_repeat(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.mtr("1.1.1.1", repeat_checks=2)

    def test_repeat_checks_upper_bound_for_ping(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.ping("1.1.1.1", repeat_checks=121)


class TestErrorPropagation:
    def test_400_propagated(self, transport: FakeTransport) -> None:
        transport.queue_http_error(400, b'{"message":"bad"}')
        with CheckHost() as ch, pytest.raises(CheckHostBadRequestError):
            ch.ping("1.1.1.1")

    def test_429_propagated(self, transport: FakeTransport) -> None:
        transport.queue_http_error(429, b'{"message":"rate"}')
        with CheckHost() as ch, pytest.raises(CheckHostRateLimitError):
            ch.ping("1.1.1.1")


class TestReportAndPolling:
    def test_report_single_fetch(self, transport: FakeTransport) -> None:
        transport.queue_json({"node-a": [["ok"]], "node-b": None})
        with CheckHost() as ch:
            rpt = ch.report("uuid-x")
        assert isinstance(rpt, Report)
        assert rpt.uuid == "uuid-x"
        assert rpt.pending_nodes == ["node-b"]
        assert rpt.is_complete is False
        assert transport.last_call["url"].endswith("/report/uuid-x")

    def test_wait_for_report_returns_when_complete(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        transport.queue_json({"node-a": None, "node-b": None})  # poll 1
        transport.queue_json({"node-a": [["ok"]], "node-b": None})  # poll 2
        transport.queue_json({"node-a": [["ok"]], "node-b": [["ok"]]})  # poll 3
        with CheckHost() as ch:
            rpt = ch.wait_for_report("u", interval=0.01, max_wait=10.0)
        assert rpt.is_complete
        assert len(transport.calls) == 3

    def test_wait_for_report_times_out_with_require_complete(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        # Always pending — three polls then we hit the timeout window
        for _ in range(5):
            transport.queue_json({"a": None, "b": None})
        with CheckHost() as ch, pytest.raises(CheckHostTimeoutError):
            ch.wait_for_report(
                "u",
                interval=0.01,
                max_wait=0.0,
                require_complete=True,
            )

    def test_wait_for_report_returns_partial_without_require(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(time, "sleep", lambda _s: None)
        transport.queue_json({"a": [["ok"]], "b": None})
        with CheckHost() as ch:
            rpt = ch.wait_for_report(
                "u",
                interval=0.01,
                max_wait=0.0,
                require_complete=False,
            )
        assert rpt.is_complete is False
        assert rpt.pending_nodes == ["b"]

    def test_wait_for_report_validates_uuid(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.wait_for_report("")

    def test_wait_for_report_clamps_interval(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed: list[float] = []

        def record_sleep(seconds: float) -> None:
            observed.append(seconds)

        monkeypatch.setattr(time, "sleep", record_sleep)
        transport.queue_json({"a": None})
        transport.queue_json({"a": [["ok"]]})
        with CheckHost() as ch:
            ch.wait_for_report("u", interval=0.1, max_wait=10.0)
        # First sleep should be the clamped minimum (1.0s) or the remaining
        # budget — never the literal 0.1 we passed in.
        assert observed
        assert all(s >= 1.0 or s <= 10.0 for s in observed)
        assert all(s != 0.1 for s in observed)


class TestOGImage:
    def test_og_image_returns_bytes(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"\x89PNG\r\n\x1a\n-fake-")
        with CheckHost() as ch:
            data = ch.og_image("uuid-img")
        assert data.startswith(b"\x89PNG")
        assert transport.last_call["url"].endswith("/report/uuid-img/og-image")
        assert "image/png" in transport.last_call["headers"]["Accept"]

    def test_save_og_image_writes_file(self, transport: FakeTransport, tmp_path: Path) -> None:
        transport.queue_bytes(b"\x89PNGdata")
        target = tmp_path / "sub" / "status.png"
        with CheckHost() as ch:
            written = ch.save_og_image("uuid-img", target)
        assert written.read_bytes() == b"\x89PNGdata"


class TestCountryMap:
    def test_country_map_default_svg(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"<svg xmlns='...'>...</svg>", content_type="image/svg+xml")
        with CheckHost() as ch:
            data = ch.country_map("uuid-cm")
        assert data.startswith(b"<svg")
        assert "format=svg" in transport.last_call["url"]
        assert "res=med" in transport.last_call["url"]
        assert "/report/uuid-cm/country-map" in transport.last_call["url"]

    def test_country_map_png_high(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"\x89PNG\r\n\x1a\n")
        with CheckHost() as ch:
            data = ch.country_map("uuid-cm", format="png", resolution="high")
        assert data.startswith(b"\x89PNG")
        assert "format=png" in transport.last_call["url"]
        assert "res=high" in transport.last_call["url"]

    def test_country_map_validates_format(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.country_map("uuid", format="jpg")

    def test_country_map_validates_resolution(self, transport: FakeTransport) -> None:
        with CheckHost() as ch, pytest.raises(CheckHostValidationError):
            ch.country_map("uuid", resolution="ultra")

    def test_save_country_map_writes_svg(self, transport: FakeTransport, tmp_path: Path) -> None:
        transport.queue_bytes(b"<svg>data</svg>", content_type="image/svg+xml")
        target = tmp_path / "map.svg"
        with CheckHost() as ch:
            written = ch.save_country_map("uuid-cm", target)
        assert written.read_bytes() == b"<svg>data</svg>"


class TestContextManager:
    def test_close_prevents_further_calls(self, transport: FakeTransport) -> None:
        ch = CheckHost()
        ch.close()
        with pytest.raises(RuntimeError):
            ch.myip()

    def test_context_manager_closes_on_exit(self, transport: FakeTransport) -> None:
        with CheckHost() as ch:
            transport.queue_json("1.1.1.1")
            ch.myip()
        with pytest.raises(RuntimeError):
            ch.myip()
