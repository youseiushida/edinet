"""EDINET ダウンロードファイルの永続ディスクキャッシュ。

``configure(cache_dir=...)`` で有効化すると、``Filing.fetch()`` が透過的に
ディスクキャッシュを使用する。キャッシュキーは ``doc_id``（書類管理番号）。

EDINET の開示書類は不変であり（訂正報告書は別の doc_id が付与される）、
TTL や LRU eviction は不要。

利用例::

    import edinet
    edinet.configure(cache_dir="~/.cache/edinet")

    filing.fetch()          # 1回目: ダウンロード → ディスク保存 → 返却
    filing.fetch()          # 2回目: ディスクから読み込み → 返却
    filing.fetch(refresh=True)  # 強制再ダウンロード → ディスク上書き

    from edinet.api.cache import clear_cache, cache_info
    info = cache_info()     # 統計情報
    clear_cache()           # downloads/ を全削除
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CacheInfo:
    """キャッシュの統計情報。

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
    """

    enabled: bool
    cache_dir: Path | None
    entry_count: int
    total_bytes: int


class CacheStore:
    """ZIP ダウンロードのディスクキャッシュストア。

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
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._downloads_dir = cache_dir / "downloads"

    @property
    def cache_dir(self) -> Path:
        """キャッシュのルートディレクトリ。"""
        return self._cache_dir

    def cache_path(self, doc_id: str) -> Path:
        """doc_id に対応するキャッシュファイルのパスを返す。

        Args:
            doc_id: 書類管理番号。

        Returns:
            ``{cache_dir}/downloads/{doc_id}.zip``

        Note:
            現在は file_type=XBRL_AND_AUDIT 固定のため doc_id のみでキー化。
            fetch_pdf 対応時にキャッシュキーの拡張が必要。
        """
        return self._downloads_dir / f"{doc_id}.zip"

    def get(self, doc_id: str) -> bytes | None:
        """キャッシュから ZIP バイナリを取得する。

        Args:
            doc_id: 書類管理番号。

        Returns:
            キャッシュヒット時は bytes。ミス時は ``None``。
        """
        path = self.cache_path(doc_id)
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            logger.debug("キャッシュヒット: %s (%d bytes)", doc_id, len(data))
            return data
        except OSError:
            logger.warning("キャッシュ読み込み失敗: %s", doc_id, exc_info=True)
            return None

    def put(self, doc_id: str, data: bytes) -> None:
        """ZIP バイナリをキャッシュに保存する。

        原子的書き込み: tempfile に書き込み後、``os.replace()`` でリネーム。

        Note:
            ``os.fsync()`` は意図的に省略。キャッシュは最適化であり耐久ストレージ
            ではないため、クラッシュ時にエントリが消失しても再ダウンロードすれば
            よい。fsync 省略により HDD 環境でのパフォーマンスを維持する。

        Args:
            doc_id: 書類管理番号。
            data: ZIP バイナリ。
        """
        self._downloads_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_path(doc_id)
        tmp_name: str | None = None
        try:
            # 同一ディレクトリに一時ファイルを作成（os.replace のクロスデバイス問題を回避）
            fd = tempfile.NamedTemporaryFile(
                dir=self._downloads_dir,
                delete=False,
                suffix=".tmp",
            )
            tmp_name = fd.name
            try:
                fd.write(data)
                fd.flush()
            finally:
                fd.close()
            os.replace(tmp_name, target)
            tmp_name = None  # リネーム成功 → 掃除不要
            logger.debug("キャッシュ保存: %s (%d bytes)", doc_id, len(data))
        except OSError:
            # ディスク I/O エラー（容量不足、権限不足等）のみ吸収。
            # MemoryError 等の非 I/O エラーはここを通過して上位に伝播する。
            logger.warning("キャッシュ書き込み失敗: %s", doc_id, exc_info=True)
        finally:
            # 一時ファイルの掃除（リネーム前に例外が発生した場合）
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def delete(self, doc_id: str) -> None:
        """指定した doc_id のキャッシュを削除する。

        Args:
            doc_id: 書類管理番号。
        """
        path = self.cache_path(doc_id)
        try:
            path.unlink(missing_ok=True)
            logger.debug("キャッシュ削除: %s", doc_id)
        except OSError:
            logger.warning("キャッシュ削除失敗: %s", doc_id, exc_info=True)

    def clear(self) -> None:
        """``downloads/`` サブディレクトリを削除する。

        Note:
            ``cache_dir`` 直下ではなく ``downloads/`` のみを削除する。
            ``TaxonomyResolver`` の pickle キャッシュ等、同じ ``cache_dir``
            を共有する他のキャッシュを巻き込まないための安全策。
        """
        if self._downloads_dir.exists():
            shutil.rmtree(self._downloads_dir)
            logger.info("キャッシュ全削除: %s", self._downloads_dir)

    def info(self) -> CacheInfo:
        """キャッシュの統計情報を返す。

        Returns:
            ``CacheInfo`` dataclass。
        """
        if not self._downloads_dir.exists():
            return CacheInfo(
                enabled=True,
                cache_dir=self._cache_dir,
                entry_count=0,
                total_bytes=0,
            )
        count = 0
        total = 0
        for f in self._downloads_dir.glob("*.zip"):
            try:
                total += f.stat().st_size
                count += 1
            except OSError:
                pass
        return CacheInfo(
            enabled=True,
            cache_dir=self._cache_dir,
            entry_count=count,
            total_bytes=total,
        )


def _get_cache_store() -> CacheStore | None:
    """キャッシュが有効なら ``CacheStore`` を返す。無効なら ``None``。

    ``Filing`` のヘルパーメソッドと ``clear_cache()`` / ``cache_info()`` が
    共通で使う内部関数。``get_config()`` + ``Path.expanduser()`` を 1 箇所に集約し、
    モック対象も 1 箇所にする。
    """
    from edinet._config import get_config

    config = get_config()
    if config.cache_dir is None:
        return None
    return CacheStore(Path(config.cache_dir).expanduser())


def clear_cache() -> None:
    """グローバル設定のダウンロードキャッシュを全削除する。

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
    """
    store = _get_cache_store()
    if store is None:
        logger.debug("キャッシュ無効のため clear_cache() はスキップ")
        return
    store.clear()


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
    store = _get_cache_store()
    if store is None:
        return CacheInfo(enabled=False, cache_dir=None, entry_count=0, total_bytes=0)
    return store.info()
