"""test_statements.py — build_statements() のテスト。"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from edinet.exceptions import EdinetWarning
from edinet.models.financial import (
    FinancialStatement,
    LineItem,
    StatementType,
)
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
)
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.statements import (
    Statements,
    build_statements,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# テスト用名前空間
_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)
# jpcrp モジュール配下の提出者拡張名前空間（jpcrp030000-asr_E00001-000 形式）
_NS_FILER_JPCRP = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp030000-asr_E00001-000"

# 共通期間
_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_PREV_DURATION = DurationPeriod(
    start_date=date(2023, 4, 1), end_date=date(2024, 3, 31)
)
_CUR_INSTANT = InstantPeriod(instant=date(2025, 3, 31))
_PREV_INSTANT = InstantPeriod(instant=date(2024, 3, 31))

# dimension
_NON_CONSOLIDATED_DIM = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}NonConsolidatedMember",
    ),
)
_CONSOLIDATED_DIM = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedMember",
    ),
)
_SEGMENT_DIM = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/E00001/2025-11-01}SegmentAMember",
    ),
)
_NON_CONSOLIDATED_WITH_SEGMENT = (
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}NonConsolidatedMember",
    ),
    DimensionMember(
        axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis",
        member="{http://disclosure.edinet-fsa.go.jp/taxonomy/E00001/2025-11-01}SegmentAMember",
    ),
)


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


def _make_pl_item(
    *,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000000"),
    period: DurationPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearDuration",
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    namespace_uri: str = _NS_JPPFS,
    is_nil: bool = False,
    unit_ref: str | None = "JPY",
) -> LineItem:
    """テスト用 PL LineItem を構築するヘルパー。"""
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
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=is_nil,
        source_line=1,
        order=order,
    )


def _make_bs_item(
    *,
    local_name: str = "Assets",
    value: Decimal = Decimal("5000000000"),
    period: InstantPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearInstant",
    label_ja: str = "資産合計",
    label_en: str = "Total assets",
) -> LineItem:
    """テスト用 BS LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_INSTANT
    return LineItem(
        concept=f"{{{_NS_JPPFS}}}{local_name}",
        namespace_uri=_NS_JPPFS,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )


# ---------------------------------------------------------------------------
# P0 テスト（必須）
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestBuildStatementsBasic:
    """Statements 構築の基本テスト。"""

    def test_build_statements_returns_statements(self) -> None:
        """build_statements() が Statements を返すこと。"""
        items = (_make_pl_item(),)
        stmts = build_statements(items)
        assert isinstance(stmts, Statements)

    def test_income_statement_returns_financial_statement(self) -> None:
        """stmts.income_statement() が FinancialStatement を返すこと。"""
        items = (_make_pl_item(),)
        stmts = build_statements(items)
        pl = stmts.income_statement()
        assert isinstance(pl, FinancialStatement)
        assert pl.statement_type == StatementType.INCOME_STATEMENT


@pytest.mark.small
@pytest.mark.unit
class TestFactSelectionRules:
    """Fact 選択ルールのテスト。"""

    def test_pl_selects_numeric_facts_only(self) -> None:
        """テキスト Fact と nil Fact が除外されること。"""
        numeric = _make_pl_item(local_name="NetSales", value=Decimal("100"))
        text = _make_pl_item(
            local_name="CostOfSales",
            value="テキスト値",
            label_ja="売上原価",
            label_en="Cost of sales",
            unit_ref=None,
        )
        nil = _make_pl_item(
            local_name="GrossProfit",
            value=None,
            is_nil=True,
            label_ja="売上総利益",
            label_en="Gross profit",
        )
        stmts = build_statements((numeric, text, nil))
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl.items[0].local_name == "NetSales"

    def test_pl_selects_latest_period(self) -> None:
        """当期の Fact のみが選択されること。"""
        current = _make_pl_item(
            local_name="NetSales", period=_CUR_DURATION
        )
        prior = _make_pl_item(
            local_name="NetSales",
            period=_PREV_DURATION,
            context_id="PriorYearDuration",
            value=Decimal("800000000"),
        )
        stmts = build_statements((current, prior))
        pl = stmts.income_statement()
        assert pl.period == _CUR_DURATION
        local_names = [item.local_name for item in pl.items]
        assert "NetSales" in local_names
        # 値が当期のものであること
        net_sales = pl["NetSales"]
        assert net_sales.value == Decimal("1000000000")

    def test_pl_selects_consolidated_by_default(self) -> None:
        """dimension なし（連結）が選択されること。"""
        consolidated = _make_pl_item(
            local_name="NetSales", dimensions=()
        )
        non_consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearDuration_NonConsolidatedMember",
            value=Decimal("500000000"),
        )
        stmts = build_statements((consolidated, non_consolidated))
        pl = stmts.income_statement()
        assert pl.consolidated is True
        assert pl["NetSales"].value == Decimal("1000000000")

    def test_pl_fallback_to_non_consolidated(self) -> None:
        """連結 Fact が 0 件で個別にフォールバックし EdinetWarning が出ること。"""
        non_consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearDuration_NonConsolidatedMember",
        )
        stmts = build_statements((non_consolidated,))
        with pytest.warns(EdinetWarning, match="連結データなし"):
            pl = stmts.income_statement()
        assert pl.consolidated is False
        assert len(pl.items) == 1

    def test_pl_excludes_dimension_facts(self) -> None:
        """セグメント軸を持つ Fact が除外されること。"""
        total = _make_pl_item(local_name="NetSales")
        segment = _make_pl_item(
            local_name="NetSales",
            dimensions=_SEGMENT_DIM,
            context_id="CurrentYearDuration_SegmentA",
            value=Decimal("300000000"),
        )
        stmts = build_statements((total, segment))
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl["NetSales"].value == Decimal("1000000000")

    def test_empty_fallback_preserves_requested_mode(self) -> None:
        """連結も個別もない場合、要求されたモードが保持され誤警告が出ないこと。"""
        # セグメント軸のみの Fact（連結でも個別でもない）
        segment_only = _make_pl_item(
            local_name="NetSales",
            dimensions=_SEGMENT_DIM,
        )
        stmts = build_statements((segment_only,))

        # consolidated=True で警告なし（フォールバック「していない」ため）
        pl = stmts.income_statement(consolidated=True)
        assert pl.consolidated is True
        assert len(pl.items) == 0
        assert not any("フォールバック" in w for w in pl.warnings_issued)

        # consolidated=False でも同様
        pl2 = stmts.income_statement(consolidated=False)
        assert pl2.consolidated is False
        assert len(pl2.items) == 0
        assert not any("フォールバック" in w for w in pl2.warnings_issued)

    def test_explicit_consolidated_member_treated_as_consolidated(
        self,
    ) -> None:
        """明示的な ConsolidatedMember が連結として扱われること。"""
        explicit = _make_pl_item(
            local_name="NetSales",
            dimensions=_CONSOLIDATED_DIM,
            value=Decimal("1000"),
        )
        stmts = build_statements((explicit,))
        pl = stmts.income_statement()
        assert pl.consolidated is True
        assert len(pl.items) == 1
        assert pl["NetSales"].value == Decimal("1000")

    def test_non_consolidated_segment_only_triggers_fallback(self) -> None:
        """個別+セグメントのみで連結全社合計がある場合、連結にフォールバック。

        個別 Fact が NonConsolidatedMember + SegmentAxis の場合、
        全社合計ではないためフォールバック判定では無視される。
        """
        consol_total = _make_pl_item(
            local_name="NetSales",
            dimensions=(),
            value=Decimal("1000"),
        )
        non_consol_segment = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_WITH_SEGMENT,
            value=Decimal("300"),
            context_id="CurrentYearDuration_NonConsol_SegA",
        )
        stmts = build_statements((consol_total, non_consol_segment))
        with pytest.warns(EdinetWarning, match="個別データなし"):
            pl = stmts.income_statement(consolidated=False)
        assert pl.consolidated is True
        assert pl["NetSales"].value == Decimal("1000")

    def test_pl_duplicate_selects_first(self) -> None:
        """同一 concept で 2 件残った場合、先頭が採用されること。"""
        first = _make_pl_item(
            local_name="NetSales", order=0, value=Decimal("100")
        )
        second = _make_pl_item(
            local_name="NetSales",
            order=1,
            value=Decimal("200"),
            context_id="CurrentYearDuration_Alt",
        )
        stmts = build_statements((first, second))
        pl = stmts.income_statement()
        assert pl["NetSales"].value == Decimal("100")


