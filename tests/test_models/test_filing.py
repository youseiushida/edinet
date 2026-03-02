"""filing.py のテスト。

from_api_response() の変換ロジックを中心に検証する。
"""
from datetime import date, datetime

import pytest

from edinet.models.doc_types import DocType
from edinet.models.ordinance_code import OrdinanceCode
from edinet.models.filing import (
    Filing, _parse_date, _parse_datetime, _parse_datetime_optional, _parse_flag,
    _extract_filer_taxonomy_files, _select_filer_xsd,
)


# --- テストフィクスチャ ---

SAMPLE_DOC: dict = {
    "seqNumber": 1,
    "docID": "S100TEST",
    "edinetCode": "E02144",
    "secCode": "72030",
    "JCN": "1180301018771",
    "filerName": "トヨタ自動車株式会社",
    "fundCode": None,
    "ordinanceCode": "010",
    "formCode": "030000",
    "docTypeCode": "120",
    "periodStart": "2024-04-01",
    "periodEnd": "2025-03-31",
    "submitDateTime": "2025-06-26 15:00",
    "docDescription": "有価証券報告書－第85期(2024/04/01－2025/03/31)",
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
    "attachDocFlag": "1",
    "englishDocFlag": "0",
    "csvFlag": "1",
    "legalStatus": "1",
}


# --- from_api_response() 基本変換 ---

def test_from_api_response_basic_fields():
    """基本フィールドが正しく変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.doc_id == "S100TEST"
    assert filing.seq_number == 1
    assert filing.filer_name == "トヨタ自動車株式会社"
    assert filing.doc_type_code == "120"
    assert filing.edinet_code == "E02144"


def test_from_api_response_date_conversion():
    """日付文字列が date/datetime に変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.submit_date_time == datetime(2025, 6, 26, 15, 0)
    assert filing.period_start == date(2024, 4, 1)
    assert filing.period_end == date(2025, 3, 31)


def test_from_api_response_null_dates():
    """null の日付が None になること。"""
    doc = {**SAMPLE_DOC, "periodStart": None, "periodEnd": None}
    filing = Filing.from_api_response(doc)
    assert filing.period_start is None
    assert filing.period_end is None


def test_from_api_response_flag_conversion():
    """フラグ "0"/"1" が bool に変換されること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.has_xbrl is True
    assert filing.has_pdf is True
    assert filing.has_english is False


def test_from_api_response_null_optional_fields():
    """null のオプションフィールドが None になること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.fund_code is None
    assert filing.issuer_edinet_code is None
    assert filing.parent_doc_id is None
    assert filing.ope_date_time is None


def test_filing_from_api_response_optional_fields_none():
    """Optional 5フィールドがキー欠落時に None で保持されること。"""
    doc = {**SAMPLE_DOC}
    for key in ["docTypeCode", "ordinanceCode", "formCode", "filerName", "docDescription"]:
        doc.pop(key, None)
    filing = Filing.from_api_response(doc)
    assert filing.doc_type_code is None
    assert filing.ordinance_code is None
    assert filing.form_code is None
    assert filing.filer_name is None
    assert filing.doc_description is None


# --- computed fields ---

def test_doc_type_computed_field():
    """doc_type が DocType Enum を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.doc_type == DocType.ANNUAL_SECURITIES_REPORT


def test_filing_date_computed_field():
    """filing_date が submit_date_time の日付部分を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.filing_date == date(2025, 6, 26)


def test_ticker_computed_field():
    """ticker が sec_code の先頭4桁を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.ticker == "7203"


def test_ticker_none_when_sec_code_is_none():
    """sec_code が None のとき ticker は None であること。"""
    doc = {**SAMPLE_DOC, "secCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.ticker is None


def test_doc_type_unknown_code():
    """未知の docTypeCode で doc_type が None になること。"""
    import warnings
    doc = {**SAMPLE_DOC, "docTypeCode": "999"}
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        filing = Filing.from_api_response(doc)
        assert filing.doc_type is None
        assert filing.doc_type_code == "999"


def test_filing_ordinance_property():
    """ordinance_code から OrdinanceCode が引けること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    assert filing.ordinance == OrdinanceCode.DISCLOSURE


