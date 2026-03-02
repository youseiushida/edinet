from _typeshed import Incomplete
from dataclasses import dataclass
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._linkbase_utils import ROLE_LABEL as ROLE_LABEL, ROLE_NEGATED_LABEL as ROLE_NEGATED_LABEL, ROLE_PERIOD_END_LABEL as ROLE_PERIOD_END_LABEL, ROLE_PERIOD_START_LABEL as ROLE_PERIOD_START_LABEL, ROLE_TERSE_LABEL as ROLE_TERSE_LABEL, ROLE_TOTAL_LABEL as ROLE_TOTAL_LABEL, ROLE_VERBOSE_LABEL as ROLE_VERBOSE_LABEL
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XLINK as NS_XLINK

logger: Incomplete

@dataclass(frozen=True, slots=True)
class _LocInfo:
    """loc 要素から抽出した情報。

    Attributes:
        href: xlink:href 属性値（元の値）。
        concept: 正規化済み concept 名。
    """
    href: str
    concept: str

@dataclass(frozen=True, slots=True)
class _RawArc:
    """presentationArc 要素から抽出した情報。

    Attributes:
        from_label: xlink:from 属性値。
        to_label: xlink:to 属性値。
        order: order 属性値。
        preferred_label: preferredLabel 属性値。
    """
    from_label: str
    to_label: str
    order: float
    preferred_label: str | None

@dataclass(frozen=True, slots=True)
class PresentationNode:
    '''Presentation Linkbase のツリーノード。

    Attributes:
        concept: 正規化済み concept 名（例: "CashAndDeposits"）。
        href: 元の xlink:href 値。
        order: 表示順序。
        preferred_label: preferredLabel ロール URI。None の場合は標準ラベル。
        depth: ツリーにおける深さ（ルート = 0）。
        children: 子ノードのタプル（order 順）。
        is_abstract: Abstract ノードかどうか。concept 名が "Abstract" で
            終わるかどうかで判定する。
        is_dimension_node: ディメンション関連ノードかどうか。
    '''
    concept: str
    href: str
    order: float
    preferred_label: str | None = ...
    depth: int = ...
    children: tuple[PresentationNode, ...] = ...
    is_abstract: bool = ...
    is_dimension_node: bool = ...
    @property
    def is_total(self) -> bool:
        """合計行かどうかを返す。

        Returns:
            preferred_label が totalLabel ロールの場合 True。
        """

@dataclass(frozen=True, slots=True)
class PresentationTree:
    """1 つの role URI に対応する Presentation ツリー。

    Attributes:
        role_uri: ツリーが属する role URI。
        roots: ルートノード群（order 順）。
        node_count: ツリー内の全ノード数。
    """
    role_uri: str
    roots: tuple[PresentationNode, ...] = ...
    node_count: int = ...
    def line_items_roots(self) -> tuple[PresentationNode, ...]:
        """LineItems ノード以下のルートを返す。

        Presentation ツリーでは Heading → Table → LineItems の構造が
        一般的であり、実際の科目は LineItems の子として並ぶ。
        本メソッドは LineItems ノードを探索し、その子をルートとして返す。

        LineItems が見つからない場合は roots をそのまま返す。

        Returns:
            LineItems ノードの子、または roots。
        """
    def flatten(self, *, skip_abstract: bool = False, skip_dimension: bool = False) -> tuple[PresentationNode, ...]:
        """ツリーを深さ優先で平坦化する。

        Args:
            skip_abstract: True の場合、Abstract ノードをスキップする。
            skip_dimension: True の場合、ディメンション関連ノードをスキップする。

        Returns:
            深さ優先順のノードタプル。

        Note:
            同一 concept が複数の位置に出現する場合（例: dimension ノードと
            科目ツリーの両方に同じ concept が参照される場合）、返り値には
            同一 concept 名の異なるノードが含まれる。concept のユニーク
            集合が必要な場合は ``{n.concept for n in tree.flatten()}`` を使用する。
        """

def parse_presentation_linkbase(xml_bytes: bytes, *, source_path: str | None = None) -> dict[str, PresentationTree]:
    """Presentation Linkbase XML をパースし、role URI ごとのツリーを返す。

    Args:
        xml_bytes: linkbase XML のバイト列。
        source_path: エラーメッセージ用のソースファイルパス。

    Returns:
        role URI をキー、PresentationTree を値とする辞書。

    Raises:
        EdinetParseError: XML が不正な場合。
    """
def merge_presentation_trees(*tree_dicts: dict[str, PresentationTree]) -> dict[str, PresentationTree]:
    """複数の PresentationTree 辞書をマージする。

    同一 role URI のツリーは再帰的に子をマージし、異なる role URI の
    ツリーはそのまま結合する。

    Args:
        *tree_dicts: マージ対象の辞書群。

    Returns:
        マージ済み辞書。
    """
