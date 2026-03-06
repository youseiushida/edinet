"""taxonomy_install モジュールのテスト。"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from edinet._config import _reset_for_testing, get_config
from edinet.exceptions import EdinetConfigError, EdinetError
from edinet.taxonomy_install import (
    TaxonomyInfo,
    _detect_zip_prefix,
    _download_url,
    _folder_name,
    _latest_year,
    _KNOWN_VERSIONS,
    install_taxonomy,
    list_taxonomy_versions,
    taxonomy_info,
    uninstall_taxonomy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """各テスト後にグローバル設定をリセットする。"""
    yield
    _reset_for_testing()


def _make_taxonomy_zip(prefix: str = "タクソノミ") -> bytes:
    """テスト用のタクソノミ ZIP を生成する。

    Args:
        prefix: ZIP 内のトップレベルフォルダ名。

    Returns:
        ZIP ファイルのバイト列。
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if prefix:
            zf.writestr(f"{prefix}/", "")
            zf.writestr(f"{prefix}/taxonomy/", "")
            zf.writestr(
                f"{prefix}/taxonomy/jppfs/2025-11-01/jppfs_cor.xsd",
                "<xsd/>",
            )
            zf.writestr(f"{prefix}/samples/", "")
            zf.writestr(
                f"{prefix}/samples/2025-11-01/sample.xsd",
                "<xsd/>",
            )
        else:
            zf.writestr("taxonomy/", "")
            zf.writestr("taxonomy/jppfs/2025-11-01/jppfs_cor.xsd", "<xsd/>")
            zf.writestr("samples/", "")
            zf.writestr("samples/2025-11-01/sample.xsd", "<xsd/>")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 内部関数テスト
# ---------------------------------------------------------------------------


class TestInternalFunctions:
    """内部ヘルパー関数のテスト。"""

    def test_download_url_valid(self):
        url = _download_url(2026)
        assert "fsa.go.jp" in url
        assert "20251111" in url
        assert "1c_Taxonomy.zip" in url

    def test_download_url_invalid_year(self):
        with pytest.raises(EdinetConfigError, match="不明"):
            _download_url(2000)

    def test_folder_name(self):
        assert _folder_name(2026) == "ALL_20251101"
        assert _folder_name(2025) == "ALL_20241101"

    def test_latest_year(self):
        assert _latest_year() == max(_KNOWN_VERSIONS)

    def test_detect_zip_prefix_with_prefix(self):
        zf = zipfile.ZipFile(BytesIO(_make_taxonomy_zip("タクソノミ")))
        assert _detect_zip_prefix(zf) == "タクソノミ"

    def test_detect_zip_prefix_without_prefix(self):
        zf = zipfile.ZipFile(BytesIO(_make_taxonomy_zip("")))
        assert _detect_zip_prefix(zf) == ""

    def test_detect_zip_prefix_garbled(self):
        """Shift-JIS エンコードで文字化けしたプレフィックスも検出できる。"""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("garbled_name/taxonomy/foo.xsd", "<xsd/>")
        zf = zipfile.ZipFile(BytesIO(buf.getvalue()))
        assert _detect_zip_prefix(zf) == "garbled_name"


# ---------------------------------------------------------------------------
# list_taxonomy_versions
# ---------------------------------------------------------------------------


class TestListTaxonomyVersions:
    """list_taxonomy_versions のテスト。"""

    def test_returns_sorted_descending(self):
        versions = list_taxonomy_versions()
        assert versions == sorted(versions, reverse=True)

    def test_contains_known_years(self):
        versions = list_taxonomy_versions()
        assert 2026 in versions
        assert 2025 in versions
        assert 2018 in versions

    def test_returns_list_of_ints(self):
        versions = list_taxonomy_versions()
        assert all(isinstance(v, int) for v in versions)


# ---------------------------------------------------------------------------
# taxonomy_info
# ---------------------------------------------------------------------------


class TestTaxonomyInfo:
    """taxonomy_info のテスト。"""

    def test_no_installed_taxonomy(self, tmp_path: Path):
        """インストールなしの場合 None を返す。"""
        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            assert taxonomy_info() is None

    def test_detects_installed_taxonomy(self, tmp_path: Path):
        """インストール済みタクソノミを検出する。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            info = taxonomy_info()

        assert info is not None
        assert info.year == 2026
        assert info.folder_name == "ALL_20251101"
        assert info.path == folder

    def test_returns_latest_when_multiple(self, tmp_path: Path):
        """複数バージョンがある場合、最新を返す。"""
        (tmp_path / "ALL_20251101" / "taxonomy").mkdir(parents=True)
        (tmp_path / "ALL_20241101" / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            info = taxonomy_info()

        assert info is not None
        assert info.year == 2026

    def test_configured_flag(self, tmp_path: Path):
        """taxonomy_path が一致する場合 configured=True。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        from edinet._config import configure

        configure(taxonomy_path=str(folder))

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            info = taxonomy_info()

        assert info is not None
        assert info.configured is True


# ---------------------------------------------------------------------------
# install_taxonomy
# ---------------------------------------------------------------------------