def test_filing_ordinance_none_when_code_none():
    """ordinance_code が None のとき ordinance も None。"""
    doc = {**SAMPLE_DOC, "ordinanceCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.ordinance is None


def test_filing_form_property():
    """ordinance_code + form_code で FormCodeEntry が引けること。"""
    doc = {**SAMPLE_DOC, "ordinanceCode": "010", "formCode": "010000"}
    filing = Filing.from_api_response(doc)
    assert filing.form is not None
    assert filing.form.form_name == "有価証券通知書"


def test_filing_form_none_when_code_none():
    """form_code が None のとき form も None。"""
    doc = {**SAMPLE_DOC, "formCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.form is None


# --- frozen ---

def test_filing_is_frozen():
    """Filing がイミュータブルであること。"""
    from pydantic import ValidationError

    filing = Filing.from_api_response(SAMPLE_DOC)
    with pytest.raises(ValidationError):
        filing.doc_id = "S200OTHER"  # type: ignore[misc]


# --- __str__ ---

def test_str_representation():
    """__str__ が簡潔なフォーマットを返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    s = str(filing)
    assert "S100TEST" in s
    assert "トヨタ" in s


def test_str_representation_unknown_doc_type():
    """未知の docTypeCode でも __str__ が壊れないこと。"""
    import warnings

    doc = {**SAMPLE_DOC, "docTypeCode": "999"}
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        filing = Filing.from_api_response(doc)
        s = str(filing)
        assert "999" in s  # フォールバックでコードが表示される
        assert "S100TEST" in s


# --- from_api_list() ---

def test_from_api_list():
    """from_api_list() が results 配列を Filing リストに変換すること。"""
    response = {
        "metadata": {"status": "200"},
        "results": [SAMPLE_DOC, {**SAMPLE_DOC, "seqNumber": 2, "docID": "S100TEST2"}],
    }
    filings = Filing.from_api_list(response)
    assert len(filings) == 2
    assert filings[0].doc_id == "S100TEST"
    assert filings[1].doc_id == "S100TEST2"


def test_from_api_list_empty_results():
    """results が空の場合に空リストを返すこと。"""
    response = {"metadata": {"status": "200"}, "results": []}
    assert Filing.from_api_list(response) == []


def test_from_api_list_missing_results():
    """results キーが存在しない場合に空リストを返すこと。"""
    response = {"metadata": {"status": "200"}}
    assert Filing.from_api_list(response) == []


def test_from_api_list_wraps_error_with_index():
    """from_api_list() が変換失敗時に index 情報を含む ValueError を出すこと。"""
    bad_doc = {**SAMPLE_DOC}
    del bad_doc["docID"]
    response = {
        "metadata": {"status": "200"},
        "results": [SAMPLE_DOC, bad_doc],  # 2件目が壊れている
    }
    with pytest.raises(ValueError, match="index=1"):
        Filing.from_api_list(response)


def test_from_api_list_wraps_type_error_with_index():
    """TypeError も index 情報つき ValueError に正規化されること。"""
    bad_doc = {**SAMPLE_DOC, "submitDateTime": None}
    response = {
        "metadata": {"status": "200"},
        "results": [bad_doc],
    }
    with pytest.raises(ValueError, match="index=0"):
        Filing.from_api_list(response)


# --- model_dump() ---

def test_model_dump_keys_are_snake_case():
    """model_dump() が snake_case キーを返すこと。

    Day 6 以降でログ/キャッシュ/テスト比較に使うため、
    出力キーの安定性を保証しておく。
    """
    filing = Filing.from_api_response(SAMPLE_DOC)
    dumped = filing.model_dump()
    assert "doc_id" in dumped
    assert "doc_type_code" in dumped
    assert "submit_date_time" in dumped
    assert "has_xbrl" in dumped
    # computed fields もデフォルト引数の model_dump() で含まれること（Pydantic v2 の仕様として固定）
    assert "doc_type" in dumped
    assert "filing_date" in dumped
    assert "ticker" in dumped
    assert "ordinance" not in dumped
    assert "form" not in dumped
    # camelCase が混入していないこと
    # (API フィールド "JCN" は Filing では "jcn" にマッピング済み)
    import re
    for key in dumped:
        assert re.match(r"^[a-z][a-z0-9_]*$", key), f"non-snake_case key found: {key}"


# --- 異常系テスト ---

def test_from_api_response_missing_doc_id():
    """必須フィールド（docID）欠落で KeyError が発生すること。"""
    doc = {**SAMPLE_DOC}
    del doc["docID"]
    with pytest.raises(KeyError, match="docID"):
        Filing.from_api_response(doc)


def test_from_api_response_missing_doc_type_code():
    """Optional フィールド（docTypeCode）欠落で None になること。"""
    doc = {**SAMPLE_DOC}
    del doc["docTypeCode"]
    filing = Filing.from_api_response(doc)
    assert filing.doc_type_code is None


def test_from_api_response_missing_filer_name():
    """Optional フィールド（filerName）欠落で None になること。"""
    doc = {**SAMPLE_DOC}
    del doc["filerName"]
    filing = Filing.from_api_response(doc)
    assert filing.filer_name is None


def test_from_api_response_invalid_datetime_format():
    """不正な日時フォーマットで ValueError が発生すること。"""
    doc = {**SAMPLE_DOC, "submitDateTime": "2025/06/26 15:00"}
    with pytest.raises(ValueError, match="Invalid datetime format"):
        Filing.from_api_response(doc)


def test_from_api_response_invalid_date_format():
    """不正な日付フォーマットで ValueError が発生すること。"""
    doc = {**SAMPLE_DOC, "periodStart": "2025/04/01"}
    with pytest.raises(ValueError):
        Filing.from_api_response(doc)


# --- ヘルパー関数 ---

def test_parse_date_valid():
    assert _parse_date("2025-03-31") == date(2025, 3, 31)


def test_parse_date_none():
    assert _parse_date(None) is None


def test_parse_date_empty():
    assert _parse_date("") is None


def test_parse_date_whitespace_only():
    """空白のみの文字列が None になること。"""
    assert _parse_date(" ") is None
    assert _parse_date("  ") is None


def test_parse_datetime_valid():
    assert _parse_datetime("2025-06-26 15:00") == datetime(2025, 6, 26, 15, 0)


def test_parse_datetime_invalid_format():
    """不正なフォーマットで ValueError が発生し、フィールド名が含まれること。"""
    with pytest.raises(ValueError, match="submitDateTime"):
        _parse_datetime("2025/06/26 15:00", field_name="submitDateTime")


def test_parse_datetime_optional_valid():
    """有効な日時文字列が datetime に変換されること。"""
    assert _parse_datetime_optional("2025-06-26 15:00") == datetime(2025, 6, 26, 15, 0)


def test_parse_datetime_optional_none():
    """None が None を返すこと。"""
    assert _parse_datetime_optional(None) is None


def test_parse_datetime_optional_empty():
    """空文字が None を返すこと。"""
    assert _parse_datetime_optional("") is None


def test_parse_datetime_optional_whitespace():
    """空白のみが None を返すこと。"""
    assert _parse_datetime_optional(" ") is None


def test_parse_flag_true():
    assert _parse_flag("1") is True


def test_parse_flag_false():
    assert _parse_flag("0") is False


def test_parse_flag_none():
    assert _parse_flag(None) is False


def test_company_property_returns_company():
    """company プロパティが Company を返すこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    company = filing.company
    assert company is not None
    assert company.edinet_code == "E02144"
    assert company.name_ja == "トヨタ自動車株式会社"
    assert company.sec_code == "72030"


def test_company_property_returns_none_when_edinet_code_missing():
    """edinet_code が無い場合は company が None になること。"""
    doc = {**SAMPLE_DOC, "edinetCode": None}
    filing = Filing.from_api_response(doc)
    assert filing.company is None


def test_fetch_raises_when_has_xbrl_false():
    """xbrlFlag=0 の書類で fetch() が EdinetAPIError を返すこと。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    with pytest.raises(EdinetAPIError, match="XBRL が含まれていません"):
        filing.fetch()


def test_fetch_propagates_edinet_error_from_download(monkeypatch: pytest.MonkeyPatch):
    """download_document の EdinetError が透過されること。"""
    from edinet.exceptions import EdinetError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        raise EdinetError("network timeout")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(EdinetError, match="network timeout"):
        filing.fetch()


def test_fetch_propagates_edinet_api_error_from_download(monkeypatch: pytest.MonkeyPatch):
    """download_document の EdinetAPIError が透過されること。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        raise EdinetAPIError(503, "upstream unavailable")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(EdinetAPIError, match="EDINET API error 503"):
        filing.fetch()


def test_fetch_downloads_primary_xbrl(monkeypatch: pytest.MonkeyPatch):
    """fetch() が ZIP から代表 XBRL を返すこと。"""
    from edinet.api.download import DownloadFileType

    filing = Filing.from_api_response(SAMPLE_DOC)
    zip_bytes = b"PK\x03\x04dummy"
    expected = ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
    called = {"download": 0, "extract": 0}

    def fake_download(doc_id: str, *, file_type):
        called["download"] += 1
        assert doc_id == "S100TEST"
        assert file_type is DownloadFileType.XBRL_AND_AUDIT
        return zip_bytes

    def fake_extract(raw: bytes):
        called["extract"] += 1
        assert raw == zip_bytes
        return expected

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    assert filing.fetch() == expected
    assert called == {"download": 1, "extract": 1}


def test_clear_fetch_cache_forces_redownload(monkeypatch: pytest.MonkeyPatch):
    """clear_fetch_cache() 後は再ダウンロードされること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda raw: ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    filing.fetch()
    filing.clear_fetch_cache()
    filing.fetch()
    assert called["download"] == 2


def test_fetch_uses_cache(monkeypatch: pytest.MonkeyPatch):
    """fetch() の2回目はキャッシュを使うこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0, "extract": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    def fake_extract(raw: bytes):
        del raw
        called["extract"] += 1
        return ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    first = filing.fetch()
    second = filing.fetch()
    assert first == second
    assert called == {"download": 1, "extract": 1}


def test_fetch_refresh_bypasses_cache(monkeypatch: pytest.MonkeyPatch):
    """refresh=True でキャッシュを無視して再取得すること。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda raw: ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    filing.fetch()
    filing.fetch(refresh=True)
    assert called["download"] == 2


def test_fetch_normalizes_zip_value_error_to_edinet_parse_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """ZIP 解析 ValueError が EdinetParseError に正規化されること。"""
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    def fake_extract(_raw: bytes):
        raise ValueError("broken zip")

    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    with pytest.raises(EdinetParseError, match="EDINET ZIP の解析に失敗しました") as exc_info:
        filing.fetch()
    assert isinstance(exc_info.value.__cause__, ValueError)

    with pytest.raises(EdinetParseError, match="EDINET ZIP の解析に失敗しました"):
        filing.fetch()
    assert called["download"] == 2


def test_fetch_normalizes_download_input_value_error_to_edinet_parse_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """download_document の ValueError が EdinetParseError に正規化されること。"""
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        raise ValueError("doc_id must be alphanumeric only")

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)

    with pytest.raises(
        EdinetParseError,
        match="XBRL ZIP のダウンロードに失敗しました",
    ) as exc_info:
        filing.fetch()
    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "doc_id must be alphanumeric only" in str(exc_info.value)


def test_fetch_raises_when_primary_xbrl_not_found(monkeypatch: pytest.MonkeyPatch):
    """primary XBRL が見つからない場合に EdinetParseError を返すこと。"""
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", lambda _raw: None)

    with pytest.raises(EdinetParseError, match="ZIP 内に主要な XBRL が見つかりません"):
        filing.fetch()

    with pytest.raises(EdinetParseError, match="ZIP 内に主要な XBRL が見つかりません"):
        filing.fetch()
    assert called["download"] == 2


# ============================================================
# afetch() async テスト
# ============================================================


async def test_afetch_downloads_primary_xbrl(monkeypatch: pytest.MonkeyPatch):
    """afetch() が ZIP から代表 XBRL を返すこと。"""
    from edinet.api.download import DownloadFileType

    filing = Filing.from_api_response(SAMPLE_DOC)
    zip_bytes = b"PK\x03\x04dummy"
    expected = ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
    called = {"download": 0, "extract": 0}

    async def fake_adownload(doc_id: str, *, file_type):
        called["download"] += 1
        assert doc_id == "S100TEST"
        assert file_type is DownloadFileType.XBRL_AND_AUDIT
        return zip_bytes

    def fake_extract(raw: bytes):
        called["extract"] += 1
        assert raw == zip_bytes
        return expected

    monkeypatch.setattr("edinet.api.download.adownload_document", fake_adownload)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    assert await filing.afetch() == expected
    assert called == {"download": 1, "extract": 1}


async def test_afetch_raises_when_has_xbrl_false():
    """xbrlFlag=0 の書類で afetch() が EdinetAPIError を返すこと。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    with pytest.raises(EdinetAPIError, match="XBRL が含まれていません"):
        await filing.afetch()


async def test_afetch_uses_cache(monkeypatch: pytest.MonkeyPatch):
    """afetch() の2回目はキャッシュを使うこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0, "extract": 0}

    async def fake_adownload(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    def fake_extract(raw: bytes):
        del raw
        called["extract"] += 1
        return ("XBRL/PublicDoc/main.xbrl", b"<xbrli:xbrl/>")

    monkeypatch.setattr("edinet.api.download.adownload_document", fake_adownload)
    monkeypatch.setattr("edinet.api.download.extract_primary_xbrl", fake_extract)

    first = await filing.afetch()
    second = await filing.afetch()
    assert first == second
    assert called == {"download": 1, "extract": 1}


# ============================================================
# _extract_filer_taxonomy_files() テスト（F-1〜F-4）
# ============================================================

def test_extract_filer_files_from_zip():
    """F-1: PublicDoc 配下の _lab.xml, _lab-en.xml, .xsd が正しく抽出されること。"""
    import io
    import zipfile

    lab_bytes = b"<lab>ja</lab>"
    lab_en_bytes = b"<lab>en</lab>"
    xsd_bytes = b"<xsd/>"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
        zf.writestr("PublicDoc/filer_lab.xml", lab_bytes)
        zf.writestr("PublicDoc/filer_lab-en.xml", lab_en_bytes)
        zf.writestr("PublicDoc/filer.xsd", xsd_bytes)
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    assert result["lab"] == lab_bytes
    assert result["lab_en"] == lab_en_bytes
    assert result["xsd"] == xsd_bytes


def test_extract_filer_files_excludes_audit():
    """F-2: 監査報告書の XSD が除外されること。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
        zf.writestr("PublicDoc/jpaud_cor_audit.xsd", b"<audit_xsd/>")
        zf.writestr("AuditDoc/jpaud_cor.xsd", b"<audit_xsd2/>")
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    assert "xsd" not in result


def test_extract_filer_files_none_zip():
    """F-3: zip_bytes=None で空辞書が返ること。"""
    assert _extract_filer_taxonomy_files(None) == {}


def test_extract_filer_files_no_filer_files():
    """F-4: 提出者ファイルがない ZIP で空辞書が返ること。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/main.xbrl", b"<xbrli:xbrl/>")
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    assert result == {}


# ============================================================
# _select_filer_xsd() テスト（F-5〜F-8）
# ============================================================


def test_select_filer_xsd_single():
    """F-5: 候補が1件の場合はそのまま返すこと。"""
    assert _select_filer_xsd(["PublicDoc/some.xsd"]) == "PublicDoc/some.xsd"


def test_select_filer_xsd_prefers_edinet_code():
    """F-6: EDINET コードを含む XSD が優先されること。"""
    candidates = [
        "PublicDoc/taxonomy_standard.xsd",
        "PublicDoc/jpcrp030000-asr-001_E02144.xsd",
    ]
    assert _select_filer_xsd(candidates) == "PublicDoc/jpcrp030000-asr-001_E02144.xsd"


def test_select_filer_xsd_deterministic_without_edinet_code():
    """F-7: EDINET コードがない場合はアルファベット順で先頭を返すこと。"""
    candidates = [
        "PublicDoc/zzz_schema.xsd",
        "PublicDoc/aaa_schema.xsd",
    ]
    assert _select_filer_xsd(candidates) == "PublicDoc/aaa_schema.xsd"


def test_select_filer_xsd_empty():
    """F-8: 候補がない場合は None を返すこと。"""
    assert _select_filer_xsd([]) is None


def test_extract_filer_files_multiple_xsds():
    """F-9: 複数の非 audit XSD がある場合に EDINET コード付きが選ばれること。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/taxonomy_std.xsd", b"<std/>")
        zf.writestr("PublicDoc/jpcrp030000-asr-001_E02144.xsd", b"<filer/>")
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    assert result["xsd"] == b"<filer/>"


def test_extract_filer_files_labels_aligned_with_xsd():
    """F-10: 複数ラベルファイルがある場合に XSD と同じベース名のラベルが選ばれること。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # 別のタクソノミのラベル（先に出現）
        zf.writestr("PublicDoc/other_lab.xml", b"<other_lab/>")
        zf.writestr("PublicDoc/other_lab-en.xml", b"<other_lab_en/>")
        zf.writestr("PublicDoc/other.xsd", b"<other_xsd/>")
        # filer のタクソノミ（後に出現）
        zf.writestr("PublicDoc/jpcrp030000-asr-001_E02144_lab.xml", b"<filer_lab/>")
        zf.writestr("PublicDoc/jpcrp030000-asr-001_E02144_lab-en.xml", b"<filer_lab_en/>")
        zf.writestr("PublicDoc/jpcrp030000-asr-001_E02144.xsd", b"<filer_xsd/>")
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    # XSD は EDINET コード付きが選ばれる
    assert result["xsd"] == b"<filer_xsd/>"
    # ラベルも XSD と同じベース名から導出される
    assert result["lab"] == b"<filer_lab/>"
    assert result["lab_en"] == b"<filer_lab_en/>"


def test_extract_filer_files_uppercase_xsd_suffix():
    """F-11: 大文字 .XSD 拡張子でもラベル導出が正しく動作すること。"""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/filer_lab.xml", b"<lab/>")
        zf.writestr("PublicDoc/filer_lab-en.xml", b"<lab_en/>")
        zf.writestr("PublicDoc/filer.XSD", b"<xsd/>")
    zip_bytes = buf.getvalue()

    result = _extract_filer_taxonomy_files(zip_bytes)
    assert result["xsd"] == b"<xsd/>"
    assert result["lab"] == b"<lab/>"
    assert result["lab_en"] == b"<lab_en/>"


# ============================================================
# _normalize_doc_type() 日本語マッチング テスト（N-1〜N-4）
# ============================================================


def test_normalize_doc_type_japanese_name():
    """N-1: '有価証券報告書' → '120' に正規化されること。"""
    from edinet.public_api import _normalize_doc_type

    assert _normalize_doc_type("有価証券報告書") == "120"


def test_normalize_doc_type_japanese_correction():
    """N-2: '訂正有価証券報告書' → '130' に正規化されること。"""
    from edinet.public_api import _normalize_doc_type

    assert _normalize_doc_type("訂正有価証券報告書") == "130"


def test_normalize_doc_type_unknown_japanese():
    """N-3: 存在しない日本語名で ValueError が発生すること。"""
    from edinet.public_api import _normalize_doc_type

    with pytest.raises(ValueError, match="Unknown doc_type"):
        _normalize_doc_type("存在しない書類")


def test_normalize_doc_type_code_still_works():
    """N-4: 既存のコード文字列が引き続き動作すること。"""
    from edinet.public_api import _normalize_doc_type

    assert _normalize_doc_type("120") == "120"
    assert _normalize_doc_type("140") == "140"


# ============================================================
# Filing.xbrl() / axbrl() テスト（X-3〜X-9, AX-2）
# ============================================================


def test_xbrl_uses_taxonomy_path_arg(monkeypatch: pytest.MonkeyPatch):
    """X-3: xbrl(taxonomy_path=...) の引数が configure() より優先されること。"""
    from edinet._config import configure

    configure(taxonomy_path="/global/path")
    filing = Filing.from_api_response(SAMPLE_DOC)

    captured_path: list[str] = []

    def fake_build(self, taxonomy_path, xbrl_path, xbrl_bytes):
        captured_path.append(taxonomy_path)
        from edinet.financial.statements import Statements
        return Statements(_items=())

    monkeypatch.setattr(Filing, "_build_statements", fake_build)
    monkeypatch.setattr(
        "edinet.api.download.download_document",
        lambda *a, **kw: b"PK\x03\x04dummy",
    )
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda _: ("PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    filing.xbrl(taxonomy_path="/explicit/path")
    assert captured_path == ["/explicit/path"]


def test_xbrl_raises_without_taxonomy_path():
    """X-4: taxonomy_path 未設定で EdinetConfigError が発生すること。"""
    from edinet.exceptions import EdinetConfigError

    filing = Filing.from_api_response(SAMPLE_DOC)
    with pytest.raises(EdinetConfigError, match="taxonomy_path が未設定です"):
        filing.xbrl()


def test_xbrl_raises_for_no_xbrl():
    """X-5: has_xbrl=False の Filing で EdinetAPIError が発生すること。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    with pytest.raises(EdinetAPIError, match="XBRL が含まれていません"):
        filing.xbrl(taxonomy_path="/dummy")


def test_xbrl_raises_api_error_before_config_error():
    """X-5b: has_xbrl=False で taxonomy_path 未設定でも EdinetAPIError が先に発生すること。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    # taxonomy_path も未設定だが、has_xbrl チェックが先に発動すべき
    with pytest.raises(EdinetAPIError, match="XBRL が含まれていません"):
        filing.xbrl()


def test_xbrl_reuses_zip_cache(monkeypatch: pytest.MonkeyPatch):
    """X-6: fetch() 済みの Filing で xbrl() が追加ダウンロードしないこと。"""
    filing = Filing.from_api_response(SAMPLE_DOC)
    called = {"download": 0}

    def fake_download(doc_id: str, *, file_type):
        del doc_id, file_type
        called["download"] += 1
        return b"PK\x03\x04dummy"

    monkeypatch.setattr("edinet.api.download.download_document", fake_download)
    monkeypatch.setattr(
        "edinet.api.download.extract_primary_xbrl",
        lambda _: ("PublicDoc/main.xbrl", b"<xbrli:xbrl/>"),
    )

    def fake_build(self, taxonomy_path, xbrl_path, xbrl_bytes):
        from edinet.financial.statements import Statements
        return Statements(_items=())

    monkeypatch.setattr(Filing, "_build_statements", fake_build)

    # 1回目: fetch + xbrl
    filing.fetch()
    assert called["download"] == 1

    # 2回目: xbrl のみ (キャッシュ再利用)
    filing.xbrl(taxonomy_path="/dummy")
    assert called["download"] == 1


def test_xbrl_warns_on_non_jgaap_namespace(monkeypatch: pytest.MonkeyPatch):
    """X-8: jppfs_cor 名前空間がない場合に EdinetWarning が発生すること。"""
    import io
    import warnings
    import zipfile

    # IFRS のみの最小 XBRL（schemaRef 付き）
    ifrs_xbrl = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:link="http://www.xbrl.org/2003/linkbase"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
            xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2023-03-23/ifrs-full">
  <link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>
  <xbrli:context id="ctx1">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
  <ifrs-full:Revenue contextRef="ctx1" unitRef="JPY" decimals="0">1000</ifrs-full:Revenue>
</xbrli:xbrl>"""

    # 有効な ZIP を作成
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/main.xbrl", ifrs_xbrl)
    valid_zip = buf.getvalue()

    filing = Filing.from_api_response(SAMPLE_DOC)
    object.__setattr__(filing, "_xbrl_cache", ("PublicDoc/main.xbrl", ifrs_xbrl))
    object.__setattr__(filing, "_zip_cache", valid_zip)

    # build_line_items と build_statements をモック
    monkeypatch.setattr(
        "edinet.xbrl.facts.build_line_items", lambda *a, **kw: ()
    )
    monkeypatch.setattr(
        "edinet.financial.statements.build_statements",
        lambda items: __import__("edinet.financial.statements", fromlist=["Statements"]).Statements(_items=items),
    )

    taxonomy_path = str(
        __import__("pathlib").Path(__file__).parent.parent / "fixtures" / "taxonomy_mini"
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        filing.xbrl(taxonomy_path=taxonomy_path)

    from edinet.exceptions import EdinetWarning

    jppfs_warnings = [x for x in w if "jppfs_cor" in str(x.message)]
    assert len(jppfs_warnings) >= 1
    assert issubclass(jppfs_warnings[0].category, EdinetWarning)
    # stacklevel=3 により、warning の発生元は呼び出し元（このテスト）を指すこと
    assert jppfs_warnings[0].filename == __file__


def test_xbrl_wraps_unexpected_error_with_doc_id(monkeypatch: pytest.MonkeyPatch):
    """X-9: 予期しない例外が EdinetParseError にラップされ doc_id が含まれること。"""
    from edinet.exceptions import EdinetParseError

    filing = Filing.from_api_response(SAMPLE_DOC)
    object.__setattr__(filing, "_xbrl_cache", ("PublicDoc/main.xbrl", b"<xbrli:xbrl/>"))
    object.__setattr__(filing, "_zip_cache", b"dummy")

    # parse_xbrl_facts を RuntimeError で失敗させる
    monkeypatch.setattr(
        "edinet.xbrl.parser.parse_xbrl_facts",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )

    with pytest.raises(EdinetParseError, match="S100TEST"):
        filing.xbrl(taxonomy_path="/dummy")


async def test_axbrl_raises_without_taxonomy_path():
    """AX-2: taxonomy_path 未設定で EdinetConfigError が発生すること。"""
    from edinet.exceptions import EdinetConfigError

    filing = Filing.from_api_response(SAMPLE_DOC)
    with pytest.raises(EdinetConfigError, match="taxonomy_path が未設定です"):
        await filing.axbrl()


async def test_axbrl_raises_api_error_before_config_error():
    """AX-3: axbrl() でも has_xbrl=False が taxonomy 未設定より優先されること。"""
    from edinet.exceptions import EdinetAPIError

    filing = Filing.from_api_response({**SAMPLE_DOC, "xbrlFlag": "0"})
    with pytest.raises(EdinetAPIError, match="XBRL が含まれていません"):
        await filing.axbrl()


async def test_axbrl_warns_stacklevel_correct(monkeypatch: pytest.MonkeyPatch):
    """AX-4: axbrl() 経由でも warning.filename が呼び出し元を指すこと。"""
    import io
    import warnings
    import zipfile

    ifrs_xbrl = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:link="http://www.xbrl.org/2003/linkbase"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
            xmlns:ifrs-full="http://xbrl.ifrs.org/taxonomy/2023-03-23/ifrs-full">
  <link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>
  <xbrli:context id="ctx1">
    <xbrli:entity><xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
  <ifrs-full:Revenue contextRef="ctx1" unitRef="JPY" decimals="0">1000</ifrs-full:Revenue>
</xbrli:xbrl>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("PublicDoc/main.xbrl", ifrs_xbrl)
    valid_zip = buf.getvalue()

    filing = Filing.from_api_response(SAMPLE_DOC)
    object.__setattr__(filing, "_xbrl_cache", ("PublicDoc/main.xbrl", ifrs_xbrl))
    object.__setattr__(filing, "_zip_cache", valid_zip)

    monkeypatch.setattr(
        "edinet.xbrl.facts.build_line_items", lambda *_a, **_kw: ()
    )
    monkeypatch.setattr(
        "edinet.financial.statements.build_statements",
        lambda items: __import__("edinet.financial.statements", fromlist=["Statements"]).Statements(_items=items),
    )

    taxonomy_path = str(
        __import__("pathlib").Path(__file__).parent.parent / "fixtures" / "taxonomy_mini"
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        await filing.axbrl(taxonomy_path=taxonomy_path)

    jppfs_warnings = [x for x in w if "jppfs_cor" in str(x.message)]
    assert len(jppfs_warnings) >= 1
    # axbrl() 経由でも stacklevel=3 が正しく呼び出し元を指すこと
    assert jppfs_warnings[0].filename == __file__
