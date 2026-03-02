"""名前空間分類機能のテスト。"""

import pytest

from edinet.xbrl._namespaces import (
    EDINET_BASE,
    EDINET_TAXONOMY_BASE,
    NS_ISO4217,
    NS_LINK,
    NS_NONNUM,
    NS_NUM,
    NS_XBRLDI,
    NS_XBRLDT,
    NS_XBRLI,
    NS_XSI,
    NS_XLINK,
    NS_XML,
    NamespaceCategory,
    classify_namespace,
    extract_taxonomy_module,
    extract_taxonomy_version,
    is_filer_namespace,
    is_standard_taxonomy,
)


@pytest.fixture(autouse=True)
def _clear_namespace_cache():
    """テスト間のキャッシュ汚染を防ぐ。"""
    classify_namespace.cache_clear()
    yield
    classify_namespace.cache_clear()


# ============================================================
# 既存定数の不変性テスト
# ============================================================


def test_existing_constants_unchanged():
    """既存の 6 定数が変更されていないことを確認する。"""
    assert NS_XBRLI == "http://www.xbrl.org/2003/instance"
    assert NS_XBRLDI == "http://xbrl.org/2006/xbrldi"
    assert NS_LINK == "http://www.xbrl.org/2003/linkbase"
    assert NS_XLINK == "http://www.w3.org/1999/xlink"
    assert NS_XSI == "http://www.w3.org/2001/XMLSchema-instance"
    assert NS_XML == "http://www.w3.org/XML/1998/namespace"


def test_new_constants():
    """追加定数が正しい値を持つことを確認する。"""
    assert NS_ISO4217 == "http://www.xbrl.org/2003/iso4217"
    assert NS_XBRLDT == "http://xbrl.org/2005/xbrldt"
    assert NS_NUM == "http://www.xbrl.org/dtr/type/numeric"
    assert NS_NONNUM == "http://www.xbrl.org/dtr/type/non-numeric"
    assert EDINET_BASE == "http://disclosure.edinet-fsa.go.jp/"
    assert EDINET_TAXONOMY_BASE == "http://disclosure.edinet-fsa.go.jp/taxonomy/"


# ============================================================
# 標準タクソノミの分類テスト
# ============================================================


@pytest.mark.parametrize(
    "uri,expected_module,expected_group,expected_version",
    [
        # J-GAAP 財務諸表
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor",
            "jppfs_cor",
            "jppfs",
            "2025-11-01",
        ),
        # 有報固有
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor",
            "jpcrp_cor",
            "jpcrp",
            "2025-11-01",
        ),
        # DEI（バージョン固定）
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor",
            "jpdei_cor",
            "jpdei",
            "2013-08-31",
        ),
        # IFRS
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor",
            "jpigp_cor",
            "jpigp",
            "2025-11-01",
        ),
        # 旧バージョン（H-3: バージョン横断テスト）
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor",
            "jppfs_cor",
            "jppfs",
            "2024-11-01",
        ),
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2022-11-01/jppfs_cor",
            "jppfs_cor",
            "jppfs",
            "2022-11-01",
        ),
        # 大量保有報告書
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jplvh/2025-11-01/jplvh_cor",
            "jplvh_cor",
            "jplvh",
            "2025-11-01",
        ),
        # 公開買付
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jptoi/2025-11-01/jptoi_cor",
            "jptoi_cor",
            "jptoi",
            "2025-11-01",
        ),
        # 内部統制
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpctl/2025-11-01/jpctl_cor",
            "jpctl_cor",
            "jpctl",
            "2025-11-01",
        ),
        # 特定有価証券
        (
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpsps/2025-11-01/jpsps_cor",
            "jpsps_cor",
            "jpsps",
            "2025-11-01",
        ),
    ],
)
def test_standard_taxonomy_classification(
    uri, expected_module, expected_group, expected_version
):
    """標準タクソノミ URI が正しく分類されることを確認する。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.STANDARD_TAXONOMY
    assert info.is_standard is True
    assert info.module_name == expected_module
    assert info.module_group == expected_group
    assert info.taxonomy_version == expected_version


# ============================================================
# 提出者別タクソノミの分類テスト
# ============================================================


@pytest.mark.parametrize(
    "uri,expected_edinet_code",
    [
        # J-GAAP サンプル
        (
            "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/X99001-000/2026-03-31/01/2026-06-12",
            "X99001",
        ),
        # IFRS サンプル
        (
            "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/X99002-000/2026-03-31/01/2026-06-12",
            "X99002",
        ),
        # トヨタ実データ
        (
            "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18",
            "E02144",
        ),
    ],
)
def test_filer_taxonomy_classification(uri, expected_edinet_code):
    """提出者別タクソノミ URI が正しく分類されることを確認する。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.FILER_TAXONOMY
    assert info.is_standard is False
    assert info.edinet_code == expected_edinet_code