@pytest.mark.small
@pytest.mark.unit
class TestItemOrdering:
    """科目分類と並び順のテスト。"""

    def test_pl_items_ordered_by_display_order(self) -> None:
        """display_order 通りに並ぶこと。"""
        # 逆順に投入
        ordinary = _make_pl_item(
            local_name="OrdinaryIncome",
            order=2,
            label_ja="経常利益",
            label_en="Ordinary income",
        )
        operating = _make_pl_item(
            local_name="OperatingIncome",
            order=1,
            label_ja="営業利益",
            label_en="Operating income",
        )
        net_sales = _make_pl_item(
            local_name="NetSales", order=0
        )
        stmts = build_statements((ordinary, operating, net_sales))
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        assert local_names == [
            "NetSales",
            "OperatingIncome",
            "OrdinaryIncome",
        ]

    def test_unknown_concept_excluded(self) -> None:
        """概念セットに定義されていない concept が PL に含まれないこと。"""
        net_sales = _make_pl_item(local_name="NetSales", order=0)
        # jppfs_cor だが概念セットに載っていない科目
        unknown = _make_pl_item(
            local_name="SomeExtraItem",
            order=1,
            label_ja="その他",
            label_en="Some extra",
        )
        stmts = build_statements((net_sales, unknown))
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        assert local_names == ["NetSales"]


@pytest.mark.small
@pytest.mark.unit
class TestFinancialStatementAPI:
    """FinancialStatement の API テスト。"""

    @pytest.fixture()
    def pl_fixture(self) -> FinancialStatement:
        """テスト用 PL を構築する fixture。"""
        items = (
            _make_pl_item(local_name="NetSales", order=0),
            _make_pl_item(
                local_name="OperatingIncome",
                order=1,
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )
        stmts = build_statements(items)
        return stmts.income_statement()

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            ("売上高", "NetSales"),
            ("Net sales", "NetSales"),
            ("NetSales", "NetSales"),
        ],
    )
    def test_getitem_by_key(
        self,
        key: str,
        expected: str,
        pl_fixture: FinancialStatement,
    ) -> None:
        """ラベル・local_name で LineItem にアクセスできること。"""
        assert pl_fixture[key].local_name == expected

    def test_getitem_not_found_raises_key_error(
        self,
        pl_fixture: FinancialStatement,
    ) -> None:
        """存在しない科目で KeyError が raise されること。"""
        with pytest.raises(KeyError):
            pl_fixture["存在しない科目"]

    def test_contains(self, pl_fixture: FinancialStatement) -> None:
        """``in`` 演算子が正しく動作すること。"""
        assert "売上高" in pl_fixture
        assert "存在しない" not in pl_fixture


@pytest.mark.small
@pytest.mark.unit
class TestBSAndCF:
    """BS / CF のテスト。"""

    def test_balance_sheet_uses_instant_period(self) -> None:
        """BS が InstantPeriod を使用すること。"""
        item = _make_bs_item(local_name="Assets", order=0)
        stmts = build_statements((item,))
        bs = stmts.balance_sheet()
        assert bs.statement_type == StatementType.BALANCE_SHEET
        assert isinstance(bs.period, InstantPeriod)
        assert bs.period == _CUR_INSTANT

    def test_cash_flow_uses_duration_period(self) -> None:
        """CF が DurationPeriod を使用すること。"""
        item = _make_pl_item(
            local_name="NetCashProvidedByUsedInOperatingActivities",
            order=0,
            label_ja="営業活動によるキャッシュ・フロー",
            label_en="Net cash provided by operating activities",
        )
        stmts = build_statements((item,))
        cf = stmts.cash_flow_statement()
        assert cf.statement_type == StatementType.CASH_FLOW_STATEMENT
        assert isinstance(cf.period, DurationPeriod)
        assert cf.period == _CUR_DURATION


@pytest.mark.small
@pytest.mark.unit
class TestKnownConceptFiltering:
    """既知概念セットに含まれる科目のみが表示されるテスト。"""

    def test_unknown_concept_excluded_from_pl(self) -> None:
        """概念セットに定義されていない concept が PL に含まれないこと。"""
        net_sales = _make_pl_item(local_name="NetSales", order=0)
        # jpcrp_cor 名前空間の科目（概念セットに未定義）
        employees = _make_pl_item(
            local_name="NumberOfEmployees",
            namespace_uri=_NS_JPCRP,
            label_ja="従業員数",
            label_en="Number of employees",
            order=1,
        )
        stmts = build_statements((net_sales, employees))
        pl = stmts.income_statement()
        assert "NumberOfEmployees" not in [i.local_name for i in pl.items]

    def test_filer_extension_excluded_from_pl(self) -> None:
        """提出者拡張科目（概念セットに未定義）が PL に含まれないこと。"""
        net_sales = _make_pl_item(local_name="NetSales", order=0)
        filer_item = _make_pl_item(
            local_name="CustomExpenseItem",
            namespace_uri=_NS_FILER_JPCRP,
            label_ja="独自費用科目",
            label_en="Custom expense item",
            order=1,
        )
        stmts = build_statements((net_sales, filer_item))
        pl = stmts.income_statement()
        pl_names = [i.local_name for i in pl.items]
        assert "CustomExpenseItem" not in pl_names


@pytest.mark.small
@pytest.mark.unit
class TestPeriodTiebreak:
    """期間タイブレークのテスト。"""

    def test_pl_selects_cumulative_over_quarterly(self) -> None:
        """累計期間と四半期が同一 end_date で共存する場合、累計が選択されること。"""
        cumulative = DurationPeriod(
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
        )
        quarterly = DurationPeriod(
            start_date=date(2025, 1, 1), end_date=date(2025, 3, 31)
        )
        item_cum = _make_pl_item(
            local_name="NetSales",
            period=cumulative,
            value=Decimal("4000"),
            order=0,
        )
        item_q4 = _make_pl_item(
            local_name="NetSales",
            period=quarterly,
            value=Decimal("1000"),
            order=1,
            context_id="CurrentQ4Duration",
        )
        stmts = build_statements((item_cum, item_q4))
        pl = stmts.income_statement()
        assert pl.period == cumulative
        assert pl["NetSales"].value == Decimal("4000")


# ---------------------------------------------------------------------------
# P1 テスト（推奨）
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestP1Additional:
    """P1 追加テスト。"""

    def test_pl_explicit_period_argument(self) -> None:
        """period 引数を明示的に渡した場合、指定期間の Fact が使われること。"""
        current = _make_pl_item(
            local_name="NetSales",
            period=_CUR_DURATION,
            value=Decimal("1000"),
        )
        prior = _make_pl_item(
            local_name="NetSales",
            period=_PREV_DURATION,
            value=Decimal("800"),
            context_id="PriorYearDuration",
        )
        stmts = build_statements((current, prior))
        pl = stmts.income_statement(period=_PREV_DURATION)
        assert pl.period == _PREV_DURATION
        assert pl["NetSales"].value == Decimal("800")

    def test_pl_non_consolidated_explicit(self) -> None:
        """consolidated=False で個別 Fact のみが選択されること。"""
        consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=(),
            value=Decimal("1000"),
        )
        non_consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            value=Decimal("500"),
            context_id="CurrentYearDuration_NonConsolidated",
        )
        stmts = build_statements((consolidated, non_consolidated))
        pl = stmts.income_statement(consolidated=False)
        assert pl.consolidated is False
        assert pl["NetSales"].value == Decimal("500")

    def test_empty_items_returns_empty_statement(self) -> None:
        """空の items で空の FinancialStatement が返ること。"""
        stmts = build_statements(())
        pl = stmts.income_statement()
        assert pl.items == ()
        assert pl.period is None
        assert pl.entity_id == ""

    def test_warnings_issued_recorded(self) -> None:
        """FinancialStatement.warnings_issued に警告メッセージが記録されること。"""
        non_consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
        )
        stmts = build_statements((non_consolidated,))
        with pytest.warns(EdinetWarning):
            pl = stmts.income_statement()
        assert len(pl.warnings_issued) > 0
        assert any("フォールバック" in w for w in pl.warnings_issued)

    def test_len_and_iter(self) -> None:
        """len(pl) と list(pl) が items と一致すること。"""
        items = (
            _make_pl_item(local_name="NetSales", order=0),
            _make_pl_item(
                local_name="OperatingIncome",
                order=1,
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )
        stmts = build_statements(items)
        pl = stmts.income_statement()
        assert len(pl) == len(pl.items)
        assert list(pl) == list(pl.items)

    def test_non_consolidated_only_with_explicit_false(self) -> None:
        """個別のみ存在するケースで consolidated=False が正しく動作すること。"""
        non_consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearDuration_NonConsolidated",
        )
        stmts = build_statements((non_consolidated,))
        pl = stmts.income_statement(consolidated=False)
        assert pl.consolidated is False
        assert len(pl.items) == 1

    def test_consolidated_false_fallback_to_consolidated(self) -> None:
        """consolidated=False で個別がなく連結にフォールバックすること。"""
        consolidated = _make_pl_item(
            local_name="NetSales",
            dimensions=(),
        )
        stmts = build_statements((consolidated,))
        with pytest.warns(EdinetWarning, match="個別データなし"):
            pl = stmts.income_statement(consolidated=False)
        assert pl.consolidated is True
        assert len(pl.items) == 1

    def test_get_returns_item(self) -> None:
        """get() で科目を取得できること。"""
        stmts = build_statements((_make_pl_item(),))
        pl = stmts.income_statement()
        item = pl.get("売上高")
        assert item is not None
        assert item.local_name == "NetSales"

    def test_get_returns_default_on_missing(self) -> None:
        """get() で存在しない科目に対して default を返すこと。"""
        stmts = build_statements((_make_pl_item(),))
        pl = stmts.income_statement()
        assert pl.get("存在しない科目") is None

    def test_repr_is_concise(self) -> None:
        """__repr__ が巨大な出力にならないこと。"""
        stmts = build_statements((_make_pl_item(),))
        pl = stmts.income_statement()
        r = repr(pl)
        assert "FinancialStatement(" in r
        assert "income_statement" in r
        assert "items=1" in r
        # 全 LineItem が展開されていないこと
        assert "NetSales" not in r or "items=1" in r

    def test_bs_fallback_to_non_consolidated(self) -> None:
        """BS でも連結→個別フォールバックが正しく動作すること。"""
        non_consolidated = _make_bs_item(
            local_name="Assets",
            dimensions=_NON_CONSOLIDATED_DIM,
        )
        stmts = build_statements((non_consolidated,))
        with pytest.warns(EdinetWarning, match="連結データなし"):
            bs = stmts.balance_sheet()
        assert bs.consolidated is False
        assert len(bs.items) == 1

    def test_explicit_period_nonexistent_returns_empty(self) -> None:
        """存在しない期間を指定した場合、空の statement が返ること。"""
        item = _make_pl_item(local_name="NetSales", period=_CUR_DURATION)
        stmts = build_statements((item,))
        nonexistent = DurationPeriod(
            start_date=date(2020, 4, 1), end_date=date(2021, 3, 31)
        )
        pl = stmts.income_statement(period=nonexistent)
        assert pl.items == ()
        assert pl.period == nonexistent


