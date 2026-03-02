"""_linkbase_utils モジュールのテスト。"""

from __future__ import annotations

import pytest

from edinet.xbrl._linkbase_utils import (
    ROLE_LABEL,
    ROLE_NEGATED_LABEL,
    ROLE_PERIOD_END_LABEL,
    ROLE_PERIOD_START_LABEL,
    ROLE_TERSE_LABEL,
    ROLE_TOTAL_LABEL,
    ROLE_VERBOSE_LABEL,
    extract_concept_from_href,
    split_fragment_prefix_local,
)


# ============================================================
# extract_concept_from_href
# ============================================================


class TestExtractConceptFromHref:
    """extract_concept_from_href のテスト群。"""

    def test_standard_taxonomy(self) -> None:
        """標準タクソノミの href から concept を抽出できる。"""
        href = "jppfs_cor_2025-11-01.xsd#jppfs_cor_CashAndDeposits"
        assert extract_concept_from_href(href) == "CashAndDeposits"

    def test_filer_taxonomy_strategy2(self) -> None:
        """提出者タクソノミの href から Strategy 2 で concept を抽出できる。"""
        href = "jpcrp030000-asr-001_X99001-000.xsd#X99001-000_ProvisionForBonuses"
        assert extract_concept_from_href(href) == "ProvisionForBonuses"

    def test_bare_fragment(self) -> None:
        """bare fragment（# 以降のみ、大文字始まり）を concept として返す。"""
        href = "#BareConceptHeading"
        assert extract_concept_from_href(href) == "BareConceptHeading"

    def test_no_fragment_returns_none(self) -> None:
        """フラグメントなしの場合は None を返す。"""
        href = "test.xsd"
        assert extract_concept_from_href(href) is None

    def test_empty_fragment_returns_none(self) -> None:
        """空フラグメントの場合は None を返す。"""
        href = "test.xsd#"
        assert extract_concept_from_href(href) is None

    def test_all_lowercase_fragment(self) -> None:
        """全小文字フラグメントはフラグメント全体を返す。"""
        href = "test.xsd#alllowercase"
        assert extract_concept_from_href(href) == "alllowercase"


# ============================================================
# split_fragment_prefix_local
# ============================================================


class TestSplitFragmentPrefixLocal:
    """split_fragment_prefix_local のテスト群。"""

    def test_standard_taxonomy_fragment(self) -> None:
        """標準タクソノミのフラグメントを分離できる。"""
        result = split_fragment_prefix_local("jppfs_cor_CashAndDeposits")
        assert result == ("jppfs_cor", "CashAndDeposits")

    def test_filer_taxonomy_fragment(self) -> None:
        """提出者タクソノミのフラグメントを分離できる。"""
        result = split_fragment_prefix_local(
            "jpcrp030000-asr_E02144-000_CustomExpense"
        )
        assert result == ("jpcrp030000-asr_E02144-000", "CustomExpense")

    def test_unsplittable_returns_none(self) -> None:
        """分割不可なフラグメントの場合は None を返す。"""
        assert split_fragment_prefix_local("alllowercase") is None


# ============================================================
# ラベルロール定数
# ============================================================


class TestRoleConstants:
    """ラベルロール定数の値検証。"""

    @pytest.mark.parametrize(
        ("constant", "expected"),
        [
            (ROLE_LABEL, "http://www.xbrl.org/2003/role/label"),
            (ROLE_TOTAL_LABEL, "http://www.xbrl.org/2003/role/totalLabel"),
            (ROLE_VERBOSE_LABEL, "http://www.xbrl.org/2003/role/verboseLabel"),
            (ROLE_TERSE_LABEL, "http://www.xbrl.org/2003/role/terseLabel"),
            (
                ROLE_PERIOD_START_LABEL,
                "http://www.xbrl.org/2003/role/periodStartLabel",
            ),
            (
                ROLE_PERIOD_END_LABEL,
                "http://www.xbrl.org/2003/role/periodEndLabel",
            ),
            (
                ROLE_NEGATED_LABEL,
                "http://www.xbrl.org/2003/role/negatedLabel",
            ),
        ],
    )
    def test_role_value(self, constant: str, expected: str) -> None:
        """ラベルロール定数が正しい URI 値を持つ。"""
        assert constant == expected
