"""api/_errors.py の単体テスト。"""
from __future__ import annotations

from typing import Any

import pytest

from edinet.api._errors import parse_api_error_response, raise_for_api_error_response
from edinet.exceptions import EdinetAPIError


class DummyResponse:
    def __init__(self, *, json_data: Any, status_code: int = 200) -> None:
        self.status_code = status_code
        self._json_data = json_data

    def json(self) -> Any:
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def test_parse_api_error_response_accepts_status_code_key_variants() -> None:
    upper = DummyResponse(json_data={"StatusCode": 401, "message": "upper"})
    lower = DummyResponse(json_data={"statusCode": "401", "message": "lower"})

    assert parse_api_error_response(upper) == (401, "upper")
    assert parse_api_error_response(lower) == (401, "lower")


def test_parse_api_error_response_metadata_non_numeric_status_falls_back_default() -> None:
    response = DummyResponse(
        json_data={"metadata": {"status": "oops", "message": "bad status"}},
    )
    assert parse_api_error_response(response, default_status_code=503) == (503, "bad status")


@pytest.mark.parametrize("json_data", [[], "oops", 1])
def test_parse_api_error_response_non_dict_json_is_handled(
    json_data: Any,
) -> None:
    response = DummyResponse(json_data=json_data)
    status_code, message = parse_api_error_response(response, default_status_code=418)
    assert status_code == 418
    assert "must be an object" in message


def test_parse_api_error_response_json_failure_uses_fallback_status() -> None:
    response = DummyResponse(json_data=ValueError("broken json"), status_code=502)
    status_code, message = parse_api_error_response(response, default_status_code=502)
    assert status_code == 502
    assert "Response is not valid JSON" in message


def test_raise_for_api_error_response_raises_edinet_api_error() -> None:
    response = DummyResponse(
        json_data={"metadata": {"status": "404", "message": "Not Found"}},
        status_code=200,
    )
    with pytest.raises(EdinetAPIError) as exc_info:
        raise_for_api_error_response(response, default_status_code=response.status_code)
    assert exc_info.value.status_code == 404
    assert "Not Found" in str(exc_info.value)


def test_raise_for_api_error_response_default_status_falls_back_to_zero() -> None:
    response = DummyResponse(json_data={"metadata": {"status": "bad", "message": "x"}})
    with pytest.raises(EdinetAPIError) as exc_info:
        raise_for_api_error_response(response)
    assert exc_info.value.status_code == 0


def test_edinet_parse_error_is_edinet_error() -> None:
    """EdinetParseError が EdinetError を継承していること。"""
    from edinet.exceptions import EdinetError, EdinetParseError

    exc = EdinetParseError("broken zip")
    assert isinstance(exc, EdinetError)
    assert "broken zip" in str(exc)
