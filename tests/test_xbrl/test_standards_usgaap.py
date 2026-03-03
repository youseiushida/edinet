"""US-GAAP 要約指標抽出モジュールのテスト。

Detroit 派（古典派）テスト: モック不使用、公開 API のみテスト。
"""

from __future__ import annotations

import datetime
import os
import re
import warnings
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from edinet.exceptions import EdinetWarning
from edinet.xbrl.contexts import (
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.parser import RawFact
from edinet.financial.standards.usgaap import (
    canonical_key,
    extract_usgaap_summary,
    get_jgaap_mapping,
    get_usgaap_concept_names,
    is_usgaap_element,
    reverse_lookup,
)

# ---------------------------------------------------------------------------
# テスト用定数
# ---------------------------------------------------------------------------

_JPCRP_NS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)
_JPPFS_NS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)

_CUR_DURATION = DurationPeriod(
    start_date=datetime.date(2025, 4, 1),
    end_date=datetime.date(2026, 3, 31),
)
_PREV_DURATION = DurationPeriod(
    start_date=datetime.date(2024, 4, 1),
    end_date=datetime.date(2025, 3, 31),
)
_CUR_INSTANT = InstantPeriod(instant=datetime.date(2026, 3, 31))

# ---------------------------------------------------------------------------
# テストヘルパー
# ---------------------------------------------------------------------------


def _make_usgaap_fact(
    local_name: str,
    value_raw: str | None = None,
    *,
    context_ref: str = "CurrentYearDuration",
    unit_ref: str | None = "JPY",
    is_nil: bool = False,
    order: int = 0,
) -> RawFact:
    """US-GAAP テスト用の RawFact を簡便に構築する。"""
    return RawFact(
        concept_qname=f"{{{_JPCRP_NS}}}{local_name}",
        namespace_uri=_JPCRP_NS,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=order,
    )


def _make_jgaap_fact(
    local_name: str,
    value_raw: str | None = None,
) -> RawFact:
    """J-GAAP テスト用の RawFact（US-GAAP でないことの検証用）。"""
    return RawFact(
        concept_qname=f"{{{_JPPFS_NS}}}{local_name}",
        namespace_uri=_JPPFS_NS,
        local_name=local_name,
        context_ref="CurrentYearDuration",
        unit_ref="JPY",
        decimals=None,
        value_raw=value_raw,
        is_nil=False,
        fact_id=None,
        xml_lang=None,
        source_line=None,
        order=0,
    )


def _make_ctx(
    context_id: str,
    period: DurationPeriod | InstantPeriod,
) -> StructuredContext:
    """テスト用の StructuredContext を構築する。"""
    return StructuredContext(
        context_id=context_id,
        period=period,
        entity_id="E99999",
        dimensions=(),
        source_line=None,
    )


def _make_ctx_map() -> dict[str, StructuredContext]:
    """標準的なコンテキストマップを返す。"""
    return {
        "CurrentYearDuration": _make_ctx("CurrentYearDuration", _CUR_DURATION),
        "PriorYearDuration": _make_ctx("PriorYearDuration", _PREV_DURATION),
        "CurrentYearInstant": _make_ctx("CurrentYearInstant", _CUR_INSTANT),
    }


# ---------------------------------------------------------------------------
# 全 19 概念名リスト
# ---------------------------------------------------------------------------

