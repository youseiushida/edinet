"""永続ディスクキャッシュのテスト。

CacheStore 単体テスト、_config 統合テスト、Filing.fetch/afetch 統合テスト、
clear_cache/cache_info モジュールレベル関数テストを含む。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from edinet.api.cache import CacheStore, cache_info, clear_cache


# ---------------------------------------------------------------------------
# テスト用 Filing ファクトリ
# ---------------------------------------------------------------------------


def _make_filing(
    doc_id: str = "S100TEST",
    has_xbrl: bool = True,
    **overrides: Any,
) -> Any:
    """テスト用の最小限 Filing を生成する。"""
    from edinet.models.filing import Filing

    defaults = dict(
        seq_number=1,
        doc_id=doc_id,
        doc_type_code="120",
        ordinance_code="010",
        form_code="030000",
        edinet_code=None,
        sec_code=None,
        jcn=None,
        filer_name="テスト株式会社",
        fund_code=None,
        submit_date_time=datetime(2026, 1, 1, 9, 0),
        period_start=None,
        period_end=None,
        doc_description="テスト書類",
        issuer_edinet_code=None,
        subject_edinet_code=None,
        subsidiary_edinet_code=None,
        current_report_reason=None,
        parent_doc_id=None,
        ope_date_time=None,
        withdrawal_status="0",
        doc_info_edit_status="0",
        disclosure_status="0",
        has_xbrl=has_xbrl,
        has_pdf=False,
        has_attachment=False,
        has_english=False,
        has_csv=False,
        legal_status="0",
    )
    defaults.update(overrides)
    return Filing(**defaults)


# ===========================================================================
# CacheStore 単体テスト
# ===========================================================================


class TestCacheStore:
    """CacheStore の基本操作テスト。"""

    def test_put_and_get(self, tmp_path: Path) -> None:
        """put() で保存したデータを get() で取得できる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"dummy zip data")
        result = store.get("S100ABC0")
        assert result == b"dummy zip data"

    def test_get_miss(self, tmp_path: Path) -> None:
        """存在しない doc_id では None が返る。"""
        store = CacheStore(tmp_path)
        result = store.get("S100NOEXIST")
        assert result is None

    def test_delete(self, tmp_path: Path) -> None:
        """delete() でキャッシュを削除できる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data")
        store.delete("S100ABC0")
        assert store.get("S100ABC0") is None

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        """存在しないキーの delete() はエラーにならない。"""
        store = CacheStore(tmp_path)
        store.delete("S100NOEXIST")  # 例外が発生しない

    def test_clear(self, tmp_path: Path) -> None:
        """clear() で downloads/ サブディレクトリを削除する。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data1")
        store.put("S100DEF1", b"data2")
        # cache_dir 直下に他のファイルを作成（taxonomy pickle 等を想定）
        (tmp_path / "other_cache.pkl").write_bytes(b"taxonomy")
        store.clear()
        assert store.get("S100ABC0") is None
        assert store.get("S100DEF1") is None
        assert not (tmp_path / "downloads").exists()
        # cache_dir 自体と他のファイルは保護される
        assert tmp_path.exists()
        assert (tmp_path / "other_cache.pkl").exists()

    def test_clear_empty(self, tmp_path: Path) -> None:
        """空のキャッシュで clear() してもエラーにならない。"""
        store = CacheStore(tmp_path / "nonexistent")
        store.clear()  # 例外が発生しない

    def test_cache_path_structure(self, tmp_path: Path) -> None:
        """キャッシュパスが {cache_dir}/downloads/{doc_id}.zip の形式。"""
        store = CacheStore(tmp_path)
        path = store.cache_path("S100ABC0")
        assert path == tmp_path / "downloads" / "S100ABC0.zip"

    def test_put_creates_directory(self, tmp_path: Path) -> None:
        """put() がディレクトリを自動作成する。"""
        cache_dir = tmp_path / "deep" / "nested"
        store = CacheStore(cache_dir)
        store.put("S100ABC0", b"data")
        assert store.get("S100ABC0") == b"data"

    def test_put_overwrite(self, tmp_path: Path) -> None:
        """同じ doc_id に対して put() を再実行すると上書きされる。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"old data")
        store.put("S100ABC0", b"new data")
        assert store.get("S100ABC0") == b"new data"

    def test_atomic_write_no_partial_file(self, tmp_path: Path) -> None:
        """正常書き込み後に .tmp ファイルが残らない。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"valid data")
        downloads_dir = tmp_path / "downloads"
        tmp_files = list(downloads_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_info_empty(self, tmp_path: Path) -> None:
        """空キャッシュの info() はエントリ数 0。"""
        store = CacheStore(tmp_path)
        info = store.info()
        assert info.entry_count == 0
        assert info.total_bytes == 0
        assert info.enabled is True

    def test_info_with_entries(self, tmp_path: Path) -> None:
        """info() がエントリ数と合計バイト数を返す。"""
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"x" * 100)
        store.put("S100DEF1", b"y" * 200)
        info = store.info()
        assert info.entry_count == 2
        assert info.total_bytes == 300
        assert info.enabled is True
        assert info.cache_dir == tmp_path


