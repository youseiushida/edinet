"""公開 API (`edinet.documents`) のテスト。"""
from __future__ import annotations

from datetime import date, datetime

import pytest

import edinet
from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.models.doc_types import DocType
from edinet.public_api import adocuments


def _api_doc(
    doc_id: str,
    *,
    doc_type_code: str = "120",
    edinet_code: str = "E02144",
) -> dict:
    return {
        "seqNumber": 1,
        "docID": doc_id,
        "edinetCode": edinet_code,
        "secCode": "72030",
        "filerName": "テスト株式会社",
        "docTypeCode": doc_type_code,
        "submitDateTime": "2026-02-07 12:00",
        "xbrlFlag": "1",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "0",
        "csvFlag": "0",
    }


def _api_response(results: list[object], *, count: int | str | None = None) -> dict:
    declared_count = len(results) if count is None else count
    return {
        "metadata": {
            "status": "200",
            "message": "OK",
            "resultset": {"count": str(declared_count)},
        },
        "results": results,
    }


def test_documents_single_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """単日指定で取得できること。"""
    called: list[tuple[str, bool]] = []

    def fake_get_documents(date_str: str, *, include_details: bool = True):
        called.append((date_str, include_details))
        return _api_response([_api_doc("S100A001")])

    monkeypatch.setattr("edinet.api.documents.get_documents", fake_get_documents)

    filings = edinet.documents("2026-02-07")
    assert [f.doc_id for f in filings] == ["S100A001"]
    assert called == [("2026-02-07", True)]


def test_documents_accepts_withdrawn_record_with_nullable_core_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """取り下げ済みレコードで主要項目が None でも変換できること。"""
    row = _api_doc("S100XJNI")
    row["withdrawalStatus"] = "1"
    row["docTypeCode"] = None
    row["ordinanceCode"] = None
    row["formCode"] = None
    row["filerName"] = None
    row["docDescription"] = None

    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response([row]),
    )
    filings = edinet.documents("2026-02-07")
    assert len(filings) == 1
    assert filings[0].withdrawal_status == "1"
    assert filings[0].doc_type_code is None
    assert filings[0].filer_name is None
    assert filings[0].doc_description is None


def test_documents_date_object_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """date オブジェクトを受け付けること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response([_api_doc("S100A001")]),
    )
    filings = edinet.documents(date(2026, 2, 7))
    assert len(filings) == 1


def test_documents_date_range_inclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    """日付範囲が両端含みで反復されること。"""
    called: list[str] = []
    responses = {
        "2026-02-07": [_api_doc("S100A007")],
        "2026-02-08": [_api_doc("S100A008")],
        "2026-02-09": [_api_doc("S100A009")],
    }

    def fake_get_documents(date_str: str, *, include_details: bool = True):
        called.append(date_str)
        return _api_response(responses[date_str])

    monkeypatch.setattr("edinet.api.documents.get_documents", fake_get_documents)

    filings = edinet.documents(start="2026-02-07", end="2026-02-09")
    assert [f.doc_id for f in filings] == ["S100A007", "S100A008", "S100A009"]
    assert called == ["2026-02-07", "2026-02-08", "2026-02-09"]


def test_documents_filters_by_doc_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """doc_type で絞り込みできること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A120", doc_type_code="120"),
                _api_doc("S100A140", doc_type_code="140"),
            ],
        ),
    )
    filings = edinet.documents("2026-02-07", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_prefilters_raw_results_before_filing_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doc_type 非対象の壊れ行があっても対象行だけ変換できること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A120", doc_type_code="120"),
                {"docTypeCode": "140", "broken": "missing required fields"},
            ],
        ),
    )
    filings = edinet.documents("2026-02-07", doc_type="120")
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_prefilters_raw_results_even_if_non_dict_row_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """フィルタ指定時は non-dict 行を無視できること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A120", doc_type_code="120"), "broken-row"],
            count=2,
        ),
    )
    with pytest.warns(EdinetWarning):
        filings = edinet.documents("2026-02-07", doc_type="120")
    assert [f.doc_id for f in filings] == ["S100A120"]


def test_documents_raises_parse_error_when_result_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """metadata.resultset.count と results の不一致を検知すること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001")],
            count=99,
        ),
    )
    with pytest.raises(EdinetParseError, match="result count mismatch"):
        edinet.documents("2026-02-07")


def test_documents_normalizes_filing_parse_value_error_to_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filing 変換 ValueError を EdinetParseError に正規化すること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [{"docTypeCode": "120", "broken": "missing required fields"}],
            count=1,
        ),
    )
    with pytest.raises(EdinetParseError, match=r"Filing変換に失敗"):
        edinet.documents("2026-02-07", on_invalid="error")


