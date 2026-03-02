"""EDINET API 向け HTTP 通信層。"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from random import uniform
from typing import Any

import httpx

from edinet._config import (
    get_config,
)
from edinet.exceptions import EdinetAPIError, EdinetError
from edinet._version import __version__

logger = logging.getLogger(__name__)

# --- 同期クライアント状態 ---

_client: httpx.Client | None = None
_last_request_time: float = 0.0

# --- async クライアント状態 ---

_async_client: httpx.AsyncClient | None = None
_async_last_request_time: float = 0.0
_async_rate_limit_lock: asyncio.Lock | None = None  # 遅延初期化


# ============================================================
# リトライ判定（sync/async 共通の純粋関数）
# ============================================================

@dataclass(frozen=True)
class _RetryDecision:
    """1 回のリクエスト結果からのリトライ判定。"""

    should_retry: bool
    wait_seconds: float
    exception: EdinetError | None


def _backoff_seconds(attempt: int, max_retries: int) -> float:
    """指数バックオフ + jitter の待機秒数を返す。最後の試行なら 0。

    Args:
        attempt: 現在の試行回数（1 始まり）。
        max_retries: 最大試行回数。

    Returns:
        待機秒数。
    """
    if attempt >= max_retries:
        return 0.0
    base_delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
    jitter = uniform(0, base_delay * 0.5)  # 最大50%のランダムジッタ
    return base_delay + jitter


def _evaluate_response(
    response: httpx.Response | None,
    *,
    transport_error: httpx.TransportError | None,
    attempt: int,
    max_retries: int,
    path: str,
) -> _RetryDecision:
    """レスポンスまたは transport エラーを評価し、リトライ判定を返す。

    純粋関数のため sync/async 共通で使用する。

    Args:
        response: HTTP レスポンス（transport エラー時は None）。
        transport_error: transport 層の例外（正常時は None）。
        attempt: 現在の試行回数（1 始まり）。
        max_retries: 最大試行回数。
        path: リクエストパス（ログ用）。

    Returns:
        リトライ判定。
    """
    is_last = attempt >= max_retries

    # --- transport エラー ---
    if transport_error is not None:
        logger.debug(
            "Transport error %s on %s (attempt %d/%d)",
            type(transport_error).__name__, path, attempt, max_retries,
        )
        exc = EdinetError("Network error")
        if is_last:
            return _RetryDecision(should_retry=False, wait_seconds=0.0, exception=exc)
        return _RetryDecision(
            should_retry=True,
            wait_seconds=_backoff_seconds(attempt, max_retries),
            exception=exc,
        )

    assert response is not None

    # --- 200 OK ---
    if response.status_code == 200:
        return _RetryDecision(should_retry=False, wait_seconds=0.0, exception=None)

    # --- 429 Too Many Requests ---
    if response.status_code == 429:
        retry_after = _parse_retry_after(response)
        logger.warning(
            "Rate limited (429). Retrying after %d seconds (attempt %d/%d)",
            retry_after, attempt, max_retries,
        )
        exc = EdinetAPIError(429, "Too Many Requests")
        if is_last:
            return _RetryDecision(should_retry=False, wait_seconds=0.0, exception=exc)
        return _RetryDecision(
            should_retry=True,
            wait_seconds=float(retry_after),
            exception=exc,
        )

    # --- 5xx サーバーエラー ---
    if response.status_code >= 500:
        exc = EdinetAPIError(response.status_code, _safe_message(response))
        if is_last:
            return _RetryDecision(should_retry=False, wait_seconds=0.0, exception=exc)
        return _RetryDecision(
            should_retry=True,
            wait_seconds=_backoff_seconds(attempt, max_retries),
            exception=exc,
        )

    # --- 4xx クライアントエラー（リトライ不要、即座に raise） ---
    return _RetryDecision(
        should_retry=False,
        wait_seconds=0.0,
        exception=EdinetAPIError(response.status_code, _safe_message(response)),
    )


# ============================================================
# 同期クライアント管理
# ============================================================

def _get_client() -> httpx.Client:
    """httpx.Client のシングルトンを返す。初回呼び出し時に生成。"""
    global _client
    config = get_config()
    if _client is None:
        _client = httpx.Client(
            base_url=config.base_url,
            timeout=httpx.Timeout(
                connect=config.timeout,
                read=config.timeout,
                write=config.timeout,
                pool=config.timeout,
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
            headers={"User-Agent": f"edinet-python/{__version__}"},
        )
    return _client


def invalidate_client() -> None:
    """既存の httpx.Client を破棄し、レート制限状態もリセットする。"""
    global _client, _last_request_time
    if _client is not None:
        _client.close()
        _client = None
    _last_request_time = 0.0


def _redact(text: str, secret: str) -> str:
    """文字列中の secret を '***' に置換する。API キー漏洩防止用。"""
    return text.replace(secret, "***") if secret else text


def _wait_for_rate_limit() -> None:
    """レート制限制御: 前回リクエストから rate_limit 秒が経過するまで待つ。"""
    global _last_request_time
    config = get_config()
    now = time.monotonic()
    elapsed = now - _last_request_time
    if _last_request_time > 0 and elapsed < config.rate_limit:
        sleep_time = config.rate_limit - elapsed
        logger.debug("Rate limit: sleeping %.2f seconds", sleep_time)
        time.sleep(sleep_time)


def _record_request_time() -> None:
    """リクエスト「開始」時刻を記録する。

    レスポンス受信後ではなく送信直前に記録することで、
    サーバーの応答時間に関わらず一定の「リクエスト開始間隔」を保つ。
    """
    global _last_request_time
    _last_request_time = time.monotonic()


def get(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """EDINET API に GET リクエストを送信する。

    Args:
        path: API のパス（例: "/documents.json"）
        params: クエリパラメータ（date, type 等）

    Returns:
        httpx.Response

    Raises:
        EdinetConfigError: API キーが未設定
        EdinetAPIError: EDINET API がエラーレスポンスを返した
    """

    config = get_config()
    api_key = config.ensure_api_key()
    client = _get_client()

    request_params = dict(params or {})
    request_params["Subscription-Key"] = api_key

    last_exception: EdinetError | None = None

    for attempt in range(1, config.max_retries + 1):
        _wait_for_rate_limit()
        _record_request_time()

        response: httpx.Response | None = None
        transport_error: httpx.TransportError | None = None
        try:
            response = client.get(path, params=request_params)
        except httpx.TransportError as exc:
            transport_error = exc

        decision = _evaluate_response(
            response,
            transport_error=transport_error,
            attempt=attempt,
            max_retries=config.max_retries,
            path=path,
        )

        if not decision.should_retry:
            if decision.exception is not None:
                raise decision.exception
            assert response is not None
            return response

        last_exception = decision.exception
        if decision.wait_seconds > 0:
            logger.debug(
                "Retrying in %.2f seconds (attempt %d/%d)",
                decision.wait_seconds, attempt, config.max_retries,
            )
            time.sleep(decision.wait_seconds)

    raise EdinetError(
        f"Request failed after {config.max_retries} attempts: {last_exception}"
    )


def _parse_retry_after(response: httpx.Response) -> int:
    """Retry-After ヘッダを解析して秒数を返す。ヘッダがなければ60秒。

    Args:
        response: httpx.Response

    Returns:
        int: 待つ秒数
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(1, int(retry_after))
        except ValueError:
            # HTTP-date 形式の可能性があるが、EDINET では発生しない想定。
            # 安全側として 60 秒を返す。
            pass
    return 60


