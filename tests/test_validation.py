"""Tests for the client-side validation helpers."""

from __future__ import annotations

import pytest

from checkhost._exceptions import CheckHostValidationError
from checkhost._validation import (
    validate_dns_query_method,
    validate_mtr_force_ip_version,
    validate_mtr_force_protocol,
    validate_port,
    validate_region,
    validate_repeat_checks,
    validate_target,
    validate_timeout,
)


class TestValidateTarget:
    def test_strips_whitespace(self) -> None:
        assert validate_target("  example.com  ") == "example.com"

    def test_rejects_empty(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_target("   ")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_target(123)  # type: ignore[arg-type]


class TestValidatePort:
    @pytest.mark.parametrize("port", [1, 80, 443, 65535])
    def test_accepts_valid_ports(self, port: int) -> None:
        assert validate_port(port) == port

    @pytest.mark.parametrize("port", [0, -1, 65536, 100000])
    def test_rejects_out_of_range(self, port: int) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_port(port)

    def test_rejects_bool(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_port(True)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_port("80")  # type: ignore[arg-type]


class TestValidateRepeatChecks:
    @pytest.mark.parametrize("v", [0, 1, 60, 120])
    def test_monitoring_range(self, v: int) -> None:
        assert validate_repeat_checks(v) == v

    def test_monitoring_rejects_above_max(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_repeat_checks(121)

    @pytest.mark.parametrize("v", [3, 10, 30])
    def test_mtr_range(self, v: int) -> None:
        assert validate_repeat_checks(v, mtr=True) == v

    @pytest.mark.parametrize("v", [2, 31, 0, -1])
    def test_mtr_rejects_outside(self, v: int) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_repeat_checks(v, mtr=True)


class TestValidateDNSQueryMethod:
    @pytest.mark.parametrize("m", ["A", "AAAA", "MX", "txt", " caa "])
    def test_accepts_known_types(self, m: str) -> None:
        assert validate_dns_query_method(m) == m.strip().upper()

    def test_rejects_unknown(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_dns_query_method("BOGUS")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_dns_query_method(1)  # type: ignore[arg-type]


class TestValidateMTRForceIPVersion:
    def test_none_passes(self) -> None:
        assert validate_mtr_force_ip_version(None) is None

    @pytest.mark.parametrize("v", [4, 6])
    def test_accepts_valid(self, v: int) -> None:
        assert validate_mtr_force_ip_version(v) == v

    @pytest.mark.parametrize("v", [5, 0, 46])
    def test_rejects_other(self, v: int) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_mtr_force_ip_version(v)


class TestValidateMTRForceProtocol:
    def test_none_passes(self) -> None:
        assert validate_mtr_force_protocol(None) is None

    @pytest.mark.parametrize("p", ["ICMP", "udp", " TCP "])
    def test_normalises(self, p: str) -> None:
        assert validate_mtr_force_protocol(p) == p.strip().lower()

    def test_rejects_unknown(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_mtr_force_protocol("sctp")


class TestValidateRegion:
    def test_none_returns_none(self) -> None:
        assert validate_region(None) is None

    def test_accepts_list_of_strings(self) -> None:
        assert validate_region(["EU", "DE", " NL "]) == ["EU", "DE", "NL"]

    def test_rejects_bare_string(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_region("EU")  # type: ignore[arg-type]

    def test_rejects_empty_entry(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_region(["EU", "  "])

    def test_rejects_non_string_entry(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_region(["EU", 1])  # type: ignore[list-item]


class TestValidateTimeout:
    def test_none_returns_none(self) -> None:
        assert validate_timeout(None) is None

    @pytest.mark.parametrize("v", [0, 1, 60])
    def test_accepts_non_negative(self, v: int) -> None:
        assert validate_timeout(v) == v

    def test_rejects_negative(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_timeout(-1)

    def test_rejects_non_int(self) -> None:
        with pytest.raises(CheckHostValidationError):
            validate_timeout(1.5)  # type: ignore[arg-type]
