import httpx
from _typeshed import Incomplete
from dataclasses import dataclass
from edinet._config import get_config as get_config
from edinet._version import __version__ as __version__
from edinet.exceptions import EdinetAPIError as EdinetAPIError, EdinetError as EdinetError
from typing import Any

logger: Incomplete

@dataclass(frozen=True)
class _RetryDecision:
    """1 回のリクエスト結果からのリトライ判定。"""
    should_retry: bool
    wait_seconds: float
    exception: EdinetError | None

def invalidate_client() -> None:
    """既存の httpx.Client を破棄し、レート制限状態もリセットする。"""
def get(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    '''EDINET API に GET リクエストを送信する。

    Args:
        path: API のパス（例: "/documents.json"）
        params: クエリパラメータ（date, type 等）

    Returns:
        httpx.Response

    Raises:
        EdinetConfigError: API キーが未設定
        EdinetAPIError: EDINET API がエラーレスポンスを返した
    '''
def close() -> None:
    """HTTP クライアントを閉じる。テストやシャットダウン時に使用。"""
async def aget(path: str, params: dict[str, Any] | None = None) -> httpx.Response:
    '''EDINET API に非同期 GET リクエストを送信する。

    Args:
        path: API のパス（例: "/documents.json"）
        params: クエリパラメータ（date, type 等）

    Returns:
        httpx.Response

    Raises:
        EdinetConfigError: API キーが未設定
        EdinetAPIError: EDINET API がエラーレスポンスを返した
    '''
async def ainvalidate_client() -> None:
    """既存の async クライアントを破棄し、レート制限状態もリセットする。"""
async def aclose() -> None:
    """async HTTP クライアントを閉じる。テストやシャットダウン時に使用。"""
def invalidate_async_client_sync() -> None:
    """async クライアントのグローバル状態を同期的にリセットする。

    ``ainvalidate_client()`` の同期版。await なしでクライアント参照を
    切るだけのため、コネクションの graceful close は行わない。
    用途: ``configure()`` からの呼び出し、テスト teardown。
    """
