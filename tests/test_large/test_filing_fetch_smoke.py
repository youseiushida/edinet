"""Large テスト: Filing.fetch() の実 API スモークテスト。"""
import pytest

import edinet

from .conftest import LARGE_TEST_DATE


@pytest.mark.large
def test_filing_fetch_returns_xbrl() -> None:
    """has_xbrl=True の Filing で fetch() が XBRL を返すこと。"""
    filings = edinet.documents(LARGE_TEST_DATE, doc_type="120")
    xbrl_filings = [f for f in filings if f.has_xbrl]
    if not xbrl_filings:
        pytest.skip("No XBRL filings found for the test date")

    target = xbrl_filings[0]
    path, data = target.fetch()
    assert path.endswith(".xbrl")
    assert len(data) > 0