def test_documents_raises_parse_error_when_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """metadata 欠落を EdinetParseError にすること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {"results": []},
    )
    with pytest.raises(EdinetParseError, match="response 'metadata' must be dict"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_resultset_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """metadata.resultset 欠落を EdinetParseError にすること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {"status": "200", "message": "OK"},
            "results": [],
        },
    )
    with pytest.raises(EdinetParseError, match="response 'metadata.resultset' must be dict"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_result_count_is_not_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """count が整数変換できない場合に EdinetParseError を返すこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {
                "status": "200",
                "message": "OK",
                "resultset": {"count": "NaN"},
            },
            "results": [],
        },
    )
    with pytest.raises(EdinetParseError, match="count' must be int-compatible"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_results_is_not_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """results が list でない場合に EdinetParseError を返すこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: {
            "metadata": {"status": "200", "message": "OK", "resultset": {"count": "1"}},
            "results": {"not": "list"},
        },
    )
    with pytest.raises(EdinetParseError, match="response 'results' must be list"):
        edinet.documents("2026-02-07")


def test_documents_raises_parse_error_when_results_contains_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="error" + 非 dict 行で EdinetParseError を返すこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001"), "broken"],
            count=2,
        ),
    )
    with pytest.raises(EdinetParseError, match=r"非 dict 行"):
        edinet.documents("2026-02-07", on_invalid="error")


def test_documents_prefilters_by_edinet_code_before_filing_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edinet_code でも生データ先絞りされること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100T001", doc_type_code="120", edinet_code="E02144"),
                {"edinetCode": "E00001", "broken": "missing required fields"},
            ],
        ),
    )
    filings = edinet.documents("2026-02-07", edinet_code="E02144")
    assert [f.doc_id for f in filings] == ["S100T001"]


def test_documents_normalizes_edinet_code_for_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """edinet_code の空白除去と大文字化が行われること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100T001", doc_type_code="120", edinet_code="E02144"),
                _api_doc("S100O001", doc_type_code="120", edinet_code="E00001"),
            ],
        ),
    )
    filings = edinet.documents("2026-02-07", edinet_code=" e02144 ")
    assert [f.doc_id for f in filings] == ["S100T001"]


def test_documents_rejects_invalid_doc_type_string() -> None:
    """未知の doc_type 文字列を拒否すること。"""
    with pytest.raises(ValueError, match="Unknown doc_type"):
        edinet.documents("2026-02-07", doc_type="12O")


def test_documents_does_not_accept_include_details_argument() -> None:
    """公開 documents() が include_details を受けないこと。"""
    with pytest.raises(TypeError):
        edinet.documents("2026-02-07", include_details=False)  # type: ignore[call-arg]


def test_documents_rejects_invalid_edinet_code() -> None:
    """フォーマット不正の edinet_code を拒否すること。"""
    with pytest.raises(ValueError, match="Invalid edinet_code"):
        edinet.documents("2026-02-07", edinet_code="7203")


def test_documents_rejects_non_string_edinet_code() -> None:
    """型不正の edinet_code を ValueError に統一すること。"""
    with pytest.raises(ValueError, match="edinet_code must be str or None"):
        edinet.documents("2026-02-07", edinet_code=7203)  # type: ignore[arg-type]


def test_documents_rejects_invalid_date_format() -> None:
    """不正フォーマット日付を拒否すること。"""
    with pytest.raises(ValueError, match="date must be YYYY-MM-DD"):
        edinet.documents("2026/02/07")


def test_documents_rejects_invalid_date_type() -> None:
    """不正型の日付入力を拒否すること。"""
    with pytest.raises(ValueError, match="date must be YYYY-MM-DD string or date"):
        edinet.documents(20260207)  # type: ignore[arg-type]


def test_documents_rejects_datetime_value() -> None:
    """datetime は拒否すること。"""
    with pytest.raises(ValueError, match="without time component"):
        edinet.documents(datetime(2026, 2, 7, 12, 0, 0))


def test_documents_rejects_invalid_start_format() -> None:
    """start の不正フォーマットを拒否すること。"""
    with pytest.raises(ValueError, match="start must be YYYY-MM-DD"):
        edinet.documents(start="2026/02/01", end="2026-02-07")


def test_documents_rejects_invalid_date_arguments() -> None:
    """日付引数の排他ルールを検証すること。"""
    with pytest.raises(ValueError, match="mutually exclusive"):
        edinet.documents("2026-02-07", start="2026-02-01", end="2026-02-07")

    with pytest.raises(ValueError, match="Specify either date or both start/end"):
        edinet.documents()

    with pytest.raises(ValueError, match="Specify either date or both start/end"):
        edinet.documents(start="2026-02-01")

    with pytest.raises(ValueError, match="start must be <= end"):
        edinet.documents(start="2026-02-10", end="2026-02-01")


def test_documents_rejects_too_large_date_range() -> None:
    """366日を超える日付範囲を拒否すること。"""
    with pytest.raises(ValueError, match="Date range too large"):
        edinet.documents(start="2024-01-01", end="2026-02-07")


# --- on_invalid テスト ---


def test_documents_on_invalid_skip_filters_non_dict_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="skip" で非 dict 行をスキップし、正常行のみ返すこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001"), "broken-row"],
            count=2,
        ),
    )
    with pytest.warns(EdinetWarning):
        filings = edinet.documents("2026-02-07", on_invalid="skip")
    assert [f.doc_id for f in filings] == ["S100A001"]


def test_documents_on_invalid_skip_filters_broken_dict_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="skip" で壊れ dict をスキップし、正常行のみ返すこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A001"),
                {"docTypeCode": "120", "broken": "missing required fields"},
            ],
        ),
    )
    with pytest.warns(EdinetWarning):
        filings = edinet.documents("2026-02-07", on_invalid="skip")
    assert [f.doc_id for f in filings] == ["S100A001"]


def test_documents_on_invalid_skip_warns_with_edinet_warning_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="skip" の warning カテゴリが EdinetWarning であること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A001"),
                {"docTypeCode": "120", "broken": "missing required fields"},
            ],
        ),
    )
    with pytest.warns(EdinetWarning) as record:
        edinet.documents("2026-02-07", on_invalid="skip")
    assert len(record) >= 1
    assert issubclass(record[0].category, EdinetWarning)


def test_documents_on_invalid_skip_warning_contains_skip_count_and_doc_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """warning メッセージにスキップ件数と代表 docID が含まれること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [
                _api_doc("S100A001"),
                {"docID": "S100BROKEN", "broken": "missing required fields"},
            ],
        ),
    )
    with pytest.warns(EdinetWarning, match=r"1件.*S100BROKEN"):
        edinet.documents("2026-02-07", on_invalid="skip")


