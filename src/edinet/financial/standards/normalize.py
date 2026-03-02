"""会計基準横断の統一アクセスレイヤー。

J-GAAP / IFRS / US-GAAP / JMIS の各会計基準モジュールを束ね、
``statements.py`` が会計基準を意識せずに概念セットやソート順序を
取得できるようにするファサード。

主な用途:
    - ``get_known_concepts(standard, st)`` で該当基準の概念集合を取得
    - ``get_concept_order(standard, st)`` で表示順序を取得
    - ``cross_standard_lookup(name, src, tgt)`` で基準間の概念変換
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.xbrl.taxonomy.concept_sets import ConceptSet

from edinet.models.financial import StatementType
from edinet.xbrl.dei import AccountingStandard
from edinet.financial.standards import jgaap, ifrs

logger = logging.getLogger(__name__)

__all__ = [
    "get_canonical_key",
    "get_concept_for_key",
    "get_concept_set",
    "get_known_concepts",
    "get_concept_order",
    "cross_standard_lookup",
    "get_canonical_key_for_sector",
]


# ---------------------------------------------------------------------------
# 1. get_canonical_key
# ---------------------------------------------------------------------------


def get_canonical_key(
    local_name: str,
    standard: AccountingStandard | None = None,
) -> str | None:
    """concept ローカル名から正規化キーを返す。

    Args:
        local_name: タクソノミの concept ローカル名
            （例: ``"NetSales"``, ``"RevenueIFRS"``）。
        standard: 検索対象の会計基準。``None`` の場合は
            J-GAAP → IFRS の順で全基準を検索する。

    Returns:
        正規化キー（例: ``"revenue"``）。見つからなければ ``None``。
    """
    if standard is None:
        # 全基準検索: J-GAAP → IFRS の順
        result = jgaap.canonical_key(local_name)
        if result is not None:
            return result
        return ifrs.canonical_key(local_name)
    if standard == AccountingStandard.JAPAN_GAAP:
        return jgaap.canonical_key(local_name)
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return ifrs.canonical_key(local_name)
    # US_GAAP — BLOCK_ONLY のため個別概念マッピングなし
    return None


# ---------------------------------------------------------------------------
# 2. get_concept_for_key
# ---------------------------------------------------------------------------


def get_concept_for_key(
    canonical_key: str,
    target_standard: AccountingStandard,
) -> str | None:
    """正規化キーから対象基準の concept ローカル名を返す。

    Args:
        canonical_key: 正規化キー（例: ``"revenue"``）。
        target_standard: 対象の会計基準。

    Returns:
        concept ローカル名。見つからなければ ``None``。
    """
    if target_standard == AccountingStandard.JAPAN_GAAP:
        m = jgaap.reverse_lookup(canonical_key)
        return m.concept if m is not None else None
    if target_standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        m = ifrs.reverse_lookup(canonical_key)
        return m.concept if m is not None else None
    return None


# ---------------------------------------------------------------------------
# 3. 内部ヘルパー — concept_sets 接続
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

    NOTE: ``consolidated=True`` で連結テンプレートのみ使用。
    現在の ``_build_single_statement()`` は ``known_concepts`` を
    「この statement type に属する concept の集合」として使い、
    連結/個別フィルタは後段の ``_filter_consolidated_with_fallback()``
    で処理する。概念名自体は連結/個別で同一のため問題ないが、
    将来個別テンプレート固有の概念が必要になった場合は
    ``consolidated`` パラメータの伝搬が必要。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。
        taxonomy_root: タクソノミルートパス。
        industry_code: 業種コード。

    Returns:
        ConceptSet。取得できなかった場合は ``None``。
    """
    # 遅延 import（taxonomy_root=None の場合に不要な import を避ける）
    from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets

    module_group = _standard_to_module_group(standard)
    registry = derive_concept_sets(taxonomy_root, module_group=module_group)
    ind = industry_code or ("ifrs" if module_group == "jpigp" else "cai")
    return registry.get(statement_type, consolidated=True, industry_code=ind)


# ---------------------------------------------------------------------------
# 4. 内部ヘルパー — レガシーフォールバック
# ---------------------------------------------------------------------------