_ALL_SUMMARY_CONCEPTS = [
    ("revenue", "RevenuesUSGAAPSummaryOfBusinessResults"),
    ("operating_income", "OperatingIncomeLossUSGAAPSummaryOfBusinessResults"),
    ("income_before_tax", "ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults"),
    (
        "net_income_parent",
        "NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    ),
    (
        "comprehensive_income",
        "ComprehensiveIncomeUSGAAPSummaryOfBusinessResults",
    ),
    (
        "comprehensive_income_parent",
        "ComprehensiveIncomeAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    ),
    (
        "shareholders_equity",
        "EquityAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults",
    ),
    (
        "net_assets",
        "EquityIncludingPortionAttributableToNonControllingInterestUSGAAPSummaryOfBusinessResults",
    ),
    ("total_assets", "TotalAssetsUSGAAPSummaryOfBusinessResults"),
    ("equity_ratio", "EquityToAssetRatioUSGAAPSummaryOfBusinessResults"),
    ("roe", "RateOfReturnOnEquityUSGAAPSummaryOfBusinessResults"),
    ("per", "PriceEarningsRatioUSGAAPSummaryOfBusinessResults"),
    (
        "operating_cf",
        "CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults",
    ),
    (
        "investing_cf",
        "CashFlowsFromUsedInInvestingActivitiesUSGAAPSummaryOfBusinessResults",
    ),
    (
        "financing_cf",
        "CashFlowsFromUsedInFinancingActivitiesUSGAAPSummaryOfBusinessResults",
    ),
    (
        "cash_end",
        "CashAndCashEquivalentsUSGAAPSummaryOfBusinessResults",
    ),
    ("eps", "BasicEarningsLossPerShareUSGAAPSummaryOfBusinessResults"),
    (
        "eps_diluted",
        "DilutedEarningsLossPerShareUSGAAPSummaryOfBusinessResults",
    ),
    (
        "bps",
        "EquityAttributableToOwnersOfParentPerShareUSGAAPSummaryOfBusinessResults",
    ),
]


# =========================================================================
# P0 テスト — extract_usgaap_summary のメインフロー
# =========================================================================


class TestExtractMainFlow:
    """extract_usgaap_summary のメインフローをテストする。"""

    def test_extract_revenue(self) -> None:
        """T1: SummaryOfBusinessResults の売上高が正規化キー "revenue" で抽出される。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000000",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 1
        item = summary.summary_items[0]
        assert item.key == "revenue"
        assert item.value == Decimal("1000000")

    def test_extract_all_summary_items(self) -> None:
        """T2: 全 19 個の SummaryOfBusinessResults 要素が抽出される。"""
        facts = tuple(
            _make_usgaap_fact(concept, "100")
            for _, concept in _ALL_SUMMARY_CONCEPTS
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 19

    def test_summary_item_has_correct_key(self) -> None:
        """T3: 各項目の正規化キーが定義通りである。"""
        facts = tuple(
            _make_usgaap_fact(concept, "100")
            for _, concept in _ALL_SUMMARY_CONCEPTS
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        extracted_keys = {item.key for item in summary.summary_items}
        expected_keys = {key for key, _ in _ALL_SUMMARY_CONCEPTS}
        assert extracted_keys == expected_keys

    def test_summary_item_value_is_decimal(self) -> None:
        """T4: 数値 Fact の value が Decimal である。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "12345678",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert isinstance(summary.summary_items[0].value, Decimal)
        assert summary.summary_items[0].value == Decimal("12345678")

    def test_summary_item_nil_value_is_none(self) -> None:
        """T5: nil Fact の value が None である。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                None,
                is_nil=True,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.summary_items[0].value is None

    def test_text_block_extracted(self) -> None:
        """T6: TextBlock 要素が抽出される。"""
        facts = (
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<table>...</table>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.text_blocks) == 1
        assert summary.text_blocks[0].html_content == "<table>...</table>"

    def test_text_block_statement_hint(self) -> None:
        """T7: TextBlock の statement_hint が正しく推定される。"""
        test_cases = [
            # --- 年次 ---
            ("ConsolidatedBalanceSheetUSGAAPTextBlock", "balance_sheet"),
            (
                "ConsolidatedStatementOfIncomeUSGAAPTextBlock",
                "income_statement",
            ),
            (
                "ConsolidatedStatementOfCashFlowsUSGAAPTextBlock",
                "cash_flow_statement",
            ),
            (
                "ConsolidatedStatementOfEquityUSGAAPTextBlock",
                "statement_of_changes_in_equity",
            ),
            (
                "ConsolidatedStatementOfComprehensiveIncomeUSGAAPTextBlock",
                "comprehensive_income",
            ),
            (
                "ConsolidatedStatementOfComprehensiveIncomeSingleStatementUSGAAPTextBlock",
                "comprehensive_income_single",
            ),
            (
                "NotesToConsolidatedFinancialStatementsUSGAAPTextBlock",
                "notes",
            ),
            # --- 半期（命名規則逆転パターン含む） ---
            (
                "SemiAnnualConsolidatedBalanceSheetUSGAAPTextBlock",
                "balance_sheet",
            ),
            (
                "SemiAnnualConsolidatedStatementOfIncomeUSGAAPTextBlock",
                "income_statement",
            ),
            (
                "SemiAnnualConsolidatedStatementOfCashFlowsUSGAAPTextBlock",
                "cash_flow_statement",
            ),
            (
                "SemiAnnualConsolidatedStatementOfComprehensiveIncomeUSGAAPTextBlock",
                "comprehensive_income",
            ),
            (
                "SemiAnnualConsolidatedStatementOfComprehensiveIncomeSingleStatementUSGAAPTextBlock",
                "comprehensive_income_single",
            ),
            # NOTE: 半期 SS は "ConsolidatedSemiAnnual..."（命名規則逆転）
            (
                "ConsolidatedSemiAnnualStatementOfEquityUSGAAPTextBlock",
                "statement_of_changes_in_equity",
            ),
            (
                "NotesToSemiAnnualConsolidatedFinancialStatementsUSGAAPTextBlock",
                "notes",
            ),
        ]
        for concept, expected_hint in test_cases:
            facts = (
                _make_usgaap_fact(concept, "<html>...</html>", unit_ref=None),
            )
            ctx_map = _make_ctx_map()
            summary = extract_usgaap_summary(facts, ctx_map)
            assert summary.text_blocks[0].statement_hint == expected_hint, (
                f"{concept} -> expected {expected_hint}"
            )

    def test_text_block_semi_annual_flag(self) -> None:
        """T8: TextBlock の is_semi_annual フラグが正しい。"""
        annual = _make_usgaap_fact(
            "ConsolidatedBalanceSheetUSGAAPTextBlock",
            "<html>annual</html>",
            unit_ref=None,
        )
        semi = _make_usgaap_fact(
            "SemiAnnualConsolidatedBalanceSheetUSGAAPTextBlock",
            "<html>semi</html>",
            unit_ref=None,
        )
        facts = (annual, semi)
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        blocks = {b.concept: b for b in summary.text_blocks}
        assert (
            blocks["ConsolidatedBalanceSheetUSGAAPTextBlock"].is_semi_annual
            is False
        )
        assert (
            blocks[
                "SemiAnnualConsolidatedBalanceSheetUSGAAPTextBlock"
            ].is_semi_annual
            is True
        )

    def test_description_extracted(self) -> None:
        """T9: 米国基準適用の説明文が抽出される。"""
        desc_concept = (
            "DescriptionOfFactThatConsolidatedFinancialStatements"
            "HaveBeenPreparedInAccordanceWithUSGAAPFinancialInformation"
        )
        facts = (
            _make_usgaap_fact(
                desc_concept,
                "米国基準に基づいています。",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.description == "米国基準に基づいています。"

    def test_total_elements_count(self) -> None:
        """T10: total_usgaap_elements が正しい。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "100"
            ),
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<html/>",
                unit_ref=None,
            ),
            _make_usgaap_fact(
                "TotalAssetsUSGAAPSummaryOfBusinessResults", "200"
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.total_usgaap_elements == 3

    def test_empty_facts_returns_empty_summary(self) -> None:
        """T11: 空の facts で空の USGAAPSummary が返る。"""
        summary = extract_usgaap_summary((), {})

        assert len(summary.summary_items) == 0
        assert len(summary.text_blocks) == 0
        assert summary.description is None
        assert summary.total_usgaap_elements == 0

    def test_jgaap_facts_returns_empty_summary(self) -> None:
        """T12: J-GAAP の facts で空の USGAAPSummary が返る。"""
        facts = (
            _make_jgaap_fact("NetSales", "1000000"),
            _make_jgaap_fact("OperatingIncome", "500000"),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 0
        assert summary.total_usgaap_elements == 0


# =========================================================================
# P0 テスト — USGAAPSummary のメソッド
# =========================================================================


class TestUSGAAPSummaryMethods:
    """USGAAPSummary のメソッドをテストする。"""

    def test_get_item_by_key(self) -> None:
        """T13: get_item() で正規化キーにより項目を取得できる。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "5000"
            ),
            _make_usgaap_fact(
                "TotalAssetsUSGAAPSummaryOfBusinessResults",
                "9000",
                context_ref="CurrentYearInstant",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        rev = summary.get_item("revenue")
        assert rev is not None
        assert rev.value == Decimal("5000")

        ta = summary.get_item("total_assets")
        assert ta is not None
        assert ta.value == Decimal("9000")

    def test_get_item_returns_none_for_missing_key(self) -> None:
        """T14: 存在しないキーで None が返る。"""
        summary = extract_usgaap_summary((), {})

        assert summary.get_item("nonexistent") is None

    def test_get_items_by_period(self) -> None:
        """T15: get_items_by_period() で期間ごとにフィルタできる。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="CurrentYearDuration",
            ),
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "800",
                context_ref="PriorYearDuration",
            ),
            _make_usgaap_fact(
                "TotalAssetsUSGAAPSummaryOfBusinessResults",
                "5000",
                context_ref="CurrentYearDuration",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        cur_items = summary.get_items_by_period(_CUR_DURATION)
        assert len(cur_items) == 2

        prev_items = summary.get_items_by_period(_PREV_DURATION)
        assert len(prev_items) == 1
        assert prev_items[0].key == "revenue"

    def test_available_periods(self) -> None:
        """T16: available_periods が新しい順にソートされている。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="CurrentYearDuration",
            ),
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "800",
                context_ref="PriorYearDuration",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        periods = summary.available_periods
        assert len(periods) == 2
        assert periods[0] == _CUR_DURATION
        assert periods[1] == _PREV_DURATION

    def test_to_dict_format(self) -> None:
        """T17: to_dict() が正しい辞書形式を返す。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "1234567"
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        result = summary.to_dict()
        assert len(result) == 1
        d = result[0]
        assert d["key"] == "revenue"
        assert d["label_ja"] == "売上高"
        assert d["value"] == "1234567"
        assert d["unit"] == "JPY"
        assert d["concept"] == "RevenuesUSGAAPSummaryOfBusinessResults"

    def test_to_dict_excludes_text_blocks(self) -> None:
        """T18: to_dict() に TextBlock が含まれない。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "100"
            ),
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<table/>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.text_blocks) == 1
        result = summary.to_dict()
        assert len(result) == 1
        assert result[0]["key"] == "revenue"

    def test_repr(self) -> None:
        """T19: __repr__ が要素数を含む。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "100"
            ),
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<table/>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        r = repr(summary)
        assert "summary_items=1" in r
        assert "text_blocks=1" in r
        assert "total_elements=2" in r


