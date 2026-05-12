"""Tests for the response dataclasses."""

from __future__ import annotations

from checkhost._models import CheckCreated, MinResponseINFO, Report


class TestMinResponseINFO:
    def test_roundtrip_from_full_payload(self) -> None:
        payload = {
            "ip": "1.2.3.4",
            "reverse": "host.example",
            "iprange": "1.2.3.0-1.2.3.255",
            "country": "Germany",
            "city": "Berlin",
            "zipcode": "10115",
            "asn": "AS12345",  # extra field stays accessible via .raw
        }
        info = MinResponseINFO.from_json(payload)
        assert info.ip == "1.2.3.4"
        assert info.reverse == "host.example"
        assert info.iprange == "1.2.3.0-1.2.3.255"
        assert info.country == "Germany"
        assert info.city == "Berlin"
        assert info.zipcode == "10115"
        assert info.raw["asn"] == "AS12345"

    def test_handles_missing_keys_gracefully(self) -> None:
        info = MinResponseINFO.from_json({"ip": "9.9.9.9"})
        assert info.ip == "9.9.9.9"
        assert info.country == ""
        assert info.zipcode == ""


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
