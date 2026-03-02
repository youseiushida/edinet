"""company.py のテスト。"""
from __future__ import annotations

from datetime import date as DateType, datetime, timezone
from zoneinfo import ZoneInfoNotFoundError

import pytest

from edinet.models.company import Company
from edinet.models.doc_types import DocType
from edinet.models.filing import Filing


def _sample_doc(*, doc_id: str, edinet_code: str | None) -> dict:
    return {
        "seqNumber": 1,
        "docID": doc_id,
        "edinetCode": edinet_code,
        "secCode": "72030",
        "filerName": "トヨタ自動車株式会社",
        "docTypeCode": "120",
        "submitDateTime": "2025-06-26 15:00",
        "xbrlFlag": "1",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "0",
        "csvFlag": "0",
    }


def test_ticker_property() -> None:
    """ticker が sec_code の先頭 4 桁になること。"""
    company = Company(edinet_code="E02144", name_ja="トヨタ", sec_code="72030")
    assert company.ticker == "7203"


def test_company_normalizes_edinet_code() -> None:
    """edinet_code が正規化されること。"""
    company = Company(edinet_code=" e02144 ")
    assert company.edinet_code == "E02144"


def test_company_rejects_invalid_edinet_code() -> None:
    """不正フォーマットの edinet_code を拒否すること。"""
    with pytest.raises(ValueError, match="Invalid edinet_code"):
        Company(edinet_code="7203")


def test_from_filing_returns_company() -> None:
    """Filing から Company を構築できること。"""
    filing = Filing.from_api_response(
        _sample_doc(doc_id="S100TEST", edinet_code="E02144"),
    )
    company = Company.from_filing(filing)
    assert company is not None
    assert company.edinet_code == "E02144"
    assert company.name_ja == "トヨタ自動車株式会社"


def test_from_filing_returns_none_when_edinet_code_missing() -> None:
    """edinet_code がない Filing では None を返すこと。"""
    filing = Filing.from_api_response(
        _sample_doc(doc_id="S100TEST", edinet_code=None),
    )
    assert Company.from_filing(filing) is None


def test_get_filings_filters_by_edinet_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_filings() が自身の edinet_code を渡すこと。"""
    company = Company(edinet_code="E02144", name_ja="トヨタ", sec_code="72030")
    called: dict[str, object] = {}

    def fake_documents(
        date=None,
        *,
        start=None,
        end=None,
        doc_type=None,
        edinet_code=None,
    ):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return [
            Filing.from_api_response(
                _sample_doc(doc_id="S100T001", edinet_code="E02144"),
            ),
        ]

    monkeypatch.setattr("edinet.documents", fake_documents)

    result = company.get_filings(
        "2026-02-07",
        doc_type=DocType.ANNUAL_SECURITIES_REPORT,
    )
    assert [f.doc_id for f in result] == ["S100T001"]
    assert called["edinet_code"] == "E02144"


def test_get_filings_forwards_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """引数が documents() に透過されること。"""
    company = Company(edinet_code="E02144")
    called: dict[str, object] = {}

    def fake_documents(
        date=None,
        *,
        start=None,
        end=None,
        doc_type=None,
        edinet_code=None,
    ):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)
    company.get_filings(start="2026-02-01", end="2026-02-07", doc_type="120")
    assert called == {
        "date": None,
        "start": "2026-02-01",
        "end": "2026-02-07",
        "doc_type": "120",
        "edinet_code": "E02144",
    }


def test_get_filings_defaults_to_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """日付引数省略時に JST 当日が使われること。"""
    company = Company(edinet_code="E02144")
    called: dict[str, object] = {}
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))

    def fake_documents(
        date=None,
        *,
        start=None,
        end=None,
        doc_type=None,
        edinet_code=None,
    ):
        called["date"] = date
        called["start"] = start
        called["end"] = end
        called["doc_type"] = doc_type
        called["edinet_code"] = edinet_code
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)

    company.get_filings()
    assert called == {
        "date": DateType(2026, 2, 16),
        "start": None,
        "end": None,
        "doc_type": None,
        "edinet_code": "E02144",
    }


def test_today_jst_falls_back_when_tzdb_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tzdb が無い場合に UTC+9 フォールバックすること。"""
    from edinet.models import company as company_module

    class FakeDateTime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return datetime(2026, 2, 16, 0, 0, 0)
            return datetime(2026, 2, 15, 15, 0, 0, tzinfo=timezone.utc)

    def fake_zone_info(_name: str):
        raise ZoneInfoNotFoundError("tzdb missing")

    monkeypatch.setattr(company_module, "datetime", FakeDateTime)
    monkeypatch.setattr(company_module, "ZoneInfo", fake_zone_info)

    assert company_module._today_jst() == DateType(2026, 2, 16)