# =========================================================================
# P0 テスト — is_usgaap_element / ユーティリティ
# =========================================================================


class TestIsUSGAAPElement:
    """is_usgaap_element のテスト。"""

    def test_is_usgaap_element_true(self) -> None:
        """T20: US-GAAP 要素名で True。"""
        assert is_usgaap_element(
            "RevenuesUSGAAPSummaryOfBusinessResults"
        ) is True
        assert is_usgaap_element(
            "ConsolidatedBalanceSheetUSGAAPTextBlock"
        ) is True

    def test_is_usgaap_element_false_for_jgaap(self) -> None:
        """T21: J-GAAP 要素名で False。"""
        assert is_usgaap_element("NetSales") is False
        assert is_usgaap_element("OperatingIncome") is False

    def test_is_usgaap_element_false_for_empty(self) -> None:
        """T22: 空文字列で False。"""
        assert is_usgaap_element("") is False


# =========================================================================
# P0 テスト — get_jgaap_mapping / get_usgaap_concept_names
# =========================================================================


class TestMappingAndConceptNames:
    """get_jgaap_mapping / get_usgaap_concept_names のテスト。"""

    def test_jgaap_mapping_revenue(self) -> None:
        """T23: "revenue" → "NetSales"。"""
        mapping = get_jgaap_mapping()
        assert mapping["revenue"] == "NetSales"

    def test_jgaap_mapping_none_for_ratio(self) -> None:
        """T24: "per" → None。"""
        mapping = get_jgaap_mapping()
        assert mapping["per"] is None

    def test_jgaap_mapping_completeness(self) -> None:
        """T25: 全 19 キーが辞書に含まれる。"""
        mapping = get_jgaap_mapping()
        expected_keys = {key for key, _ in _ALL_SUMMARY_CONCEPTS}
        assert set(mapping.keys()) == expected_keys
        assert len(mapping) == 19

    def test_concept_names_count(self) -> None:
        """T26: 19 個の concept 名が返る。"""
        names = get_usgaap_concept_names()
        assert len(names) == 19

    def test_concept_names_frozenset(self) -> None:
        """T27: 戻り値が frozenset である。"""
        names = get_usgaap_concept_names()
        assert isinstance(names, frozenset)

    def test_concept_names_contains_revenues(self) -> None:
        """T28: "RevenuesUSGAAPSummaryOfBusinessResults" が含まれる。"""
        names = get_usgaap_concept_names()
        assert "RevenuesUSGAAPSummaryOfBusinessResults" in names


