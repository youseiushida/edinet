import enum
from dataclasses import dataclass
from edinet.xbrl.dei import AccountingStandard, DEI, PeriodType
from edinet.xbrl.parser import RawFact

__all__ = ['DetectedStandard', 'DetectionMethod', 'DetailLevel', 'detect_accounting_standard', 'detect_from_dei', 'detect_from_namespaces']

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
    DEI = 'dei'
    NAMESPACE = 'namespace'
    UNKNOWN = 'unknown'

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
    DETAILED = 'detailed'
    BLOCK_ONLY = 'block_only'

@dataclass(frozen=True, slots=True)
class DetectedStandard:
    '''会計基準の判別結果。

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
    '''
    standard: AccountingStandard | str | None
    method: DetectionMethod
    detail_level: DetailLevel | None = ...
    has_consolidated: bool | None = ...
    period_type: PeriodType | str | None = ...
    namespace_modules: frozenset[str] = ...

def detect_accounting_standard(facts: tuple[RawFact, ...], *, dei: DEI | None = None) -> DetectedStandard:
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
def detect_from_namespaces(facts: tuple[RawFact, ...]) -> DetectedStandard:
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