@pytest.mark.medium
@pytest.mark.integration
class TestIntegrationPipeline:
    """フルパイプライン統合テスト。"""

    def test_integration_with_full_pipeline(self) -> None:
        """simple_pl.xbrl のフルパイプラインで PL が組み立てられること。"""
        from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

        from edinet.xbrl.contexts import structure_contexts
        from edinet.xbrl.facts import build_line_items
        from edinet.xbrl.parser import parse_xbrl_facts
        from edinet.xbrl.taxonomy import TaxonomyResolver

        xbrl_bytes = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(xbrl_bytes, source_path="simple_pl.xbrl")
        ctx_map = structure_contexts(parsed.contexts)

        resolver = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)

        # 提出者別ラベル読み込み
        filer_dir = TAXONOMY_MINI_DIR / "filer"
        filer_lab = (filer_dir / "filer_lab.xml").read_bytes()
        filer_lab_en = (filer_dir / "filer_lab-en.xml").read_bytes()
        filer_xsd = (filer_dir / "filer.xsd").read_bytes()
        resolver.load_filer_labels(
            filer_lab, filer_lab_en, xsd_bytes=filer_xsd
        )

        line_items = build_line_items(parsed.facts, ctx_map, resolver)
        stmts = build_statements(line_items)

        pl = stmts.income_statement()
        assert isinstance(pl, FinancialStatement)
        assert pl.statement_type == StatementType.INCOME_STATEMENT
        assert len(pl.items) > 0

        # 主要科目が含まれることを検証
        local_names = {item.local_name for item in pl.items}
        # simple_pl.xbrl には NetSales と OperatingIncome が含まれる
        expected = {"NetSales", "OperatingIncome"}
        assert expected <= local_names, (
            f"主要科目が不足しています: 期待={expected}, 実際={local_names}"
        )

    def test_integration_bs_uses_instant_period(self) -> None:
        """フルパイプラインで BS が InstantPeriod を使用し主要科目を含むこと。"""
        from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

        from edinet.xbrl.contexts import structure_contexts
        from edinet.xbrl.facts import build_line_items
        from edinet.xbrl.parser import parse_xbrl_facts
        from edinet.xbrl.taxonomy import TaxonomyResolver

        xbrl_bytes = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(xbrl_bytes, source_path="simple_pl.xbrl")
        ctx_map = structure_contexts(parsed.contexts)

        resolver = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)
        filer_dir = TAXONOMY_MINI_DIR / "filer"
        resolver.load_filer_labels(
            (filer_dir / "filer_lab.xml").read_bytes(),
            (filer_dir / "filer_lab-en.xml").read_bytes(),
            xsd_bytes=(filer_dir / "filer.xsd").read_bytes(),
        )

        line_items = build_line_items(parsed.facts, ctx_map, resolver)
        stmts = build_statements(line_items)

        bs = stmts.balance_sheet()
        assert isinstance(bs, FinancialStatement)
        assert bs.statement_type == StatementType.BALANCE_SHEET
        assert isinstance(bs.period, InstantPeriod)
        assert len(bs.items) > 0

        local_names = {item.local_name for item in bs.items}
        assert {"Assets", "Liabilities", "NetAssets"} <= local_names

    def test_integration_pl_bs_period_consistency(self) -> None:
        """PL の DurationPeriod.end_date と BS の InstantPeriod.instant が一致すること。"""
        from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

        from edinet.xbrl.contexts import structure_contexts
        from edinet.xbrl.facts import build_line_items
        from edinet.xbrl.parser import parse_xbrl_facts
        from edinet.xbrl.taxonomy import TaxonomyResolver

        xbrl_bytes = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(xbrl_bytes, source_path="simple_pl.xbrl")
        ctx_map = structure_contexts(parsed.contexts)

        resolver = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)
        filer_dir = TAXONOMY_MINI_DIR / "filer"
        resolver.load_filer_labels(
            (filer_dir / "filer_lab.xml").read_bytes(),
            (filer_dir / "filer_lab-en.xml").read_bytes(),
            xsd_bytes=(filer_dir / "filer.xsd").read_bytes(),
        )

        line_items = build_line_items(parsed.facts, ctx_map, resolver)
        stmts = build_statements(line_items)

        pl = stmts.income_statement()
        bs = stmts.balance_sheet()

        assert isinstance(pl.period, DurationPeriod)
        assert isinstance(bs.period, InstantPeriod)
        assert pl.period.end_date == bs.period.instant

    def test_integration_cf_uses_duration_period(self) -> None:
        """フルパイプラインで CF が DurationPeriod を使用し主要科目を含むこと。"""
        from .conftest import TAXONOMY_MINI_DIR, load_xbrl_bytes

        from edinet.xbrl.contexts import structure_contexts
        from edinet.xbrl.facts import build_line_items
        from edinet.xbrl.parser import parse_xbrl_facts
        from edinet.xbrl.taxonomy import TaxonomyResolver

        xbrl_bytes = load_xbrl_bytes("simple_pl.xbrl")
        parsed = parse_xbrl_facts(xbrl_bytes, source_path="simple_pl.xbrl")
        ctx_map = structure_contexts(parsed.contexts)

        resolver = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)
        filer_dir = TAXONOMY_MINI_DIR / "filer"
        resolver.load_filer_labels(
            (filer_dir / "filer_lab.xml").read_bytes(),
            (filer_dir / "filer_lab-en.xml").read_bytes(),
            xsd_bytes=(filer_dir / "filer.xsd").read_bytes(),
        )

        line_items = build_line_items(parsed.facts, ctx_map, resolver)
        stmts = build_statements(line_items)

        cf = stmts.cash_flow_statement()
        assert isinstance(cf, FinancialStatement)
        assert cf.statement_type == StatementType.CASH_FLOW_STATEMENT
        assert isinstance(cf.period, DurationPeriod)
        assert len(cf.items) > 0

        local_names = {item.local_name for item in cf.items}
        assert "NetCashProvidedByUsedInOperatingActivities" in local_names


# ---------------------------------------------------------------------------
# Statements.__str__() テスト
# ---------------------------------------------------------------------------


class TestStatementsStr:
    """Statements.__str__() のテスト。"""

    def test_str_contains_all_types(self) -> None:
        """PL + BS + CF が全て含まれること。"""
        items = (
            _make_pl_item(local_name="NetSales"),
            _make_bs_item(local_name="Assets"),
        )
        stmts = build_statements(items)
        output = str(stmts)
        assert "損益計算書" in output
        assert "貸借対照表" in output

    def test_str_empty_statements(self) -> None:
        """全 statement が空の場合 '財務諸表なし' が出力されること。"""
        stmts = build_statements(())
        assert "財務諸表なし" in str(stmts)

    def test_str_partial(self) -> None:
        """PL のみにデータがある場合、BS/CF は出力に含まれないこと。"""
        items = (_make_pl_item(local_name="NetSales"),)
        stmts = build_statements(items)
        output = str(stmts)
        assert "損益計算書" in output
        assert "貸借対照表" not in output


