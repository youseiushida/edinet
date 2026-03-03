from dataclasses import dataclass
from edinet.financial.statements import Statements as Statements
from edinet.models.financial import LineItem as LineItem
from edinet.xbrl._namespaces import NamespaceInfo as NamespaceInfo, classify_namespace as classify_namespace, is_standard_taxonomy as is_standard_taxonomy
from edinet.xbrl.linkbase.calculation import CalculationLinkbase as CalculationLinkbase
from edinet.xbrl.linkbase.definition import DefinitionTree as DefinitionTree

@dataclass(frozen=True, slots=True)
class _CalcMappingResult:
    """CalculationLinkbase ベースのマッピング結果（内部用）。

    Attributes:
        ancestor: summation-item 由来の最近接標準科目のローカル名。
            標準科目が見つからない場合は None。
        path: 非標準科目からの経路（ローカル名のタプル）。
        role_uri: マッピングが特定された role URI。
    """
    ancestor: str | None
    path: tuple[str, ...]
    role_uri: str

@dataclass(frozen=True, slots=True)
class CustomItemInfo:
    """非標準（拡張）科目の分析結果。

    Attributes:
        item: 元の LineItem への参照。
        namespace_info: 名前空間の分類結果（カテゴリ、EDINET コード等）。
        parent_standard_concept: general-special arcrole で推定した
            親標準科目のローカル名。DefinitionLinkbase が未指定、
            または該当する関係がない場合は None。
        calculation_ancestor: Calculation Linkbase (summation-item) 由来の
            最近接標準科目のローカル名。CalculationLinkbase が未指定、
            または該当する計算関係がない場合は None。
        calculation_path: 非標準科目から calculation_ancestor までの経路
            （ローカル名のタプル）。先頭が非標準科目、末尾が
            calculation_ancestor。calculation_ancestor が None の場合は
            ルートまでの経路。CalculationLinkbase が未指定の場合は None。
        calculation_role_uri: マッピングが特定された Calculation Linkbase の
            role URI。CalculationLinkbase が未指定の場合は None。
    """
    item: LineItem
    namespace_info: NamespaceInfo
    parent_standard_concept: str | None
    calculation_ancestor: str | None = ...
    calculation_path: tuple[str, ...] | None = ...
    calculation_role_uri: str | None = ...

@dataclass(frozen=True, slots=True)
class CustomDetectionResult:
    """標準/非標準科目の分類結果。

    Attributes:
        custom_items: 非標準科目の分析結果タプル。
        standard_items: 標準科目の LineItem タプル。
        custom_ratio: 非標準科目の割合（0.0〜1.0）。
            全科目数が 0 の場合は 0.0。Fact 単位の割合であり、
            ユニーク concept 数ベースの割合ではない。
        total_count: 全科目数（custom + standard）。
    """
    custom_items: tuple[CustomItemInfo, ...]
    standard_items: tuple[LineItem, ...]
    custom_ratio: float
    total_count: int

def detect_custom_items(statements: Statements, *, definition_linkbase: dict[str, DefinitionTree] | None = None, calculation_linkbase: CalculationLinkbase | None = None) -> CustomDetectionResult:
    """各 LineItem を標準/非標準に分類する。

    Statements 内の全 LineItem について、名前空間 URI を基に
    標準タクソノミか提出者別タクソノミかを判定する。
    非標準科目については NamespaceInfo と、Definition Linkbase が
    利用可能な場合は親標準科目の推定結果を付与する。

    Calculation Linkbase が指定された場合は、summation-item arcrole を
    辿って「どの標準科目の計算内訳か」も推定する。

    Note:
        本関数は XBRL インスタンス内の Fact（LineItem）のみを対象とする。
        タクソノミ定義上の abstract 要素（domainItemType のセグメント Member 等）は
        XBRL インスタンスに Fact として出現しないため検出対象外である。

        同一 concept が複数の期間・次元に出現する場合、各 Fact は独立にカウント
        される。custom_ratio は Fact 単位の割合であり、ユニーク concept 数ベース
        の割合ではない。concept レベルの割合が必要な場合は
        ``{ci.item.local_name for ci in result.custom_items}`` で重複除去すること。

    Args:
        statements: build_statements() で構築した Statements。
        definition_linkbase: parse_definition_linkbase() の戻り値。
            指定した場合、general-special arcrole を用いて
            拡張科目の親標準科目を推定する。None の場合は推定しない。
        calculation_linkbase: parse_calculation_linkbase() の戻り値。
            指定した場合、summation-item arcrole を用いて
            拡張科目の計算上の最近接標準科目を推定する。
            None の場合は推定しない。

    Returns:
        CustomDetectionResult。
    """
def find_custom_concepts(calc_linkbase: CalculationLinkbase) -> tuple[str, ...]:
    """Calculation Linkbase 内の全非標準科目を自動検出する。

    全 CalculationArc の parent/child の href を走査し、
    提出者タクソノミに属する concept を抽出する。

    Args:
        calc_linkbase: パース済みの CalculationLinkbase。

    Returns:
        非標準科目ローカル名のタプル（重複除去・ソート済み）。
    """