# =========================================================================
# P0 テスト — contexts 引数の動作
# =========================================================================


class TestContextsIntegration:
    """contexts 引数の動作テスト。"""

    def test_extract_with_contexts_dict(self) -> None:
        """T29: contexts 引数で StructuredContext の period が使われる。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="CurrentYearDuration",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.summary_items[0].period == _CUR_DURATION

    def test_extract_skips_unknown_context_ref(self) -> None:
        """T30: contexts 辞書にない context_ref の fact がスキップされ EdinetWarning が発出される。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="UnknownContext",
            ),
        )
        ctx_map = _make_ctx_map()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 0
        edinet_warnings = [
            x for x in w if issubclass(x.category, EdinetWarning)
        ]
        assert len(edinet_warnings) >= 1
        assert "UnknownContext" in str(edinet_warnings[0].message)


# =========================================================================
# P1 テスト — エッジケース
# =========================================================================


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_multiple_periods_summary(self) -> None:
        """T31: 当期・前期の SummaryOfBusinessResults が両方抽出される。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="CurrentYearDuration",
            ),
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "800",
                context_ref="PriorYearDuration",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 2
        values = {item.value for item in summary.summary_items}
        assert values == {Decimal("1000"), Decimal("800")}

    def test_text_block_unknown_type(self) -> None:
        """T32: 未知の TextBlock パターンで statement_hint=None。"""
        facts = (
            _make_usgaap_fact(
                "SomethingNewUSGAAPTextBlock",
                "<html/>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.text_blocks) == 1
        assert summary.text_blocks[0].statement_hint is None

    def test_frozen_dataclass(self) -> None:
        """T33: USGAAPSummary, USGAAPSummaryItem, USGAAPTextBlockItem が frozen である。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "100"
            ),
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<html/>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        with pytest.raises(FrozenInstanceError):
            summary.total_usgaap_elements = 999  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            summary.summary_items[0].key = "x"  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            summary.text_blocks[0].concept = "x"  # type: ignore[misc]

    def test_mixed_usgaap_and_jgaap_facts(self) -> None:
        """T34: US-GAAP と J-GAAP の facts が混在しても US-GAAP のみ抽出される。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults", "1000"
            ),
            _make_jgaap_fact("NetSales", "2000"),
            _make_usgaap_fact(
                "TotalAssetsUSGAAPSummaryOfBusinessResults",
                "5000",
                context_ref="CurrentYearInstant",
            ),
            _make_jgaap_fact("Assets", "6000"),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert len(summary.summary_items) == 2
        keys = {item.key for item in summary.summary_items}
        assert keys == {"revenue", "total_assets"}

    def test_text_block_html_content_preserved(self) -> None:
        """T35: HTML タグを含む TextBlock の内容がそのまま保持される。"""
        html = '<table class="report"><tr><td>売上高</td><td>1,000,000</td></tr></table>'
        facts = (
            _make_usgaap_fact(
                "ConsolidatedStatementOfIncomeUSGAAPTextBlock",
                html,
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.text_blocks[0].html_content == html

    def test_text_block_annual_vs_semi_annual(self) -> None:
        """T36: 年次 BS と半期 BS の TextBlock が is_semi_annual で区別される。"""
        facts = (
            _make_usgaap_fact(
                "ConsolidatedBalanceSheetUSGAAPTextBlock",
                "<annual/>",
                unit_ref=None,
            ),
            _make_usgaap_fact(
                "SemiAnnualConsolidatedBalanceSheetUSGAAPTextBlock",
                "<semi/>",
                unit_ref=None,
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        blocks = sorted(summary.text_blocks, key=lambda b: b.is_semi_annual)
        assert blocks[0].is_semi_annual is False
        assert blocks[0].statement_hint == "balance_sheet"
        assert blocks[1].is_semi_annual is True
        assert blocks[1].statement_hint == "balance_sheet"

    def test_get_item_prefers_latest_period(self) -> None:
        """T37: get_item() が最新期間を優先する。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "800",
                context_ref="PriorYearDuration",
            ),
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "1000",
                context_ref="CurrentYearDuration",
            ),
        )
        ctx_map = _make_ctx_map()
        summary = extract_usgaap_summary(facts, ctx_map)

        rev = summary.get_item("revenue")
        assert rev is not None
        assert rev.value == Decimal("1000")
        assert rev.period == _CUR_DURATION

    def test_parse_value_warning_on_non_numeric(self) -> None:
        """T38: unit_ref がある fact の値が非数値の場合に EdinetWarning が発出される。"""
        facts = (
            _make_usgaap_fact(
                "RevenuesUSGAAPSummaryOfBusinessResults",
                "not-a-number",
                unit_ref="JPY",
            ),
        )
        ctx_map = _make_ctx_map()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            summary = extract_usgaap_summary(facts, ctx_map)

        assert summary.summary_items[0].value == "not-a-number"
        edinet_warnings = [
            x for x in w if issubclass(x.category, EdinetWarning)
        ]
        assert len(edinet_warnings) >= 1
        assert "Decimal に変換できません" in str(edinet_warnings[0].message)