# ---------------------------------------------------------------------------
# Day 18 追加: 期間タイプフィルタリング
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestPeriodTypeFiltering:
    """期間タイプフィルタリングの未テスト分岐をカバーする。"""

    def test_bs_with_only_duration_facts_returns_empty(self) -> None:
        """BS に DurationPeriod しかない場合、空の statement と警告が返ること。"""
        # BS concept だが DurationPeriod を持つ（通常あり得ない不整合ケース）
        item = _make_pl_item(
            local_name="Assets",
            period=_CUR_DURATION,
            label_ja="資産合計",
            label_en="Total assets",
        )
        stmts = build_statements((item,))
        with pytest.warns(EdinetWarning, match="periodType"):
            bs = stmts.balance_sheet()
        assert bs.items == ()
        assert bs.period is None

    def test_pl_ignores_instant_period_facts(self) -> None:
        """PL に InstantPeriod と DurationPeriod が混在する場合、DurationPeriod のみ選択されること。"""
        duration_item = _make_pl_item(
            local_name="NetSales",
            period=_CUR_DURATION,
            value=Decimal("1000"),
        )
        # PL concept だが InstantPeriod を持つ（異常データ）— BS ヘルパーで構築
        instant_item = _make_bs_item(
            local_name="OperatingIncome",
            value=Decimal("500"),
            period=_CUR_INSTANT,
            context_id="CurrentYearInstant",
            label_ja="営業利益",
            label_en="Operating income",
        )
        stmts = build_statements((duration_item, instant_item))
        pl = stmts.income_statement()
        assert pl.period == _CUR_DURATION
        local_names = [item.local_name for item in pl.items]
        assert "NetSales" in local_names
        # InstantPeriod の OperatingIncome は除外される
        assert "OperatingIncome" not in local_names

    def test_cf_with_only_instant_facts_returns_empty(self) -> None:
        """CF に InstantPeriod しかない場合、空の statement と警告が返ること。"""
        # CF concept だが InstantPeriod — BS ヘルパーで構築
        item = _make_bs_item(
            local_name="NetCashProvidedByUsedInOperatingActivities",
            value=Decimal("1200000000"),
            period=_CUR_INSTANT,
            label_ja="営業活動によるキャッシュ・フロー",
            label_en="Net cash provided by operating activities",
        )
        stmts = build_statements((item,))
        with pytest.warns(EdinetWarning, match="periodType"):
            cf = stmts.cash_flow_statement()
        assert cf.items == ()
        assert cf.period is None

    def test_pl_multiple_durations_selects_latest_then_longest(self) -> None:
        """3 つの DurationPeriod で end_date DESC → start_date ASC のタイブレークが正しく動作すること。"""
        # end_date が最新で長い期間（累計）
        cumulative = DurationPeriod(
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
        )
        # end_date が最新で短い期間（四半期）
        quarterly = DurationPeriod(
            start_date=date(2025, 1, 1), end_date=date(2025, 3, 31)
        )
        # end_date が古い期間（前期累計）
        prior = DurationPeriod(
            start_date=date(2023, 4, 1), end_date=date(2024, 3, 31)
        )

        items = (
            _make_pl_item(
                local_name="NetSales",
                period=cumulative,
                value=Decimal("4000"),
                context_id="CumulativeDuration",
            ),
            _make_pl_item(
                local_name="NetSales",
                period=quarterly,
                value=Decimal("1000"),
                context_id="Q4Duration",
            ),
            _make_pl_item(
                local_name="NetSales",
                period=prior,
                value=Decimal("3500"),
                context_id="PriorDuration",
            ),
        )
        stmts = build_statements(items)
        pl = stmts.income_statement()
        # 最新 end_date（2025-03-31）の中で最長（start_date が最も古い）= cumulative
        assert pl.period == cumulative
        assert pl["NetSales"].value == Decimal("4000")


@pytest.mark.small
@pytest.mark.unit
class TestZeroAndEdgeValues:
    """数値エッジケースのテスト。"""

    def test_zero_decimal_value_included(self) -> None:
        """Decimal("0") の Fact が除外されないこと。"""
        item = _make_pl_item(
            local_name="NetSales",
            value=Decimal("0"),
        )
        stmts = build_statements((item,))
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl["NetSales"].value == Decimal("0")

    def test_negative_value_included(self) -> None:
        """Decimal("-100") の Fact が含まれること。"""
        item = _make_pl_item(
            local_name="OperatingIncome",
            value=Decimal("-100"),
            label_ja="営業利益",
            label_en="Operating income",
        )
        stmts = build_statements((item,))
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl["OperatingIncome"].value == Decimal("-100")


@pytest.mark.small
@pytest.mark.unit
class TestDimensionEdgeCases:
    """dimension フィルタの未テスト分岐。"""

    def test_is_total_false_with_non_consolidated_axis(self) -> None:
        """ConsolidatedOrNonConsolidatedAxis 以外の軸のみを持つ Fact が除外されること。"""
        # SegmentAxis のみ → _is_total() = False → 除外
        segment_only = _make_pl_item(
            local_name="NetSales",
            dimensions=_SEGMENT_DIM,
            context_id="CurrentYearDuration_SegmentA",
        )
        stmts = build_statements((segment_only,))
        pl = stmts.income_statement()
        assert len(pl.items) == 0

    def test_consolidated_with_additional_axis_not_total(self) -> None:
        """ConsolidatedAxis + SegmentAxis の場合、セグメント軸のため全社合計ではなく除外されること。"""
        # ConsolidatedMember + SegmentAxis の複合軸
        consolidated_segment_dim = (
            DimensionMember(
                axis=f"{{{_NS_JPPFS}}}ConsolidatedOrNonConsolidatedAxis",
                member=f"{{{_NS_JPPFS}}}ConsolidatedMember",
            ),
            DimensionMember(
                axis="{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis",
                member="{http://disclosure.edinet-fsa.go.jp/taxonomy/E00001/2025-11-01}SegmentAMember",
            ),
        )
        item = _make_pl_item(
            local_name="NetSales",
            dimensions=consolidated_segment_dim,
            context_id="CurrentYearDuration_Consol_SegA",
            value=Decimal("300"),
        )
        stmts = build_statements((item,))
        pl = stmts.income_statement()
        # SegmentAxis があるため _is_total() = False → 全社合計ではない → 除外
        assert len(pl.items) == 0


@pytest.mark.small
@pytest.mark.unit
class TestWarningPaths:
    """警告パスの未テスト分岐。"""

    def test_no_candidates_returns_empty_without_warning(self) -> None:
        """全 Fact が概念セット未定義の場合、空 statement が警告なしで返ること。"""
        # jppfs_cor だが概念セットに載っていない科目のみ
        item = _make_pl_item(
            local_name="SomeNonExistentConcept",
            label_ja="存在しない科目",
            label_en="Non-existent concept",
        )
        stmts = build_statements((item,))
        # 警告なしで空の statement が返る
        pl = stmts.income_statement()
        assert pl.items == ()
        assert len(pl.warnings_issued) == 0

    def test_period_type_mismatch_issues_warning(self) -> None:
        """BS 用 concept が DurationPeriod のみの場合、periodType 不一致の警告が出ること。"""
        # BS concept（Assets）を DurationPeriod で作成
        item = _make_pl_item(
            local_name="Assets",
            period=_CUR_DURATION,
            label_ja="資産合計",
            label_en="Total assets",
        )
        stmts = build_statements((item,))
        with pytest.warns(EdinetWarning, match="periodType"):
            bs = stmts.balance_sheet()
        assert bs.items == ()
        assert any("periodType" in w for w in bs.warnings_issued)


# ---------------------------------------------------------------------------
# Wave 3 追加: 会計基準統合テスト
# ---------------------------------------------------------------------------

_NS_JPIGP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor"
)


