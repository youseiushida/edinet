"""documents API の回帰テスト。"""
from __future__ import annotations

from typing import Any

import pytest

from edinet.api import documents
from edinet.api.documents import aget_documents
from edinet.exceptions import EdinetAPIError


class DummyResponse:
    """_http.get の戻り値を差し替えるための最小レスポンス。"""

    def __init__(self, *, json_data: Any, status_code: int = 200) -> None:
        self.status_code = status_code
        self._json_data = json_data

    def json(self) -> Any:
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def test_get_documents_success_and_include_details_true(monkeypatch: pytest.MonkeyPatch) -> None:
    response_body = {
        "metadata": {"status": "200", "message": "OK"},
        "results": [{"docID": "S100TEST"}],
    }
    dummy = DummyResponse(json_data=response_body)
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(documents._http, "get", fake_get)
    result = documents.get_documents("2026-02-07", include_details=True)
    assert result is response_body
    assert called["path"] == "/documents.json"
    assert called["params"] == {"date": "2026-02-07", "type": "2"}


def test_get_documents_success_and_include_details_false(monkeypatch: pytest.MonkeyPatch) -> None:
    response_body = {
        "metadata": {"status": "200", "message": "OK"},
        "results": [],
    }
    dummy = DummyResponse(json_data=response_body)
    called: dict[str, Any] = {}

    def fake_get(path: str, params: dict[str, Any]) -> DummyResponse:
        called["path"] = path
        called["params"] = params
        return dummy

    monkeypatch.setattr(documents._http, "get", fake_get)
    result = documents.get_documents("2026-02-08", include_details=False)
    assert result is response_body
    assert called["path"] == "/documents.json"
    assert called["params"] == {"date": "2026-02-08", "type": "1"}


def test_get_documents_raises_on_status_code_error(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        json_data={"StatusCode": 401, "message": "invalid api key"},
        status_code=200,
    )
    monkeypatch.setattr(documents._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        documents.get_documents("2026-02-07")
    assert exc_info.value.status_code == 401


def test_get_documents_raises_on_status_code_error_lowercase_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = DummyResponse(
        json_data={"statusCode": 401, "message": "invalid api key"},
        status_code=200,
    )
    monkeypatch.setattr(documents._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        documents.get_documents("2026-02-07")
    assert exc_info.value.status_code == 401


def test_get_documents_raises_on_metadata_error(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(
        json_data={"metadata": {"status": "404", "message": "Not Found"}},
        status_code=200,
    )
    monkeypatch.setattr(documents._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        documents.get_documents("2026-02-07")
    assert exc_info.value.status_code == 404


def test_get_documents_raises_when_json_is_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyResponse(json_data=ValueError("broken"), status_code=503)
    monkeypatch.setattr(documents._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        documents.get_documents("2026-02-07")
    assert exc_info.value.status_code == 503


@pytest.mark.parametrize("json_data", [[], "oops", 123])
def test_get_documents_raises_when_json_is_not_dict(
    monkeypatch: pytest.MonkeyPatch,
    json_data: Any,
) -> None:
    dummy = DummyResponse(json_data=json_data, status_code=502)
    monkeypatch.setattr(documents._http, "get", lambda *_args, **_kwargs: dummy)
    with pytest.raises(EdinetAPIError) as exc_info:
        documents.get_documents("2026-02-07")
    assert exc_info.value.status_code == 502


# ============================================================
# aget_documents() async テスト
# ============================================================


async def test_aget_documents_returns_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    """aget_documents() が正常な dict を返すこと。"""
    response_body = {
        "metadata": {"status": "200", "message": "OK"},
        "results": [{"docID": "S100TEST"}],
    }
    dummy = DummyResponse(json_data=response_body)

    async def fake_aget(path: str, params: dict[str, Any] | None = None) -> DummyResponse:
        return dummy

    monkeypatch.setattr(documents._http, "aget", fake_aget)
    result = await aget_documents("2026-02-07")
    assert result is response_body


async def test_aget_documents_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """aget_documents() が API エラーで EdinetAPIError を返すこと。"""
    dummy = DummyResponse(
        json_data={"StatusCode": 401, "message": "invalid api key"},
        status_code=200,
    )

    async def fake_aget(path: str, params: dict[str, Any] | None = None) -> DummyResponse:
        return dummy

    monkeypatch.setattr(documents._http, "aget", fake_aget)
    with pytest.raises(EdinetAPIError) as exc_info:
        await aget_documents("2026-02-07")
    assert exc_info.value.status_code == 401
