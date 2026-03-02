from dataclasses import dataclass, field
from edinet.exceptions import EdinetConfigError as EdinetConfigError

@dataclass
class _Config:
    """ライブラリのグローバル設定。直接インスタンス化しない。"""
    api_key: str | None = field(default=None, repr=False)
    base_url: str = ...
    timeout: float = ...
    max_retries: int = ...
    rate_limit: float = ...
    taxonomy_path: str | None = ...
    cache_dir: str | None = ...
    def ensure_api_key(self) -> str:
        """API キーが設定されていなければ EdinetConfigError を送出。"""

def configure(*, api_key: str | None = ..., base_url: str = ..., timeout: float = ..., max_retries: int = ..., rate_limit: float = ..., taxonomy_path: str | None = ..., cache_dir: str | None = ...) -> None:
    """ライブラリのグローバル設定を更新する。"""
def get_config() -> _Config:
    """現在のグローバル設定を返す（内部用）。"""