class TestInstallTaxonomy:
    """install_taxonomy のテスト（ネットワーク不要）。"""

    def test_invalid_year(self):
        with pytest.raises(EdinetConfigError, match="不明"):
            install_taxonomy(year=1999)

    def test_already_installed_skips_download(self, tmp_path: Path):
        """既にインストール済みなら再ダウンロードしない。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            info = install_taxonomy(year=2026)

        assert info.year == 2026
        assert info.configured is True
        # configure が呼ばれたことを確認
        cfg = get_config()
        assert cfg.taxonomy_path == str(folder)

    def test_download_and_extract(self, tmp_path: Path):
        """正常なダウンロード・展開フローのテスト。"""
        zip_bytes = _make_taxonomy_zip("タクソノミ")

        class MockResponse:
            content = zip_bytes
            status_code = 200

            def raise_for_status(self):
                pass

        class MockClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                return MockResponse()

        with (
            patch(
                "edinet.taxonomy_install._data_dir", return_value=tmp_path
            ),
            patch("edinet.taxonomy_install.httpx.Client", MockClient),
        ):
            info = install_taxonomy(year=2026)

        assert info.year == 2026
        assert info.folder_name == "ALL_20251101"
        assert info.configured is True

        # ファイルが展開されていることを確認
        dest = tmp_path / "ALL_20251101"
        assert (dest / "taxonomy").exists()
        assert (dest / "taxonomy" / "jppfs" / "2025-11-01" / "jppfs_cor.xsd").exists()
        assert (dest / "samples").exists()

    def test_download_failure_raises(self, tmp_path: Path):
        """ダウンロード失敗時に EdinetError を送出する。"""

        class MockClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                raise httpx.HTTPError("接続失敗")

        import httpx

        with (
            patch(
                "edinet.taxonomy_install._data_dir", return_value=tmp_path
            ),
            patch("edinet.taxonomy_install.httpx.Client", MockClient),
        ):
            with pytest.raises(EdinetError, match="ダウンロード"):
                install_taxonomy(year=2026)

    def test_invalid_zip_raises(self, tmp_path: Path):
        """不正な ZIP の場合 EdinetError を送出する。"""

        class MockResponse:
            content = b"not a zip file"
            status_code = 200

            def raise_for_status(self):
                pass

        class MockClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                return MockResponse()

        with (
            patch(
                "edinet.taxonomy_install._data_dir", return_value=tmp_path
            ),
            patch("edinet.taxonomy_install.httpx.Client", MockClient),
        ):
            with pytest.raises(EdinetError, match="ZIP"):
                install_taxonomy(year=2026)

    def test_force_reinstall(self, tmp_path: Path):
        """force=True で再インストールする。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)
        (folder / "old_marker.txt").write_text("old")

        zip_bytes = _make_taxonomy_zip("タクソノミ")

        class MockResponse:
            content = zip_bytes
            status_code = 200

            def raise_for_status(self):
                pass

        class MockClient:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def get(self, url):
                return MockResponse()

        with (
            patch(
                "edinet.taxonomy_install._data_dir", return_value=tmp_path
            ),
            patch("edinet.taxonomy_install.httpx.Client", MockClient),
        ):
            info = install_taxonomy(year=2026, force=True)

        assert info.year == 2026
        # 古いファイルが消えている
        assert not (folder / "old_marker.txt").exists()
        # 新しいファイルがある
        assert (folder / "taxonomy").exists()

    def test_default_year_is_latest(self, tmp_path: Path):
        """year=None の場合は最新版がインストールされる。"""
        folder = tmp_path / _folder_name(_latest_year())
        (folder / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            info = install_taxonomy()

        assert info.year == _latest_year()


# ---------------------------------------------------------------------------
# uninstall_taxonomy
# ---------------------------------------------------------------------------


class TestUninstallTaxonomy:
    """uninstall_taxonomy のテスト。"""

    def test_uninstall_existing(self, tmp_path: Path):
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            result = uninstall_taxonomy(year=2026)

        assert result is True
        assert not folder.exists()

    def test_uninstall_nonexistent(self, tmp_path: Path):
        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            result = uninstall_taxonomy(year=2026)

        assert result is False

    def test_uninstall_clears_config(self, tmp_path: Path):
        """削除対象が設定済みなら taxonomy_path をクリアする。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        from edinet._config import configure

        configure(taxonomy_path=str(folder))

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            uninstall_taxonomy(year=2026)

        assert get_config().taxonomy_path is None

    def test_uninstall_invalid_year(self):
        with pytest.raises(EdinetConfigError, match="不明"):
            uninstall_taxonomy(year=1999)

    def test_uninstall_default_latest(self, tmp_path: Path):
        """year=None の場合はインストール済みの最新版を削除する。"""
        folder = tmp_path / "ALL_20251101"
        (folder / "taxonomy").mkdir(parents=True)

        with patch(
            "edinet.taxonomy_install._data_dir", return_value=tmp_path
        ):
            result = uninstall_taxonomy()

        assert result is True
        assert not folder.exists()


# ---------------------------------------------------------------------------
# 公開 API の lazy import テスト
# ---------------------------------------------------------------------------


class TestLazyImport:
    """edinet パッケージからの遅延インポートが機能するか。"""

    def test_import_install_taxonomy(self):
        import edinet

        assert callable(edinet.install_taxonomy)

    def test_import_list_taxonomy_versions(self):
        import edinet

        assert callable(edinet.list_taxonomy_versions)

    def test_import_taxonomy_info(self):
        import edinet

        assert callable(edinet.taxonomy_info)

    def test_import_uninstall_taxonomy(self):
        import edinet

        assert callable(edinet.uninstall_taxonomy)

    def test_import_taxonomy_info_class(self):
        import edinet

        assert edinet.TaxonomyInfo is TaxonomyInfo