def test_filer_taxonomy_without_edinet_code():
    """提出者別 URI だが EDINET コードが抽出できないケース。"""
    uri = "http://disclosure.edinet-fsa.go.jp/some-short-path"
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.FILER_TAXONOMY
    assert info.is_standard is False
    assert info.edinet_code is None


# ============================================================
# XBRL インフラ名前空間の分類テスト
# ============================================================


@pytest.mark.parametrize(
    "uri",
    [
        NS_XBRLI,
        NS_XBRLDI,
        NS_LINK,
        NS_XLINK,
        NS_XBRLDT,
    ],
)
def test_xbrl_infrastructure_classification(uri):
    """XBRL インフラ名前空間が正しく分類されることを確認する。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.XBRL_INFRASTRUCTURE
    assert info.is_standard is False


# ============================================================
# その他の名前空間の分類テスト
# ============================================================


@pytest.mark.parametrize(
    "uri",
    [
        NS_XSI,  # W3C 汎用名前空間（XBRL 固有ではない）
        NS_XML,  # W3C 汎用名前空間（XBRL 固有ではない）
        NS_ISO4217,  # 通貨コード
        NS_NUM,  # XBRL Data Type Registry: 数値型
        NS_NONNUM,  # XBRL Data Type Registry: 非数値型
        "http://example.com/unknown",
        "",
    ],
)
def test_other_namespace_classification(uri):
    """OTHER に分類される名前空間を確認する。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.OTHER
    assert info.is_standard is False


# ============================================================
# 標準タクソノミのフォールバック分類テスト
# ============================================================


@pytest.mark.parametrize(
    "uri",
    [
        "http://disclosure.edinet-fsa.go.jp/taxonomy/unknown/format",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/invalid-date/jppfs_cor",
        "http://disclosure.edinet-fsa.go.jp/taxonomy/",
    ],
)
def test_standard_taxonomy_unknown_format(uri):
    """EDINET_TAXONOMY_BASE で始まるが既知パターンに合わない URI は STANDARD_TAXONOMY に分類される。"""
    info = classify_namespace(uri)
    assert info.category == NamespaceCategory.STANDARD_TAXONOMY
    assert info.is_standard is True
    assert info.module_name is None
    assert info.module_group is None
    assert info.taxonomy_version is None


# ============================================================
# 便利関数のテスト
# ============================================================


def test_is_standard_taxonomy():
    """is_standard_taxonomy が正しい結果を返すことを確認する。"""
    assert (
        is_standard_taxonomy(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
        )
        is True
    )
    assert is_standard_taxonomy(NS_XBRLI) is False
    assert is_standard_taxonomy("http://example.com/foo") is False


def test_is_filer_namespace():
    """is_filer_namespace が正しい結果を返すことを確認する。"""
    assert (
        is_filer_namespace(
            "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18"
        )
        is True
    )
    assert (
        is_filer_namespace(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
        )
        is False
    )


def test_extract_taxonomy_module():
    """extract_taxonomy_module が正しいモジュール名を返すことを確認する。"""
    assert (
        extract_taxonomy_module(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
        )
        == "jppfs_cor"
    )
    assert (
        extract_taxonomy_module(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor"
        )
        == "jpigp_cor"
    )
    assert extract_taxonomy_module(NS_XBRLI) is None


def test_extract_taxonomy_version():
    """extract_taxonomy_version が正しいバージョンを返すことを確認する。"""
    assert (
        extract_taxonomy_version(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
        )
        == "2025-11-01"
    )
    assert (
        extract_taxonomy_version(
            "http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor"
        )
        == "2013-08-31"
    )
    assert extract_taxonomy_version(NS_XBRLI) is None


# ============================================================
# バージョン横断テスト（H-3 の要件）
# ============================================================


@pytest.mark.parametrize(
    "version",
    [
        "2020-11-01",
        "2021-11-01",
        "2022-11-01",
        "2023-12-01",
        "2024-11-01",
        "2025-11-01",
    ],
)
def test_same_module_different_versions(version):
    """同一モジュールの異なるバージョンが同一モジュール名を返すことを確認する。"""
    uri = f"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/{version}/jppfs_cor"
    assert extract_taxonomy_module(uri) == "jppfs_cor"
    assert extract_taxonomy_version(uri) == version
    assert is_standard_taxonomy(uri) is True


# ============================================================
# キャッシュの動作テスト
# ============================================================


def test_classify_returns_identical_object_for_same_uri():
    """同一 URI に対する呼び出しが同一オブジェクトを返すことを確認する。

    frozen dataclass + lru_cache の組み合わせによる意図的な設計保証。
    """
    uri = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    result1 = classify_namespace(uri)
    result2 = classify_namespace(uri)
    assert result1 == result2  # 等値性
    assert result1 is result2  # 同一オブジェクト（キャッシュヒット）


def test_namespace_info_is_frozen():
    """NamespaceInfo が frozen dataclass であることを確認する。"""
    info = classify_namespace(
        "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
    )
    with pytest.raises(AttributeError):
        info.uri = "modified"  # type: ignore[misc]