# ===========================================================================
# タクソノミ実在検証（EDINET_TAXONOMY_ROOT 必須）
# ===========================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_xsd_concepts_jpcrp(taxonomy_root: str) -> frozenset[str]:
    """jpcrp_cor の XSD から全 concept 名を抽出する。"""
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    target = Path(taxonomy_root) / "taxonomy" / "jpcrp"
    if not target.exists():
        return frozenset()
    for xsd_file in target.rglob("*.xsd"):
        for line in xsd_file.read_text(encoding="utf-8").splitlines():
            m = pattern.search(line)
            if m:
                concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.medium
@pytest.mark.integration
class TestTaxonomyExistence:
    """US-GAAP concept がタクソノミ XSD に実在するか検証する。

    ハルシネーション防止のための品質ゲート。
    US-GAAP concept は jpcrp_cor に定義されている。
    """

    @pytest.fixture(scope="class")
    def xsd_concepts(self) -> frozenset[str]:
        """jpcrp_cor XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts_jpcrp(_TAXONOMY_ROOT)

    def test_all_usgaap_concepts_exist_in_taxonomy(
        self,
        xsd_concepts: frozenset[str],
    ) -> None:
        """全 US-GAAP concept が jpcrp_cor XSD に実在する。"""
        from edinet.financial.standards.usgaap import get_usgaap_concept_names

        missing = [
            name for name in get_usgaap_concept_names()
            if name not in xsd_concepts
        ]
        assert not missing, (
            f"jpcrp_cor XSD に存在しない US-GAAP concept: {missing}"
        )


# =========================================================================
# canonical_key / reverse_lookup テスト
# =========================================================================


class TestCanonicalKeyAndReverseLookup:
    """canonical_key() / reverse_lookup() のテスト。"""

    def test_canonical_key_returns_key(self) -> None:
        """concept ローカル名から正規化キーが返る。"""
        assert canonical_key("RevenuesUSGAAPSummaryOfBusinessResults") == "revenue"

    def test_canonical_key_operating_income(self) -> None:
        """営業利益の正規化キーが返る。"""
        result = canonical_key(
            "OperatingIncomeLossUSGAAPSummaryOfBusinessResults"
        )
        assert result == "operating_income"

    def test_canonical_key_unknown_returns_none(self) -> None:
        """未登録 concept では None が返る。"""
        assert canonical_key("UnknownConcept") is None

    def test_reverse_lookup_revenue(self) -> None:
        """正規化キーから概念定義が取得できる。"""
        d = reverse_lookup("revenue")
        assert d is not None
        assert d.concept_local_name == "RevenuesUSGAAPSummaryOfBusinessResults"
        assert d.label_ja == "売上高"
        assert d.label_en == "Revenue"

    def test_reverse_lookup_unknown_returns_none(self) -> None:
        """未登録キーでは None が返る。"""
        assert reverse_lookup("unknown_key") is None

    def test_label_en_on_all_concepts(self) -> None:
        """全 19 概念に label_en が設定されている。"""
        mapping = get_jgaap_mapping()
        for key in mapping:
            d = reverse_lookup(key)
            assert d is not None, f"reverse_lookup({key!r}) が None"
            assert d.label_en, f"{key} の label_en が空"
            # 英語ラベルは大文字始まり（canonical key と区別）
            assert d.label_en[0].isupper(), (
                f"{key} の label_en={d.label_en!r} が大文字始まりでない"
            )
