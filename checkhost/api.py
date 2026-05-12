"""High-level :class:`CheckHost` client - the public entry point of the SDK."""

from __future__ import annotations

import logging
import time
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Any

from ._client import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, Client
from ._exceptions import CheckHostTimeoutError, CheckHostValidationError
from ._models import CheckCreated, MinResponseINFO, Report
from ._validation import (
    validate_dns_query_method,
    validate_mtr_force_ip_version,
    validate_mtr_force_protocol,
    validate_port,
    validate_region,
    validate_repeat_checks,
    validate_target,
    validate_timeout,
)

logger = logging.getLogger("checkhost")

_MIN_POLL_INTERVAL = 1.0


class CheckHost:
    """Synchronous client for the Check-Host.cc API.

    Args:
        apikey: API key. Falls back to environment variable
            ``CHECK_HOST_API_KEY`` when ``None``.
        base_url: Override the API base URL (useful for tests or dev mirrors).
        timeout: Per-request HTTP timeout in seconds.
        user_agent: Custom ``User-Agent`` header. Defaults to
            ``check-host-python/<version>``.

    Example:
        >>> with CheckHost() as ch:
        ...     task = ch.ping("1.1.1.1", region=["EU"], repeat_checks=3)
        ...     report = ch.wait_for_report(task.uuid)
    """

    __slots__ = ("_client",)

    def __init__(
        self,
        apikey: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        user_agent: str | None = None,
    ) -> None:
        self._client = Client(
            apikey=apikey,
            base_url=base_url,
            timeout=timeout,
            user_agent=user_agent,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> CheckHost:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Mark the underlying client as closed."""
        self._client.close()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def myip(self) -> str:
        """Return the requesting client's public IP address (``GET /myip``)."""
        result = self._client.get("/myip")
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("ip", "myip", "client_ip"):
                value = result.get(key)
                if isinstance(value, str):
                    return value
            return next(
                (v for v in result.values() if isinstance(v, str)),
                "",
            )
        return str(result) if result is not None else ""

    def locations(self) -> dict[str, Any]:
        """Return the full list of operational monitoring nodes (``GET /locations``).

        Returns the raw API response as a dictionary. The Check-Host API does
        not publish a schema for this endpoint; we therefore preserve every
        field instead of forcing it into a dataclass.
        """
        result = self._client.get("/locations")
        return result if isinstance(result, dict) else {}

    def info(self, target: str) -> MinResponseINFO:
        """Retrieve geolocation / ISP information for *target* (``POST /info``)."""
        target = validate_target(target)
        data = self._client.post("/info", {"target": target})
        if not isinstance(data, dict):
            raise CheckHostValidationError(f"Unexpected /info response type: {type(data).__name__}")
        return MinResponseINFO.from_json(data)

    def whois(self, target: str) -> dict[str, Any]:
        """Run a WHOIS lookup for *target* (``POST /whois``).

        Returns the raw API response. The Check-Host API does not publish a
        schema for this endpoint.
        """
        target = validate_target(target)
        data = self._client.post("/whois", {"target": target})
        return data if isinstance(data, dict) else {"raw": data}

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def ping(
        self,
        target: str,
        *,
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None,
    ) -> CheckCreated:
        """Trigger an ICMP ping check (``POST /ping``)."""
        body = self._build_monitoring_body(
            target,
            region=region,
            repeat_checks=repeat_checks,
            timeout=timeout,
        )
        return CheckCreated.from_json(self._client.post("/ping", body))

    def dns(
        self,
        target: str,
        *,
        query_method: str = "A",
        region: Sequence[str] | None = None,
    ) -> CheckCreated:
        """Trigger a DNS propagation check (``POST /dns``)."""
        body: dict[str, Any] = {
            "target": validate_target(target),
            "querymethod": validate_dns_query_method(query_method),
        }
        region_list = validate_region(region)
        if region_list is not None:
            body["region"] = region_list
        return CheckCreated.from_json(self._client.post("/dns", body))

    def tcp(
        self,
        target: str,
        port: int,
        *,
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None,
    ) -> CheckCreated:
        """Trigger a TCP handshake check (``POST /tcp``)."""
        body = self._build_monitoring_body(
            target,
            region=region,
            repeat_checks=repeat_checks,
            timeout=timeout,
        )
        body["port"] = validate_port(port)
        return CheckCreated.from_json(self._client.post("/tcp", body))

    def udp(
        self,
        target: str,
        port: int,
        *,
        payload: str | None = None,
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None,
    ) -> CheckCreated:
        """Trigger a UDP probe (``POST /udp``)."""
        body = self._build_monitoring_body(
            target,
            region=region,
            repeat_checks=repeat_checks,
            timeout=timeout,
        )
        body["port"] = validate_port(port)
        if payload is not None:
            if not isinstance(payload, str):
                raise CheckHostValidationError(
                    f"payload must be a string, got {type(payload).__name__}"
                )
            body["payload"] = payload
        return CheckCreated.from_json(self._client.post("/udp", body))

    def http(
        self,
        target: str,
        *,
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None,
    ) -> CheckCreated:
        """Trigger an HTTP performance check (``POST /http``)."""
        body = self._build_monitoring_body(
            target,
            region=region,
            repeat_checks=repeat_checks,
            timeout=timeout,
        )
        return CheckCreated.from_json(self._client.post("/http", body))

    def mtr(
        self,
        target: str,
        *,
        region: Sequence[str] | None = None,
        repeat_checks: int = 10,
        force_ip_version: int | None = None,
        force_protocol: str | None = None,
    ) -> CheckCreated:
        """Trigger an MTR (My Traceroute) diagnostic (``POST /mtr``)."""
        body: dict[str, Any] = {
            "target": validate_target(target),
            "repeatchecks": validate_repeat_checks(repeat_checks, mtr=True),
        }
        region_list = validate_region(region)
        if region_list is not None:
            body["region"] = region_list

        fiv = validate_mtr_force_ip_version(force_ip_version)
        if fiv is not None:
            body["forceIPversion"] = fiv

        fp = validate_mtr_force_protocol(force_protocol)
        if fp is not None:
            body["forceProtocol"] = fp

        return CheckCreated.from_json(self._client.post("/mtr", body))

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def report(self, uuid: str) -> Report:
        """Single fetch of a check's report (``GET /report/{uuid}``).

        The result may be incomplete; nodes that haven't yet reported show
        up as ``None`` values inside :attr:`Report.nodes`.
        """
        uuid = self._validate_uuid(uuid)
        data = self._client.get(f"/report/{urllib.parse.quote(uuid, safe='')}")
        if not isinstance(data, dict):
            return Report(uuid=uuid, raw={})
        return Report(uuid=uuid, raw=data)

    def wait_for_report(
        self,
        uuid: str,
        *,
        interval: float = 1.5,
        max_wait: float = 30.0,
        require_complete: bool = True,
    ) -> Report:
        """Poll ``/report/{uuid}`` until every node has reported or *max_wait* elapses.

        The poll interval is held constant (no exponential back-off). The API
        documentation recommends a minimum of one request per second per UUID;
        callers passing ``interval < 1.0`` will be clamped automatically.

        Args:
            uuid: The UUID returned by a monitoring method.
            interval: Seconds between polls (clamped to ``>= 1.0``).
            max_wait: Maximum total seconds to wait.
            require_complete: When ``True`` (default), raise
                :class:`CheckHostTimeoutError` if the timeout fires before
                every node has reported. When ``False``, return the latest
                (possibly incomplete) :class:`Report` instead.

        Returns:
            The completed :class:`Report` (or the latest one if
            ``require_complete=False``).

        Raises:
            CheckHostTimeoutError: When ``require_complete=True`` and the
                deadline elapses before completion.
        """
        uuid = self._validate_uuid(uuid)
        if max_wait < 0:
            raise CheckHostValidationError(f"max_wait must be >= 0, got {max_wait}")
        if interval <= 0:
            raise CheckHostValidationError(f"interval must be > 0, got {interval}")
        poll = max(interval, _MIN_POLL_INTERVAL)

        deadline = time.monotonic() + max_wait
        last: Report = self.report(uuid)
        if last.is_complete:
            return last
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll, remaining))
            last = self.report(uuid)
            if last.is_complete:
                return last
        if require_complete:
            raise CheckHostTimeoutError(
                f"Report {uuid} not complete after {max_wait}s "
                f"({len(last.completed_nodes)}/{len(last.nodes)} nodes reported)"
            )
        return last

    def og_image(self, uuid: str) -> bytes:
        """Fetch the dynamic 1200x630 PNG status map for *uuid*."""
        uuid = self._validate_uuid(uuid)
        data = self._client.get_bytes(f"/report/{urllib.parse.quote(uuid, safe='')}/og-image")
        return data

    def save_og_image(self, uuid: str, path: str | Path) -> Path:
        """Fetch :meth:`og_image` and write it to disk.

        Returns:
            The resolved path that was written.
        """
        image = self.og_image(uuid)
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(image)
        return out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_monitoring_body(
        self,
        target: str,
        *,
        region: Sequence[str] | None,
        repeat_checks: int,
        timeout: int | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "target": validate_target(target),
            "repeatchecks": validate_repeat_checks(repeat_checks),
        }
        region_list = validate_region(region)
        if region_list is not None:
            body["region"] = region_list
        timeout_value = validate_timeout(timeout)
        if timeout_value is not None:
            body["timeout"] = timeout_value
        return body

    @staticmethod
    def _validate_uuid(uuid: str) -> str:
        if not isinstance(uuid, str):
            raise CheckHostValidationError(f"uuid must be a string, got {type(uuid).__name__}")
        stripped = uuid.strip()
        if not stripped:
            raise CheckHostValidationError("uuid must be a non-empty string")
        return stripped
