"""edinet ライブラリのグローバル設定管理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from edinet.exceptions import EdinetConfigError

_UNSET: Any = object()

@dataclass
class _Config:
    """ライブラリのグローバル設定。直接インスタンス化しない。"""

    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.edinet-fsa.go.jp/api/v2"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit: float = 1.0
    taxonomy_path: str | None = None
    cache_dir: str | None = None

    def ensure_api_key(self) -> str:
        """API キーが設定されていなければ EdinetConfigError を送出。"""
        if self.api_key is None:
            raise EdinetConfigError(
                "API key is not configured. Call edinet.configure(api_key='...') first."
            )
        return self.api_key

_global_config = _Config()

_CLIENT_PARAMS = {"base_url", "timeout"}

def configure(
    *,
    api_key: str | None = _UNSET,
    base_url: str = _UNSET,
    timeout: float = _UNSET,
    max_retries: int = _UNSET,
    rate_limit: float = _UNSET,
    taxonomy_path: str | None = _UNSET,
    cache_dir: str | None = _UNSET,
) -> None:
    """ライブラリのグローバル設定を更新する。"""
    global _global_config
    need_invalidate = False
    updates: dict[str, Any] = {}

    # 各引数を _UNSET でなければ更新対象に登録
    if api_key is not _UNSET:
        updates["api_key"] = api_key
    if base_url is not _UNSET:
        updates["base_url"] = base_url
    if timeout is not _UNSET:
        updates["timeout"] = timeout
    if max_retries is not _UNSET:
        updates["max_retries"] = max_retries
    if rate_limit is not _UNSET:
        updates["rate_limit"] = rate_limit
    if taxonomy_path is not _UNSET:
        updates["taxonomy_path"] = taxonomy_path
    if cache_dir is not _UNSET:
        updates["cache_dir"] = cache_dir
    
    # ランタイムバリデーション: 型ヒントだけでは Python は None を弾かない。
    # Day 6 以降どこから configure() が呼ばても壊れた設定が入らないよう、
    # ここで実行時に検証する。
    _NOT_NONE = {"base_url", "timeout", "max_retries", "rate_limit"}
    for name in _NOT_NONE:
        if name in updates and updates[name] is None:
            raise EdinetConfigError(
                f"{name} must not be None. "
                f"Only api_key, taxonomy_path, and cache_dir can be cleared with None."
            )
    if "timeout" in updates and updates["timeout"] <= 0:
        raise EdinetConfigError("timeout must be positive")
    if "max_retries" in updates and updates["max_retries"] < 1:
        raise EdinetConfigError("max_retries must be >= 1")
    if "rate_limit" in updates and updates["rate_limit"] < 0:
        raise EdinetConfigError("rate_limit must be >= 0")
    
    # 設定を反映し、_CLIENT_PARAMS に該当するものがあれば invalidate フラグを立てる
    for name, value in updates.items():
        setattr(_global_config, name, value)
        if name in _CLIENT_PARAMS:
            need_invalidate = True
    
    # base_url / timeout が変更された場合、既存の httpx.Client を破棄して
    # 次の get() で再生成する（古い設定のクライアントが残る事故を防止）
    # 注意: `from edinet import _http` はパッケージ __init__.py を経由するため、
    # Day 6 で __init__.py に configure を公開した瞬間に循環 import になる。
    # 相対 import で直接モジュールを指定して回避する。
    if need_invalidate:
        from ._http import invalidate_client, invalidate_async_client_sync
        invalidate_client()
        # async クライアントも破棄する。ainvalidate_client() は async のため
        # 同期関数から呼べないが、参照を切るだけで次の aget() で再生成される。
        invalidate_async_client_sync()

def get_config() -> _Config:
    """現在のグローバル設定を返す（内部用）。"""
    return _global_config

def _reset_for_testing() -> None:
    """テスト用: グローバル設定をデフォルトに戻す。
    _Config() のデフォルト値を正とするため、conftest.py でデフォルト値を
    """
    global _global_config
    _global_config = _Config()
