"""Filing.fetch_pdf() / afetch_pdf() のテスト。

PDF ダウンロード機能の3層キャッシュ（メモリ → ディスク → ネットワーク）を検証する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from edinet.models.filing import Filing


# --- テストヘルパー ---

SAMPLE_DOC: dict = {
    "seqNumber": 1,
    "docID": "S100PDF1",
    "edinetCode": "E02144",
    "secCode": "72030",
    "JCN": "1180301018771",
    "filerName": "テスト株式会社",
    "fundCode": None,
    "ordinanceCode": "010",
    "formCode": "030000",
    "docTypeCode": "120",
    "periodStart": "2024-04-01",
    "periodEnd": "2025-03-31",
    "submitDateTime": "2025-06-26 15:00",
    "docDescription": "有価証券報告書",
    "issuerEdinetCode": None,
    "subjectEdinetCode": None,
    "subsidiaryEdinetCode": None,
    "currentReportReason": None,
    "parentDocID": None,
    "opeDateTime": None,
    "withdrawalStatus": "0",
    "docInfoEditStatus": "0",
    "disclosureStatus": "0",
    "xbrlFlag": "1",
    "pdfFlag": "1",
    "attachDocFlag": "0",
    "englishDocFlag": "0",
    "csvFlag": "0",
    "legalStatus": "1",
}

FAKE_PDF = b"%PDF-1.4 fake pdf content"


def _make_filing(*, has_pdf: bool = True, has_xbrl: bool = True) -> Filing:
    """テスト用の Filing インスタンスを生成する。"""
    doc = {
        **SAMPLE_DOC,
        "pdfFlag": "1" if has_pdf else "0",
        "xbrlFlag": "1" if has_xbrl else "0",
    }
    return Filing.from_api_response(doc)


# ============================================================
# TestFetchPdf: 基本的な同期テスト
# ============================================================


class TestFetchPdf:
    """fetch_pdf() の基本動作テスト。"""

    def test_fetch_pdf_returns_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_pdf() が PDF バイト列を返すこと。"""
        from edinet.api.download import DownloadFileType

        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        def fake_download(doc_id: str, *, file_type):
            called["download"] += 1
            assert doc_id == "S100PDF1"
            assert file_type is DownloadFileType.PDF
            return FAKE_PDF

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        result = filing.fetch_pdf()
        assert result == FAKE_PDF
        assert called["download"] == 1

    def test_fetch_pdf_raises_when_no_pdf(self) -> None:
        """has_pdf=False の書類で EdinetAPIError が発生すること。"""
        from edinet.exceptions import EdinetAPIError

        filing = _make_filing(has_pdf=False)
        with pytest.raises(EdinetAPIError, match="PDF が含まれていません"):
            filing.fetch_pdf()

    def test_fetch_pdf_memory_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """2回目の呼び出しではダウンロードが発生しないこと。"""
        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        def fake_download(doc_id: str, *, file_type):
            called["download"] += 1
            return FAKE_PDF

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        first = filing.fetch_pdf()
        second = filing.fetch_pdf()
        assert first == second == FAKE_PDF
        assert called["download"] == 1

    def test_fetch_pdf_refresh_bypasses_cache(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """refresh=True でキャッシュを無視して再取得すること。"""
        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        def fake_download(doc_id: str, *, file_type):
            called["download"] += 1
            return FAKE_PDF

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        filing.fetch_pdf()
        filing.fetch_pdf(refresh=True)
        assert called["download"] == 2

    def test_fetch_pdf_wraps_value_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download_document の ValueError が EdinetParseError に正規化されること。"""
        from edinet.exceptions import EdinetParseError

        filing = _make_filing()

        def fake_download(doc_id: str, *, file_type):
            raise ValueError("invalid doc_id")

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        with pytest.raises(EdinetParseError, match="PDF のダウンロードに失敗しました"):
            filing.fetch_pdf()


# ============================================================
# TestFetchPdfDiskCache: ディスクキャッシュのテスト
# ============================================================


class TestFetchPdfDiskCache:
    """fetch_pdf() のディスクキャッシュ連携テスト。"""

    def test_fetch_pdf_saves_to_disk(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """fetch_pdf() がディスクキャッシュに .pdf ファイルを保存すること。"""
        from edinet._config import configure

        configure(cache_dir=str(tmp_path))
        filing = _make_filing()

        def fake_download(doc_id: str, *, file_type):
            return FAKE_PDF

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        filing.fetch_pdf()

        pdf_path = tmp_path / "downloads" / "S100PDF1.pdf"
        assert pdf_path.exists()
        assert pdf_path.read_bytes() == FAKE_PDF

    def test_fetch_pdf_loads_from_disk(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """ディスクキャッシュに .pdf が存在する場合はダウンロードしないこと。"""
        from edinet._config import configure

        configure(cache_dir=str(tmp_path))
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir()
        (downloads_dir / "S100PDF1.pdf").write_bytes(FAKE_PDF)

        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        def fake_download(doc_id: str, *, file_type):
            called["download"] += 1
            return b"should not be called"

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        result = filing.fetch_pdf()
        assert result == FAKE_PDF
        assert called["download"] == 0

    def test_pdf_cache_independent_from_xbrl(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    ) -> None:
        """.zip と .pdf がそれぞれ独立して共存できること。"""
        from edinet._config import configure

        configure(cache_dir=str(tmp_path))
        downloads_dir = tmp_path / "downloads"
        downloads_dir.mkdir()

        zip_bytes = b"PK\x03\x04dummy"
        (downloads_dir / "S100PDF1.zip").write_bytes(zip_bytes)
        (downloads_dir / "S100PDF1.pdf").write_bytes(FAKE_PDF)

        filing = _make_filing()

        # PDF はディスクキャッシュから取得される
        pdf_called: dict[str, int] = {"download": 0}

        def fake_pdf_download(doc_id: str, *, file_type):
            pdf_called["download"] += 1
            return b"should not be called"

        monkeypatch.setattr("edinet.api.download.download_document", fake_pdf_download)

        result = filing.fetch_pdf()
        assert result == FAKE_PDF
        assert pdf_called["download"] == 0

        # 両ファイルが共存していること
        assert (downloads_dir / "S100PDF1.zip").exists()
        assert (downloads_dir / "S100PDF1.pdf").exists()


# ============================================================
# TestAfetchPdf: 非同期テスト
# ============================================================


class TestAfetchPdf:
    """afetch_pdf() の非同期テスト。"""

    async def test_afetch_pdf_returns_bytes(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """afetch_pdf() が PDF バイト列を返すこと。"""
        from edinet.api.download import DownloadFileType

        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        async def fake_adownload(doc_id: str, *, file_type):
            called["download"] += 1
            assert doc_id == "S100PDF1"
            assert file_type is DownloadFileType.PDF
            return FAKE_PDF

        monkeypatch.setattr(
            "edinet.api.download.adownload_document", fake_adownload,
        )

        result = await filing.afetch_pdf()
        assert result == FAKE_PDF
        assert called["download"] == 1

    async def test_afetch_pdf_raises_when_no_pdf(self) -> None:
        """has_pdf=False の書類で afetch_pdf() が EdinetAPIError を返すこと。"""
        from edinet.exceptions import EdinetAPIError

        filing = _make_filing(has_pdf=False)
        with pytest.raises(EdinetAPIError, match="PDF が含まれていません"):
            await filing.afetch_pdf()


# ============================================================
# TestClearFetchCache: キャッシュクリアのテスト
# ============================================================


class TestClearFetchCache:
    """clear_fetch_cache() が PDF キャッシュもクリアすること。"""

    def test_clear_cache_clears_pdf(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """clear_fetch_cache() 後に _pdf_cache が None になること。"""
        filing = _make_filing()
        called: dict[str, int] = {"download": 0}

        def fake_download(doc_id: str, *, file_type):
            called["download"] += 1
            return FAKE_PDF

        monkeypatch.setattr("edinet.api.download.download_document", fake_download)

        filing.fetch_pdf()
        assert filing._pdf_cache is not None

        filing.clear_fetch_cache()
        assert filing._pdf_cache is None

        # クリア後に再取得でダウンロードが発生すること
        filing.fetch_pdf()
        assert called["download"] == 2