def _safe_message(response: httpx.Response) -> str:
    """レスポンスからエラーメッセージを安全に抽出する。"""
    try:
        data = response.json()
        return str(data.get("metadata", {}).get("message", "Unknown error"))
    except Exception:  # noqa: BLE001
        # 意図的に広い except。EDINET がメンテナンス中/障害時に HTML (502/503)
        # を返すと json.JSONDecodeError になるが、それ以外の予期しない例外
        # （壊れた JSON 等）も安全に fallback させるため Exception で受ける。
        return f"HTTP {response.status_code}"


def close() -> None:
    """HTTP クライアントを閉じる。テストやシャットダウン時に使用。"""
    invalidate_client()


# ============================================================
# async クライアント管理
# ============================================================

def _get_async_client() -> httpx.AsyncClient:
    """httpx.AsyncClient のシングルトンを返す。初回呼び出し時に生成。"""
    global _async_client
    config = get_config()
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(
                connect=config.timeout,
                read=config.timeout,
                write=config.timeout,
                pool=config.timeout,
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
            headers={"User-Agent": f"edinet-python/{__version__}"},
        )
    return _async_client


def _get_async_rate_limit_lock() -> asyncio.Lock:
    """asyncio.Lock の遅延初期化。

    モジュール読み込み時にはイベントループが存在しない可能性があるため、
    初回呼び出し時に生成する。
    """
    global _async_rate_limit_lock
    if _async_rate_limit_lock is None:
        _async_rate_limit_lock = asyncio.Lock()
    return _async_rate_limit_lock