# ===========================================================================
# _config 統合テスト
# ===========================================================================


class TestCacheConfig:
    """configure() でのキャッシュ設定テスト。"""

    def test_cache_disabled_by_default(self) -> None:
        """デフォルトでは cache_dir は None。"""
        from edinet._config import get_config

        config = get_config()
        assert config.cache_dir is None

    def test_configure_cache_dir(self, tmp_path: Path) -> None:
        """configure() で cache_dir を設定できる。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))
        from edinet._config import get_config

        assert get_config().cache_dir == str(tmp_path)

    def test_configure_cache_dir_none_disables(self) -> None:
        """cache_dir=None でキャッシュを無効化できる。"""
        import edinet

        edinet.configure(cache_dir="/tmp/test")
        edinet.configure(cache_dir=None)
        from edinet._config import get_config

        assert get_config().cache_dir is None


# ===========================================================================
# Filing.fetch() ディスクキャッシュ統合テスト
# ===========================================================================


class TestFilingFetchWithCache:
    """Filing.fetch() のディスクキャッシュ統合テスト。

    ネットワーク呼び出し（download_document）はモックし、
    ディスクキャッシュ（CacheStore）は実物を使う。
    """

    def test_cache_hit_no_download(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """ディスクキャッシュにヒットした場合、ダウンロードしない。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        store = CacheStore(tmp_path)
        store.put("S100TEST", zip_bytes)

        def must_not_call(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("download_document が呼ばれた")

        monkeypatch.setattr(
            "edinet.api.download.download_document", must_not_call
        )

        filing = _make_filing(doc_id="S100TEST")
        path, data = filing.fetch()
        assert len(data) > 0

    def test_cache_miss_triggers_download(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """ディスクキャッシュにミスした場合、ダウンロードする。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        call_count = 0

        def mock_download(doc_id: str, **kwargs: Any) -> bytes:
            nonlocal call_count
            call_count += 1
            return zip_bytes

        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100MISS")
        filing.fetch()
        assert call_count == 1

    def test_refresh_true_bypasses_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """refresh=True の場合、キャッシュを無視してダウンロードする。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)

        store = CacheStore(tmp_path)
        store.put("S100TEST", zip_bytes)

        call_count = 0

        def mock_download(doc_id: str, **kwargs: Any) -> bytes:
            nonlocal call_count
            call_count += 1
            return zip_bytes

        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100TEST")
        filing.fetch(refresh=True)
        assert call_count == 1

    def test_download_result_saved_to_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """ダウンロード結果がディスクキャッシュに保存される。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document",
            lambda *a, **kw: zip_bytes,
        )

        filing = _make_filing(doc_id="S100NEW")
        filing.fetch()

        store = CacheStore(tmp_path)
        cached = store.get("S100NEW")
        assert cached == zip_bytes

    def test_corrupted_cache_self_heals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """破損したキャッシュファイルが自動的に削除される。"""
        import edinet
        from edinet.exceptions import EdinetParseError

        edinet.configure(cache_dir=str(tmp_path))

        # 破損データ（有効な ZIP ではない）をディスクキャッシュに直接配置
        store = CacheStore(tmp_path)
        store.put("S100CORRUPT", b"this is not a zip file")

        # ネットワークからも取得させない
        def must_not_call(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("download_document が呼ばれた")

        monkeypatch.setattr(
            "edinet.api.download.download_document", must_not_call
        )

        filing = _make_filing(doc_id="S100CORRUPT")
        with pytest.raises(EdinetParseError):
            filing.fetch()

        # ディスクキャッシュの当該エントリが削除されている
        assert store.get("S100CORRUPT") is None

    def test_cache_disabled_no_disk_io(
        self, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """キャッシュ無効時にディスク I/O が発生しない。"""
        # cache_dir=None（デフォルト）のまま
        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document",
            lambda *a, **kw: zip_bytes,
        )

        filing = _make_filing(doc_id="S100NOCACHE")
        path, data = filing.fetch()
        assert len(data) > 0

    def test_second_fetch_hits_memory_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """2回目の fetch() は in-memory キャッシュにヒットし、disk にもアクセスしない。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document",
            lambda *a, **kw: zip_bytes,
        )

        filing = _make_filing(doc_id="S100MEM")
        filing.fetch()  # 1回目: network → disk → memory

        # ディスクキャッシュを削除しても 2 回目は成功する（in-memory から返る）
        CacheStore(tmp_path).delete("S100MEM")
        path, data = filing.fetch()  # 2回目: memory hit
        assert len(data) > 0

    def test_refresh_true_updates_disk_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """refresh=True でダウンロードした結果がディスクキャッシュを上書きする。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        old_xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance">old</xbrl>'
        new_xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance">new</xbrl>'

        store = CacheStore(tmp_path)
        store.put("S100REF", make_test_zip(old_xbrl))

        new_zip = make_test_zip(new_xbrl)
        monkeypatch.setattr(
            "edinet.api.download.download_document",
            lambda *a, **kw: new_zip,
        )

        filing = _make_filing(doc_id="S100REF")
        filing.fetch(refresh=True)

        assert store.get("S100REF") == new_zip

    def test_cache_dir_change_uses_new_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """cache_dir 変更後は新しいディレクトリを参照する。"""
        import edinet

        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"

        edinet.configure(cache_dir=str(dir_a))
        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        call_count = 0

        def mock_download(doc_id: str, **kwargs: Any) -> bytes:
            nonlocal call_count
            call_count += 1
            return zip_bytes

        monkeypatch.setattr(
            "edinet.api.download.download_document", mock_download
        )

        filing = _make_filing(doc_id="S100SWITCH")
        filing.fetch()
        assert CacheStore(dir_a).get("S100SWITCH") is not None
        assert call_count == 1

        # cache_dir 変更 → 新しいディレクトリにはキャッシュがない
        edinet.configure(cache_dir=str(dir_b))
        filing2 = _make_filing(doc_id="S100SWITCH")
        filing2.fetch()
        assert call_count == 2
        assert CacheStore(dir_b).get("S100SWITCH") is not None


# ===========================================================================
# Filing.afetch() ディスクキャッシュ統合テスト（非同期版）
# ===========================================================================


class TestFilingAfetchWithCache:
    """Filing.afetch() のディスクキャッシュ統合テスト。"""

    async def test_afetch_cache_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """afetch() もディスクキャッシュを使用する。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)
        store = CacheStore(tmp_path)
        store.put("S100ASYNC", zip_bytes)

        async def must_not_call(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("adownload_document が呼ばれた")

        monkeypatch.setattr(
            "edinet.api.download.adownload_document", must_not_call
        )

        filing = _make_filing(doc_id="S100ASYNC")
        path, data = await filing.afetch()
        assert len(data) > 0

    async def test_afetch_saves_to_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_test_zip: Any
    ) -> None:
        """afetch() のダウンロード結果もディスクキャッシュに保存される。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))

        xbrl = b'<xbrl xmlns="http://www.xbrl.org/2003/instance"></xbrl>'
        zip_bytes = make_test_zip(xbrl)

        async def mock_adownload(doc_id: str, **kwargs: Any) -> bytes:
            return zip_bytes

        monkeypatch.setattr(
            "edinet.api.download.adownload_document", mock_adownload
        )

        filing = _make_filing(doc_id="S100ASYNC2")
        await filing.afetch()

        assert CacheStore(tmp_path).get("S100ASYNC2") == zip_bytes


# ===========================================================================
# clear_cache / cache_info テスト
# ===========================================================================


class TestClearCache:
    """clear_cache() 関数のテスト。"""

    def test_clear_cache_function(self, tmp_path: Path) -> None:
        """clear_cache() が downloads/ サブディレクトリを削除する。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"data")
        clear_cache()
        assert not (tmp_path / "downloads").exists()
        assert tmp_path.exists()  # cache_dir 自体は残る

    def test_clear_cache_when_disabled(self) -> None:
        """キャッシュ無効時の clear_cache() は何もしない。"""
        clear_cache()  # cache_dir=None（デフォルト）、例外が発生しない


class TestCacheInfo:
    """cache_info() 関数のテスト。"""

    def test_cache_info_when_disabled(self) -> None:
        """キャッシュ無効時は enabled=False を返す。"""
        info = cache_info()
        assert info.enabled is False
        assert info.entry_count == 0

    def test_cache_info_with_entries(self, tmp_path: Path) -> None:
        """キャッシュにエントリがある場合の統計情報。"""
        import edinet

        edinet.configure(cache_dir=str(tmp_path))
        store = CacheStore(tmp_path)
        store.put("S100ABC0", b"x" * 1000)
        store.put("S100DEF1", b"y" * 2000)
        info = cache_info()
        assert info.enabled is True
        assert info.entry_count == 2
        assert info.total_bytes == 3000
