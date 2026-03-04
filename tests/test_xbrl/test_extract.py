"""test_extract.py — extract_values() / extracted_to_dict() のテスト。

v0.3.0: extract_values() はパイプラインマッパーで 1 パス走査する。
デフォルト [summary_mapper, statement_mapper] は v0.2.0 と同一結果。
"""

from __future__ import annotations

import warnings
from datetime import date
from decimal import Decimal

import pytest

from edinet.financial.extract import (
    ExtractedValue,
    extract_values,
    extracted_to_dict,
)
from edinet.financial.mapper import (
    dict_mapper,
    statement_mapper,
    summary_mapper,
)
from edinet.financial.standards.canonical_keys import CK
from edinet.financial.statements import Statements
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# ---------------------------------------------------------------------------
# テスト用定数
# ---------------------------------------------------------------------------

_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)

_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_CUR_INSTANT = InstantPeriod(instant=date(2025, 3, 31))


# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用 LabelInfo を構築するヘルパー。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_line_item(
    *,
    local_name: str = "NetSalesSummaryOfBusinessResults",
    value: Decimal | str | None = Decimal("1000000"),
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    order: int = 0,
    namespace_uri: str = _NS_JPCRP,
    is_nil: bool = False,
    unit_ref: str | None = "JPY",
) -> LineItem:
    """テスト用 LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref=unit_ref,
        decimals=-6 if isinstance(value, Decimal) else None,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=(),
        is_nil=is_nil,
        source_line=1,
        order=order,
    )


def _make_stmts(*items: LineItem) -> Statements:
    """テスト用 Statements を構築するヘルパー。"""
    return Statements(_items=tuple(items))


# ---------------------------------------------------------------------------
# TestExtractValues
# ---------------------------------------------------------------------------


class TestExtractValues:
    """extract_values() のテスト（v0.3.0: パイプラインマッパー）。"""

    def test_extract_specific_keys(self) -> None:
        """指定した canonical key の値が正しく返る。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000000"),
            ),
            _make_line_item(
                local_name="OrdinaryIncomeLossSummaryOfBusinessResults",
                value=Decimal("200000"),
                label_ja="経常利益",
                label_en="Ordinary income",
                order=1,
            ),
        )
        result = extract_values(stmts, [CK.REVENUE, CK.ORDINARY_INCOME])

        assert CK.REVENUE in result
        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000000")
        assert result[CK.REVENUE].mapper_name == "summary_mapper"
        assert result[CK.ORDINARY_INCOME] is not None
        assert result[CK.ORDINARY_INCOME].value == Decimal("200000")
        assert result[CK.ORDINARY_INCOME].mapper_name == "summary_mapper"

    def test_extract_missing_key_returns_none(self) -> None:
        """存在しない canonical key は None で返る。"""
        stmts = _make_stmts(
            _make_line_item(local_name="NetSalesSummaryOfBusinessResults"),
        )
        result = extract_values(stmts, [CK.REVENUE, CK.TOTAL_ASSETS])

        assert result[CK.REVENUE] is not None
        assert result[CK.TOTAL_ASSETS] is None

    def test_extract_all_keys(self) -> None:
        """keys=None で全マッピング可能科目を発見する。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000000"),
            ),
            _make_line_item(
                local_name="TotalAssetsSummaryOfBusinessResults",
                value=Decimal("5000000"),
                label_ja="総資産",
                label_en="Total assets",
                order=1,
                period=_CUR_INSTANT,
            ),
            # マッピングされない独自科目
            _make_line_item(
                local_name="CustomFilerItem",
                value=Decimal("50000"),
                label_ja="独自科目",
                label_en="Custom item",
                order=2,
            ),
        )
        result = extract_values(stmts)

        assert "revenue" in result
        assert "total_assets" in result
        assert len(result) == 2

    def test_extract_preserves_item(self) -> None:
        """.item が元の LineItem と同一オブジェクトを参照する。"""
        item = _make_line_item(local_name="NetSalesSummaryOfBusinessResults")
        stmts = _make_stmts(item)

        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].item is item

    def test_extract_empty(self) -> None:
        """空の Statements で空辞書が返る。"""
        stmts = _make_stmts()

        result = extract_values(stmts, [CK.REVENUE])
        assert result == {CK.REVENUE: None}

    def test_extract_empty_all_keys(self) -> None:
        """空の Statements + keys=None で空辞書が返る。"""
        stmts = _make_stmts()

        result = extract_values(stmts)
        assert result == {}

    def test_extract_ifrs_summary(self) -> None:
        """IFRS の SummaryOfBusinessResults 概念名でマッチする。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="RevenueIFRSSummaryOfBusinessResults",
                value=Decimal("5000000"),
                label_ja="売上収益",
            ),
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("5000000")

    def test_extract_usgaap_summary(self) -> None:
        """US-GAAP の SummaryOfBusinessResults 概念名でマッチする。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                value=Decimal("8000000"),
            ),
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("8000000")

    def test_extract_canonical_key_field(self) -> None:
        """ExtractedValue.canonical_key が正しく設定される。"""
        stmts = _make_stmts(
            _make_line_item(local_name="NetSalesSummaryOfBusinessResults"),
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].canonical_key == "revenue"

    def test_extract_nil_value(self) -> None:
        """nil 値の科目も抽出される。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=None, is_nil=True,
            ),
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value is None

    def test_pl_concept_not_matched_with_summary_only(self) -> None:
        """mapper=[summary_mapper] なら PL 本体の概念名はマッチしない。"""
        stmts = _make_stmts(
            _make_line_item(local_name="NetSales"),
        )
        result = extract_values(
            stmts, [CK.REVENUE], mapper=[summary_mapper],
        )

        assert result[CK.REVENUE] is None

    def test_rejects_financial_statement(self) -> None:
        """FinancialStatement を渡すと TypeError が発生する。"""
        fs = FinancialStatement(
            statement_type=StatementType.INCOME_STATEMENT,
            period=_CUR_DURATION,
            items=(),
            consolidated=True,
            entity_id="E00001",
            warnings_issued=(),
        )
        with pytest.raises(TypeError, match="Statements"):
            extract_values(fs)


