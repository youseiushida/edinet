"""test_diff.py — diff_revisions() と diff_periods() のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.exceptions import EdinetWarning
from edinet.financial.diff import (
    DiffItem,
    DiffResult,
    _compute_difference,
    _values_equal,
    diff_periods,
    diff_revisions,
)
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

_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)

_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_PREV_DURATION = DurationPeriod(
    start_date=date(2023, 4, 1), end_date=date(2024, 3, 31)
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


def _make_line_item(
    *,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    label_ja: str = "売上高",
    label_en: str = "Net sales",
    order: int = 0,
    namespace_uri: str = _NS_JPPFS,
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


def _make_statements(*items: LineItem) -> Statements:
    """テスト用 Statements を構築するヘルパー。"""
    return Statements(_items=items)


def _make_financial_statement(
    *items: LineItem,
    statement_type: StatementType = StatementType.INCOME_STATEMENT,
    period: DurationPeriod | InstantPeriod | None = None,
) -> FinancialStatement:
    """テスト用 FinancialStatement を構築するヘルパー。"""
    if period is None:
        period = items[0].period if items else None
    return FinancialStatement(
        statement_type=statement_type,
        period=period,
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


# ---------------------------------------------------------------------------
# TestHelpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """_values_equal / _compute_difference のテスト。"""

    def test_compute_difference_decimals(self) -> None:
        """Decimal 同士の差額が正しく計算される。"""
        assert _compute_difference(Decimal("100"), Decimal("300")) == Decimal(
            "200"
        )
        assert _compute_difference(Decimal("500"), Decimal("200")) == Decimal(
            "-300"
        )

    def test_compute_difference_mixed_types(self) -> None:
        """型が異なる場合 None が返る。"""
        assert _compute_difference("text", Decimal("100")) is None
        assert _compute_difference(Decimal("100"), None) is None
        assert _compute_difference(None, None) is None
        assert _compute_difference("old", "new") is None

    def test_values_equal_decimals(self) -> None:
        """Decimal 同士の等価判定。"""
        assert _values_equal(Decimal("1000"), Decimal("1000")) is True
        assert _values_equal(Decimal("1000"), Decimal("2000")) is False
        # Decimal の精度の違い（同値）
        assert _values_equal(Decimal("1000"), Decimal("1000.000")) is True

    def test_values_equal_none(self) -> None:
        """None 同士が等しいと判定される。"""
        assert _values_equal(None, None) is True
        assert _values_equal(None, Decimal("0")) is False
        assert _values_equal(Decimal("0"), None) is False

    def test_values_equal_str(self) -> None:
        """str 同士の等価判定。"""
        assert _values_equal("abc", "abc") is True
        assert _values_equal("abc", "xyz") is False

    def test_values_equal_type_mismatch(self) -> None:
        """型が異なる場合は不等。"""
        assert _values_equal(Decimal("0"), "0") is False
        assert _values_equal("100", Decimal("100")) is False


# ---------------------------------------------------------------------------
# TestDiffResult
# ---------------------------------------------------------------------------


class TestDiffResult:
    """DiffResult のプロパティとメソッドのテスト。"""

    def test_has_changes_true(self) -> None:
        """変更がある場合 has_changes が True。"""
        item = _make_line_item()
        result = DiffResult(
            added=(item,), removed=(), modified=(), unchanged_count=0
        )
        assert result.has_changes is True

    def test_has_changes_false(self) -> None:
        """変更がない場合 has_changes が False。"""
        result = DiffResult(
            added=(), removed=(), modified=(), unchanged_count=5
        )
        assert result.has_changes is False

    def test_total_compared(self) -> None:
        """total_compared が全科目数を返す。"""
        item = _make_line_item()
        diff_item = DiffItem(
            concept="X",
            label_ja=_make_label("X"),
            label_en=_make_label("X", "en"),
            old_value=Decimal("1"),
            new_value=Decimal("2"),
            difference=Decimal("1"),
        )
        result = DiffResult(
            added=(item,),
            removed=(item,),
            modified=(diff_item,),
            unchanged_count=10,
        )
        assert result.total_compared == 13  # 1 + 1 + 1 + 10

    def test_summary(self) -> None:
        """summary() が正しいフォーマットの文字列を返す。"""
        item = _make_line_item()
        result = DiffResult(
            added=(item, item),
            removed=(item,),
            modified=(),
            unchanged_count=50,
        )
        assert result.summary() == "追加: 2, 削除: 1, 変更: 0, 変更なし: 50"


# ---------------------------------------------------------------------------
# TestDiffRevisions
# ---------------------------------------------------------------------------


class TestDiffRevisions:
    """diff_revisions() のテスト。"""

    def test_identical_statements(self) -> None:
        """同一の Statements 同士で変更なし。"""
        items = (
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
            _make_line_item(
                local_name="OperatingIncome", value=Decimal("200"),
                label_ja="営業利益", label_en="Operating income",
            ),
        )
        original = _make_statements(*items)
        corrected = _make_statements(*items)

        result = diff_revisions(original, corrected)

        assert result.has_changes is False
        assert result.unchanged_count == 2
        assert len(result.added) == 0
        assert len(result.removed) == 0
        assert len(result.modified) == 0

    def test_single_modified_value(self) -> None:
        """1 科目の値が変更された場合 modified に分類される。"""
        original = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
        )
        corrected = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1500")),
        )

        result = diff_revisions(original, corrected)

        assert len(result.modified) == 1
        assert result.modified[0].concept == "NetSales"
        assert result.modified[0].old_value == Decimal("1000")
        assert result.modified[0].new_value == Decimal("1500")
        assert result.unchanged_count == 0

    def test_added_item(self) -> None:
        """訂正後にのみ存在する科目が added に分類される。"""
        original = _make_statements(
            _make_line_item(local_name="NetSales"),
        )
        new_item = _make_line_item(
            local_name="ExtraordinaryIncome",
            value=Decimal("500"),
            label_ja="特別利益",
            label_en="Extraordinary income",
        )
        corrected = _make_statements(
            _make_line_item(local_name="NetSales"),
            new_item,
        )

        result = diff_revisions(original, corrected)

        assert len(result.added) == 1
        assert result.added[0].local_name == "ExtraordinaryIncome"

    def test_removed_item(self) -> None:
        """訂正前にのみ存在する科目が removed に分類される。"""
        removed_item = _make_line_item(
            local_name="OldConcept",
            value=Decimal("100"),
            label_ja="旧科目",
            label_en="Old concept",
        )
        original = _make_statements(
            _make_line_item(local_name="NetSales"),
            removed_item,
        )
        corrected = _make_statements(
            _make_line_item(local_name="NetSales"),
        )

        result = diff_revisions(original, corrected)

        assert len(result.removed) == 1
        assert result.removed[0].local_name == "OldConcept"

    def test_mixed_changes(self) -> None:
        """added + removed + modified + unchanged の混合ケース。"""
        original = _make_statements(
            _make_line_item(
                local_name="NetSales", value=Decimal("1000"),
            ),
            _make_line_item(
                local_name="CostOfSales", value=Decimal("600"),
                label_ja="売上原価", label_en="Cost of sales",
            ),
            _make_line_item(
                local_name="OldItem", value=Decimal("50"),
                label_ja="旧科目", label_en="Old item",
            ),
        )
        corrected = _make_statements(
            _make_line_item(
                local_name="NetSales", value=Decimal("1000"),
            ),
            _make_line_item(
                local_name="CostOfSales", value=Decimal("700"),
                label_ja="売上原価", label_en="Cost of sales",
            ),
            _make_line_item(
                local_name="NewItem", value=Decimal("30"),
                label_ja="新科目", label_en="New item",
            ),
        )

        result = diff_revisions(original, corrected)

        assert result.unchanged_count == 1  # NetSales
        assert len(result.modified) == 1  # CostOfSales
        assert len(result.removed) == 1  # OldItem
        assert len(result.added) == 1  # NewItem

    def test_difference_calculated(self) -> None:
        """数値科目の DiffItem.difference が正しく計算される。"""
        original = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
        )
        corrected = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1500")),
        )

        result = diff_revisions(original, corrected)

        assert result.modified[0].difference == Decimal("500")

    def test_text_value_change(self) -> None:
        """テキスト科目の変更が検出される。"""
        original = _make_statements(
            _make_line_item(
                local_name="BusinessDescription",
                value="旧テキスト",
                label_ja="事業の内容",
                label_en="Business description",
                unit_ref=None,
            ),
        )
        corrected = _make_statements(
            _make_line_item(
                local_name="BusinessDescription",
                value="新テキスト",
                label_ja="事業の内容",
                label_en="Business description",
                unit_ref=None,
            ),
        )

        result = diff_revisions(original, corrected)

        assert len(result.modified) == 1
        assert result.modified[0].old_value == "旧テキスト"
        assert result.modified[0].new_value == "新テキスト"
        assert result.modified[0].difference is None

    def test_nil_to_value(self) -> None:
        """None → Decimal の変更が modified に分類される。"""
        original = _make_statements(
            _make_line_item(
                local_name="NetSales", value=None, is_nil=True,
            ),
        )
        corrected = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
        )

        result = diff_revisions(original, corrected)

        assert len(result.modified) == 1
        assert result.modified[0].old_value is None
        assert result.modified[0].new_value == Decimal("1000")
        assert result.modified[0].difference is None

    def test_value_to_nil(self) -> None:
        """Decimal → None の変更が modified に分類される。"""
        original = _make_statements(
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
        )
        corrected = _make_statements(
            _make_line_item(
                local_name="NetSales", value=None, is_nil=True,
            ),
        )

        result = diff_revisions(original, corrected)

        assert len(result.modified) == 1
        assert result.modified[0].old_value == Decimal("1000")
        assert result.modified[0].new_value is None

    def test_nil_to_nil_unchanged(self) -> None:
        """None → None は unchanged に分類される。"""
        original = _make_statements(
            _make_line_item(
                local_name="NetSales", value=None, is_nil=True,
            ),
        )
        corrected = _make_statements(
            _make_line_item(
                local_name="NetSales", value=None, is_nil=True,
            ),
        )

        result = diff_revisions(original, corrected)

        assert result.has_changes is False
        assert result.unchanged_count == 1

    def test_context_id_matching(self) -> None:
        """context_id が異なる同名科目は別科目として扱われる。"""
        original = _make_statements(
            _make_line_item(
                local_name="NetSales",
                context_id="CurrentYearDuration",
                value=Decimal("1000"),
            ),
        )
        corrected = _make_statements(
            _make_line_item(
                local_name="NetSales",
                context_id="Prior1YearDuration",
                period=_PREV_DURATION,
                value=Decimal("800"),
            ),
        )

        result = diff_revisions(original, corrected)

        # 同名だが context_id が異なるため別科目
        assert len(result.removed) == 1  # CurrentYearDuration の NetSales
        assert len(result.added) == 1  # Prior1YearDuration の NetSales
        assert result.unchanged_count == 0

    def test_empty_statements(self) -> None:
        """空の Statements 同士で空の DiffResult が返る。"""
        original = _make_statements()
        corrected = _make_statements()

        result = diff_revisions(original, corrected)

        assert result.has_changes is False
        assert result.unchanged_count == 0
        assert result.total_compared == 0


# ---------------------------------------------------------------------------
# TestDiffPeriods
# ---------------------------------------------------------------------------


class TestDiffPeriods:
    """diff_periods() のテスト。"""

    def test_identical_periods(self) -> None:
        """同一の FinancialStatement 同士で変更なし。"""
        items = (
            _make_line_item(local_name="NetSales", value=Decimal("1000")),
            _make_line_item(
                local_name="OperatingIncome", value=Decimal("200"),
                label_ja="営業利益", label_en="Operating income",
            ),
        )
        prior = _make_financial_statement(*items)
        current = _make_financial_statement(*items)

        result = diff_periods(prior, current)

        assert result.has_changes is False
        assert result.unchanged_count == 2

    def test_value_increase(self) -> None:
        """売上高増加が modified + 正の difference で検出される。"""
        prior = _make_financial_statement(
            _make_line_item(
                local_name="NetSales",
                context_id="Prior1YearDuration",
                period=_PREV_DURATION,
                value=Decimal("1000"),
            ),
        )
        current = _make_financial_statement(
            _make_line_item(
                local_name="NetSales",
                context_id="CurrentYearDuration",
                value=Decimal("1500"),
            ),
        )

        result = diff_periods(prior, current)

        assert len(result.modified) == 1
        assert result.modified[0].difference == Decimal("500")

    def test_value_decrease(self) -> None:
        """利益減少が modified + 負の difference で検出される。"""
        prior = _make_financial_statement(
            _make_line_item(
                local_name="OperatingIncome",
                context_id="Prior1YearDuration",
                period=_PREV_DURATION,
                value=Decimal("500"),
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )
        current = _make_financial_statement(
            _make_line_item(
                local_name="OperatingIncome",
                context_id="CurrentYearDuration",
                value=Decimal("300"),
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )

        result = diff_periods(prior, current)

        assert len(result.modified) == 1
        assert result.modified[0].difference == Decimal("-200")

    def test_new_concept_in_current(self) -> None:
        """当期にのみ存在する科目が added に分類される。"""
        prior = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
        )
        current = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
            _make_line_item(
                local_name="NewRevenue",
                value=Decimal("100"),
                label_ja="新収益",
                label_en="New revenue",
            ),
        )

        result = diff_periods(prior, current)

        assert len(result.added) == 1
        assert result.added[0].local_name == "NewRevenue"
        assert result.unchanged_count == 1

    def test_removed_concept_in_current(self) -> None:
        """前期にのみ存在する科目が removed に分類される。"""
        prior = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
            _make_line_item(
                local_name="DiscontinuedOps",
                value=Decimal("50"),
                label_ja="廃止事業",
                label_en="Discontinued operations",
            ),
        )
        current = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
        )

        result = diff_periods(prior, current)

        assert len(result.removed) == 1
        assert result.removed[0].local_name == "DiscontinuedOps"

    def test_local_name_matching(self) -> None:
        """local_name ベースで前期/当期が照合される（context_id は無視）。"""
        prior = _make_financial_statement(
            _make_line_item(
                local_name="NetSales",
                context_id="Prior1YearDuration",
                period=_PREV_DURATION,
                value=Decimal("1000"),
            ),
        )
        current = _make_financial_statement(
            _make_line_item(
                local_name="NetSales",
                context_id="CurrentYearDuration",
                value=Decimal("1000"),
            ),
        )

        result = diff_periods(prior, current)

        # context_id が異なっても local_name が同じなら照合される
        assert result.has_changes is False
        assert result.unchanged_count == 1

    def test_empty_prior(self) -> None:
        """空の prior で全 current が added。"""
        prior = _make_financial_statement()
        current = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
            _make_line_item(
                local_name="OperatingIncome",
                label_ja="営業利益",
                label_en="Operating income",
            ),
        )

        result = diff_periods(prior, current)

        assert len(result.added) == 2
        assert len(result.removed) == 0
        assert result.unchanged_count == 0

    def test_empty_current(self) -> None:
        """空の current で全 prior が removed。"""
        prior = _make_financial_statement(
            _make_line_item(local_name="NetSales"),
        )
        current = _make_financial_statement()

        result = diff_periods(prior, current)

        assert len(result.removed) == 1
        assert len(result.added) == 0

    def test_both_empty(self) -> None:
        """両方空で空の DiffResult。"""
        prior = _make_financial_statement()
        current = _make_financial_statement()

        result = diff_periods(prior, current)

        assert result.has_changes is False
        assert result.unchanged_count == 0
        assert result.total_compared == 0

    def test_duplicate_local_name_warns(self) -> None:
        """同一 local_name が複数存在する場合に警告が発行される。"""
        prior = _make_financial_statement(
            _make_line_item(
                local_name="NetSales",
                value=Decimal("1000"),
                context_id="Prior1YearDuration",
                period=_PREV_DURATION,
                order=0,
            ),
            _make_line_item(
                local_name="NetSales",
                value=Decimal("2000"),
                context_id="Prior1YearDuration_NonConsolidated",
                period=_PREV_DURATION,
                order=1,
            ),
        )
        current = _make_financial_statement(
            _make_line_item(local_name="NetSales", value=Decimal("1500")),
        )

        with pytest.warns(EdinetWarning, match="同一 local_name"):
            result = diff_periods(prior, current)

        # 先頭（value=1000）が使われるので差額は 500
        assert len(result.modified) == 1
        assert result.modified[0].difference == Decimal("500")
