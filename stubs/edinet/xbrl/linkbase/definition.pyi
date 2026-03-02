from _typeshed import Incomplete
from dataclasses import dataclass
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XBRLDT as NS_XBRLDT, NS_XLINK as NS_XLINK

logger: Incomplete

@dataclass(frozen=True, slots=True)
class DefinitionArc:
    '''Definition Linkbase の 1 本の arc。

    Attributes:
        from_concept: 親 concept のローカル名（例: ``"ConsolidatedBalanceSheetHeading"``）。
        to_concept: 子 concept のローカル名（例: ``"BalanceSheetTable"``）。
        from_href: 親 concept の xlink:href（XSD 相対パス + フラグメント）。
        to_href: 子 concept の xlink:href。
        arcrole: arcrole URI。
        order: 表示順。
        closed: xbrldt:closed 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``（XML に属性が存在しても無視される）。
        context_element: xbrldt:contextElement 属性値。``all`` arcrole のアークでのみ設定される。
            それ以外のアークでは**常に** ``None``。
        usable: usable 属性値。全 arc 型の XML 属性から読み取るが、
            意味的に有効なのは ``domain-member`` arcrole のみ。
    '''
    from_concept: str
    to_concept: str
    from_href: str
    to_href: str
    arcrole: str
    order: float
    closed: bool | None = ...
    context_element: str | None = ...
    usable: bool = ...

@dataclass(frozen=True, slots=True)
class MemberNode:
    '''ドメイン配下のメンバーノード（ツリー構造）。

    ドメインをルートとし、domain-member arc による階層を再帰的に保持する。
    SS の列ヘッダー構築等で階層情報と usable フラグが必要。

    Attributes:
        concept: メンバーのローカル名（例: ``"ShareholdersEquityAbstract"``）。
        href: xlink:href（XSD 相対パス + フラグメント）。
        usable: Fact を持ちうるか。``False`` の場合は表示専用（Abstract 等）。
        children: 子メンバーノードのタプル（order 順ソート済み）。
    '''
    concept: str
    href: str
    usable: bool = ...
    children: tuple[MemberNode, ...] = ...

@dataclass(frozen=True, slots=True)
class AxisInfo:
    '''1 つの Axis（次元軸）の構造化情報。

    Attributes:
        axis_concept: Axis のローカル名（例: ``"ComponentsOfEquityAxis"``）。
        order: hypercube-dimension arc の order 値（複数 Axis の表示順序）。
        domain: ドメインのルートノード。子にメンバー階層を再帰的に持つ。
            ドメインが未定義の場合は None。
        default_member: デフォルトメンバーのローカル名。
            デフォルトがない場合は None。
    '''
    axis_concept: str
    order: float = ...
    domain: MemberNode | None = ...
    default_member: str | None = ...

@dataclass(frozen=True, slots=True)
class HypercubeInfo:
    '''ハイパーキューブの構造化情報。

    Attributes:
        table_concept: Table のローカル名。
        heading_concept: Heading（ルート要素）のローカル名。
        axes: ハイパーキューブに属する Axis の情報
            （``hypercube-dimension`` arc の order 昇順でソート済み）。
        closed: ハイパーキューブが closed かどうか。
        context_element: ``"segment"`` or ``"scenario"``。
        line_items_concept: LineItems のローカル名。
            LineItems がない場合は None。
    '''
    table_concept: str
    heading_concept: str
    axes: tuple[AxisInfo, ...]
    closed: bool
    context_element: str
    line_items_concept: str | None = ...

@dataclass(frozen=True, slots=True)
class DefinitionTree:
    """1 つの role URI に対応する定義ツリー。

    Attributes:
        role_uri: ロール URI。
        arcs: 全 arc のタプル。認識されない arcrole の arc も含む。
        hypercubes: 構造化されたハイパーキューブ情報のタプル。
            ``arcs`` の部分集合（``all``, ``hypercube-dimension``,
            ``dimension-domain``, ``dimension-default``, ``domain-member``
            arcrole）を構造化したもの。``general-special`` のみの role では
            空タプル（``has_hypercube`` == False）。
    """
    role_uri: str
    arcs: tuple[DefinitionArc, ...]
    hypercubes: tuple[HypercubeInfo, ...]
    @property
    def has_hypercube(self) -> bool:
        """ハイパーキューブ構造を含むかどうか。"""

def parse_definition_linkbase(xml_bytes: bytes, *, source_path: str | None = None) -> dict[str, DefinitionTree]:
    """Definition Linkbase の XML bytes をパースする。

    Args:
        xml_bytes: ``_def.xml`` の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        role_uri をキー、DefinitionTree を値とする辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
