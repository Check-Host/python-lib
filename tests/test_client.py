"""Unit tests for the internal HTTP layer."""

from __future__ import annotations

import json

import pytest

from checkhost._client import ENV_TOKEN, ENV_TOKEN_LEGACY, Client
from checkhost._exceptions import (
    CheckHostAPIError,
    CheckHostBadRequestError,
    CheckHostNetworkError,
    CheckHostNotFoundError,
    CheckHostRateLimitError,
    CheckHostServerError,
)
from tests.conftest import FakeTransport


class TestTokenTransport:
    def test_token_is_sent_as_bearer_header(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(token="ctor-token")
        client.post("/ping", {"target": "1.1.1.1"})
        assert transport.last_call["headers"]["Authorization"] == "Bearer ctor-token"

    def test_token_never_reaches_the_request_body(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(token="ctor-token")
        client.post("/ping", {"target": "1.1.1.1"})
        body = transport.last_body_json
        assert body == {"target": "1.1.1.1"}
        assert "apikey" not in body

    def test_token_never_reaches_the_url(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(token="ctor-token")
        client.get("/locations")
        assert "ctor-token" not in transport.last_call["url"]

    def test_get_requests_are_authenticated_too(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(token="ctor-token")
        client.get("/ip/1.1.1.1")
        assert transport.last_call["headers"]["Authorization"] == "Bearer ctor-token"

    def test_binary_requests_are_authenticated_too(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"\x89PNG")
        client = Client(token="ctor-token")
        client.get_bytes("/report/x/og-image")
        assert transport.last_call["headers"]["Authorization"] == "Bearer ctor-token"

    def test_env_var_fallback(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_TOKEN, "env-token")
        transport.queue_json({"ok": True})
        client = Client()
        client.post("/ping", {"target": "1.1.1.1"})
        assert transport.last_call["headers"]["Authorization"] == "Bearer env-token"

    def test_legacy_env_var_still_honoured(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_TOKEN_LEGACY, "legacy-token")
        transport.queue_json({"ok": True})
        client = Client()
        client.post("/ping", {"target": "1.1.1.1"})
        assert transport.last_call["headers"]["Authorization"] == "Bearer legacy-token"

    def test_new_env_var_wins_over_legacy(
        self, transport: FakeTransport, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_TOKEN, "new-token")
        monkeypatch.setenv(ENV_TOKEN_LEGACY, "legacy-token")
        transport.queue_json({"ok": True})
        client = Client()
        client.post("/ping", {"target": "1.1.1.1"})
        assert transport.last_call["headers"]["Authorization"] == "Bearer new-token"

    def test_no_authorization_header_when_anonymous(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client()
        client.post("/ping", {"target": "1.1.1.1"})
        assert "Authorization" not in transport.last_call["headers"]


class TestStatusMapping:
    @pytest.mark.parametrize(
        ("status", "exc"),
        [
            (400, CheckHostBadRequestError),
            (404, CheckHostNotFoundError),
            (429, CheckHostRateLimitError),
            (500, CheckHostServerError),
            (503, CheckHostServerError),
        ],
    )
    def test_each_status_raises_specific_exception(
        self,
        transport: FakeTransport,
        status: int,
        exc: type[CheckHostAPIError],
    ) -> None:
        transport.queue_http_error(
            status, json.dumps({"message": f"failure {status}"}).encode("utf-8")
        )
        client = Client()
        with pytest.raises(exc) as info:
            client.post("/ping", {"target": "x"})
        assert info.value.status == status
        assert info.value.response is not None
        assert info.value.response["message"].endswith(str(status))

    def test_unknown_4xx_raises_generic_api_error(self, transport: FakeTransport) -> None:
        transport.queue_http_error(418, b"I'm a teapot", content_type="text/plain")
        client = Client()
        with pytest.raises(CheckHostAPIError) as info:
            client.get("/teapot")
        assert info.value.status == 418
        assert info.value.response is None
        assert info.value.raw_body == "I'm a teapot"


class TestNetworkErrors:
    def test_url_error_wraps_to_network_error(self, transport: FakeTransport) -> None:
        transport.queue_url_error("connection refused")
        client = Client()
        with pytest.raises(CheckHostNetworkError):
            client.get("/myip")

    def test_timeout_wraps_to_network_error(self, transport: FakeTransport) -> None:
        transport.queue_timeout()
        client = Client()
        with pytest.raises(CheckHostNetworkError):
            client.get("/myip")


class TestResponseDecoding:
    def test_post_returns_parsed_json_dict(self, transport: FakeTransport) -> None:
        transport.queue_json({"uuid": "abc"})
        client = Client()
        assert client.post("/ping", {"target": "x"}) == {"uuid": "abc"}

    def test_get_returns_parsed_json(self, transport: FakeTransport) -> None:
        transport.queue_json(["a", "b"])
        client = Client()
        assert client.get("/locations") == ["a", "b"]

    def test_get_returns_text_when_not_json(self, transport: FakeTransport) -> None:
        # /myip returns a plain string in some cases; the client should
        # still be able to expose the raw payload.
        transport.queue_text('"1.2.3.4"', content_type="application/json")
        client = Client()
        # JSON-quoted string parses to a Python str
        assert client.get("/myip") == "1.2.3.4"

    def test_get_bytes_returns_raw(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"\x89PNG\r\n\x1a\n")
        client = Client()
        assert client.get_bytes("/report/x/og-image") == b"\x89PNG\r\n\x1a\n"

    def test_empty_response_returns_none(self, transport: FakeTransport) -> None:
        transport.queue_text("")
        client = Client()
        assert client.get("/myip") is None

    def test_invalid_json_raises(self, transport: FakeTransport) -> None:
        transport.queue_text("not-json{", content_type="application/json")
        client = Client()
        with pytest.raises(CheckHostAPIError):
            client.get("/foo")


class TestRequestShape:
    def test_post_sets_content_type_and_accept(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(user_agent="myagent/1.0")
        client.post("/ping", {"target": "x"})
        call = transport.last_call
        assert call["method"] == "POST"
        assert call["headers"]["Content-type"] == "application/json"
        assert call["headers"]["Accept"] == "application/json"
        assert call["headers"]["User-agent"] == "myagent/1.0"

    def test_get_does_not_set_content_type(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client()
        client.get("/locations")
        call = transport.last_call
        assert call["method"] == "GET"
        assert "Content-type" not in call["headers"]
        assert call["body"] is None

    def test_get_bytes_sets_image_accept(self, transport: FakeTransport) -> None:
        transport.queue_bytes(b"\x89PNG")
        client = Client()
        client.get_bytes("/report/x/og-image")
        assert "image/png" in transport.last_call["headers"]["Accept"]

    def test_base_url_normalised(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(base_url="https://example.com/api/")
        client.get("/myip")
        assert transport.last_call["url"] == "https://example.com/api/myip"

    def test_timeout_passed_through(self, transport: FakeTransport) -> None:
        transport.queue_json({"ok": True})
        client = Client(timeout=5.0)
        client.get("/myip")
        assert transport.last_call["timeout"] == 5.0


class TestClose:
    def test_close_blocks_further_calls(self, transport: FakeTransport) -> None:
        client = Client()
        client.close()
        with pytest.raises(RuntimeError):
            client.get("/myip")

    def test_context_manager_closes(self, transport: FakeTransport) -> None:
        with Client() as client:
            transport.queue_json({"ok": True})
            assert client.get("/myip") == {"ok": True}
        with pytest.raises(RuntimeError):
            client.get("/myip")