def _make_ifrs_pl_item(
    *,
    local_name: str = "RevenueIFRS",
    value: Decimal = Decimal("2000000000"),
    period: DurationPeriod | None = None,
    order: int = 0,
    label_ja: str = "売上収益",
    label_en: str = "Revenue",
) -> LineItem:
    """テスト用 IFRS PL LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{_NS_JPIGP}}}{local_name}",
        namespace_uri=_NS_JPIGP,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=period,
        entity_id="E90001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_ifrs_bs_item(
    *,
    local_name: str = "AssetsIFRS",
    value: Decimal = Decimal("10000000000"),
    period: InstantPeriod | None = None,
    order: int = 0,
    label_ja: str = "資産合計",
    label_en: str = "Total assets",
) -> LineItem:
    """テスト用 IFRS BS LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_INSTANT
    return LineItem(
        concept=f"{{{_NS_JPIGP}}}{local_name}",
        namespace_uri=_NS_JPIGP,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearInstant",
        period=period,
        entity_id="E90001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


@pytest.mark.small
@pytest.mark.unit
class TestStandardsIntegration:
    """会計基準統合テスト（Wave 3 Lane 1）。"""

    def test_s01_ifrs_pl_assembled(self) -> None:
        """T-S01: IFRS 概念で PL が組み立てられる。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_ifrs_pl_item(local_name="RevenueIFRS", order=0),
            _make_ifrs_pl_item(
                local_name="OperatingProfitLossIFRS",
                value=Decimal("500000000"),
                order=1,
                label_ja="営業利益",
                label_en="Operating profit",
            ),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.IFRS,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(
            _items=items, _detected_standard=detected,
        )
        pl = stmts.income_statement()
        assert pl.statement_type == StatementType.INCOME_STATEMENT
        assert len(pl.items) == 2
        local_names = [item.local_name for item in pl.items]
        assert "RevenueIFRS" in local_names
        assert "OperatingProfitLossIFRS" in local_names

    def test_s02_ifrs_bs_assembled(self) -> None:
        """T-S02: IFRS 概念で BS が組み立てられる。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_ifrs_bs_item(local_name="AssetsIFRS", order=0),
            _make_ifrs_bs_item(
                local_name="EquityIFRS",
                value=Decimal("3000000000"),
                order=1,
                label_ja="資本合計",
                label_en="Total equity",
            ),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.IFRS,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(
            _items=items, _detected_standard=detected,
        )
        bs = stmts.balance_sheet()
        assert bs.statement_type == StatementType.BALANCE_SHEET
        assert len(bs.items) == 2
        assert any(i.local_name == "AssetsIFRS" for i in bs.items)

    def test_s03_build_statements_backward_compat(self) -> None:
        """T-S03: build_statements(items) (facts なし) 後方互換。"""
        items = (_make_pl_item(local_name="NetSales"),)
        stmts = build_statements(items)
        assert stmts.detected_standard is None
        pl = stmts.income_statement()
        assert len(pl.items) == 1

    def test_s04_detected_jgaap_uses_jgaap_concepts(self) -> None:
        """T-S04: detected_standard=J-GAAP で J-GAAP 概念セットが使われる。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (_make_pl_item(local_name="NetSales"),)
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl.items[0].local_name == "NetSales"

    def test_s05_detected_ifrs_uses_ifrs_concepts(self) -> None:
        """T-S05: detected_standard=IFRS で IFRS 概念セットが使われる。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_ifrs_pl_item(local_name="RevenueIFRS"),
            # J-GAAP 概念は IFRS セットに含まれないため除外される
            _make_pl_item(local_name="OrdinaryIncome", label_ja="経常利益"),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.IFRS,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        assert "RevenueIFRS" in local_names
        # OrdinaryIncome は IFRS の概念セットに含まれないため除外
        assert "OrdinaryIncome" not in local_names

    def test_s07_unknown_standard_fallback_jgaap(self) -> None:
        """T-S07: 不明基準で J-GAAP フォールバック。"""
        items = (_make_pl_item(local_name="NetSales"),)
        # detected_standard=None は J-GAAP フォールバック
        stmts = build_statements(items)
        pl = stmts.income_statement()
        assert len(pl.items) == 1

    def test_s08_display_order_consistency(self) -> None:
        """T-S08: 表示順が display_order と一致。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        # J-GAAP: OperatingIncome(display_order=5) は NetSales(display_order=1) より後
        items = (
            _make_pl_item(
                local_name="OperatingIncome",
                order=99,  # XML order は無視される
                label_ja="営業利益",
                label_en="Operating income",
            ),
            _make_pl_item(local_name="NetSales", order=0),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        assert local_names.index("NetSales") < local_names.index("OperatingIncome")

    def test_s09_jmis_uses_ifrs_concepts(self) -> None:
        """T-S09: JMIS は IFRS 概念セットを使用する。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_ifrs_pl_item(local_name="RevenueIFRS"),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JMIS,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl.items[0].local_name == "RevenueIFRS"

    def test_s10_jmis_block_only_empty_with_warning(self) -> None:
        """T-S10: JMIS BLOCK_ONLY で空 + 警告。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (_make_pl_item(local_name="NetSales"),)
        detected = DetectedStandard(
            standard=AccountingStandard.JMIS,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.BLOCK_ONLY,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        with pytest.warns(EdinetWarning, match="BLOCK_ONLY"):
            pl = stmts.income_statement()
        assert pl.items == ()
        assert len(pl.warnings_issued) > 0

    def test_s13_same_statements_different_types(self) -> None:
        """T-S13: 同一 Statements から異なる StatementType を取得。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_pl_item(local_name="NetSales"),
            _make_bs_item(local_name="Assets"),
            _make_pl_item(
                local_name="NetCashProvidedByUsedInOperatingActivities",
                label_ja="営業CF",
                label_en="Operating CF",
            ),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(_items=items, _detected_standard=detected)
        pl = stmts.income_statement()
        bs = stmts.balance_sheet()
        cf = stmts.cash_flow_statement()
        assert pl.statement_type == StatementType.INCOME_STATEMENT
        assert bs.statement_type == StatementType.BALANCE_SHEET
        assert cf.statement_type == StatementType.CASH_FLOW_STATEMENT


# ---------------------------------------------------------------------------
# US-GAAP サマリーテスト (T-S06, T-S11, T-S12)
# ---------------------------------------------------------------------------

_NS_JPCRP_COR = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)


def _make_usgaap_raw_fact(
    *,
    local_name: str,
    context_ref: str = "CurrentYearDuration",
    value_raw: str = "1000000",
    unit_ref: str | None = "JPY",
    order: int = 0,
):  # noqa: ANN201
    """テスト用 US-GAAP RawFact を構築するヘルパー。"""
    from edinet.xbrl.parser import RawFact

    return RawFact(
        concept_qname=f"{{{_NS_JPCRP_COR}}}{local_name}",
        namespace_uri=_NS_JPCRP_COR,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=-6,
        value_raw=value_raw,
        is_nil=False,
        fact_id=None,
        xml_lang=None,
        source_line=1,
        order=order,
    )


def _make_usgaap_contexts() -> dict:
    """US-GAAP テスト用の contexts 辞書を構築するヘルパー。"""
    from edinet.xbrl.contexts import StructuredContext

    return {
        "CurrentYearDuration": StructuredContext(
            context_id="CurrentYearDuration",
            period=_CUR_DURATION,
            entity_id="E99999",
            dimensions=(),
            source_line=1,
            entity_scheme="http://disclosure.edinet-fsa.go.jp",
        ),
        "PriorYearDuration": StructuredContext(
            context_id="PriorYearDuration",
            period=_PREV_DURATION,
            entity_id="E99999",
            dimensions=(),
            source_line=2,
            entity_scheme="http://disclosure.edinet-fsa.go.jp",
        ),
        "CurrentYearInstant": StructuredContext(
            context_id="CurrentYearInstant",
            period=_CUR_INSTANT,
            entity_id="E99999",
            dimensions=(),
            source_line=3,
            entity_scheme="http://disclosure.edinet-fsa.go.jp",
        ),
        "PriorYearInstant": StructuredContext(
            context_id="PriorYearInstant",
            period=_PREV_INSTANT,
            entity_id="E99999",
            dimensions=(),
            source_line=4,
            entity_scheme="http://disclosure.edinet-fsa.go.jp",
        ),
    }


@pytest.mark.small
@pytest.mark.unit
class TestUSGAAPSummaryStatements:
    """US-GAAP サマリー経由の財務諸表組み立てテスト（T-S06, T-S11, T-S12）。"""

    def test_s06_usgaap_returns_summary_with_warning(self) -> None:
        """T-S06: US-GAAP でサマリー形式 + 警告メッセージ。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        facts = (
            _make_usgaap_raw_fact(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearDuration",
                value_raw="5000000000",
            ),
            _make_usgaap_raw_fact(
                local_name="OperatingIncomeLossUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearDuration",
                value_raw="1000000000",
                order=1,
            ),
            _make_usgaap_raw_fact(
                local_name="TotalAssetsUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearInstant",
                value_raw="20000000000",
                order=2,
            ),
        )
        contexts = _make_usgaap_contexts()
        detected = DetectedStandard(
            standard=AccountingStandard.US_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.BLOCK_ONLY,
        )
        stmts = Statements(
            _items=(),
            _detected_standard=detected,
            _facts=facts,
            _contexts=contexts,
        )

        # PL: revenue + operating_income が含まれる
        pl = stmts.income_statement()
        assert pl.statement_type == StatementType.INCOME_STATEMENT
        assert len(pl.items) >= 2
        pl_names = [item.local_name for item in pl.items]
        assert "RevenuesUSGAAPSummaryOfBusinessResults" in pl_names
        assert "OperatingIncomeLossUSGAAPSummaryOfBusinessResults" in pl_names
        assert len(pl.warnings_issued) > 0
        assert any("BLOCK_ONLY" in w for w in pl.warnings_issued)

        # BS: total_assets が含まれる
        bs = stmts.balance_sheet()
        assert bs.statement_type == StatementType.BALANCE_SHEET
        bs_names = [item.local_name for item in bs.items]
        assert "TotalAssetsUSGAAPSummaryOfBusinessResults" in bs_names

    def test_s11_usgaap_period_filtering(self) -> None:
        """T-S11: US-GAAP で period 指定時に該当期間のみ返される。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        facts = (
            # 当期の revenue
            _make_usgaap_raw_fact(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearDuration",
                value_raw="5000000000",
            ),
            # 前期の revenue
            _make_usgaap_raw_fact(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                context_ref="PriorYearDuration",
                value_raw="4000000000",
                order=1,
            ),
        )
        contexts = _make_usgaap_contexts()
        detected = DetectedStandard(
            standard=AccountingStandard.US_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.BLOCK_ONLY,
        )
        stmts = Statements(
            _items=(),
            _detected_standard=detected,
            _facts=facts,
            _contexts=contexts,
        )

        # 前期を明示指定
        pl = stmts.income_statement(period=_PREV_DURATION)
        assert pl.period == _PREV_DURATION
        assert len(pl.items) == 1
        assert pl.items[0].value == Decimal("4000000000")

    def test_s12_usgaap_latest_period_auto_select(self) -> None:
        """T-S12: US-GAAP で period=None 時に最新期間が自動選択される。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        facts = (
            # 当期の revenue
            _make_usgaap_raw_fact(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearDuration",
                value_raw="5000000000",
            ),
            # 前期の revenue
            _make_usgaap_raw_fact(
                local_name="RevenuesUSGAAPSummaryOfBusinessResults",
                context_ref="PriorYearDuration",
                value_raw="4000000000",
                order=1,
            ),
            # 当期の total_assets (instant)
            _make_usgaap_raw_fact(
                local_name="TotalAssetsUSGAAPSummaryOfBusinessResults",
                context_ref="CurrentYearInstant",
                value_raw="20000000000",
                order=2,
            ),
            # 前期の total_assets (instant)
            _make_usgaap_raw_fact(
                local_name="TotalAssetsUSGAAPSummaryOfBusinessResults",
                context_ref="PriorYearInstant",
                value_raw="18000000000",
                order=3,
            ),
        )
        contexts = _make_usgaap_contexts()
        detected = DetectedStandard(
            standard=AccountingStandard.US_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.BLOCK_ONLY,
        )
        stmts = Statements(
            _items=(),
            _detected_standard=detected,
            _facts=facts,
            _contexts=contexts,
        )

        # PL: 最新の DurationPeriod が自動選択される
        pl = stmts.income_statement()
        assert pl.period == _CUR_DURATION
        assert pl.items[0].value == Decimal("5000000000")

        # BS: 最新の InstantPeriod が自動選択される
        bs = stmts.balance_sheet()
        assert bs.period == _CUR_INSTANT
        assert bs.items[0].value == Decimal("20000000000")


# ---------------------------------------------------------------------------
# Wave 3 追加: industry_code パラメータテスト
# ---------------------------------------------------------------------------

# 銀行業の名前空間
_NS_BNK = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)


def _make_banking_pl_item(
    *,
    local_name: str = "OrdinaryIncomeBNK",
    value: Decimal = Decimal("500000000"),
    period: DurationPeriod | None = None,
    order: int = 0,
    label_ja: str = "経常収益",
    label_en: str = "Ordinary income",
) -> LineItem:
    """テスト用銀行業 PL LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{_NS_BNK}}}{local_name}",
        namespace_uri=_NS_BNK,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=period,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=order,
    )