# ---------------------------------------------------------------------------
# TestPipelineMapper
# ---------------------------------------------------------------------------


class TestPipelineMapper:
    """パイプラインマッパーのテスト（v0.3.0）。"""

    def test_operating_income_from_pl(self) -> None:
        """PL 本体の OperatingIncome がデフォルトパイプラインで取得できる。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )
        result = extract_values(stmts, [CK.OPERATING_INCOME])

        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].value == Decimal("500000")
        assert result[CK.OPERATING_INCOME].mapper_name == "statement_mapper"

    def test_summary_priority_over_statement(self) -> None:
        """Summary の値が PL 本体より優先される。"""
        summary_item = _make_line_item(
            local_name="NetSalesSummaryOfBusinessResults",
            value=Decimal("1000000"),
            label_ja="売上高（Summary）",
        )
        pl_item = _make_line_item(
            local_name="NetSales",
            value=Decimal("999999"),
            label_ja="売上高（PL）",
            order=1,
        )
        stmts = _make_stmts(summary_item, pl_item)

        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000000")
        assert result[CK.REVENUE].item is summary_item
        assert result[CK.REVENUE].mapper_name == "summary_mapper"

    def test_summary_only_mapper_skips_pl(self) -> None:
        """mapper=[summary_mapper] なら PL 本体から取得しない。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
            ),
        )
        result = extract_values(
            stmts, [CK.OPERATING_INCOME], mapper=[summary_mapper],
        )

        assert result[CK.OPERATING_INCOME] is None

    def test_goodwill_from_bs(self) -> None:
        """新規 CK（GOODWILL）が statement_mappings 経由で取得できる。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="Goodwill",
                value=Decimal("300000"),
                label_ja="のれん",
                label_en="Goodwill",
                period=_CUR_INSTANT,
            ),
        )
        result = extract_values(stmts, [CK.GOODWILL])

        assert result[CK.GOODWILL] is not None
        assert result[CK.GOODWILL].value == Decimal("300000")

    def test_interest_income_from_pl(self) -> None:
        """新規 CK（INTEREST_INCOME_PL）が取得できる。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="InterestIncomeNOI",
                value=Decimal("10000"),
                label_ja="受取利息",
                label_en="Interest income",
            ),
        )
        result = extract_values(stmts, [CK.INTEREST_INCOME_PL])

        assert result[CK.INTEREST_INCOME_PL] is not None
        assert result[CK.INTEREST_INCOME_PL].value == Decimal("10000")

    def test_bonds_payable_from_bs(self) -> None:
        """新規 CK（BONDS_PAYABLE）が取得できる。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="BondsPayable",
                value=Decimal("50000000"),
                label_ja="社債",
                label_en="Bonds payable",
                period=_CUR_INSTANT,
            ),
        )
        result = extract_values(stmts, [CK.BONDS_PAYABLE])

        assert result[CK.BONDS_PAYABLE] is not None
        assert result[CK.BONDS_PAYABLE].value == Decimal("50000000")

    def test_all_keys_includes_statements(self) -> None:
        """keys=None でデフォルトパイプラインなら PL 本体の科目も含まれる。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000000"),
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
                order=1,
            ),
        )
        result = extract_values(stmts)

        assert CK.REVENUE in result
        assert CK.OPERATING_INCOME in result

    def test_single_mapper_no_implicit_fallback(self) -> None:
        """mapper=単一関数 では暗黙的なフォールバックが追加されない。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000000"),
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
                order=1,
            ),
        )
        # summary_mapper のみ → statement_mapper は使われない
        result = extract_values(stmts, mapper=summary_mapper)

        assert result[CK.REVENUE] is not None
        # OperatingIncome は summary_mapper ではマッチしない
        assert CK.OPERATING_INCOME not in result

    def test_pipeline_explicit_fallback(self) -> None:
        """カスタム→summary→statement の明示的パイプライン。"""
        custom = dict_mapper(
            {"MyCustomConcept": CK.REVENUE}, name="custom",
        )
        stmts = _make_stmts(
            _make_line_item(
                local_name="MyCustomConcept",
                value=Decimal("9999"),
                label_ja="カスタム売上",
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
                order=1,
            ),
        )
        result = extract_values(
            stmts,
            [CK.REVENUE, CK.OPERATING_INCOME],
            mapper=[custom, summary_mapper, statement_mapper],
        )

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("9999")
        assert result[CK.REVENUE].mapper_name == "custom"
        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].mapper_name == "statement_mapper"

    def test_priority_earlier_mapper_wins(self) -> None:
        """パイプライン先頭のマッパーが後方より優先される。"""
        custom = dict_mapper(
            {"OperatingIncome": CK.OPERATING_INCOME}, name="custom_oi",
        )
        stmts = _make_stmts(
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
            ),
        )
        # custom が先 → custom が勝つ
        result = extract_values(
            stmts, [CK.OPERATING_INCOME],
            mapper=[custom, statement_mapper],
        )

        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].mapper_name == "custom_oi"

    def test_priority_summary_over_statement(self) -> None:
        """item 出現順に関係なく summary_mapper が statement_mapper に勝つ。

        回帰テスト: 3パス→1パス移行で優先度逆転が起きないことを検証。
        """
        # statement 先、summary 後の item 順序
        pl_item = _make_line_item(
            local_name="NetSales",
            value=Decimal("999999"),
            label_ja="売上高（PL）",
            order=0,
        )
        summary_item = _make_line_item(
            local_name="NetSalesSummaryOfBusinessResults",
            value=Decimal("1000000"),
            label_ja="売上高（Summary）",
            order=1,
        )
        stmts = _make_stmts(pl_item, summary_item)

        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].item is summary_item
        assert result[CK.REVENUE].mapper_name == "summary_mapper"

    def test_mapper_name_summary(self) -> None:
        """デフォルトで summary マッチ → mapper_name="summary_mapper"。"""
        stmts = _make_stmts(
            _make_line_item(local_name="NetSalesSummaryOfBusinessResults"),
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].mapper_name == "summary_mapper"

    def test_mapper_name_statement(self) -> None:
        """デフォルトで statement マッチ → mapper_name="statement_mapper"。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
            ),
        )
        result = extract_values(stmts, [CK.OPERATING_INCOME])

        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].mapper_name == "statement_mapper"

    def test_extract_values_no_mapper(self) -> None:
        """mapper=None（デフォルト）で従来と同一結果。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000000"),
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500000"),
                label_ja="営業利益",
                order=1,
            ),
        )
        result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000000")
        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].value == Decimal("500000")


# ---------------------------------------------------------------------------
# TestCKWarning
# ---------------------------------------------------------------------------


class TestCKWarning:
    """CK typo 警告のテスト。"""

    def test_unknown_ck_warns(self) -> None:
        """keys=None で未知 CK を返した場合に UserWarning が発行される。"""
        custom = dict_mapper(
            {"SomeItem": "unknown_ck_typo"}, name="typo_mapper",
        )
        stmts = _make_stmts(
            _make_line_item(
                local_name="SomeItem",
                value=Decimal("100"),
                label_ja="何か",
            ),
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = extract_values(stmts, mapper=custom)

        assert "unknown_ck_typo" in result
        assert any("unknown_ck_typo" in str(warning.message) for warning in w)

    def test_unknown_ck_no_warn_with_keys(self) -> None:
        """keys を明示指定した場合は CK typo 警告なし。"""
        custom = dict_mapper(
            {"SomeItem": "my_custom_key"}, name="custom",
        )
        stmts = _make_stmts(
            _make_line_item(
                local_name="SomeItem",
                value=Decimal("100"),
                label_ja="何か",
            ),
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = extract_values(
                stmts, ["my_custom_key"], mapper=custom,
            )

        assert result["my_custom_key"] is not None
        assert not any("タイポ" in str(warning.message) for warning in w)


# ---------------------------------------------------------------------------
# TestRegressionPriorityInversion
# ---------------------------------------------------------------------------


class TestRegressionPriorityInversion:
    """3パス→1パス移行の回帰テスト。"""

    def test_regression_priority_inversion(self) -> None:
        """NetSales（statement）と NetSalesSummary（summary）が同じ CK に解決。

        item の出現順に関係なく summary 側が採用される。
        """
        # statement item が先に出現
        pl_item = _make_line_item(
            local_name="NetSales",
            value=Decimal("999"),
            label_ja="売上高（PL）",
            order=0,
        )
        summary_item = _make_line_item(
            local_name="NetSalesSummaryOfBusinessResults",
            value=Decimal("1000"),
            label_ja="売上高（Summary）",
            order=1,
        )
        stmts = _make_stmts(pl_item, summary_item)
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000")
        assert result[CK.REVENUE].item is summary_item


# ---------------------------------------------------------------------------
# TestStatementMappings
# ---------------------------------------------------------------------------


class TestStatementMappings:
    """statement_mappings.py の単体テスト。"""

    def test_lookup_jgaap_pl(self) -> None:
        """J-GAAP PL の lookup_statement が正しく返る。"""
        from edinet.financial.standards.statement_mappings import lookup_statement

        assert lookup_statement("OperatingIncome") == CK.OPERATING_INCOME
        assert lookup_statement("NetSales") == CK.REVENUE
        assert lookup_statement("GrossProfit") == CK.GROSS_PROFIT

    def test_lookup_jgaap_bs(self) -> None:
        """J-GAAP BS の lookup_statement が正しく返る。"""
        from edinet.financial.standards.statement_mappings import lookup_statement

        assert lookup_statement("Assets") == CK.TOTAL_ASSETS
        assert lookup_statement("Goodwill") == CK.GOODWILL
        assert lookup_statement("ShortTermLoansPayable") == CK.SHORT_TERM_LOANS

    def test_lookup_ifrs(self) -> None:
        """IFRS の lookup_statement が正しく返る。"""
        from edinet.financial.standards.statement_mappings import lookup_statement

        assert lookup_statement("GoodwillIFRS") == CK.GOODWILL
        assert lookup_statement("OperatingProfitLossIFRS") == CK.OPERATING_INCOME

    def test_lookup_unknown_returns_none(self) -> None:
        """未知の concept は None を返す。"""
        from edinet.financial.standards.statement_mappings import lookup_statement

        assert lookup_statement("UnknownConcept") is None

    def test_statement_concepts_order(self) -> None:
        """statement_concepts が正しい順序で概念名を返す。"""
        from edinet.financial.standards.statement_mappings import statement_concepts

        pl = statement_concepts("jgaap", "pl")
        assert pl[0] == "NetSales"
        assert "OperatingIncome" in pl

    def test_new_ck_members_exist(self) -> None:
        """新規 CK メンバーが存在し、正しい値を持つ。"""
        assert CK.GOODWILL == "goodwill"
        assert CK.SHORT_TERM_LOANS == "short_term_loans"
        assert CK.LONG_TERM_LOANS == "long_term_loans"
        assert CK.BONDS_PAYABLE == "bonds_payable"
        assert CK.INTEREST_INCOME_PL == "interest_income_pl"
        assert CK.INTEREST_EXPENSE_PL == "interest_expense_pl"
        assert CK.RD_EXPENSES == "rd_expenses"


# ---------------------------------------------------------------------------
# TestNormalizeConcept
# ---------------------------------------------------------------------------


class TestNormalizeConcept:
    """normalize_concept() のテスト（サフィックス剥離ロジック）。"""

    def test_strip_ifrs(self) -> None:
        """IFRS サフィックスを剥離する。"""
        from edinet.financial.standards.statement_mappings import normalize_concept

        assert normalize_concept("GoodwillIFRS") == "Goodwill"
        assert normalize_concept("ProfitLossIFRS") == "ProfitLoss"

    def test_strip_position_tag(self) -> None:
        """ポジションタグ（CA, CL 等）を 2 段目で剥離する。"""
        from edinet.financial.standards.statement_mappings import normalize_concept

        assert normalize_concept("InventoriesCAIFRS") == "Inventories"
        assert normalize_concept("TradeAndOtherPayablesCLIFRS") == "TradeAndOtherPayables"

    def test_preserve_opecf(self) -> None:
        """OpeCF / InvCF / FinCF は CF 科目名の一部なので剥離しない。"""
        from edinet.financial.standards.statement_mappings import normalize_concept

        assert normalize_concept("DepreciationAndAmortizationOpeCFIFRS") == "DepreciationAndAmortizationOpeCF"
        assert normalize_concept("SubtotalOpeCF") == "SubtotalOpeCF"

    def test_no_suffix(self) -> None:
        """サフィックスがなければそのまま返す。"""
        from edinet.financial.standards.statement_mappings import normalize_concept

        assert normalize_concept("OperatingIncome") == "OperatingIncome"
        assert normalize_concept("Assets") == "Assets"

    def test_strip_summary(self) -> None:
        """SummaryOfBusinessResults サフィックスを剥離する。"""
        from edinet.financial.standards.statement_mappings import normalize_concept

        assert normalize_concept("NetSalesSummaryOfBusinessResults") == "NetSales"
        assert normalize_concept("TotalAssetsIFRSSummaryOfBusinessResults") == "TotalAssets"

    def test_lookup_via_normalize_fallback(self) -> None:
        """辞書にない IFRS 概念名が正規化フォールバックで解決する。"""
        from edinet.financial.standards.statement_mappings import lookup_statement

        # "CostOfSalesIFRS" は辞書にあるので Layer 1 で解決
        assert lookup_statement("CostOfSalesIFRS") == CK.COST_OF_SALES

        # 仮に辞書から削除された IFRS 概念名でもフォールバックで解決
        # （実際は辞書にもあるが、基底名 "Goodwill" が辞書にあることを確認）
        assert lookup_statement("GoodwillIFRS") == CK.GOODWILL

    def test_rd_expenses_from_raw_items(self) -> None:
        """R&D費が _items 直接走査で取得できる（注記セクション）。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="ResearchAndDevelopmentExpensesSGA",
                value=Decimal("160246000"),
                label_ja="研究開発費",
                label_en="R&D expenses",
            ),
        )
        result = extract_values(stmts, [CK.RD_EXPENSES])

        assert result[CK.RD_EXPENSES] is not None
        assert result[CK.RD_EXPENSES].value == Decimal("160246000")


