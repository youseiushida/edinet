"""会計基準の自動判別モジュール。

XBRL インスタンスから会計基準（J-GAAP / IFRS / US-GAAP / JMIS）を
自動判別する。DEI 要素を第一手段、名前空間パターンをフォールバックとする
2 段階の判別ロジックを提供する。
"""

from __future__ import annotations

import enum
import warnings
from dataclasses import dataclass

from edinet.exceptions import EdinetWarning
from edinet.xbrl._namespaces import classify_namespace
from edinet.xbrl.dei import (
    DEI,
    AccountingStandard,
    PeriodType,
    extract_dei,
)
from edinet.xbrl.parser import RawFact

__all__ = [
    "DetectedStandard",
    "DetectionMethod",
    "DetailLevel",
    "detect_accounting_standard",
    "detect_from_dei",
    "detect_from_namespaces",
]


# ---------------------------------------------------------------------------
# 列挙型
# ---------------------------------------------------------------------------


class DetectionMethod(enum.Enum):
    """会計基準の判別に**成功した**手段。

    判別を「試みたが結果が得られなかった」場合も UNKNOWN となる。
    例: DEI を参照したが AccountingStandardsDEI が nil だった場合も UNKNOWN。

    Attributes:
        DEI: DEI 要素 (AccountingStandardsDEI) から判別。最も確実。
        NAMESPACE: 名前空間 URI のパターンマッチから推定。
            DEI が存在しない書類タイプ（大量保有報告書等）で使用。
        UNKNOWN: いずれの手段でも判別に成功しなかった。
    """

    DEI = "dei"
    NAMESPACE = "namespace"
    UNKNOWN = "unknown"


class DetailLevel(enum.Enum):
    """XBRL データの詳細度（タグ付けレベル）。

    会計基準によって XBRL の構造化レベルが大きく異なる。
    J-GAAP と IFRS は個別勘定科目レベルの詳細タグ付けが行われるが、
    US-GAAP と JMIS は包括タグ付け（TextBlock）のみ。

    Attributes:
        DETAILED: 個別勘定科目レベルの詳細タグ付け。
            財務諸表の各勘定科目が独立した Fact として存在する。
            PL/BS/CF の構造化パースが可能。
        BLOCK_ONLY: 包括タグ付けのみ。
            財務諸表は TextBlock（HTML ブロック）として格納され、
            個別勘定科目の Fact は存在しない。
            SummaryOfBusinessResults 要素で主要経営指標のみ取得可能。
    """

    DETAILED = "detailed"
    BLOCK_ONLY = "block_only"


# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DetectedStandard:
    """会計基準の判別結果。

    Attributes:
        standard: 判別された会計基準。
            既知の 4 値は AccountingStandard Enum、未知の値は str。
            判別不能の場合は None。
        method: 判別に使用された手段。
        detail_level: XBRL データの詳細度。
            standard が確定していない場合（None）は None。
        has_consolidated: 連結財務諸表の有無。
            DEI の WhetherConsolidatedFinancialStatementsArePreparedDEI 値。
            DEI から取得できない場合は None（不明）。
        period_type: 報告期間の種類（通期/半期）。
            DEI の TypeOfCurrentPeriodDEI 値。
            DEI から取得できない場合は None。
        namespace_modules: 検出された標準タクソノミモジュールグループの集合。
            名前空間フォールバック判別のデバッグ用。
            DEI ベースの判別が成功した場合は空（frozenset()）となる。
            名前空間フォールバック時のみ有意な値が設定される。
            必要に応じて detect_from_namespaces() を別途呼び出すことで
            DEI 成功時にも名前空間情報を取得可能。
            例: {"jppfs", "jpcrp", "jpdei"} (J-GAAP),
                {"jppfs", "jpcrp", "jpdei", "jpigp"} (IFRS)
    """

    standard: AccountingStandard | str | None
    method: DetectionMethod
    detail_level: DetailLevel | None = None
    has_consolidated: bool | None = None
    period_type: PeriodType | str | None = None
    namespace_modules: frozenset[str] = frozenset()

    def __str__(self) -> str:
        """短い文字列表現を返す（例: ``"J-GAAP"``、``"IFRS"``）。"""
        _SHORT_NAMES: dict[AccountingStandard, str] = {
            AccountingStandard.JAPAN_GAAP: "J-GAAP",
            AccountingStandard.IFRS: "IFRS",
            AccountingStandard.US_GAAP: "US-GAAP",
            AccountingStandard.JMIS: "JMIS",
        }
        if isinstance(self.standard, AccountingStandard):
            return _SHORT_NAMES.get(self.standard, self.standard.value)
        if self.standard is not None:
            return str(self.standard)
        return "Unknown"


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DETAIL_LEVEL_MAP: dict[AccountingStandard, DetailLevel] = {
    AccountingStandard.JAPAN_GAAP: DetailLevel.DETAILED,
    AccountingStandard.IFRS: DetailLevel.DETAILED,
    AccountingStandard.US_GAAP: DetailLevel.BLOCK_ONLY,
    AccountingStandard.JMIS: DetailLevel.BLOCK_ONLY,
}


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def detect_accounting_standard(
    facts: tuple[RawFact, ...],
    *,
    dei: DEI | None = None,
) -> DetectedStandard:
    """XBRL インスタンスから会計基準を自動判別する。

    2 段階のフォールバックロジックで会計基準を判別する:

    1. **DEI（第一手段）**: facts から DEI を抽出し、
       AccountingStandardsDEI の値で判別する。
       最も確実で公式な判別方法。

    2. **名前空間（第二手段）**: DEI に AccountingStandardsDEI が
       含まれない場合（大量保有報告書等の書類タイプ）、
       facts の名前空間 URI パターンから会計基準を推定する。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。
        dei: extract_dei() で取得済みの DEI。省略時は内部で抽出する。
            既に DEI を抽出済みの場合に渡すことで二重走査を回避できる。

    Returns:
        DetectedStandard。判別不能の場合でもエラーにはせず、
        standard=None, method=UNKNOWN で返す。
    """
    # Step 1: DEI から判別を試みる（既に抽出済みならそのまま使用）
    if dei is None:
        dei = extract_dei(facts)
    result = detect_from_dei(dei)

    # Step 2: DEI で判別できた場合はそのまま返す
    if result.standard is not None:
        return result

    # Step 3: 名前空間フォールバック
    ns_result = detect_from_namespaces(facts)

    # Step 4: 名前空間で判別できた場合、DEI の補助情報を統合
    if ns_result.standard is not None:
        return DetectedStandard(
            standard=ns_result.standard,
            method=ns_result.method,
            detail_level=ns_result.detail_level,
            has_consolidated=dei.has_consolidated,
            period_type=dei.type_of_current_period,
            namespace_modules=ns_result.namespace_modules,
        )

    # Step 5: 両方失敗 → UNKNOWN
    return DetectedStandard(
        standard=None,
        method=DetectionMethod.UNKNOWN,
        has_consolidated=dei.has_consolidated,
        period_type=dei.type_of_current_period,
        namespace_modules=ns_result.namespace_modules,
    )