# ============================================================
# Company.latest() テスト（L-1〜L-7）
# ============================================================

def _sample_doc_with_datetime(*, doc_id: str, submit_dt: str) -> dict:
    """submit_date_time を指定できるサンプルドキュメント。"""
    return {
        "seqNumber": 1,
        "docID": doc_id,
        "edinetCode": "E02144",
        "secCode": "72030",
        "filerName": "トヨタ自動車株式会社",
        "docTypeCode": "120",
        "submitDateTime": submit_dt,
        "xbrlFlag": "1",
        "pdfFlag": "1",
        "attachDocFlag": "0",
        "englishDocFlag": "0",
        "csvFlag": "0",
    }


def test_latest_returns_filing(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-1: latest() が Filing を返すこと。"""
    company = Company(edinet_code="E02144", name_ja="トヨタ", sec_code="72030")
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        return [
            Filing.from_api_response(
                _sample_doc_with_datetime(doc_id="S100T001", submit_dt="2026-02-10 10:00"),
            ),
        ]

    monkeypatch.setattr("edinet.documents", fake_documents)
    result = company.latest()
    assert result is not None
    assert result.doc_id == "S100T001"


def test_latest_returns_newest(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-2: 複数 Filing がある場合に最新のものを返すこと。"""
    company = Company(edinet_code="E02144")
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        return [
            Filing.from_api_response(
                _sample_doc_with_datetime(doc_id="OLD", submit_dt="2026-01-01 09:00"),
            ),
            Filing.from_api_response(
                _sample_doc_with_datetime(doc_id="NEW", submit_dt="2026-02-15 15:00"),
            ),
            Filing.from_api_response(
                _sample_doc_with_datetime(doc_id="MID", submit_dt="2026-01-20 12:00"),
            ),
        ]

    monkeypatch.setattr("edinet.documents", fake_documents)
    result = company.latest()
    assert result is not None
    assert result.doc_id == "NEW"


def test_latest_with_doc_type_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-3: doc_type フィルタが get_filings() に渡されること。"""
    company = Company(edinet_code="E02144")
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))
    captured: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        captured["doc_type"] = doc_type
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)
    company.latest("120")
    assert captured["doc_type"] == "120"


def test_latest_returns_none_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-4: Filing がない場合に None を返すこと。"""
    company = Company(edinet_code="E02144")
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: DateType(2026, 2, 16))

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)
    assert company.latest() is None


def test_latest_with_start_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-5: start / end 引数が get_filings() に渡されること。"""
    company = Company(edinet_code="E02144")
    captured: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        captured["start"] = start
        captured["end"] = end
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)
    company.latest(start="2025-06-01", end="2025-06-30")
    assert captured["start"] == "2025-06-01"
    assert captured["end"] == "2025-06-30"


def test_latest_default_range_90_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-6: start / end 未指定時に inclusive 90 日間が get_filings() に渡されること。"""
    from datetime import timedelta

    company = Company(edinet_code="E02144")
    today = DateType(2026, 2, 16)
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: today)
    captured: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        captured["start"] = start
        captured["end"] = end
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)
    company.latest()
    assert captured["end"] == today
    # timedelta(days=89) + inclusive iteration = 90 日間
    assert captured["start"] == today - timedelta(days=89)


def test_latest_auto_completes_partial_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-7: 片方指定時に自動補完されること。"""
    from datetime import timedelta

    company = Company(edinet_code="E02144")
    today = DateType(2026, 2, 16)
    monkeypatch.setattr("edinet.models.company._today_jst", lambda: today)
    captured: dict[str, object] = {}

    def fake_documents(date=None, *, start=None, end=None, doc_type=None, edinet_code=None):
        captured["start"] = start
        captured["end"] = end
        return []

    monkeypatch.setattr("edinet.documents", fake_documents)

    # start のみ指定 → end = _today_jst()
    company.latest(start="2025-06-01")
    assert captured["end"] == today
    assert captured["start"] == "2025-06-01"

    # end のみ指定 → start = end - 89日 (inclusive 90日間)
    company.latest(end="2026-01-01")
    assert captured["end"] == DateType(2026, 1, 1)
    assert captured["start"] == DateType(2026, 1, 1) - timedelta(days=89)
