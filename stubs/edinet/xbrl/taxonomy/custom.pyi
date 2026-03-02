from dataclasses import dataclass
from edinet.models.financial import LineItem as LineItem
from edinet.xbrl._namespaces import NamespaceInfo as NamespaceInfo, classify_namespace as classify_namespace, is_standard_taxonomy as is_standard_taxonomy
from edinet.xbrl.linkbase.definition import DefinitionTree as DefinitionTree
from edinet.financial.statements import Statements as Statements

@dataclass(frozen=True, slots=True)
class CustomItemInfo:
    """非標準（拡張）科目の分析結果。

    Attributes:
        item: 元の LineItem への参照。
        namespace_info: 名前空間の分類結果（カテゴリ、EDINET コード等）。
        parent_standard_concept: general-special arcrole で推定した
            親標準科目のローカル名。DefinitionLinkbase が未指定、
            または該当する関係がない場合は None。
    """
    item: LineItem
    namespace_info: NamespaceInfo
    parent_standard_concept: str | None

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

def detect_custom_items(statements: Statements, *, definition_linkbase: dict[str, DefinitionTree] | None = None) -> CustomDetectionResult:
    """各 LineItem を標準/非標準に分類する。

    Statements 内の全 LineItem について、名前空間 URI を基に
    標準タクソノミか提出者別タクソノミかを判定する。
    非標準科目については NamespaceInfo と、Definition Linkbase が
    利用可能な場合は親標準科目の推定結果を付与する。

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

    Returns:
        CustomDetectionResult。
    """
