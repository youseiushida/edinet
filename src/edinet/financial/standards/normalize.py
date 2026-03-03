"""会計基準横断の統一アクセスレイヤー。

J-GAAP / IFRS の Presentation Linkbase から ConceptSet を取得し、
``statements.py`` が会計基準を意識せずに概念セットやソート順序を
取得できるようにするファサード。

v0.2.0 で以下の関数は削除された:
    - ``get_canonical_key()``: ``summary_mappings.lookup_summary()`` に移行
    - ``get_concept_for_key()``: 利用箇所なし
    - ``cross_standard_lookup()``: 利用箇所なし
    - ``get_canonical_key_for_sector()``: sector モジュール削除に伴い削除

主な用途:
    - ``get_known_concepts(standard, st)`` で該当基準の概念集合を取得
    - ``get_concept_order(standard, st)`` で表示順序を取得
    - ``get_concept_set(standard, st, taxonomy_root)`` で ConceptSet を取得
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.xbrl.taxonomy.concept_sets import ConceptSet

from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard

logger = logging.getLogger(__name__)

__all__ = [
    "get_concept_set",
    "get_known_concepts",
    "get_concept_order",
]


# ---------------------------------------------------------------------------
# 1. 内部ヘルパー — concept_sets 接続
# ---------------------------------------------------------------------------


def _standard_to_module_group(standard: AccountingStandard | None) -> str:
    """会計基準 → module_group を返す。

    Args:
        standard: 会計基準。

    Returns:
        ``"jpigp"``（IFRS / JMIS）または ``"jppfs"``（それ以外）。
    """
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return "jpigp"
    return "jppfs"


def _get_concept_set(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    taxonomy_root: Path,
    industry_code: str | None,
) -> "ConceptSet | None":
    """concept_sets から ConceptSet を取得する共通ヘルパー。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。

    Returns:
        ConceptSet。取得できなかった場合は ``None``。
    """
    from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets

    module_group = _standard_to_module_group(standard)
    registry = derive_concept_sets(taxonomy_root, module_group=module_group)
    ind = industry_code or ("ifrs" if module_group == "jpigp" else "cai")
    return registry.get(statement_type, consolidated=True, industry_code=ind)


# ---------------------------------------------------------------------------
# 2. レガシーフォールバック（taxonomy_root なし時の概念リスト）
# ---------------------------------------------------------------------------
# statement_mappings.py に集約されたデータを参照する。


def _resolve_legacy_key(standard: AccountingStandard | None) -> str:
    """会計基準 → レガシーインデックスキー。"""
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return "ifrs"
    return "jgaap"


_STATEMENT_TYPE_TO_SHORT: dict[StatementType, str] = {
    StatementType.INCOME_STATEMENT: "pl",
    StatementType.BALANCE_SHEET: "bs",
    StatementType.CASH_FLOW_STATEMENT: "cf",
}


def _get_known_concepts_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> frozenset[str]:
    """taxonomy_root なしの場合のレガシーフォールバック。"""
    from edinet.financial.standards.statement_mappings import statement_concepts

    if standard == AccountingStandard.US_GAAP:
        return frozenset()
    key = _resolve_legacy_key(standard)
    short = _STATEMENT_TYPE_TO_SHORT.get(statement_type, "")
    return frozenset(statement_concepts(key, short))


def _get_concept_order_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> dict[str, int]:
    """taxonomy_root なしの場合のレガシー表示順序。"""
    from edinet.financial.standards.statement_mappings import statement_concepts

    if standard == AccountingStandard.US_GAAP:
        return {}
    key = _resolve_legacy_key(standard)
    short = _STATEMENT_TYPE_TO_SHORT.get(statement_type, "")
    concepts = statement_concepts(key, short)
    return {c: i for i, c in enumerate(concepts)}


# ---------------------------------------------------------------------------
# 3. get_known_concepts
# ---------------------------------------------------------------------------


def get_known_concepts(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> frozenset[str]:
    """指定基準・諸表種別の既知概念集合を返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。指定がない場合は
    インラインのレガシー概念リストにフォールバック。

    Args:
        standard: 会計基準。``None`` / ``UNKNOWN`` は J-GAAP にフォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。指定時は concept_sets を優先。
            存在しないパスを指定した場合は ``EdinetConfigError``。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        concept ローカル名の frozenset。

    Raises:
        EdinetConfigError: ``taxonomy_root`` が存在しないパスの場合。
    """
    if taxonomy_root is not None:
        cs = _get_concept_set(
            standard, statement_type, taxonomy_root, industry_code,
        )
        if cs is not None:
            return cs.non_abstract_concepts()
        logger.warning(
            "%s/%s: concept_sets から取得できず、レガシーフォールバックを使用",
            standard, statement_type.value,
        )
    return _get_known_concepts_legacy(standard, statement_type)


# ---------------------------------------------------------------------------
# 4. get_concept_order
# ---------------------------------------------------------------------------


def get_concept_order(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    *,
    taxonomy_root: Path | None = None,
    industry_code: str | None = None,
) -> dict[str, int]:
    """指定基準・諸表種別の表示順序マッピングを返す。

    ``taxonomy_root`` が指定されている場合、concept_sets（Presentation
    Linkbase 動的導出）を優先的に使用する。

    Args:
        standard: 会計基準。``None`` / 未知は J-GAAP フォールバック。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。指定時は concept_sets を優先。
            存在しないパスを指定した場合は ``EdinetConfigError``。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        ``{concept_local_name: display_order}`` の辞書。

    Raises:
        EdinetConfigError: ``taxonomy_root`` が存在しないパスの場合。
    """
    if taxonomy_root is not None:
        cs = _get_concept_set(
            standard, statement_type, taxonomy_root, industry_code,
        )
        if cs is not None:
            return {
                e.concept: int(e.order)
                for e in cs.concepts
                if not e.is_abstract
            }
        logger.warning(
            "%s/%s: concept_sets から表示順序を取得できず、"
            "レガシーフォールバックを使用",
            standard, statement_type.value,
        )
    return _get_concept_order_legacy(standard, statement_type)


# ---------------------------------------------------------------------------
# 5. get_concept_set（公開ラッパー）
# ---------------------------------------------------------------------------


def get_concept_set(
    standard: AccountingStandard | None,
    statement_type: StatementType,
    taxonomy_root: Path,
    industry_code: str | None = None,
) -> "ConceptSet | None":
    """指定基準・諸表種別の ConceptSet を返す。

    ``_get_concept_set()`` の公開ラッパー。
    階層表示（display/statements）等で ConceptSet を直接取得する場合に使用する。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。``None`` は一般事業会社。

    Returns:
        ConceptSet。取得できなかった場合は ``None``。
    """
    return _get_concept_set(standard, statement_type, taxonomy_root, industry_code)
