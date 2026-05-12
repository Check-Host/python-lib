"""Tests for the response dataclasses."""

from __future__ import annotations

from checkhost._models import CheckCreated, MinResponseINFO, Report


class TestMinResponseINFO:
    def test_roundtrip_from_legacy_swagger12_payload(self) -> None:
        """Swagger 1.2.0 shape: flat fields including ``iprange`` and ``zipcode``."""
        payload = {
            "ip": "1.2.3.4",
            "reverse": "host.example",
            "iprange": "1.2.3.0-1.2.3.255",
            "country": "Germany",
            "city": "Berlin",
            "zipcode": "10115",
            "asn": "AS12345",  # legacy string-shaped asn lives on raw only
        }
        info = MinResponseINFO.from_json(payload)
        assert info.ip == "1.2.3.4"
        assert info.reverse == "host.example"
        assert info.iprange == "1.2.3.0-1.2.3.255"  # back-compat property
        assert info.country == "Germany"
        assert info.city == "Berlin"
        assert info.zipcode == "10115"  # back-compat property (postal_code)
        assert info.postal_code == "10115"
        assert info.asn == {}  # legacy string asn doesn't match dict schema
        assert info.raw["asn"] == "AS12345"

    def test_roundtrip_from_swagger20_payload(self) -> None:
        """Swagger 2.0.0 shape: nested asn/privacy/company/abuse + new top-level fields."""
        payload = {
            "ip": "34.36.183.77",
            "reverse": "77.183.36.34.bc.googleusercontent.com",
            "country": "United States",
            "countryCode": "US",
            "isEu": False,
            "city": "Kansas City",
            "continent": "North America",
            "latitude": 39.09973,
            "longitude": -94.57857,
            "timeZone": "America/Chicago",
            "postalCode": "64101",
            "subdivision": "Missouri",
            "currencyCode": "USD",
            "callingCode": "1",
            "privacy": {"isHosting": True, "isVpn": False},
            "asn": {"asn": "AS396982", "name": "Google LLC"},
            "company": {"name": "Google LLC", "type": "hosting"},
            "abuse": {"email": "abuse@google.com"},
            "success": True,
        }
        info = MinResponseINFO.from_json(payload)
        assert info.country_code == "US"
        assert info.is_eu is False
        assert info.continent == "North America"
        assert info.latitude == 39.09973
        assert info.longitude == -94.57857
        assert info.time_zone == "America/Chicago"
        assert info.postal_code == "64101"
        assert info.zipcode == "64101"  # back-compat alias
        assert info.subdivision == "Missouri"
        assert info.currency_code == "USD"
        assert info.calling_code == "1"
        assert info.privacy["isHosting"] is True
        assert info.asn["asn"] == "AS396982"
        assert info.company["name"] == "Google LLC"
        assert info.abuse["email"] == "abuse@google.com"
        assert info.success is True

    def test_handles_missing_keys_gracefully(self) -> None:
        info = MinResponseINFO.from_json({"ip": "9.9.9.9"})
        assert info.ip == "9.9.9.9"
        assert info.country == ""
        assert info.zipcode == ""
        assert info.postal_code == ""
        assert info.privacy == {}
        assert info.asn == {}
        assert info.latitude is None


class TestCheckCreated:
    def test_maps_api_field_names_to_python_names(self) -> None:
        payload = {
            "status": 200,
            "target": "1.1.1.1",
            "method": "ping",
            "repeatchecks": 3,
            "uuid": "abcd",
            "reportURL": "https://check-host.cc/report/abcd",
            "apiURL": "https://api.check-host.cc/report/abcd",
            "autodelete": "01-01-2039",
            "message": "queued",
            "success": "success",
        }
        cc = CheckCreated.from_json(payload)
        assert cc.uuid == "abcd"
        assert cc.report_url.endswith("/report/abcd")
        assert cc.api_url.endswith("/report/abcd")
        assert cc.repeat_checks == 3
        assert cc.is_success is True

    def test_is_success_false_for_other_values(self) -> None:
        cc = CheckCreated.from_json({"success": "failure", "uuid": "x"})
        assert cc.is_success is False

    def test_is_success_handles_bool_true(self) -> None:
        """Production API returns ``success: true`` (bool, not string)."""
        cc = CheckCreated.from_json({"success": True, "uuid": "x"})
        assert cc.is_success is True
        assert cc.success == "success"

    def test_is_success_handles_bool_false(self) -> None:
        cc = CheckCreated.from_json({"success": False, "uuid": "x"})
        assert cc.is_success is False
        assert cc.success == "failure"

    def test_swagger20_fields_populated(self) -> None:
        """Live API echoes back region / og-imageURL / port / query / payload."""
        payload = {
            "status": 200,
            "success": True,
            "target": "1.1.1.1",
            "method": "udp",
            "repeatchecks": 0,
            "region": ["DE", "NL"],
            "uuid": "abc",
            "reportURL": "https://check-host.cc/report/abc",
            "apiURL": "https://api.check-host.cc/report/abc",
            "og-imageURL": "https://api.check-host.cc/report/abc/og-image",
            "autodelete": "12-05-2036",
            "message": "Broadcasted task to all slaves.",
            "port": 53,
            "query": None,
            "payload": "0xdeadbeef",
        }
        cc = CheckCreated.from_json(payload)
        assert cc.region == ["DE", "NL"]
        assert cc.og_image_url.endswith("/og-image")
        assert cc.port == 53
        assert cc.query is None
        assert cc.payload == "0xdeadbeef"

    def test_missing_optional_fields_default(self) -> None:
        cc = CheckCreated.from_json({"uuid": "x"})
        assert cc.region == []
        assert cc.og_image_url == ""
        assert cc.port is None
        assert cc.query is None
        assert cc.payload is None


