"""テスト共通の fixture。"""
import io
import sys
import zipfile
from pathlib import Path

import pytest

from edinet._config import _reset_for_testing

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TAXONOMY_MINI_DIR = FIXTURES_DIR / "taxonomy_mini"


def _make_test_zip(
    xbrl_bytes: bytes,
    xbrl_name: str = "PublicDoc/jpcrp030000-asr-001_E00001_2025-03-31.xbrl",
    filer_lab_bytes: bytes | None = None,
    filer_lab_en_bytes: bytes | None = None,
    filer_xsd_bytes: bytes | None = None,
    filer_xsd_name: str = "PublicDoc/jpcrp030000-asr-001_E00001.xsd",
) -> bytes:
    """テスト用の最小 ZIP を構築する。

    Args:
        xbrl_bytes: XBRL インスタンスのバイト列。
        xbrl_name: ZIP 内での XBRL ファイルパス。
        filer_lab_bytes: 提出者 _lab.xml のバイト列。
        filer_lab_en_bytes: 提出者 _lab-en.xml のバイト列。
        filer_xsd_bytes: 提出者 .xsd のバイト列。
        filer_xsd_name: ZIP 内での XSD ファイルパス。

    Returns:
        ZIP のバイト列。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xbrl_name, xbrl_bytes)
        if filer_lab_bytes is not None:
            lab_name = filer_xsd_name.replace(".xsd", "_lab.xml")
            zf.writestr(lab_name, filer_lab_bytes)
        if filer_lab_en_bytes is not None:
            lab_en_name = filer_xsd_name.replace(".xsd", "_lab-en.xml")
            zf.writestr(lab_en_name, filer_lab_en_bytes)
        if filer_xsd_bytes is not None:
            zf.writestr(filer_xsd_name, filer_xsd_bytes)
    return buf.getvalue()


@pytest.fixture()
def make_test_zip():
    """テスト用 ZIP 構築ヘルパーを返すファクトリフィクスチャ。"""
    return _make_test_zip


@pytest.fixture(autouse=True)
def _reset_config():
    """各テスト後にグローバル設定をデフォルトに戻す。

    テストが途中で失敗しても確実にクリーンアップされる。
    _reset_for_testing() は _Config() を新規生成するので、
    デフォルト値を conftest にハードコードする必要がない（二重管理防止）。
    """
    yield
    # teardown: 設定を初期状態に戻す
    _reset_for_testing()
    # HTTP クライアントも破棄（テスト間で状態が残らないようにする）
    from edinet._http import invalidate_client, invalidate_async_client_sync
    invalidate_client()
    invalidate_async_client_sync()

@pytest.fixture(autouse=True)
def _reset_warned_codes():
    """各テスト後に warning 抑制状態をリセットする。

    テスト順序依存のフレイキーテストを防止する。
    _warned_unknown_codes を直接操作せず、専用リセット関数を使うことで
    内部実装の変更がテストに波及しない。
    重いモデルを毎回 import しないため、import 済みモジュールのみ対象にする。
    """
    yield
    modules_to_reset = (
        "edinet.models.doc_types",
        "edinet.models.ordinance_code",
        "edinet.models.form_code",
        "edinet.models.fund_code",
        "edinet.models.edinet_code",
    )
    for module_name in modules_to_reset:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        reset = getattr(module, "_reset_warning_state", None)
        if callable(reset):
            reset()
