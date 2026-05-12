"""Client-side validation helpers.

Validation runs before any HTTP call so the caller gets immediate, well-typed
errors instead of opaque 400 responses from the API.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from ._exceptions import CheckHostValidationError

DNS_QUERY_METHODS: Final[frozenset[str]] = frozenset(
    {
        "A/AAAA",
        "A",
        "AAAA",
        "NS",
        "MD",
        "MF",
        "CNAME",
        "SOA",
        "MB",
        "MG",
        "MR",
        "NULL",
        "WKS",
        "PTR",
        "HINFO",
        "MINFO",
        "MX",
        "TXT",
        "SRV",
        "EDNS",
        "SPF",
        "AXFR",
        "MAILB",
        "MAILA",
        "ANY",
        "CAA",
        "DNSKEY",
    }
)

MTR_PROTOCOLS: Final[frozenset[str]] = frozenset({"icmp", "udp", "tcp"})

MTR_FORCE_IP_VERSIONS: Final[frozenset[int]] = frozenset({4, 6})

MIN_PORT: Final[int] = 1
MAX_PORT: Final[int] = 65535

MIN_REPEAT_CHECKS: Final[int] = 0
MAX_REPEAT_CHECKS: Final[int] = 120

MTR_MIN_REPEAT_CHECKS: Final[int] = 3
MTR_MAX_REPEAT_CHECKS: Final[int] = 30


def validate_target(target: str) -> str:
    """Ensure *target* is a non-empty string and strip surrounding whitespace."""
    if not isinstance(target, str):
        raise CheckHostValidationError(f"target must be a string, got {type(target).__name__}")
    stripped = target.strip()
    if not stripped:
        raise CheckHostValidationError("target must be a non-empty string")
    return stripped


def validate_port(port: int) -> int:
    """Ensure *port* is an int in the range [1, 65535]."""
    if isinstance(port, bool) or not isinstance(port, int):
        raise CheckHostValidationError(f"port must be an int, got {type(port).__name__}")
    if not (MIN_PORT <= port <= MAX_PORT):
        raise CheckHostValidationError(
            f"port must be between {MIN_PORT} and {MAX_PORT}, got {port}"
        )
    return port


def validate_repeat_checks(value: int, *, mtr: bool = False) -> int:
    """Validate ``repeat_checks`` against the per-endpoint limits.

    Ping/TCP/UDP/HTTP: 0-120. MTR: 3-30.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise CheckHostValidationError(f"repeat_checks must be an int, got {type(value).__name__}")
    if mtr:
        lo, hi = MTR_MIN_REPEAT_CHECKS, MTR_MAX_REPEAT_CHECKS
        kind = "MTR"
    else:
        lo, hi = MIN_REPEAT_CHECKS, MAX_REPEAT_CHECKS
        kind = "monitoring"
    if not (lo <= value <= hi):
        raise CheckHostValidationError(
            f"repeat_checks for {kind} must be between {lo} and {hi}, got {value}"
        )
    return value


def validate_dns_query_method(method: str) -> str:
    """Ensure *method* is one of the DNS record types accepted by the API.

    Accepts the special compound ``A/AAAA`` (Swagger 2.0.0 default) as
    well as the individual record types.
    """
    if not isinstance(method, str):
        raise CheckHostValidationError(
            f"query_method must be a string, got {type(method).__name__}"
        )
    stripped = method.strip()
    # Preserve "A/AAAA" verbatim; otherwise compare case-insensitively.
    normalized = stripped if stripped == "A/AAAA" else stripped.upper()
    if normalized not in DNS_QUERY_METHODS:
        raise CheckHostValidationError(
            f"query_method '{method}' is not a valid DNS record type. "
            f"Allowed: {sorted(DNS_QUERY_METHODS)}"
        )
    return normalized


def validate_mtr_force_ip_version(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CheckHostValidationError(
            f"force_ip_version must be 4 or 6, got {type(value).__name__}"
        )
    if value not in MTR_FORCE_IP_VERSIONS:
        raise CheckHostValidationError(f"force_ip_version must be 4 or 6, got {value}")
    return value


def validate_mtr_force_protocol(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CheckHostValidationError(
            f"force_protocol must be a string, got {type(value).__name__}"
        )
    normalized = value.strip().lower()
    if normalized not in MTR_PROTOCOLS:
        raise CheckHostValidationError(
            f"force_protocol must be one of {sorted(MTR_PROTOCOLS)}, got '{value}'"
        )
    return normalized


def validate_region(region: Iterable[str] | None) -> list[str] | None:
    """Normalise a region iterable into a list of trimmed non-empty strings."""
    if region is None:
        return None
    if isinstance(region, str):
        raise CheckHostValidationError("region must be a sequence of strings, not a single string")
    out: list[str] = []
    for idx, r in enumerate(region):
        if not isinstance(r, str):
            raise CheckHostValidationError(
                f"region[{idx}] must be a string, got {type(r).__name__}"
            )
        rs = r.strip()
        if not rs:
            raise CheckHostValidationError(f"region[{idx}] is empty")
        out.append(rs)
    return out


def validate_timeout(timeout: int | None) -> int | None:
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise CheckHostValidationError(f"timeout must be an int, got {type(timeout).__name__}")
    if timeout < 0:
        raise CheckHostValidationError(f"timeout must be >= 0, got {timeout}")
    return timeout