def test_documents_on_invalid_error_non_dict_raises_with_action_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="error" + 非 dict で EdinetParseError にガイダンスが含まれること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001"), "broken-row"],
            count=2,
        ),
    )
    with pytest.raises(EdinetParseError, match=r"on_invalid='skip'"):
        edinet.documents("2026-02-07", on_invalid="error")


def test_documents_on_invalid_error_broken_dict_raises_with_action_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """on_invalid="error" + 壊れ dict で EdinetParseError にガイダンスが含まれること。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [{"docTypeCode": "120", "broken": "missing required fields"}],
            count=1,
        ),
    )
    with pytest.raises(EdinetParseError, match=r"on_invalid='skip'"):
        edinet.documents("2026-02-07", on_invalid="error")


def test_documents_on_invalid_skip_no_warning_when_all_rows_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常データのみのとき warning が出ないこと。"""
    monkeypatch.setattr(
        "edinet.api.documents.get_documents",
        lambda date_str, *, include_details=True: _api_response(
            [_api_doc("S100A001"), _api_doc("S100A002")],
        ),
    )
    import warnings as _warnings

    with _warnings.catch_warnings():
        _warnings.simplefilter("error", EdinetWarning)
        filings = edinet.documents("2026-02-07", on_invalid="skip")
    assert len(filings) == 2


# ============================================================
# adocuments() async テスト
# ============================================================


async def test_adocuments_single_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """adocuments() が単日取得で list[Filing] を返すこと。"""
    async def fake_aget_documents(date_str: str, *, include_details: bool = True):
        return _api_response([_api_doc("S100A001")])

    monkeypatch.setattr("edinet.api.documents.aget_documents", fake_aget_documents)

    filings = await adocuments("2026-02-07")
    assert [f.doc_id for f in filings] == ["S100A001"]


async def test_adocuments_on_invalid_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """adocuments() の on_invalid="skip" で warning + スキップ。"""
    async def fake_aget_documents(date_str: str, *, include_details: bool = True):
        return _api_response(
            [_api_doc("S100A001"), "broken-row"],
            count=2,
        )

    monkeypatch.setattr("edinet.api.documents.aget_documents", fake_aget_documents)

    with pytest.warns(EdinetWarning):
        filings = await adocuments("2026-02-07", on_invalid="skip")
    assert [f.doc_id for f in filings] == ["S100A001"]


async def test_adocuments_on_invalid_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """adocuments() の on_invalid="error" で EdinetParseError。"""
    async def fake_aget_documents(date_str: str, *, include_details: bool = True):
        return _api_response(
            [_api_doc("S100A001"), "broken-row"],
            count=2,
        )

    monkeypatch.setattr("edinet.api.documents.aget_documents", fake_aget_documents)

    with pytest.raises(EdinetParseError, match=r"非 dict 行"):
        await adocuments("2026-02-07", on_invalid="error")
