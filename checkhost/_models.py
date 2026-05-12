"""Typed response models for the check-host API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class MinResponseINFO:
    """Geolocation / ISP information for a host or IP (``POST /info``)."""

    ip: str
    reverse: str
    iprange: str
    country: str
    city: str
    zipcode: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> MinResponseINFO:
        return cls(
            ip=str(data.get("ip", "")),
            reverse=str(data.get("reverse", "")),
            iprange=str(data.get("iprange", "")),
            country=str(data.get("country", "")),
            city=str(data.get("city", "")),
            zipcode=str(data.get("zipcode", "")),
            raw=dict(data),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckCreated:
    """Response object returned by every monitoring endpoint (``ping``,
    ``dns``, ``tcp``, ``udp``, ``http``, ``mtr``).

    The ``uuid`` field is the handle for subsequent ``report()`` / ``og_image()``
    calls.
    """

    status: int
    target: str
    method: str
    repeat_checks: int
    uuid: str
    report_url: str
    api_url: str
    autodelete: str
    message: str
    success: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_success(self) -> bool:
        """``True`` if the API marked the submission as successful.

        Handles both the original Swagger spec (``"success": "success"``) and
        the current production shape (``"success": true``).
        """
        return self.success.lower() in {"success", "true", "ok"}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CheckCreated:
        raw_success = data.get("success", "")
        if isinstance(raw_success, bool):
            success_str = "success" if raw_success else "failure"
        else:
            success_str = str(raw_success)
        return cls(
            status=int(data.get("status", 0)),
            target=str(data.get("target", "")),
            method=str(data.get("method", "")),
            repeat_checks=int(data.get("repeatchecks", 0)),
            uuid=str(data.get("uuid", "")),
            report_url=str(data.get("reportURL", "")),
            api_url=str(data.get("apiURL", "")),
            autodelete=str(data.get("autodelete", "")),
            message=str(data.get("message", "")),
            success=success_str,
            raw=dict(data),
        )


_REPORT_META_KEYS: frozenset[str] = frozenset(
    {
        "status",
        "success",
        "target",
        "method",
        "query",
        "repeatchecks",
        "created_at",
        "delete_at",
        "payload",
        "data",
        "ok",
        "request_id",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """Result wrapper for ``GET /report/{uuid}``.

    The production Check-Host API nests node results under a ``data`` field
    where each value is a dict containing node metadata plus a ``checks``
    list. Older docs (and some peer libraries) describe a flat ``{node:
    [results]}`` shape; we support both transparently.

    The raw response is always preserved via :attr:`raw` so callers can read
    fields the SDK doesn't surface explicitly (e.g. ``created_at``,
    ``delete_at``, custom ``payload`` echoes).
    """

    uuid: str
    raw: dict[str, Any]

    @property
    def nodes(self) -> dict[str, Any]:
        """Node id -> per-node payload.

        - Modern API: returns ``raw["data"]`` directly. Each value is a dict
          of node metadata (continent, country, ISP, ...) with a ``checks``
          array containing the probe results.
        - Legacy API: returns top-level keys whose value is a list or
          ``None`` (the "node hasn't reported yet" sentinel), with known
          meta keys filtered out.
        """
        data = self.raw.get("data")
        if isinstance(data, dict):
            return dict(data)
        return {
            k: v
            for k, v in self.raw.items()
            if k not in _REPORT_META_KEYS and (v is None or isinstance(v, list))
        }

    @staticmethod
    def _node_has_results(value: Any) -> bool:
        """A node is considered complete when it has at least one probe result.

        Handles both shapes:
        - dict with non-empty ``checks`` list (modern)
        - non-empty list at the top level (legacy)
        """
        if value is None:
            return False
        if isinstance(value, list):
            return len(value) > 0
        if isinstance(value, dict):
            checks = value.get("checks")
            return isinstance(checks, list) and len(checks) > 0
        return False

    @property
    def is_complete(self) -> bool:
        """``True`` iff at least one node is present and every node has
        reported probe results."""
        nodes = self.nodes
        return bool(nodes) and all(self._node_has_results(v) for v in nodes.values())

    @property
    def completed_nodes(self) -> dict[str, Any]:
        """Subset of :attr:`nodes` that have at least one probe result."""
        return {k: v for k, v in self.nodes.items() if self._node_has_results(v)}

    @property
    def pending_nodes(self) -> list[str]:
        """Node ids assigned to this check but still missing probe results."""
        return [k for k, v in self.nodes.items() if not self._node_has_results(v)]

    @property
    def status(self) -> int:
        """HTTP-status-like integer the API echoes in the body (0 if absent)."""
        v = self.raw.get("status")
        return int(v) if isinstance(v, int) else 0

    @property
    def method(self) -> str:
        """The check method the report belongs to (``ping``, ``mtr`` ...)."""
        return str(self.raw.get("method", ""))

    @property
    def target(self) -> str:
        """Target host/IP that was checked."""
        return str(self.raw.get("target", ""))

    def __len__(self) -> int:
        """Number of nodes assigned to this check."""
        return len(self.nodes)

    def __bool__(self) -> bool:
        return bool(self.nodes)