def _get_known_concepts_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> frozenset[str]:
    """taxonomy_root なしの場合の従来動作。

    jgaap / ifrs のハードコードから概念集合を取得する。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。

    Returns:
        concept ローカル名の frozenset。
    """
    # 基本セット（jgaap/ifrs）
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        return frozenset(
            m.concept for m in jgaap.mappings_for_statement(statement_type)
        )
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return frozenset(
            m.concept for m in ifrs.mappings_for_statement(statement_type)
        )
    if standard == AccountingStandard.US_GAAP:
        return frozenset()
    return frozenset(
        m.concept for m in jgaap.mappings_for_statement(statement_type)
    )


def _get_concept_order_legacy(
    standard: AccountingStandard | None,
    statement_type: StatementType,
) -> dict[str, int]:
    """taxonomy_root なしの場合の従来表示順序。

    jgaap / ifrs のハードコードから定義順（0-based）で表示順序を取得する。

    Args:
        standard: 会計基準。
        statement_type: 財務諸表の種類。

    Returns:
        ``{concept_local_name: order}`` の辞書。
    """
    if standard in (AccountingStandard.JAPAN_GAAP, None):
        return {
            m.concept: i
            for i, m in enumerate(jgaap.mappings_for_statement(statement_type))
        }
    if standard in (AccountingStandard.IFRS, AccountingStandard.JMIS):
        return {
            m.concept: i
            for i, m in enumerate(ifrs.mappings_for_statement(statement_type))
        }
    if standard == AccountingStandard.US_GAAP:
        return {}
    return {
        m.concept: i
        for i, m in enumerate(jgaap.mappings_for_statement(statement_type))
    }


# ---------------------------------------------------------------------------
# 5. get_known_concepts
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
    Linkbase 動的導出）を優先的に使用する。指定がない場合は jgaap/ifrs の
    ハードコードにフォールバック。

    ``taxonomy_root`` が指定されたがパスが存在しない場合は
    ``EdinetConfigError`` が発生する（サイレントフォールバックはしない）。

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
# 6. get_concept_order
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

    ``taxonomy_root`` が指定されたがパスが存在しない場合は
    ``EdinetConfigError`` が発生する。

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
# 7. cross_standard_lookup
# ---------------------------------------------------------------------------


def cross_standard_lookup(
    local_name: str,
    source_standard: AccountingStandard,
    target_standard: AccountingStandard,
) -> str | None:
    """会計基準間で概念を変換する。

    ``source_standard`` の ``local_name`` に対応する
    ``target_standard`` の concept ローカル名を返す。

    Args:
        local_name: 変換元の concept ローカル名。
        source_standard: 変換元の会計基準。
        target_standard: 変換先の会計基準。

    Returns:
        変換先の concept ローカル名。変換できなければ ``None``。
    """
    key = get_canonical_key(local_name, source_standard)
    if key is None:
        return None
    return get_concept_for_key(key, target_standard)


# ---------------------------------------------------------------------------
# 8. sector 対応関数（sector_key のみ維持）
# ---------------------------------------------------------------------------


def get_canonical_key_for_sector(
    local_name: str,
    standard: AccountingStandard | None = None,
    industry_code: str | None = None,
) -> str | None:
    """業種考慮の canonical_key 解決。

    sector レジストリを先に検索し、見つからなければ jgaap にフォールバック。

    Args:
        local_name: concept ローカル名。
        standard: 会計基準。
        industry_code: 業種コード。None は一般事業会社。

    Returns:
        正規化キー。見つからなければ None。
    """
    if industry_code is None or standard not in (
        AccountingStandard.JAPAN_GAAP, None,
    ):
        return get_canonical_key(local_name, standard)

    from edinet.financial.sector import get_sector_registry

    reg = get_sector_registry(industry_code)
    if reg is not None:
        key = reg.sector_key(local_name)
        if key is not None:
            return key
    # sector で見つからなければ一般事業会社にフォールバック
    return get_canonical_key(local_name, standard)


# ---------------------------------------------------------------------------
# 9. get_concept_set（公開ラッパー）
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
