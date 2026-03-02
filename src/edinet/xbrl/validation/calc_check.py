"""計算リンクベースによる合計値バリデーション。

XBRL 2.1 §5.2.5.2 に準拠し、計算リンクベース内の全ての
summation-item 親子関係を検証する。親科目の値が子科目の
加重和と一致するかを、decimals ベースの丸め許容差を考慮して判定する。

使用例::

    from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase
    from edinet.xbrl.validation.calc_check import validate_calculations

    calc_linkbase = parse_calculation_linkbase(xml_bytes)
    pl = statements.income_statement()
    result = validate_calculations(pl, calc_linkbase)
    print(result)  # 計算バリデーション: 合格 (検証=5, 合格=5, エラー=0, スキップ=2)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.linkbase.calculation import CalculationLinkbase

__all__ = ["CalcValidationResult", "ValidationIssue", "validate_calculations"]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """計算バリデーションの個別不一致。

    Attributes:
        role_uri: 計算リンクベースのロール URI。
        parent_concept: 親概念のローカル名（例: ``"GrossProfit"``）。
        expected: 子科目の加重和（計算上の期待値）。
        actual: 実際の Fact 値。
        difference: ``|expected - actual|``。
        tolerance: decimals ベースの許容誤差。
        severity: 深刻度。tolerance 超過は ``"error"``。
        message: 人間向けメッセージ（日本語）。
    """

    role_uri: str
    parent_concept: str
    expected: Decimal
    actual: Decimal
    difference: Decimal
    tolerance: Decimal
    severity: Literal["error", "warning"]
    message: str


@dataclass(frozen=True, slots=True)
class CalcValidationResult:
    """計算リンクベース検証の結果。

    Attributes:
        issues: 不一致の詳細タプル。
        checked_count: 検証した親科目の数（passed + error）。
        passed_count: 一致した（tolerance 内の）親科目の数。
        skipped_count: Fact 不足でスキップした親科目の数。
    """

    issues: tuple[ValidationIssue, ...]
    checked_count: int
    passed_count: int
    skipped_count: int

    @property
    def is_valid(self) -> bool:
        """error が 1 つもなければ True。"""
        return all(i.severity != "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        """error の件数。"""
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        """warning の件数。"""
        return sum(1 for i in self.issues if i.severity == "warning")

    def __str__(self) -> str:
        """人間向けサマリを返す。"""
        status = "合格" if self.is_valid else "不合格"
        return (
            f"計算バリデーション: {status} "
            f"(検証={self.checked_count}, 合格={self.passed_count}, "
            f"エラー={self.error_count}, スキップ={self.skipped_count})"
        )


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _build_fact_index(
    statement: FinancialStatement,
) -> dict[str, LineItem]:
    """FinancialStatement から local_name → LineItem のインデックスを構築する。

    数値以外（str 型の value や None）、nil の Fact は除外する。
    同一 local_name の LineItem が複数存在する場合は最初のものを使用する。

    Args:
        statement: 対象の FinancialStatement。

    Returns:
        local_name → LineItem の辞書。
    """
    index: dict[str, LineItem] = {}
    for item in statement.items:
        if item.local_name not in index:
            if isinstance(item.value, Decimal) and not item.is_nil:
                index[item.local_name] = item
    return index


def _compute_tolerance(
    parent_decimals: int | Literal["INF"] | None,
    child_decimals_list: list[int | Literal["INF"] | None],
) -> Decimal:
    """XBRL 2.1 §5.2.5.2 に基づく丸め許容誤差を計算する（min-decimals 方式）。

    ``tolerance = 0.5 × 10^(-min(parent_decimals, child1_decimals, ...))``

    - ``"INF"`` は無限精度。min 計算から除外し、他に有限の decimals が
      あればその最小値を使用する。全て ``"INF"`` なら tolerance=0。
    - ``None`` は未指定。安全側として min 計算から除外し tolerance=0 寄りにする。

    Args:
        parent_decimals: 親科目の decimals 属性値。
        child_decimals_list: 子科目の decimals 属性値のリスト。

    Returns:
        許容誤差（Decimal）。
    """
    all_decimals = [parent_decimals, *child_decimals_list]

    # None / "INF" を除外して数値のみ抽出
    numeric = [d for d in all_decimals if isinstance(d, int)]

    if not numeric:
        # 全て None or INF → tolerance=0（完全一致）
        return Decimal(0)

    min_dec = min(numeric)
    # 0.5 × 10^(-min_dec) を浮動小数点を避けて表現
    return Decimal(5) * Decimal(10) ** Decimal(-min_dec - 1)


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def validate_calculations(
    statement: FinancialStatement,
    calc_linkbase: CalculationLinkbase,
    *,
    role_uri: str | None = None,
) -> CalcValidationResult:
    """計算リンクベースに基づき財務諸表の合計値を検証する。

    XBRL 2.1 §5.2.5.2 に準拠し、計算リンクベース内の **全ての**
    summation-item 親子関係を検証対象とする（roots だけでなく
    中間ノードも含む）。各親科目について子科目の加重和と比較し、
    decimals ベースの丸め許容差を超える不一致を検出する。

    Args:
        statement: 検証対象の FinancialStatement。
        calc_linkbase: ``parse_calculation_linkbase()`` で取得した
            CalculationLinkbase。
        role_uri: 検証対象のロール URI。``None`` の場合は全ロールを検証する。

    Returns:
        CalcValidationResult。
    """
    fact_index = _build_fact_index(statement)
    issues: list[ValidationIssue] = []
    checked = 0
    passed = 0
    skipped = 0

    # 対象 role URI の決定
    if role_uri is not None:
        target_roles = (
            [role_uri] if calc_linkbase.get_tree(role_uri) is not None else []
        )
    else:
        target_roles = list(calc_linkbase.role_uris)

    for r_uri in target_roles:
        tree = calc_linkbase.get_tree(r_uri)
        if tree is None:  # pragma: no cover — target_roles で保証済み
            continue

        # 全てのユニーク親科目を収集（roots + 中間ノード）
        all_parents: list[str] = []
        seen: set[str] = set()
        for arc in tree.arcs:
            if arc.parent not in seen:
                all_parents.append(arc.parent)
                seen.add(arc.parent)

        for parent_concept in all_parents:
            # 親科目の Fact を取得
            parent_item = fact_index.get(parent_concept)
            if parent_item is None:
                skipped += 1
                continue

            # 子科目の arc を取得
            children = calc_linkbase.children_of(
                parent_concept, role_uri=r_uri
            )
            if not children:
                skipped += 1
                continue

            # 子科目の Fact を全て取得（1つでも欠損ならスキップ）
            child_values: list[
                tuple[Decimal, int | Literal["INF"] | None]
            ] = []
            all_found = True
            for arc in children:
                child_item = fact_index.get(arc.child)
                if child_item is None:
                    all_found = False
                    break
                assert isinstance(child_item.value, Decimal)  # noqa: S101 — _build_fact_index で保証
                child_values.append(
                    (child_item.value * arc.weight, child_item.decimals)
                )

            if not all_found:
                skipped += 1
                continue

            # 期待値の計算
            expected = sum((v for v, _ in child_values), Decimal(0))
            actual = parent_item.value
            assert isinstance(actual, Decimal)  # noqa: S101 — _build_fact_index で保証

            # 許容誤差の計算
            tolerance = _compute_tolerance(
                parent_item.decimals,
                [d for _, d in child_values],
            )

            # 比較
            difference = abs(expected - actual)
            checked += 1

            if difference <= tolerance:
                passed += 1
            else:
                msg = (
                    f"計算不一致: {parent_concept} の期待値={expected:,.0f}, "
                    f"実際値={actual:,.0f}, 差={difference:,.0f}, "
                    f"許容誤差={tolerance:,.0f}"
                )
                issues.append(
                    ValidationIssue(
                        role_uri=r_uri,
                        parent_concept=parent_concept,
                        expected=expected,
                        actual=actual,
                        difference=difference,
                        tolerance=tolerance,
                        severity="error",
                        message=msg,
                    )
                )

    return CalcValidationResult(
        issues=tuple(issues),
        checked_count=checked,
        passed_count=passed,
        skipped_count=skipped,
    )
