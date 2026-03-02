"""`edinet.api` の再エクスポート契約テスト。"""
from __future__ import annotations


def test_api_re_exports_low_level_symbols() -> None:
    """低レベル API シンボルが公開されていること。"""
    from edinet.api import (
        DownloadFileType,
        download_document,
        extract_primary_xbrl,
        extract_zip_member,
        find_primary_xbrl_path,
        get_documents,
        list_zip_members,
    )

    assert callable(get_documents)
    assert callable(download_document)
    assert callable(list_zip_members)
    assert callable(find_primary_xbrl_path)
    assert callable(extract_zip_member)
    assert callable(extract_primary_xbrl)
    assert isinstance(DownloadFileType.XBRL_AND_AUDIT.value, str)