def detect_from_dei(dei: DEI) -> DetectedStandard:
    """DEI オブジェクトから会計基準を判別する。

    extract_dei() が既に呼ばれている場合に使用する。
    名前空間フォールバックは行わない（DEI ベースの判別のみ）。

    Args:
        dei: extract_dei() で取得済みの DEI オブジェクト。

    Returns:
        DetectedStandard。DEI に AccountingStandardsDEI が
        含まれない場合は standard=None, method=UNKNOWN で返す。
    """
    standard = dei.accounting_standards

    if standard is None:
        # DEI に AccountingStandardsDEI が存在しないか xsi:nil
        return DetectedStandard(
            standard=None,
            method=DetectionMethod.UNKNOWN,
            has_consolidated=dei.has_consolidated,
            period_type=dei.type_of_current_period,
        )

    # AccountingStandard Enum に変換済みの場合
    if isinstance(standard, AccountingStandard):
        detail_level = _DETAIL_LEVEL_MAP.get(standard)
    else:
        # 未知の文字列の場合（Enum 変換失敗時）
        detail_level = None
        warnings.warn(
            f"未知の会計基準 '{standard}' が検出されました。"
            "DetailLevel を判定できません。",
            EdinetWarning,
            stacklevel=2,
        )

    return DetectedStandard(
        standard=standard,
        method=DetectionMethod.DEI,
        detail_level=detail_level,
        has_consolidated=dei.has_consolidated,
        period_type=dei.type_of_current_period,
    )


def detect_from_namespaces(
    facts: tuple[RawFact, ...],
) -> DetectedStandard:
    """facts の名前空間 URI パターンから会計基準を推定する。

    DEI が利用できない場合のフォールバック手段。
    大量保有報告書（350）等、DEI に AccountingStandardsDEI が
    含まれない書類タイプで使用される。

    判別ルール:
        1. jpigp_cor (jpigp) の存在 → IFRS
        2. jppfs_cor (jppfs) のみ存在（jpigp なし） → J-GAAP
        3. 上記に該当しない → 判別不能 (None)

    US-GAAP / JMIS は名前空間では判別不可能（専用タクソノミが
    存在しないため、D-2.a.md 参照）。

    Args:
        facts: ParsedXBRL.facts から得られる RawFact のタプル。

    Returns:
        DetectedStandard。判別成功時は method=NAMESPACE、
        判別不能時は method=UNKNOWN で返す。
    """
    # 全 facts のユニークな名前空間 URI を収集
    module_groups: set[str] = set()

    seen_uris: set[str] = set()
    for fact in facts:
        uri = fact.namespace_uri
        if uri in seen_uris:
            continue
        seen_uris.add(uri)

        info = classify_namespace(uri)
        if info.module_group is not None:
            module_groups.add(info.module_group)

    frozen_modules = frozenset(module_groups)

    # 判別ルール
    if "jpigp" in module_groups:
        # jpigp_cor（IFRS タクソノミ）が存在 → IFRS
        return DetectedStandard(
            standard=AccountingStandard.IFRS,
            method=DetectionMethod.NAMESPACE,
            detail_level=DetailLevel.DETAILED,
            namespace_modules=frozen_modules,
        )

    if "jppfs" in module_groups:
        # jppfs_cor のみ存在（jpigp なし） → J-GAAP と推定
        return DetectedStandard(
            standard=AccountingStandard.JAPAN_GAAP,
            method=DetectionMethod.NAMESPACE,
            detail_level=DetailLevel.DETAILED,
            namespace_modules=frozen_modules,
        )

    # US-GAAP / JMIS は名前空間で判別不可
    return DetectedStandard(
        standard=None,
        method=DetectionMethod.UNKNOWN,
        namespace_modules=frozen_modules,
    )