# ---------------------------------------------------------------------------
# TestExtractedToDict
# ---------------------------------------------------------------------------


class TestExtractedToDict:
    """extracted_to_dict() のテスト。"""

    def test_basic_conversion(self) -> None:
        """ExtractedValue → {key: value} の変換が正しい。"""
        extracted = {
            "revenue": ExtractedValue(
                canonical_key="revenue",
                value=Decimal("1000000"),
                item=_make_line_item(),
                mapper_name="summary_mapper",
            ),
            "ordinary_income": ExtractedValue(
                canonical_key="ordinary_income",
                value=Decimal("200000"),
                item=_make_line_item(
                    local_name="OrdinaryIncomeLossSummaryOfBusinessResults",
                    label_ja="経常利益",
                ),
                mapper_name="summary_mapper",
            ),
        }
        result = extracted_to_dict(extracted)

        assert result == {
            "revenue": Decimal("1000000"),
            "ordinary_income": Decimal("200000"),
        }

    def test_none_values(self) -> None:
        """None の ExtractedValue は None 値になる。"""
        extracted: dict[str, ExtractedValue | None] = {
            "revenue": ExtractedValue(
                canonical_key="revenue",
                value=Decimal("1000000"),
                item=_make_line_item(),
                mapper_name="summary_mapper",
            ),
            "total_assets": None,
        }
        result = extracted_to_dict(extracted)

        assert result == {
            "revenue": Decimal("1000000"),
            "total_assets": None,
        }

    def test_empty_dict(self) -> None:
        """空辞書の変換。"""
        assert extracted_to_dict({}) == {}


