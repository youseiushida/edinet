from _typeshed import Incomplete
from dataclasses import dataclass
from pathlib import Path

logger: Incomplete

@dataclass(frozen=True, slots=True)
class CacheInfo:
    '''キャッシュの統計情報。

    ``functools.lru_cache`` の ``cache_info()`` に倣ったパターン。

    Attributes:
        enabled: キャッシュが有効かどうか。
        cache_dir: キャッシュのルートディレクトリ。無効時は ``None``。
        entry_count: キャッシュエントリ数。
        total_bytes: キャッシュ合計バイト数。

    利用例::

        >>> from edinet.api.cache import cache_info
        >>> info = cache_info()
        >>> print(f"{info.entry_count} entries, {info.total_bytes / 1024 / 1024:.1f} MB")
    '''
    enabled: bool
    cache_dir: Path | None
    entry_count: int
    total_bytes: int

class CacheStore:
    '''ZIP ダウンロードのディスクキャッシュストア。

    キャッシュキーは ``doc_id``（書類管理番号）。
    EDINET の開示書類は不変であり（訂正報告書は別の doc_id が付与される）、
    TTL や LRU eviction は不要。

    原子的書き込み:
        ``put()`` は ``tempfile.NamedTemporaryFile`` で一時ファイルに書き込み、
        ``os.replace()`` でアトミックにリネームする。プロセスクラッシュ時に
        中途半端なファイルが残ることを防止する。

    Args:
        cache_dir: キャッシュのルートディレクトリ。

    利用例::

        >>> store = CacheStore(Path("/tmp/edinet_cache"))
        >>> store.put("S100ABC0", zip_bytes)
        >>> data = store.get("S100ABC0")
        >>> assert data == zip_bytes
    '''
    def __init__(self, cache_dir: Path) -> None: ...
    @property
    def cache_dir(self) -> Path:
        """キャッシュのルートディレクトリ。"""
    def cache_path(self, doc_id: str, *, suffix: str = '.zip') -> Path:
        '''doc_id に対応するキャッシュファイルのパスを返す。

        Args:
            doc_id: 書類管理番号。
            suffix: ファイル拡張子。デフォルトは ``".zip"``。

        Returns:
            ``{cache_dir}/downloads/{doc_id}{suffix}``
        '''
    def get(self, doc_id: str, *, suffix: str = '.zip') -> bytes | None:
        '''キャッシュからバイナリを取得する。

        Args:
            doc_id: 書類管理番号。
            suffix: ファイル拡張子。デフォルトは ``".zip"``。

        Returns:
            キャッシュヒット時は bytes。ミス時は ``None``。
        '''
    def put(self, doc_id: str, data: bytes, *, suffix: str = '.zip') -> None:
        '''バイナリをキャッシュに保存する。

        原子的書き込み: tempfile に書き込み後、``os.replace()`` でリネーム。

        Note:
            ``os.fsync()`` は意図的に省略。キャッシュは最適化であり耐久ストレージ
            ではないため、クラッシュ時にエントリが消失しても再ダウンロードすれば
            よい。fsync 省略により HDD 環境でのパフォーマンスを維持する。

        Args:
            doc_id: 書類管理番号。
            data: 保存するバイナリ。
            suffix: ファイル拡張子。デフォルトは ``".zip"``。
        '''
    def delete(self, doc_id: str, *, suffix: str = '.zip') -> None:
        '''指定した doc_id のキャッシュを削除する。

        Args:
            doc_id: 書類管理番号。
            suffix: ファイル拡張子。デフォルトは ``".zip"``。
        '''
    def clear(self) -> None:
        """``downloads/`` サブディレクトリを削除する。

        Note:
            ``cache_dir`` 直下ではなく ``downloads/`` のみを削除する。
            ``TaxonomyResolver`` の pickle キャッシュ等、同じ ``cache_dir``
            を共有する他のキャッシュを巻き込まないための安全策。
        """
    def info(self) -> CacheInfo:
        """キャッシュの統計情報を返す。

        Returns:
            ``CacheInfo`` dataclass。
        """

def clear_cache() -> None:
    '''グローバル設定のダウンロードキャッシュを全削除する。

    ``configure(cache_dir=...)`` で設定されたキャッシュディレクトリ内の
    ``downloads/`` サブディレクトリを ``shutil.rmtree`` で削除する。
    ``cache_dir`` 直下の他のファイル（taxonomy pickle キャッシュ等）は
    保護される。キャッシュが無効の場合は何もしない。

    利用例::

        >>> import edinet
        >>> edinet.configure(cache_dir="/tmp/edinet_cache")
        >>> # ... 何らかの操作 ...
        >>> from edinet.api.cache import clear_cache
        >>> clear_cache()
    '''
def cache_info() -> CacheInfo:
    """キャッシュの統計情報を返す。

    ``functools.lru_cache`` の ``cache_info()`` に倣ったパターン。
    キャッシュ無効時は ``enabled=False`` で ``CacheInfo`` を返す。

    Returns:
        ``CacheInfo`` dataclass。

    利用例::

        >>> from edinet.api.cache import cache_info
        >>> info = cache_info()
        >>> info.entry_count
        42
    """
