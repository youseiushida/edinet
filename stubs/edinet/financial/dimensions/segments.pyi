from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from edinet.financial.statements import Statements
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import Period, StructuredContext
from edinet.xbrl.linkbase.definition import DefinitionTree
from edinet.xbrl.taxonomy import LabelInfo, TaxonomyResolver

__all__ = ['DimensionAxisSummary', 'SegmentItem', 'SegmentData', 'list_dimension_axes', 'extract_segments']

@dataclass(frozen=True, slots=True)
class _MemberMeta:
    """DefinitionLinkbase から取得したメンバーのメタ情報。"""
    depth: int
    order: float

@dataclass(frozen=True, slots=True)
class DimensionAxisSummary:
    '''Filing 内で検出されたディメンション軸の概要。

    ``list_dimension_axes()`` が返す。ユーザーが XBRL の内部名を
    知らなくても、日本語/英語ラベルで軸を選択できる。

    Attributes:
        local_name: 軸のローカル名（例: ``"OperatingSegmentsAxis"``）。
            ``extract_segments(axis_local_name=...)`` にそのまま渡せる。
        clark: 軸の Clark notation。
        label_ja: 日本語ラベル（例: ``"事業セグメント"``）。
        label_en: 英語ラベル（例: ``"Operating segments"``）。
        is_standard: 標準タクソノミの軸なら True。
        member_count: ユニークメンバー数。
        item_count: この軸を持つ LineItem の総数。
    '''
    local_name: str
    clark: str
    label_ja: str
    label_en: str
    is_standard: bool
    member_count: int
    item_count: int

@dataclass(frozen=True, slots=True)
class SegmentItem:
    '''セグメント内の 1 科目。

    Attributes:
        concept: concept のローカル名（例: ``"NetSales"``）。
        label_ja: 日本語ラベル情報。LineItem から転写。
        label_en: 英語ラベル情報。LineItem から転写。
        value: 値。数値 Fact は Decimal、テキストは str、nil は None。
        period: 期間情報。
        context_id: contextRef 属性値（トレーサビリティ用）。
    '''
    concept: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    period: Period
    context_id: str

@dataclass(frozen=True, slots=True)
class SegmentData:
    '''1 つのセグメントのデータ。

    Attributes:
        name: セグメント名（日本語ラベル。例: ``"自動車"``）。
        member_concept: メンバーのローカル名
            （例: ``"AutomotiveReportableSegmentMember"``）。
        member_qname: メンバーの Clark notation。
        is_standard_member: 標準メンバー（jpcrp_cor）なら True。
            提出者独自メンバーなら False。
        items: セグメント内の科目タプル。
        axis_concept: ディメンション軸のローカル名。
        depth: DefinitionLinkbase から取得したメンバー階層の深さ。
            0 = ドメインルート。DefinitionLinkbase 未提供時は 0。
        is_default_member: AxisInfo.default_member と一致する場合 True。
            DefinitionLinkbase 未提供時は False。
    '''
    name: str
    member_concept: str
    member_qname: str
    is_standard_member: bool
    items: tuple[SegmentItem, ...]
    axis_concept: str = ...
    depth: int = ...
    is_default_member: bool = ...

def list_dimension_axes(source: Statements | Sequence[LineItem], context_map: dict[str, StructuredContext] | None = None, resolver: TaxonomyResolver | None = None, *, consolidated: bool = True) -> tuple[DimensionAxisSummary, ...]:
    """Filing 内の全ディメンション軸を日本語/英語ラベル付きで列挙する。

    ``Statements`` を渡す場合は ``context_map`` / ``resolver`` は不要
    （内部で自動取得される）。低レベル呼び出しでは3引数全て必須。

    Args:
        source: ``Statements`` または ``build_line_items()`` が返した全 LineItem。
        context_map: ``structure_contexts()`` が返した Context 辞書。
            ``Statements`` を渡す場合は省略可。
        resolver: ラベル解決用の TaxonomyResolver。
            ``Statements`` を渡す場合は省略可。
        consolidated: True なら連結、False なら個別の LineItem のみ対象。

    Returns:
        DimensionAxisSummary のタプル。item_count 降順。
        ディメンション軸が存在しなければ空タプル。
    """
def extract_segments(source: Statements | Sequence[LineItem], context_map: dict[str, StructuredContext] | None = None, resolver: TaxonomyResolver | None = None, *, consolidated: bool = True, period: Period | None = None, axis_local_name: str = ..., definition_trees: dict[str, DefinitionTree] | None = None) -> tuple[SegmentData, ...]:
    '''LineItem 群からセグメント別データを抽出する。

    ``Statements`` を渡す場合は ``context_map`` / ``resolver`` は不要
    （内部で自動取得される）。低レベル呼び出しでは3引数全て必須。

    Args:
        source: ``Statements`` または ``build_line_items()`` が返した全 LineItem。
        context_map: ``structure_contexts()`` が返した Context 辞書。
            ``Statements`` を渡す場合は省略可。
        resolver: ラベル解決用の TaxonomyResolver。
            ``Statements`` を渡す場合は省略可。
        consolidated: True なら連結、False なら個別。
        period: 対象期間。None なら全期間のセグメントを抽出。
        axis_local_name: ディメンション軸のローカル名。
            デフォルトは ``"OperatingSegmentsAxis"``。
        definition_trees: ``parse_definition_linkbase()`` の戻り値（任意）。
            指定した場合、メンバーの depth / is_default_member /
            タクソノミ定義順を付与する。

    Returns:
        SegmentData のタプル。セグメントが見つからなければ空タプル。
    '''
