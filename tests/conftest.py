"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest


class _FakeResponse:
    """Minimal stand-in for the object returned by ``urllib.request.urlopen``."""

    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._body = body
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeTransport:
    """Records outgoing requests and replays a queue of prepared responses."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses: list[_FakeResponse | Exception] = []

    def queue_json(
        self,
        payload: Any,
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.responses.append(
            _FakeResponse(
                body,
                status=status,
                headers={"Content-Type": content_type},
            )
        )

    def queue_text(
        self,
        text: str,
        *,
        status: int = 200,
        content_type: str = "text/plain",
    ) -> None:
        self.responses.append(
            _FakeResponse(
                text.encode("utf-8"),
                status=status,
                headers={"Content-Type": content_type},
            )
        )

    def queue_bytes(
        self,
        payload: bytes,
        *,
        status: int = 200,
        content_type: str = "image/png",
    ) -> None:
        self.responses.append(
            _FakeResponse(
                payload,
                status=status,
                headers={"Content-Type": content_type},
            )
        )

    def queue_http_error(
        self,
        status: int,
        body: bytes = b"",
        *,
        content_type: str = "application/json",
    ) -> None:
        # urllib.error.HTTPError(url, code, msg, hdrs, fp)
        err = urllib.error.HTTPError(
            url="https://api.check-host.cc/test",
            code=status,
            msg=f"HTTP {status}",
            hdrs={"Content-Type": content_type},  # type: ignore[arg-type]
            fp=io.BytesIO(body),
        )
        self.responses.append(err)

    def queue_url_error(self, reason: str = "connection refused") -> None:
        self.responses.append(urllib.error.URLError(reason))

    def queue_timeout(self) -> None:
        self.responses.append(TimeoutError("timed out"))

    def urlopen(self, req: Any, timeout: float | None = None) -> Any:
        self.calls.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "headers": dict(req.headers),
                "body": req.data,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError(
                f"FakeTransport: no responses queued for {req.get_method()} {req.full_url}"
            )
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    @property
    def last_call(self) -> dict[str, Any]:
        return self.calls[-1]

    @property
    def last_body_json(self) -> Any:
        body = self.last_call["body"]
        if body is None:
            return None
        return json.loads(body.decode("utf-8"))


@pytest.fixture(autouse=True)
def _clear_apikey_env(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure unit tests run with no ambient ``CHECK_HOST_API_KEY``.

    Without this, CI environments (which export the masked GitLab
    variable to every job) make unit tests like ``test_no_apikey_when_none``
    pick up a real key from the environment and fail. ``live`` tests opt
    out so they can use the key when present.
    """
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.delenv("CHECK_HOST_API_KEY", raising=False)


@pytest.fixture
def transport() -> Iterator[FakeTransport]:
    """Patch ``urllib.request.urlopen`` for the duration of the test."""
    fake = FakeTransport()
    with patch("checkhost._client.urllib.request.urlopen", side_effect=fake.urlopen):
        yield fake