async def _async_wait_for_rate_limit() -> None:
    """レート制限制御（async 版）。Lock で同時アクセスをシリアライズする。"""
    global _async_last_request_time
    config = get_config()
    async with _get_async_rate_limit_lock():
        now = time.monotonic()
        elapsed = now - _async_last_request_time
        if _async_last_request_time > 0 and elapsed < config.rate_limit:
            sleep_time = config.rate_limit - elapsed
            logger.debug("Rate limit (async): sleeping %.2f seconds", sleep_time)
            await asyncio.sleep(sleep_time)
        # Lock 内でリクエスト時刻を記録 → 次のコルーチンが正しい elapsed を見る
        _async_last_request_time = time.monotonic()


async def aget(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    """EDINET API に非同期 GET リクエストを送信する。

    Args:
        path: API のパス（例: "/documents.json"）
        params: クエリパラメータ（date, type 等）

    Returns:
        httpx.Response

    Raises:
        EdinetConfigError: API キーが未設定
        EdinetAPIError: EDINET API がエラーレスポンスを返した
    """
    config = get_config()
    api_key = config.ensure_api_key()
    client = _get_async_client()

    request_params = dict(params or {})
    request_params["Subscription-Key"] = api_key

    last_exception: EdinetError | None = None

    for attempt in range(1, config.max_retries + 1):
        await _async_wait_for_rate_limit()

        response: httpx.Response | None = None
        transport_error: httpx.TransportError | None = None
        try:
            response = await client.get(path, params=request_params)
        except httpx.TransportError as exc:
            transport_error = exc

        decision = _evaluate_response(
            response,
            transport_error=transport_error,
            attempt=attempt,
            max_retries=config.max_retries,
            path=path,
        )

        if not decision.should_retry:
            if decision.exception is not None:
                raise decision.exception
            assert response is not None
            return response

        last_exception = decision.exception
        if decision.wait_seconds > 0:
            logger.debug(
                "Retrying in %.2f seconds (async, attempt %d/%d)",
                decision.wait_seconds, attempt, config.max_retries,
            )
            await asyncio.sleep(decision.wait_seconds)

    raise EdinetError(
        f"Request failed after {config.max_retries} attempts: {last_exception}"
    )


async def ainvalidate_client() -> None:
    """既存の async クライアントを破棄し、レート制限状態もリセットする。"""
    global _async_client, _async_last_request_time, _async_rate_limit_lock
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
    _async_last_request_time = 0.0
    _async_rate_limit_lock = None


async def aclose() -> None:
    """async HTTP クライアントを閉じる。テストやシャットダウン時に使用。"""
    await ainvalidate_client()


def invalidate_async_client_sync() -> None:
    """async クライアントのグローバル状態を同期的にリセットする。

    ``ainvalidate_client()`` の同期版。await なしでクライアント参照を
    切るだけのため、コネクションの graceful close は行わない。
    用途: ``configure()`` からの呼び出し、テスト teardown。
    """
    global _async_client, _async_last_request_time, _async_rate_limit_lock
    if _async_client is not None:
        # イベントループが閉じている可能性があるため、
        # aclose() は呼ばず参照を切るだけにする。
        # GC が httpx.AsyncClient.__del__ でクリーンアップする。
        _async_client = None
    _async_last_request_time = 0.0
    _async_rate_limit_lock = None
