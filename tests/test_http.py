"""_http.py のテスト。

リトライ判定の純粋関数テスト + async テスト。
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from edinet._http import (
    _backoff_seconds,
    _evaluate_response,
    _redact,
    aget,
    ainvalidate_client,
    aclose,
)
from edinet.exceptions import EdinetAPIError, EdinetError


# ============================================================
# _redact テスト（既存）
# ============================================================


def test_redact_hides_secret():
    """_redact() がシークレット文字列を伏字にすること。"""
    text = "GET https://api.edinet-fsa.go.jp/api/v2/documents.json?Subscription-Key=my-secret-key"
    result = _redact(text, "my-secret-key")
    assert "my-secret-key" not in result
    assert "***" in result


def test_redact_with_empty_secret():
    """_redact() にシークレットが空文字の場合、元テキストを返す。"""
    text = "some error message"
    assert _redact(text, "") == text


def test_redact_no_match():
    """_redact() にシークレットが含まれない場合、元テキストを変えない。"""
    text = "Connection refused"
    assert _redact(text, "my-secret-key") == text


def test_edinet_api_error_does_not_contain_key():
    """EdinetAPIError の文字列に API キーが含まれないこと。"""
    secret = "super-secret-key-12345"
    exc = EdinetAPIError(429, "Too Many Requests")
    assert secret not in str(exc)
    assert secret not in repr(exc)


def test_edinet_error_wrapping_hides_key():
    """EdinetError にラップしたメッセージにキーが含まれないこと。

    実装では固定文言 "Network error" を使うため、そもそも漏れない。
    ここではその設計意図が守られていることを確認する。
    """
    # 固定文言パターン（実装の本線）
    exc_fixed = EdinetError("Network error")
    secret = "super-secret-key-12345"
    assert secret not in str(exc_fixed)

    # redact 経由パターン（logger.debug 用の文字列も検証）
    raw_msg = f"Connection failed: https://api.example.com?Subscription-Key={secret}"
    sanitized = _redact(raw_msg, secret)
    assert secret not in sanitized


# ============================================================
# _evaluate_response 単体テスト
# ============================================================


def _make_response(status_code: int, *, headers: dict[str, str] | None = None) -> httpx.Response:
    """テスト用の最小 httpx.Response を生成する。"""
    return httpx.Response(
        status_code=status_code,
        headers=headers or {},
        json={"metadata": {"message": "test"}},
    )


def test_evaluate_response_200_no_retry():
    """200 → should_retry=False, exception=None。"""
    resp = _make_response(200)
    decision = _evaluate_response(
        resp, transport_error=None, attempt=1, max_retries=3, path="/test",
    )
    assert decision.should_retry is False
    assert decision.exception is None


def test_evaluate_response_429_retry():
    """429 → should_retry=True, Retry-After 反映。"""
    resp = _make_response(429, headers={"Retry-After": "5"})
    decision = _evaluate_response(
        resp, transport_error=None, attempt=1, max_retries=3, path="/test",
    )
    assert decision.should_retry is True
    assert decision.wait_seconds == 5.0
    assert isinstance(decision.exception, EdinetAPIError)
    assert decision.exception.status_code == 429


def test_evaluate_response_500_retry():
    """5xx → should_retry=True。"""
    resp = _make_response(503)
    decision = _evaluate_response(
        resp, transport_error=None, attempt=1, max_retries=3, path="/test",
    )
    assert decision.should_retry is True
    assert decision.wait_seconds > 0
    assert isinstance(decision.exception, EdinetAPIError)


def test_evaluate_response_4xx_no_retry():
    """4xx → should_retry=False, exception あり。"""
    resp = _make_response(403)
    decision = _evaluate_response(
        resp, transport_error=None, attempt=1, max_retries=3, path="/test",
    )
    assert decision.should_retry is False
    assert isinstance(decision.exception, EdinetAPIError)
    assert decision.exception.status_code == 403


def test_evaluate_response_transport_error():
    """transport エラー → should_retry=True。"""
    decision = _evaluate_response(
        None,
        transport_error=httpx.ConnectError("connection refused"),
        attempt=1,
        max_retries=3,
        path="/test",
    )
    assert decision.should_retry is True
    assert isinstance(decision.exception, EdinetError)


def test_evaluate_response_last_attempt_no_retry():
    """最終試行 → should_retry=False。"""
    resp = _make_response(503)
    decision = _evaluate_response(
        resp, transport_error=None, attempt=3, max_retries=3, path="/test",
    )
    assert decision.should_retry is False
    assert isinstance(decision.exception, EdinetAPIError)


def test_backoff_seconds_last_attempt_zero():
    """最終試行 → 0。"""
    assert _backoff_seconds(3, 3) == 0.0
    assert _backoff_seconds(5, 5) == 0.0


# ============================================================
# aget() async テスト
# ============================================================


class _FakeAsyncResponse:
    """aget() テスト用の最小レスポンス。"""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return {"metadata": {"message": "test"}}


class _FakeAsyncClient:
    """httpx.AsyncClient のテスト用スタブ。"""

    def __init__(self, responses: list[_FakeAsyncResponse | httpx.TransportError]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> _FakeAsyncResponse:
        resp = self._responses[self._call_count]
        self._call_count += 1
        if isinstance(resp, httpx.TransportError):
            raise resp
        return resp

    async def aclose(self) -> None:
        pass


async def test_aget_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """aget() が正常レスポンスを返すこと。"""
    import edinet._http as http_mod

    fake_client = _FakeAsyncClient([_FakeAsyncResponse(200)])
    monkeypatch.setattr(http_mod, "_async_client", fake_client)
    monkeypatch.setattr(http_mod, "_async_rate_limit_lock", None)
    monkeypatch.setattr(http_mod, "_async_last_request_time", 0.0)

    from edinet._config import configure
    configure(api_key="test-key", rate_limit=0.0)

    resp = await aget("/test")
    assert resp.status_code == 200


async def test_aget_retries_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """TransportError でリトライすること。"""
    import edinet._http as http_mod

    fake_client = _FakeAsyncClient([
        httpx.ConnectError("connection refused"),
        _FakeAsyncResponse(200),
    ])
    monkeypatch.setattr(http_mod, "_async_client", fake_client)
    monkeypatch.setattr(http_mod, "_async_rate_limit_lock", None)
    monkeypatch.setattr(http_mod, "_async_last_request_time", 0.0)

    from edinet._config import configure
    configure(api_key="test-key", rate_limit=0.0)

    # backoff を 0 にして高速にテスト
    monkeypatch.setattr(http_mod, "_backoff_seconds", lambda a, m: 0.0)

    resp = await aget("/test")
    assert resp.status_code == 200


async def test_aget_raises_on_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """4xx で即座に EdinetAPIError。"""
    import edinet._http as http_mod

    fake_client = _FakeAsyncClient([_FakeAsyncResponse(403)])
    monkeypatch.setattr(http_mod, "_async_client", fake_client)
    monkeypatch.setattr(http_mod, "_async_rate_limit_lock", None)
    monkeypatch.setattr(http_mod, "_async_last_request_time", 0.0)

    from edinet._config import configure
    configure(api_key="test-key", rate_limit=0.0)

    with pytest.raises(EdinetAPIError) as exc_info:
        await aget("/test")
    assert exc_info.value.status_code == 403


async def test_ainvalidate_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """ainvalidate_client() でクライアントが破棄されること。"""
    import edinet._http as http_mod

    mock_client = AsyncMock()
    monkeypatch.setattr(http_mod, "_async_client", mock_client)
    monkeypatch.setattr(http_mod, "_async_last_request_time", 99.0)

    await ainvalidate_client()

    assert http_mod._async_client is None
    assert http_mod._async_last_request_time == 0.0
    mock_client.aclose.assert_called_once()


async def test_aclose_idempotent() -> None:
    """aclose() を 2 回呼んでもエラーにならないこと。"""
    await aclose()
    await aclose()