# ---------------------------------------------------------------------------
# TestLinkbaseMapperPipeline
# ---------------------------------------------------------------------------


class TestLinkbaseMapperPipeline:
    """definition_mapper / calc_mapper のパイプライン統合テスト。"""

    def test_definition_mapper_fallback(self) -> None:
        """summary/statement でヒットしない独自概念が definition_mapper でヒット。"""
        stmts = Statements(
            _items=(
                _make_line_item(
                    local_name="X_CompanySpecificRevenue",
                    value=Decimal("999999"),
                    label_ja="独自売上高",
                ),
            ),
            _definition_linkbase={
                "role/PL": type("FakeTree", (), {
                    "arcs": (
                        type("FakeArc", (), {
                            "from_concept": "NetSales",
                            "to_concept": "X_CompanySpecificRevenue",
                            "from_href": "jppfs_cor_2025-11-01.xsd#NetSales",
                            "to_href": "jpcrp030000.xsd#X_CompanySpecificRevenue",
                            "arcrole": "http://www.xbrl.org/2003/arcrole/general-special",
                            "order": 1.0,
                        })(),
                    ),
                    "role_uri": "role/PL",
                    "hypercubes": (),
                })(),
            },
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("999999")
        assert result[CK.REVENUE].mapper_name == "definition_mapper"

    def test_calc_mapper_fallback(self) -> None:
        """definition でもヒットしない場合に calc_mapper でヒット。"""
        from edinet.xbrl.linkbase.calculation import (
            CalculationArc,
            CalculationLinkbase,
            CalculationTree,
        )

        role = "http://example.com/role/PL"
        arcs = (
            CalculationArc(
                parent="GrossProfit",
                child="X_FilerSpecificProfit",
                parent_href="jppfs.xsd#GrossProfit",
                child_href="filer.xsd#X_FilerSpecificProfit",
                weight=1,
                order=1.0,
                role_uri=role,
            ),
        )
        tree = CalculationTree(
            role_uri=role, arcs=arcs, roots=("GrossProfit",),
        )
        calc_lb = CalculationLinkbase(
            source_path=None, trees={role: tree},
        )

        stmts = Statements(
            _items=(
                _make_line_item(
                    local_name="X_FilerSpecificProfit",
                    value=Decimal("12345"),
                    label_ja="独自利益",
                ),
            ),
            _calculation_linkbase=calc_lb,
        )
        result = extract_values(stmts, [CK.GROSS_PROFIT])

        assert result[CK.GROSS_PROFIT] is not None
        assert result[CK.GROSS_PROFIT].value == Decimal("12345")
        assert result[CK.GROSS_PROFIT].mapper_name == "calc_mapper"

    def test_linkbase_mappers_no_data(self) -> None:
        """linkbase なしでも既存 summary/statement は同一結果。"""
        stmts = _make_stmts(
            _make_line_item(
                local_name="NetSalesSummaryOfBusinessResults",
                value=Decimal("1000"),
            ),
            _make_line_item(
                local_name="OperatingIncome",
                value=Decimal("500"),
                label_ja="営業利益",
                order=1,
            ),
        )
        result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME])

        assert result[CK.REVENUE] is not None
        assert result[CK.REVENUE].value == Decimal("1000")
        assert result[CK.REVENUE].mapper_name == "summary_mapper"
        assert result[CK.OPERATING_INCOME] is not None
        assert result[CK.OPERATING_INCOME].value == Decimal("500")

    def test_standard_concept_wins_over_linkbase(self) -> None:
        """標準概念が summary/statement でヒットすれば linkbase マッパーは使われない。"""
        stmts = Statements(
            _items=(
                _make_line_item(
                    local_name="NetSales",
                    value=Decimal("8888"),
                    label_ja="売上高",
                ),
            ),
            _definition_linkbase={
                "role/PL": type("FakeTree", (), {
                    "arcs": (
                        type("FakeArc", (), {
                            "from_concept": "TotalAssets",
                            "to_concept": "NetSales",
                            "from_href": "jppfs.xsd#TotalAssets",
                            "to_href": "jppfs.xsd#NetSales",
                            "arcrole": "http://www.xbrl.org/2003/arcrole/general-special",
                            "order": 1.0,
                        })(),
                    ),
                    "role_uri": "role/PL",
                    "hypercubes": (),
                })(),
            },
        )
        result = extract_values(stmts, [CK.REVENUE])

        assert result[CK.REVENUE] is not None
        # statement_mapper で直接マッチするので definition_mapper は使われない
        assert result[CK.REVENUE].mapper_name == "statement_mapper"