class TestReportLegacyShape:
    """Older flat shape: top-level keys are node ids with list/None values."""

    def test_filters_meta_keys_from_raw(self) -> None:
        raw = {
            "de1.node.check-host.cc": [[1, "ok", 0.1]],
            "us1.node.check-host.cc": None,
            "request_id": "abc",  # meta key, filtered
            "metadata": {"some": "thing"},  # meta key, filtered
        }
        rpt = Report(uuid="u", raw=raw)
        assert set(rpt.nodes) == {
            "de1.node.check-host.cc",
            "us1.node.check-host.cc",
        }
        assert rpt.raw["request_id"] == "abc"

    def test_is_complete_only_when_all_nodes_have_results(self) -> None:
        rpt = Report(uuid="u", raw={"n1": [["ok"]], "n2": None})
        assert rpt.is_complete is False
        rpt2 = Report(uuid="u", raw={"n1": [["ok"]], "n2": [["ok"]]})
        assert rpt2.is_complete is True

    def test_completed_and_pending_split(self) -> None:
        rpt = Report(
            uuid="u",
            raw={"n1": [["ok"]], "n2": None, "n3": [["ok"]]},
        )
        assert sorted(rpt.completed_nodes) == ["n1", "n3"]
        assert rpt.pending_nodes == ["n2"]
        assert len(rpt) == 3


class TestReportEmpty:
    def test_empty_report_is_not_complete(self) -> None:
        rpt = Report(uuid="u", raw={})
        assert rpt.is_complete is False
        assert bool(rpt) is False
        assert len(rpt) == 0


class TestReportModernShape:
    """Production API shape: nodes nested under ``data`` with metadata + ``checks``."""

    @staticmethod
    def _node(checks: list[dict[str, object]] | None = None) -> dict[str, object]:
        return {
            "id": 9,
            "continent": "EU",
            "country": "Germany",
            "countryCode": "DE",
            "city": "Berlin",
            "checks": checks if checks is not None else [],
        }

    def test_pulls_nodes_from_data_field(self) -> None:
        raw = {
            "status": 200,
            "success": True,
            "target": "1.1.1.1",
            "method": "ping",
            "data": {
                "DE-BER-Hetzner": self._node([{"status": 1}]),
                "FR-PAR-OVH": self._node([{"status": 1}, {"status": 1}]),
            },
            "query": None,  # noise field, must NOT be classified as a node
            "payload": None,  # noise field, must NOT be classified as a node
        }
        rpt = Report(uuid="u", raw=raw)
        assert set(rpt.nodes) == {"DE-BER-Hetzner", "FR-PAR-OVH"}
        assert rpt.is_complete is True
        assert rpt.pending_nodes == []
        assert len(rpt) == 2
        assert rpt.target == "1.1.1.1"
        assert rpt.method == "ping"
        assert rpt.status == 200

    def test_node_without_checks_is_pending(self) -> None:
        raw = {
            "data": {
                "DE-BER-Hetzner": self._node([{"status": 1}]),
                "FR-PAR-OVH": self._node([]),  # empty checks -> pending
            },
        }
        rpt = Report(uuid="u", raw=raw)
        assert rpt.is_complete is False
        assert list(rpt.completed_nodes) == ["DE-BER-Hetzner"]
        assert rpt.pending_nodes == ["FR-PAR-OVH"]

    def test_does_not_misclassify_top_level_nones(self) -> None:
        """Regression: ``query`` / ``payload`` are ``None`` on the API response
        but must never appear as pending nodes."""
        raw = {
            "status": 200,
            "success": True,
            "query": None,
            "payload": None,
            "data": {"DE-BER-Hetzner": self._node([{"status": 1}])},
        }
        rpt = Report(uuid="u", raw=raw)
        assert "query" not in rpt.nodes
        assert "payload" not in rpt.nodes
        assert rpt.is_complete is True
