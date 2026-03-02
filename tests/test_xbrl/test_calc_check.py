"""計算リンクベースバリデーション (calc_check) のテスト。

Wave 6 Lane 5: validate_calculations() の単体テスト群。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

import pytest

from edinet.models.financial import FinancialStatement, LineItem, StatementType
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.linkbase.calculation import (
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.xbrl.validation.calc_check import (
    ValidationIssue,
    _build_fact_index,
    _compute_tolerance,
    validate_calculations,
)

# ---------------------------------------------------------------------------
# テスト用定数・ヘルパー
# ---------------------------------------------------------------------------

ROLE = "http://example.com/role/test"
ROLE_B = "http://example.com/role/test_b"
_NS = "http://example.com/ns"
_CUR_DURATION = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))


def _label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用ラベルを生成する。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _item(
    local_name: str,
    value: Decimal | str | None,
    decimals: int | Literal["INF"] | None = -6,
    *,
    is_nil: bool = False,
) -> LineItem:
    """テスト用 LineItem を生成する。"""
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS,
        local_name=local_name,
        label_ja=_label(local_name),
        label_en=_label(local_name, lang="en"),
        value=value,
        unit_ref="JPY",
        decimals=decimals,
        context_id="CurrentYearDuration",
        period=_CUR_DURATION,
        entity_id="E00001",
        dimensions=(),
        is_nil=is_nil,
        source_line=1,
        order=0,
    )


def _fs(*items: LineItem) -> FinancialStatement:
    """テスト用 FinancialStatement を生成する。"""
    return FinancialStatement(
        statement_type=StatementType.INCOME_STATEMENT,
        period=_CUR_DURATION,
        items=items,
        consolidated=True,
        entity_id="E00001",
        warnings_issued=(),
    )


def _calc_linkbase(
    arcs: list[tuple[str, str, int]],
    role_uri: str = ROLE,
) -> CalculationLinkbase:
    """テスト用 CalculationLinkbase を生成する。

    Args:
        arcs: ``(parent, child, weight)`` のリスト。
        role_uri: ロール URI。
    """
    calc_arcs = tuple(
        CalculationArc(
            parent=parent,
            child=child,
            parent_href=f"dummy.xsd#{parent}",
            child_href=f"dummy.xsd#{child}",
            weight=weight,
            order=float(i),
            role_uri=role_uri,
        )
        for i, (parent, child, weight) in enumerate(arcs)
    )
    parents = {a[0] for a in arcs}
    children_set = {a[1] for a in arcs}
    roots = tuple(p for p in parents if p not in children_set)

    tree = CalculationTree(role_uri=role_uri, arcs=calc_arcs, roots=roots)
    return CalculationLinkbase(source_path=None, trees={role_uri: tree})


def _multi_role_linkbase(
    roles: dict[str, list[tuple[str, str, int]]],
) -> CalculationLinkbase:
    """複数ロールの CalculationLinkbase を生成する。"""
    trees: dict[str, CalculationTree] = {}
    for r_uri, arcs in roles.items():
        calc_arcs = tuple(
            CalculationArc(
                parent=parent,
                child=child,
                parent_href=f"dummy.xsd#{parent}",
                child_href=f"dummy.xsd#{child}",
                weight=weight,
                order=float(i),
                role_uri=r_uri,
            )
            for i, (parent, child, weight) in enumerate(arcs)
        )
        parents = {a[0] for a in arcs}
        children_set = {a[1] for a in arcs}
        roots = tuple(p for p in parents if p not in children_set)
        trees[r_uri] = CalculationTree(role_uri=r_uri, arcs=calc_arcs, roots=roots)
    return CalculationLinkbase(source_path=None, trees=trees)


# ===========================================================================
# TestComputeTolerance
# ===========================================================================


@pytest.mark.unit
class TestComputeTolerance:
    """_compute_tolerance() の単体テスト。"""

    def test_uniform_decimals_minus_6(self) -> None:
        """全て decimals=-6 → tolerance=500,000。"""
        result = _compute_tolerance(-6, [-6, -6])
        assert result == Decimal(500_000)

    def test_uniform_decimals_minus_3(self) -> None:
        """全て decimals=-3 → tolerance=500。"""
        result = _compute_tolerance(-3, [-3])
        assert result == Decimal(500)

    def test_mixed_decimals(self) -> None:
        """parent=-3, child=-6 → min=-6 → tolerance=500,000。"""
        result = _compute_tolerance(-3, [-6])
        assert result == Decimal(500_000)

    def test_all_inf(self) -> None:
        """全て INF → tolerance=0（完全一致）。"""
        result = _compute_tolerance("INF", ["INF", "INF"])
        assert result == Decimal(0)

    def test_all_none(self) -> None:
        """全て None → tolerance=0（安全側: 完全一致）。"""
        result = _compute_tolerance(None, [None])
        assert result == Decimal(0)

    def test_inf_and_numeric(self) -> None:
        """INF + numeric=-6 → INF は除外、numeric の tolerance。"""
        result = _compute_tolerance(-6, ["INF"])
        assert result == Decimal(500_000)


# ===========================================================================
# TestBuildFactIndex
# ===========================================================================


@pytest.mark.unit
class TestBuildFactIndex:
    """_build_fact_index() の単体テスト。"""

    def test_basic_index(self) -> None:
        """3 件の数値 LineItem からインデックスが構築される。"""
        fs = _fs(
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
            _item("GrossProfit", Decimal(300_000_000)),
        )
        index = _build_fact_index(fs)
        assert len(index) == 3
        assert index["NetSales"].value == Decimal(500_000_000)

    def test_skips_nil(self) -> None:
        """is_nil=True の Fact はインデックスから除外される。"""
        fs = _fs(
            _item("NetSales", None, is_nil=True),
            _item("GrossProfit", Decimal(300_000_000)),
        )
        index = _build_fact_index(fs)
        assert "NetSales" not in index
        assert "GrossProfit" in index

    def test_skips_text_value(self) -> None:
        """str 型の value はインデックスから除外される。"""
        fs = _fs(
            _item("TextBlock", "テキスト内容"),
            _item("NetSales", Decimal(500_000_000)),
        )
        index = _build_fact_index(fs)
        assert "TextBlock" not in index
        assert "NetSales" in index

    def test_first_wins_on_duplicate(self) -> None:
        """同一 local_name の重複は最初のもの（数値）が優先される。"""
        fs = _fs(
            _item("NetSales", Decimal(100)),
            _item("NetSales", Decimal(200)),
        )
        index = _build_fact_index(fs)
        assert index["NetSales"].value == Decimal(100)


# ===========================================================================
# TestValidateCalculations
# ===========================================================================


@pytest.mark.unit
class TestValidateCalculations:
    """validate_calculations() の単体テスト群。"""

    # --- 基本的な一致/不一致 ---

    def test_perfect_match(self) -> None:
        """親=子1+子2 が完全一致。is_valid=True, error_count=0。"""
        fs = _fs(
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
            _item("GrossProfit", Decimal(300_000_000)),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True
        assert result.checked_count == 1
        assert result.passed_count == 1
        assert result.error_count == 0
        assert result.skipped_count == 0

    def test_within_tolerance(self) -> None:
        """差が tolerance 内（decimals=-6 で差=300,000 < tolerance=500,000）。"""
        fs = _fs(
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
            _item("GrossProfit", Decimal(300_300_000)),  # expected=300M, diff=300K
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True
        assert result.passed_count == 1

    def test_exceeds_tolerance(self) -> None:
        """差が tolerance 超過（decimals=-6 で差=600,000 > tolerance=500,000）。"""
        fs = _fs(
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
            _item("GrossProfit", Decimal(300_600_000)),  # expected=300M, diff=600K
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is False
        assert result.error_count == 1
        assert result.issues[0].parent_concept == "GrossProfit"
        assert result.issues[0].difference == Decimal(600_000)
        assert result.issues[0].severity == "error"

    def test_at_tolerance_boundary(self) -> None:
        """差が tolerance と完全一致（difference == tolerance）。is_valid=True。"""
        fs = _fs(
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
            _item("GrossProfit", Decimal(300_500_000)),  # expected=300M, diff=500K
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True
        assert result.passed_count == 1

    # --- decimals の扱い ---

    def test_decimals_inf_exact_match(self) -> None:
        """decimals=INF で完全一致。tolerance=0, is_valid=True。"""
        fs = _fs(
            _item("A", Decimal(100), decimals="INF"),
            _item("B", Decimal(60), decimals="INF"),
            _item("C", Decimal(40), decimals="INF"),
        )
        lb = _calc_linkbase([("A", "B", 1), ("A", "C", 1)])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    def test_decimals_inf_mismatch(self) -> None:
        """decimals=INF で 1 の差。tolerance=0, is_valid=False。"""
        fs = _fs(
            _item("A", Decimal(101), decimals="INF"),
            _item("B", Decimal(60), decimals="INF"),
            _item("C", Decimal(40), decimals="INF"),
        )
        lb = _calc_linkbase([("A", "B", 1), ("A", "C", 1)])
        result = validate_calculations(fs, lb)

        assert result.is_valid is False
        assert result.issues[0].tolerance == Decimal(0)

    def test_mixed_decimals_tolerance(self) -> None:
        """parent=-3, child=-6 の混在。tolerance=500,000 (min=-6)。"""
        fs = _fs(
            _item("A", Decimal(100_000), decimals=-3),
            _item("B", Decimal(60_000), decimals=-6),
            _item("C", Decimal(40_000), decimals=-6),
        )
        lb = _calc_linkbase([("A", "B", 1), ("A", "C", 1)])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    def test_decimals_none(self) -> None:
        """decimals=None の場合。tolerance=0（安全側: 完全一致）。"""
        fs = _fs(
            _item("A", Decimal(100), decimals=None),
            _item("B", Decimal(60), decimals=None),
            _item("C", Decimal(40), decimals=None),
        )
        lb = _calc_linkbase([("A", "B", 1), ("A", "C", 1)])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True  # 100 == 60 + 40

    # --- weight の扱い ---

    def test_weight_minus_one(self) -> None:
        """weight=-1 の減算。expected = 500 + 200*(-1) = 300。"""
        fs = _fs(
            _item("GrossProfit", Decimal(300)),
            _item("NetSales", Decimal(500)),
            _item("CostOfSales", Decimal(200)),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    def test_weight_mixed(self) -> None:
        """weight=1 と weight=-1 の混在。OP = GP(300) - SGA(200) = 100。"""
        fs = _fs(
            _item("OperatingProfit", Decimal(100)),
            _item("GrossProfit", Decimal(300)),
            _item("SGA", Decimal(200)),
        )
        lb = _calc_linkbase([
            ("OperatingProfit", "GrossProfit", 1),
            ("OperatingProfit", "SGA", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    # --- Fact 欠損のスキップ ---

    def test_missing_parent_fact_skipped(self) -> None:
        """親科目の Fact がない場合。skipped_count=1, checked_count=0。"""
        fs = _fs(
            _item("NetSales", Decimal(500)),
            _item("CostOfSales", Decimal(200)),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 0
        assert result.skipped_count == 1

    def test_missing_child_fact_skipped(self) -> None:
        """子科目の Fact が 1 つもない場合。skipped_count=1。"""
        fs = _fs(
            _item("GrossProfit", Decimal(300)),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 0
        assert result.skipped_count == 1

    def test_partial_children_missing(self) -> None:
        """子科目の一部のみ Fact がある場合。全体がスキップ。"""
        fs = _fs(
            _item("GrossProfit", Decimal(300)),
            _item("NetSales", Decimal(500)),
            # CostOfSales が欠損
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 0
        assert result.skipped_count == 1

    # --- 中間ノードの検証 ---

    def test_intermediate_parent_validated(self) -> None:
        """中間ノード（GrossProfit）も検証される。checked_count=2。"""
        fs = _fs(
            _item("OperatingProfit", Decimal(100_000_000)),
            _item("GrossProfit", Decimal(300_000_000)),
            _item("SGA", Decimal(200_000_000)),
            _item("NetSales", Decimal(500_000_000)),
            _item("CostOfSales", Decimal(200_000_000)),
        )
        lb = _calc_linkbase([
            ("OperatingProfit", "GrossProfit", 1),
            ("OperatingProfit", "SGA", -1),
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 2
        assert result.passed_count == 2
        assert result.is_valid is True

    def test_hierarchical_chain(self) -> None:
        """多段チェーンで全段階が検証される。checked_count=3。"""
        fs = _fs(
            _item("ProfitLoss", Decimal(50_000_000)),
            _item("OrdinaryIncome", Decimal(80_000_000)),
            _item("IncomeTaxes", Decimal(30_000_000)),
            _item("OperatingIncome", Decimal(100_000_000)),
            _item("NonOperatingIncome", Decimal(20_000_000)),
            _item("NonOperatingExpenses", Decimal(40_000_000)),
            _item("GrossProfit", Decimal(300_000_000)),
            _item("SGA", Decimal(200_000_000)),
        )
        lb = _calc_linkbase([
            # ProfitLoss = OrdinaryIncome - IncomeTaxes
            ("ProfitLoss", "OrdinaryIncome", 1),
            ("ProfitLoss", "IncomeTaxes", -1),
            # OrdinaryIncome = OperatingIncome + NonOp - NonOpExp
            ("OrdinaryIncome", "OperatingIncome", 1),
            ("OrdinaryIncome", "NonOperatingIncome", 1),
            ("OrdinaryIncome", "NonOperatingExpenses", -1),
            # OperatingIncome = GrossProfit - SGA
            ("OperatingIncome", "GrossProfit", 1),
            ("OperatingIncome", "SGA", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 3
        assert result.passed_count == 3

    # --- 複数科目・複数ロール ---

    def test_multiple_children(self) -> None:
        """3 つ以上の子科目。Total = A + B + C。"""
        fs = _fs(
            _item("Total", Decimal(600)),
            _item("A", Decimal(100)),
            _item("B", Decimal(200)),
            _item("C", Decimal(300)),
        )
        lb = _calc_linkbase([
            ("Total", "A", 1),
            ("Total", "B", 1),
            ("Total", "C", 1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True
        assert result.checked_count == 1

    def test_multiple_roles(self) -> None:
        """複数の role URI を検証。各ロールの結果が統合される。"""
        fs = _fs(
            _item("ParentA", Decimal(100)),
            _item("ChildA", Decimal(100)),
            _item("ParentB", Decimal(200)),
            _item("ChildB", Decimal(200)),
        )
        lb = _multi_role_linkbase({
            ROLE: [("ParentA", "ChildA", 1)],
            ROLE_B: [("ParentB", "ChildB", 1)],
        })
        result = validate_calculations(fs, lb)

        assert result.checked_count == 2
        assert result.passed_count == 2

    def test_specific_role_uri_filter(self) -> None:
        """role_uri を指定して特定ロールのみ検証。"""
        fs = _fs(
            _item("ParentA", Decimal(100)),
            _item("ChildA", Decimal(100)),
            _item("ParentB", Decimal(200)),
            _item("ChildB", Decimal(200)),
        )
        lb = _multi_role_linkbase({
            ROLE: [("ParentA", "ChildA", 1)],
            ROLE_B: [("ParentB", "ChildB", 1)],
        })
        result = validate_calculations(fs, lb, role_uri=ROLE)

        assert result.checked_count == 1
        assert result.passed_count == 1

    def test_same_concept_in_multiple_roles(self) -> None:
        """同一 concept が複数 role に出現し、各 role で独立に検証される。"""
        fs = _fs(
            _item("GrossProfit", Decimal(300)),
            _item("NetSales", Decimal(500)),
            _item("CostOfSales", Decimal(200)),
            _item("Revenue", Decimal(300)),
        )
        lb = _multi_role_linkbase({
            ROLE: [
                ("GrossProfit", "NetSales", 1),
                ("GrossProfit", "CostOfSales", -1),
            ],
            ROLE_B: [
                ("GrossProfit", "Revenue", 1),
            ],
        })
        result = validate_calculations(fs, lb)

        # ROLE: 500 - 200 = 300 ✓, ROLE_B: 300 = 300 ✓
        assert result.checked_count == 2
        assert result.passed_count == 2

    def test_nonexistent_role_uri(self) -> None:
        """存在しない role_uri を指定した場合。全て 0。"""
        fs = _fs(_item("A", Decimal(100)))
        lb = _calc_linkbase([("A", "B", 1)])
        result = validate_calculations(fs, lb, role_uri="http://nonexistent")

        assert result.checked_count == 0
        assert result.skipped_count == 0
        assert result.is_valid is True

    # --- 空のケース ---

    def test_empty_statement(self) -> None:
        """空の FinancialStatement。全親科目がスキップされる。"""
        fs = _fs()
        lb = _calc_linkbase([("A", "B", 1)])
        result = validate_calculations(fs, lb)

        assert result.checked_count == 0
        assert result.skipped_count >= 1

    def test_empty_linkbase(self) -> None:
        """空の CalculationLinkbase。checked=0, skipped=0。"""
        fs = _fs(_item("A", Decimal(100)))
        lb = CalculationLinkbase(source_path=None, trees={})
        result = validate_calculations(fs, lb)

        assert result.checked_count == 0
        assert result.skipped_count == 0
        assert result.is_valid is True

    # --- 結果プロパティ ---

    def test_checked_equals_passed_plus_errors(self) -> None:
        """checked_count = passed_count + error_count の恒等式。"""
        fs = _fs(
            _item("A", Decimal(100)),
            _item("B", Decimal(60)),
            _item("C", Decimal(40)),
            _item("X", Decimal(999)),  # 不一致
            _item("Y", Decimal(500)),
        )
        lb = _calc_linkbase([
            ("A", "B", 1),
            ("A", "C", 1),
            ("X", "Y", 1),
        ])
        result = validate_calculations(fs, lb)

        assert result.checked_count == result.passed_count + result.error_count

    def test_str_output(self) -> None:
        """__str__() が合格/不合格を含む日本語サマリを返す。"""
        fs = _fs(
            _item("A", Decimal(100)),
            _item("B", Decimal(100)),
        )
        lb = _calc_linkbase([("A", "B", 1)])
        result = validate_calculations(fs, lb)

        output = str(result)
        assert "計算バリデーション" in output
        assert "合格" in output

    # --- 数値のエッジケース ---

    def test_negative_values(self) -> None:
        """マイナスの Fact 値（赤字）。OP(-100) = GP(50) - SGA(150)。"""
        fs = _fs(
            _item("OperatingIncome", Decimal(-100)),
            _item("GrossProfit", Decimal(50)),
            _item("SGA", Decimal(150)),
        )
        lb = _calc_linkbase([
            ("OperatingIncome", "GrossProfit", 1),
            ("OperatingIncome", "SGA", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    def test_zero_value_parent(self) -> None:
        """親科目が 0。GP(0) = Sales(200) - COGS(200)。"""
        fs = _fs(
            _item("GrossProfit", Decimal(0)),
            _item("NetSales", Decimal(200)),
            _item("CostOfSales", Decimal(200)),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True

    def test_nil_and_text_excluded(self) -> None:
        """nil / テキスト Fact は除外され、数値のみ検証される。"""
        fs = _fs(
            _item("GrossProfit", Decimal(300)),
            _item("NetSales", Decimal(500)),
            _item("CostOfSales", Decimal(200)),
            _item("TextNote", "テキスト内容"),
            _item("NilItem", None, is_nil=True),
        )
        lb = _calc_linkbase([
            ("GrossProfit", "NetSales", 1),
            ("GrossProfit", "CostOfSales", -1),
        ])
        result = validate_calculations(fs, lb)

        assert result.is_valid is True
        assert result.checked_count == 1


# ===========================================================================
# TestValidationIssue
# ===========================================================================


@pytest.mark.unit
class TestValidationIssue:
    """ValidationIssue dataclass のフィールド検証。"""

    def test_issue_fields(self) -> None:
        """ValidationIssue の各フィールドが正しく設定される。"""
        issue = ValidationIssue(
            role_uri=ROLE,
            parent_concept="GrossProfit",
            expected=Decimal(300_000_000),
            actual=Decimal(301_000_000),
            difference=Decimal(1_000_000),
            tolerance=Decimal(500_000),
            severity="error",
            message="計算不一致: GrossProfit",
        )
        assert issue.role_uri == ROLE
        assert issue.parent_concept == "GrossProfit"
        assert issue.severity == "error"

    def test_message_japanese(self) -> None:
        """検証結果の message が日本語である。"""
        fs = _fs(
            _item("A", Decimal(999), decimals="INF"),
            _item("B", Decimal(100), decimals="INF"),
        )
        lb = _calc_linkbase([("A", "B", 1)])
        result = validate_calculations(fs, lb)

        assert len(result.issues) == 1
        assert "計算不一致" in result.issues[0].message