@pytest.mark.small
@pytest.mark.unit
class TestIndustryCodeParam:
    """build_statements の industry_code パラメータテスト。"""

    def test_ic01_backward_compat_no_industry_code(self) -> None:
        """T-IC01: industry_code なしで既存動作と同一。"""
        items = (_make_pl_item(local_name="NetSales"),)
        stmts = build_statements(items)
        pl = stmts.income_statement()
        assert len(pl.items) == 1
        assert pl.items[0].local_name == "NetSales"

    def test_ic02_banking_pl_without_taxonomy_root(self) -> None:
        """T-IC02: industry_code="bk1" でも taxonomy_root なしでは sector 合算しない。

        レガシーフォールバック（taxonomy_root なし）では sector 概念を合算
        しないため、銀行業固有科目は known_concepts に含まれず除外される。
        taxonomy_root ありの場合は concept_sets が業種別セットを直接返す。
        """
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_banking_pl_item(local_name="OrdinaryIncomeBNK"),
            _make_pl_item(local_name="NetSales"),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(
            _items=items,
            _detected_standard=detected,
            _industry_code="bk1",
        )
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        # taxonomy_root なしでは sector 合算しないため一般事業科目のみ
        assert "NetSales" in local_names
        assert "OrdinaryIncomeBNK" not in local_names

    def test_ic03_build_statements_passes_industry_code(self) -> None:
        """T-IC03: build_statements() が industry_code を渡す。"""
        items = (
            _make_pl_item(local_name="NetSales"),
        )
        stmts = build_statements(items, industry_code="bk1")
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        assert "NetSales" in local_names

    def test_ic04_none_industry_code_excludes_banking(self) -> None:
        """T-IC04: industry_code=None では銀行業固有科目が除外される。"""
        from edinet.financial.standards.detect import (
            DetectedStandard,
            DetailLevel,
            DetectionMethod,
        )

        items = (
            _make_banking_pl_item(local_name="OrdinaryIncomeBNK"),
            _make_pl_item(local_name="NetSales"),
        )
        detected = DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.DEI,
            detail_level=DetailLevel.DETAILED,
        )
        stmts = Statements(
            _items=items,
            _detected_standard=detected,
            # industry_code=None（デフォルト）
        )
        pl = stmts.income_statement()
        local_names = [item.local_name for item in pl.items]
        # 一般事業科目のみ
        assert "NetSales" in local_names
        # 銀行業固有科目は一般事業概念セットに含まれないため除外
        assert "OrdinaryIncomeBNK" not in local_names


# ---------------------------------------------------------------------------
# industry_code 伝播テスト
# ---------------------------------------------------------------------------


class TestIndustryCodePropagation:
    """build_statements() の industry_code 引数の伝播テスト。"""

    def test_industry_code_propagated(self) -> None:
        """industry_code が Statements._industry_code に伝播すること。"""
        items = [
            _make_pl_item(local_name="NetSales"),
        ]
        stmts = build_statements(items, industry_code="bk1")
        assert stmts._industry_code == "bk1"

    def test_industry_code_none_by_default(self) -> None:
        """industry_code 省略時は _industry_code が None であること。"""
        items = [
            _make_pl_item(local_name="NetSales"),
        ]
        stmts = build_statements(items)
        assert stmts._industry_code is None


# ---------------------------------------------------------------------------
# T38-T39: taxonomy_root / industry_code の _build_for_type 伝搬テスト
# ---------------------------------------------------------------------------

_TAXONOMY_ROOT_STR = os.environ.get("EDINET_TAXONOMY_ROOT")
_skip_no_taxonomy = pytest.mark.skipif(
    _TAXONOMY_ROOT_STR is None,
    reason="EDINET_TAXONOMY_ROOT が未設定",
)


@_skip_no_taxonomy
class TestStatementsConceptSetsIntegration:
    """Statements と concept_sets の接続テスト。"""

    def test_t38_build_for_type_passes_taxonomy_root(self) -> None:
        """T38: taxonomy_root を渡した Statements が正常に組み立てられる。

        taxonomy_root ありの場合、concept_sets から導出された概念セットが
        使われることを、結果の FinancialStatement が空でないことで確認する。
        """
        items = [
            _make_pl_item(local_name="NetSales", value=Decimal("1000")),
            _make_pl_item(
                local_name="OperatingIncome", value=Decimal("200"),
                order=1, label_ja="営業利益", label_en="Operating income",
            ),
        ]
        stmts = build_statements(
            items,
            taxonomy_root=Path(_TAXONOMY_ROOT_STR),  # type: ignore[arg-type]
        )
        pl = stmts.income_statement()
        assert len(pl.items) > 0
        names = {it.local_name for it in pl.items}
        assert "NetSales" in names

    def test_t39_build_for_type_passes_industry_code(self) -> None:
        """T39: industry_code を渡した Statements が業種別概念で組み立てられる。

        banking 固有の概念（OrdinaryIncomeBNK）が taxonomy_root +
        industry_code='bk1' で正しく認識されることを確認する。
        """
        items = [
            _make_banking_pl_item(
                local_name="OrdinaryIncomeBNK", value=Decimal("500"),
            ),
        ]
        stmts = build_statements(
            items,
            taxonomy_root=Path(_TAXONOMY_ROOT_STR),  # type: ignore[arg-type]
            industry_code="bk1",
        )
        pl = stmts.income_statement()
        assert len(pl.items) > 0
        names = {it.local_name for it in pl.items}
        assert "OrdinaryIncomeBNK" in names


