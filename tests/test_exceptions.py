"""Tests for the exception hierarchy and status-code mapping."""

from __future__ import annotations

import pytest

from checkhost._exceptions import (
    CheckHostAPIError,
    CheckHostBadRequestError,
    CheckHostError,
    CheckHostNetworkError,
    CheckHostNotFoundError,
    CheckHostRateLimitError,
    CheckHostServerError,
    CheckHostTimeoutError,
    CheckHostValidationError,
    exception_for_status,
)


class TestHierarchy:
    @pytest.mark.parametrize(
        "exc",
        [
            CheckHostNetworkError,
            CheckHostTimeoutError,
            CheckHostAPIError,
            CheckHostValidationError,
        ],
    )
    def test_all_inherit_from_base(self, exc: type[Exception]) -> None:
        assert issubclass(exc, CheckHostError)

    @pytest.mark.parametrize(
        "exc",
        [
            CheckHostBadRequestError,
            CheckHostNotFoundError,
            CheckHostRateLimitError,
            CheckHostServerError,
        ],
    )
    def test_api_subclasses_inherit_from_api_error(self, exc: type[Exception]) -> None:
        assert issubclass(exc, CheckHostAPIError)
        assert issubclass(exc, CheckHostError)

    def test_validation_is_also_value_error(self) -> None:
        assert issubclass(CheckHostValidationError, ValueError)


class TestStatusMapping:
    @pytest.mark.parametrize(
        ("status", "cls"),
        [
            (400, CheckHostBadRequestError),
            (404, CheckHostNotFoundError),
            (429, CheckHostRateLimitError),
            (500, CheckHostServerError),
            (502, CheckHostServerError),
            (503, CheckHostServerError),
            (504, CheckHostServerError),
        ],
    )
    def test_known_statuses(self, status: int, cls: type[CheckHostAPIError]) -> None:
        assert exception_for_status(status) is cls

    def test_unmapped_5xx_is_server_error(self) -> None:
        assert exception_for_status(599) is CheckHostServerError

    def test_unknown_status_falls_back_to_api_error(self) -> None:
        assert exception_for_status(418) is CheckHostAPIError


class TestAPIErrorAttributes:
    def test_carries_status_and_response(self) -> None:
        err = CheckHostBadRequestError(
            "bad target",
            status=400,
            response={"message": "bad target", "code": 400},
            raw_body='{"message": "bad target"}',
        )
        assert err.status == 400
        assert err.response is not None
        assert err.response["message"] == "bad target"
        assert err.raw_body is not None
        assert "[HTTP 400] bad target" in str(err)

    def test_can_be_raised_and_caught_as_base(self) -> None:
        with pytest.raises(CheckHostError):
            raise CheckHostRateLimitError("slow down", status=429)
