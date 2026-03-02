from _typeshed import Incomplete
from dataclasses import dataclass
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XLINK as NS_XLINK
from typing import Literal

logger: Incomplete
ARCROLE_SUMMATION: str

@dataclass(frozen=True, slots=True)
class CalculationArc:
    '''計算リンクベースの 1 本のアーク。

    親 concept から子 concept への加減算関係を表す。

    Attributes:
        parent: 親 concept のローカル名（例: ``"GrossProfit"``）。
        child: 子 concept のローカル名（例: ``"NetSales"``）。
        parent_href: 親 concept の xlink:href（元の値）。
        child_href: 子 concept の xlink:href（元の値）。
        weight: 加減算方向。``1`` が加算、``-1`` が減算。
        order: 同一親の下での表示順序。
        role_uri: 所属ロール URI。
    '''
    parent: str
    child: str
    parent_href: str
    child_href: str
    weight: Literal[1, -1]
    order: float
    role_uri: str

@dataclass(frozen=True, slots=True)
class CalculationTree:
    """1 つの role URI 内の計算木。

    Attributes:
        role_uri: ロール URI。
        arcs: 全アークのタプル（パース順保持）。
        roots: 親のみで子でない concept のタプル（XML 初出順）。
    """
    role_uri: str
    arcs: tuple[CalculationArc, ...]
    roots: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class CalculationLinkbase:
    """計算リンクベースのパース結果全体。

    Attributes:
        source_path: ソースファイルパス（エラーメッセージ用）。
        trees: role_uri → CalculationTree の辞書。
    """
    source_path: str | None
    trees: dict[str, CalculationTree]
    def __post_init__(self) -> None:
        """内部インデックスを構築する。"""
    @property
    def role_uris(self) -> tuple[str, ...]:
        """全ロール URI のタプルを返す。

        Returns:
            ロール URI のタプル。
        """
    def get_tree(self, role_uri: str) -> CalculationTree | None:
        """指定ロールの計算木を返す。

        Args:
            role_uri: ロール URI。

        Returns:
            CalculationTree。存在しない場合は ``None``。
        """
    def children_of(self, parent: str, *, role_uri: str | None = None) -> tuple[CalculationArc, ...]:
        """指定 concept の子アークを返す。

        Args:
            parent: 親 concept のローカル名。
            role_uri: ロール URI。``None`` の場合は全ロールを横断する。

        Returns:
            子アークのタプル。role_uri 指定時は order 昇順、
            ``None`` 時は ``(role_uri, order)`` 昇順。
        """
    def parent_of(self, child: str, *, role_uri: str | None = None) -> tuple[CalculationArc, ...]:
        """指定 concept の親アークを返す。

        Args:
            child: 子 concept のローカル名。
            role_uri: ロール URI。``None`` の場合は全ロールを横断する。

        Returns:
            親アークのタプル。
        """
    def ancestors_of(self, concept: str, *, role_uri: str) -> tuple[str, ...]:
        """指定 concept の祖先を根まで辿って返す。

        ``_parent_index`` を辿り、複数親がある場合は先頭を辿る。
        循環は ``visited`` で防御する。

        Args:
            concept: 起点 concept のローカル名。
            role_uri: ロール URI。

        Returns:
            祖先 concept のタプル（近い順）。ルート concept が末尾。
        """

def parse_calculation_linkbase(xml_bytes: bytes, *, source_path: str | None = None) -> CalculationLinkbase:
    """Calculation Linkbase の XML bytes をパースする。

    Args:
        xml_bytes: ``_cal.xml`` の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。

    Returns:
        パース結果の CalculationLinkbase。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