# ---------------------------------------------------------------------------
# Feature 1: strict モード
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestStrictMode:
    """strict モードのテスト。"""

    def test_strict_consolidated_only_request_nonconsolidated_data(self) -> None:
        """strict=True で連結要求、個別データのみ → 空 FS。"""
        non_cons = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearDuration_NonConsolidated",
        )
        stmts = build_statements((non_cons,))
        with pytest.warns(EdinetWarning, match="strict モード"):
            pl = stmts.income_statement(consolidated=True, strict=True)
        assert len(pl.items) == 0
        assert pl.consolidated is True
        assert any("strict" in w for w in pl.warnings_issued)

    def test_strict_nonconsolidated_request_consolidated_data(self) -> None:
        """strict=True で個別要求、連結データのみ → 空 FS。"""
        cons = _make_pl_item(local_name="NetSales", dimensions=())
        stmts = build_statements((cons,))
        with pytest.warns(EdinetWarning, match="strict モード"):
            pl = stmts.income_statement(consolidated=False, strict=True)
        assert len(pl.items) == 0
        assert pl.consolidated is False

    def test_strict_with_matching_data(self) -> None:
        """strict=True で連結データあり → 通常動作。"""
        cons = _make_pl_item(local_name="NetSales", dimensions=())
        stmts = build_statements((cons,))
        pl = stmts.income_statement(consolidated=True, strict=True)
        assert len(pl.items) == 1
        assert pl.consolidated is True

    def test_strict_false_preserves_fallback(self) -> None:
        """strict=False（デフォルト）→ 従来フォールバック動作。"""
        non_cons = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearDuration_NonConsolidated",
        )
        stmts = build_statements((non_cons,))
        with pytest.warns(EdinetWarning, match="連結データなし"):
            pl = stmts.income_statement(consolidated=True, strict=False)
        assert len(pl.items) == 1
        assert pl.consolidated is False

    def test_strict_bs(self) -> None:
        """strict モードが BS でも機能すること。"""
        non_cons = _make_bs_item(
            local_name="Assets",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="CurrentYearInstant_NonConsolidated",
        )
        stmts = build_statements((non_cons,))
        with pytest.warns(EdinetWarning, match="strict モード"):
            bs = stmts.balance_sheet(consolidated=True, strict=True)
        assert len(bs.items) == 0


# ---------------------------------------------------------------------------
# Feature 2: consolidated detection properties
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestConsolidatedDetection:
    """has_consolidated_data / has_non_consolidated_data のテスト。"""

    def test_consolidated_only(self) -> None:
        """連結データのみ → has_consolidated=True, has_non_consolidated=False。"""
        items = (_make_pl_item(dimensions=()),)
        stmts = build_statements(items)
        assert stmts.has_consolidated_data is True
        assert stmts.has_non_consolidated_data is False

    def test_non_consolidated_only(self) -> None:
        """個別データのみ → 逆。"""
        items = (_make_pl_item(dimensions=_NON_CONSOLIDATED_DIM),)
        stmts = build_statements(items)
        assert stmts.has_consolidated_data is False
        assert stmts.has_non_consolidated_data is True

    def test_mixed_data(self) -> None:
        """混合 → 両方 True。"""
        cons = _make_pl_item(local_name="NetSales", dimensions=())
        non_cons = _make_pl_item(
            local_name="NetSales",
            dimensions=_NON_CONSOLIDATED_DIM,
            context_id="NC",
            value=Decimal("500"),
        )
        stmts = build_statements((cons, non_cons))
        assert stmts.has_consolidated_data is True
        assert stmts.has_non_consolidated_data is True

    def test_empty_items(self) -> None:
        """空 → 両方 False。"""
        stmts = build_statements(())
        assert stmts.has_consolidated_data is False
        assert stmts.has_non_consolidated_data is False


# ---------------------------------------------------------------------------
# CF instant 吸収テスト
# ---------------------------------------------------------------------------

# CF 用 instant 期間
_CF_BEGIN_INSTANT = InstantPeriod(instant=date(2024, 3, 31))  # start_date - 1日
_CF_END_INSTANT = InstantPeriod(instant=date(2025, 3, 31))    # end_date

# preferredLabel ロール URI
_ROLE_PERIOD_START = "http://www.xbrl.org/2003/role/periodStartLabel"
_ROLE_PERIOD_END = "http://www.xbrl.org/2003/role/periodEndLabel"


