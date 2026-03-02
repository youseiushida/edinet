"""Large テスト: edinet.documents() の実 API スモークテスト。"""
import pytest

import edinet
from edinet.models.filing import Filing
from edinet.public_api import adocuments

from .conftest import LARGE_TEST_DATE


@pytest.mark.large
def test_documents_real_api_smoke() -> None:
    """実 API から書類一覧を取得でき、少なくとも 1 件あること。"""
    filings = edinet.documents(LARGE_TEST_DATE)
    assert isinstance(filings, list)
    assert len(filings) >= 1
    assert all(isinstance(f, Filing) for f in filings)


@pytest.mark.large
def test_documents_with_filter_smoke() -> None:
    """doc_type フィルタ付きで結果の型が正しいこと。"""
    filings = edinet.documents(LARGE_TEST_DATE, doc_type="120")
    assert isinstance(filings, list)
    assert all(isinstance(f, Filing) for f in filings)


@pytest.mark.large
async def test_adocuments_real_api_smoke() -> None:
    """実 API から adocuments() で書類一覧を取得でき、少なくとも 1 件あること。"""
    filings = await adocuments(LARGE_TEST_DATE)
    assert isinstance(filings, list)
    assert len(filings) >= 1
    assert all(isinstance(f, Filing) for f in filings)

    # クリーンアップ
    await edinet.aclose()