def _make_cf_duration_item(
    *,
    local_name: str = "NetCashProvidedByUsedInOperatingActivities",
    value: Decimal = Decimal("1200000000"),
    period: DurationPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearDuration",
    label_ja: str = "営業活動によるキャッシュ・フロー",
    label_en: str = "Net cash provided by operating activities",
) -> LineItem:
    """テスト用 CF (DurationPeriod) LineItem を構築するヘルパー。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{_NS_JPPFS}}}{local_name}",
        namespace_uri=_NS_JPPFS,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_cf_instant_item(
    *,
    local_name: str = "CashAndCashEquivalents",
    value: Decimal = Decimal("500000000"),
    period: InstantPeriod | None = None,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    context_id: str = "CurrentYearInstant",
    label_ja: str = "現金及び現金同等物",
    label_en: str = "Cash and cash equivalents",
    is_nil: bool = False,
) -> LineItem:
    """テスト用 CF instant LineItem を構築するヘルパー。"""
    if period is None:
        period = _CF_END_INSTANT
    return LineItem(
        concept=f"{{{_NS_JPPFS}}}{local_name}",
        namespace_uri=_NS_JPPFS,
        local_name=local_name,
        label_ja=_make_label(label_ja, "ja"),
        label_en=_make_label(label_en, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=is_nil,
        source_line=1,
        order=order,
    )


def _make_cf_concept_set() -> object:
    """CF 用テスト ConceptSet を構築するヘルパー。"""
    from edinet.xbrl.taxonomy import ConceptEntry, ConceptSet
    from edinet.xbrl.taxonomy.concept_sets import StatementCategory

    return ConceptSet(
        role_uri="http://test/role/cf",
        category=StatementCategory.CASH_FLOW_STATEMENT,
        is_consolidated=True,
        concepts=(
            ConceptEntry("NetCashProvidedByUsedInOperatingActivities", 1.0, False, False, 0, ""),
            ConceptEntry("CashAndCashEquivalents", 6.0, False, False, 0, "", preferred_label=_ROLE_PERIOD_START),
            ConceptEntry("CashAndCashEquivalents", 7.0, False, False, 0, "", preferred_label=_ROLE_PERIOD_END),
        ),
        source_info="test",
    )


def _absorb(fs, all_items, *, concept_set=None):
    """_absorb_cf_instant_balances のテスト用ショートカット。"""
    from edinet.financial.statements import _absorb_cf_instant_balances

    if concept_set is None:
        concept_set = _make_cf_concept_set()
    return _absorb_cf_instant_balances(
        fs, all_items, concept_set=concept_set, taxonomy_root=None,
    )


def _build_cf_fs(items, *, consolidated=True, period=None):
    """テスト用 CF FinancialStatement を組み立てるヘルパー。"""
    from edinet.models.financial import FinancialStatement

    if period is None:
        period = _CUR_DURATION
    return FinancialStatement(
        statement_type=StatementType.CASH_FLOW_STATEMENT,
        period=period,
        items=tuple(items),
        consolidated=consolidated,
        entity_id="E00001",
        warnings_issued=(),
    )


@pytest.mark.small
@pytest.mark.unit
class TestCFInstantAbsorption:
    """CF 期首/期末残高（instant）吸収のテスト。"""

    def test_basic(self) -> None:
        """duration CF + instant 期首/期末 → 両方挿入、ラベル検証。"""
        cf_item = _make_cf_duration_item()
        begin_item = _make_cf_instant_item(
            value=Decimal("300000000"),
            period=_CF_BEGIN_INSTANT,
            context_id="PriorYearInstant",
        )
        end_item = _make_cf_instant_item(
            value=Decimal("500000000"),
            period=_CF_END_INSTANT,
            context_id="CurrentYearInstant",
        )
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, begin_item, end_item))

        assert len(result.items) == 3
        # 期首は先頭
        assert result.items[0].local_name == "CashAndCashEquivalents"
        assert result.items[0].value == Decimal("300000000")
        # 期末は末尾
        assert result.items[-1].local_name == "CashAndCashEquivalents"
        assert result.items[-1].value == Decimal("500000000")
        # 中央は元の CF 科目
        assert result.items[1].local_name == "NetCashProvidedByUsedInOperatingActivities"

    def test_period_matching(self) -> None:
        """start-1日=期首, end=期末, それ以外は除外。"""
        cf_item = _make_cf_duration_item()
        begin_item = _make_cf_instant_item(
            value=Decimal("300"), period=_CF_BEGIN_INSTANT, context_id="Begin",
        )
        end_item = _make_cf_instant_item(
            value=Decimal("500"), period=_CF_END_INSTANT, context_id="End",
        )
        other_item = _make_cf_instant_item(
            value=Decimal("999"),
            period=InstantPeriod(instant=date(2023, 3, 31)),
            context_id="Other",
        )
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, begin_item, end_item, other_item))

        cash_values = [
            i.value for i in result.items
            if i.local_name == "CashAndCashEquivalents"
        ]
        assert len(cash_values) == 2
        assert Decimal("300") in cash_values
        assert Decimal("500") in cash_values
        assert Decimal("999") not in cash_values

    def test_no_instant(self) -> None:
        """instant なし → 変更なし。"""
        cf_item = _make_cf_duration_item()
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item,))
        assert len(result.items) == 1

    def test_only_end(self) -> None:
        """期末のみ → 末尾のみ追加。"""
        cf_item = _make_cf_duration_item()
        end_item = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT)
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, end_item))

        assert len(result.items) == 2
        assert result.items[0].local_name == "NetCashProvidedByUsedInOperatingActivities"
        assert result.items[1].local_name == "CashAndCashEquivalents"

    def test_only_beginning(self) -> None:
        """期首のみ → 先頭のみ追加。"""
        cf_item = _make_cf_duration_item()
        begin_item = _make_cf_instant_item(
            value=Decimal("300"), period=_CF_BEGIN_INSTANT, context_id="Prior",
        )
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, begin_item))

        assert len(result.items) == 2
        assert result.items[0].local_name == "CashAndCashEquivalents"
        assert result.items[1].local_name == "NetCashProvidedByUsedInOperatingActivities"

    def test_consolidated_filter(self) -> None:
        """連結 CF → 連結 instant のみ吸収。"""
        cf_item = _make_cf_duration_item()
        cons_end = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT)
        non_cons_end = _make_cf_instant_item(
            value=Decimal("200"), period=_CF_END_INSTANT,
            dimensions=_NON_CONSOLIDATED_DIM, context_id="NC",
        )
        fs = _build_cf_fs([cf_item], consolidated=True)
        result = _absorb(fs, (cf_item, cons_end, non_cons_end))

        cash_items = [i for i in result.items if i.local_name == "CashAndCashEquivalents"]
        assert len(cash_items) == 1
        assert cash_items[0].value == Decimal("500")

    def test_non_consolidated(self) -> None:
        """個別 CF → 個別 instant のみ吸収。"""
        cf_item = _make_cf_duration_item(
            dimensions=_NON_CONSOLIDATED_DIM, context_id="NC_D",
        )
        non_cons_end = _make_cf_instant_item(
            value=Decimal("200"), period=_CF_END_INSTANT,
            dimensions=_NON_CONSOLIDATED_DIM, context_id="NC_I",
        )
        cons_end = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT)
        fs = _build_cf_fs([cf_item], consolidated=False)
        result = _absorb(fs, (cf_item, non_cons_end, cons_end))

        cash_items = [i for i in result.items if i.local_name == "CashAndCashEquivalents"]
        assert len(cash_items) == 1
        assert cash_items[0].value == Decimal("200")

    def test_dimension_filter(self) -> None:
        """セグメント付き instant → 除外。"""
        cf_item = _make_cf_duration_item()
        segment_end = _make_cf_instant_item(
            value=Decimal("100"), period=_CF_END_INSTANT,
            dimensions=_SEGMENT_DIM, context_id="Seg",
        )
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, segment_end))
        assert len(result.items) == 1

    def test_dedup(self) -> None:
        """同一 concept 同一 instant 複数 → 先頭1件。"""
        cf_item = _make_cf_duration_item()
        end1 = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT, context_id="E1")
        end2 = _make_cf_instant_item(value=Decimal("600"), period=_CF_END_INSTANT, context_id="E2")
        fs = _build_cf_fs([cf_item])
        result = _absorb(fs, (cf_item, end1, end2))

        cash_items = [i for i in result.items if i.local_name == "CashAndCashEquivalents"]
        assert len(cash_items) == 1
        assert cash_items[0].value == Decimal("500")

    def test_no_concept_set_skips(self) -> None:
        """concept_set=None → 吸収スキップ。"""
        from edinet.financial.statements import _absorb_cf_instant_balances

        cf_item = _make_cf_duration_item()
        end_item = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT)
        fs = _build_cf_fs([cf_item])
        result = _absorb_cf_instant_balances(
            fs, (cf_item, end_item), concept_set=None, taxonomy_root=None,
        )
        assert len(result.items) == 1  # 吸収されない

    def test_empty_cf(self) -> None:
        """空 CF → 変更なし。"""
        fs = _build_cf_fs([])
        end_item = _make_cf_instant_item(value=Decimal("500"), period=_CF_END_INSTANT)
        result = _absorb(fs, (end_item,))
        assert len(result.items) == 0

    def test_december_fiscal_year(self) -> None:
        """12月決算 → 正しく期首/期末対応。"""
        dec_duration = DurationPeriod(
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        )
        dec_begin = InstantPeriod(instant=date(2023, 12, 31))
        dec_end = InstantPeriod(instant=date(2024, 12, 31))

        cf_item = _make_cf_duration_item(period=dec_duration)
        begin_item = _make_cf_instant_item(value=Decimal("300"), period=dec_begin, context_id="P")
        end_item = _make_cf_instant_item(value=Decimal("700"), period=dec_end, context_id="C")
        fs = _build_cf_fs([cf_item], period=dec_duration)
        result = _absorb(fs, (cf_item, begin_item, end_item))

        assert len(result.items) == 3
        assert result.items[0].value == Decimal("300")
        assert result.items[-1].value == Decimal("700")


# ===========================================================================
# DEFACTO-2: Statements dict-like プロトコル
# ===========================================================================


class TestStatementsDictProtocol:
    """Statements の dict-like プロトコル（DEFACTO-2）のテスト。"""

    @pytest.fixture()
    def stmts(self) -> Statements:
        """テスト用 Statements を構築する。"""
        items = (
            _make_pl_item(
                local_name="NetSales",
                label_ja="売上高",
                label_en="Net sales",
                value=Decimal("1000"),
            ),
            _make_pl_item(
                local_name="OperatingIncome",
                label_ja="営業利益",
                label_en="Operating income",
                value=Decimal("200"),
            ),
            _make_bs_item(
                local_name="Assets",
                label_ja="資産合計",
                label_en="Total assets",
                value=Decimal("5000"),
            ),
        )
        return Statements(_items=items)

    def test_getitem_by_label_ja(self, stmts: Statements) -> None:
        """日本語ラベルで検索できること。"""
        item = stmts["売上高"]
        assert item.local_name == "NetSales"

    def test_getitem_by_label_en(self, stmts: Statements) -> None:
        """英語ラベルで検索できること。"""
        item = stmts["Operating income"]
        assert item.local_name == "OperatingIncome"

    def test_getitem_by_local_name(self, stmts: Statements) -> None:
        """local_name で検索できること。"""
        item = stmts["Assets"]
        assert item.label_ja.text == "資産合計"

    def test_getitem_not_found_raises_keyerror(self, stmts: Statements) -> None:
        """存在しないキーで KeyError が発生すること。"""
        with pytest.raises(KeyError):
            stmts["存在しない科目"]

    def test_get_found(self, stmts: Statements) -> None:
        """get() で見つかった場合に LineItem を返すこと。"""
        item = stmts.get("営業利益")
        assert item is not None
        assert item.local_name == "OperatingIncome"

    def test_get_not_found_returns_default(self, stmts: Statements) -> None:
        """get() で見つからない場合に default を返すこと。"""
        result = stmts.get("存在しない科目")
        assert result is None

    def test_get_not_found_custom_default(self, stmts: Statements) -> None:
        """get() でカスタムデフォルトを返すこと。"""
        sentinel = _make_pl_item(local_name="Sentinel", label_ja="番兵", label_en="Sentinel")
        result = stmts.get("存在しない科目", sentinel)
        assert result is sentinel

    def test_contains_true(self, stmts: Statements) -> None:
        """in 演算子で存在確認できること。"""
        assert "売上高" in stmts
        assert "Net sales" in stmts
        assert "NetSales" in stmts

    def test_contains_false(self, stmts: Statements) -> None:
        """in 演算子で存在しない場合 False を返すこと。"""
        assert "存在しない科目" not in stmts

    def test_contains_non_string(self, stmts: Statements) -> None:
        """in 演算子で非文字列キーは False を返すこと。"""
        assert 123 not in stmts  # type: ignore[operator]

    def test_len(self, stmts: Statements) -> None:
        """len() で全科目数を返すこと。"""
        assert len(stmts) == 3

    def test_iter(self, stmts: Statements) -> None:
        """for ループで全科目を順に返すこと。"""
        names = [item.local_name for item in stmts]
        assert names == ["NetSales", "OperatingIncome", "Assets"]

    def test_search_partial_match_ja(self, stmts: Statements) -> None:
        """日本語部分一致で検索できること。"""
        results = stmts.search("利益")
        assert len(results) == 1
        assert results[0].local_name == "OperatingIncome"

    def test_search_partial_match_en(self, stmts: Statements) -> None:
        """英語部分一致で検索できること（大文字小文字無視）。"""
        results = stmts.search("income")
        assert len(results) == 1
        assert results[0].local_name == "OperatingIncome"

    def test_search_partial_match_local_name(self, stmts: Statements) -> None:
        """local_name 部分一致で検索できること（大文字小文字無視）。"""
        results = stmts.search("sales")
        assert len(results) == 1
        assert results[0].local_name == "NetSales"

    def test_search_no_match(self, stmts: Statements) -> None:
        """一致なしで空リストを返すこと。"""
        results = stmts.search("XXXXXXXXXX")
        assert results == []

    def test_search_multiple_matches(self, stmts: Statements) -> None:
        """複数一致で全てを返すこと。"""
        # "合計" is in "資産合計", "total" is in "Total assets"
        results = stmts.search("合計")
        assert len(results) == 1
        assert results[0].local_name == "Assets"

    def test_empty_statements(self) -> None:
        """空の Statements で各メソッドが正しく動作すること。"""
        stmts = Statements(_items=())
        assert len(stmts) == 0
        assert list(stmts) == []
        assert "何か" not in stmts
        assert stmts.get("何か") is None
        assert stmts.search("何か") == []
        with pytest.raises(KeyError):
            stmts["何か"]
