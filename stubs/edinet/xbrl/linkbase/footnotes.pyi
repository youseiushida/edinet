from _typeshed import Incomplete
from collections.abc import Sequence
from dataclasses import dataclass
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XLINK as NS_XLINK, NS_XML as NS_XML
from edinet.xbrl.parser import RawFootnoteLink as RawFootnoteLink

logger: Incomplete

@dataclass(frozen=True, slots=True)
class Footnote:
    '''脚注。

    XBRL の ``link:footnote`` 要素から抽出した脚注情報。

    Attributes:
        label: xlink:label 属性値（アーク接続用識別子）。
        text: 脚注テキスト（例: ``"※1 当事業年度の…"``）。
        lang: xml:lang 属性値（例: ``"ja"``）。
        role: xlink:role 属性値。
    '''
    label: str
    text: str
    lang: str
    role: str

@dataclass(frozen=True, slots=True)
class FootnoteMap:
    """Fact ID → 脚注のマッピング。

    ``parse_footnote_links()`` の返り値。
    Fact の id 属性値をキーに、紐付けられた脚注を検索できる。

    Attributes:
        _index: Fact ID → Footnote タプルの辞書（arc で紐付けられたもののみ）。
        _all: XML に存在する全 Footnote のタプル（arc による紐付けの有無に関わらず
              収集。重複除去済み。frozen dataclass のデフォルト ``__eq__`` による
              全フィールド一致で判定）。
    """
    def get(self, fact_id: str) -> tuple[Footnote, ...]:
        """Fact ID から脚注を取得する。

        Args:
            fact_id: Fact の id 属性値。

        Returns:
            紐付けられた Footnote のタプル。見つからなければ空タプル。
        """
    def has_footnotes(self, fact_id: str) -> bool:
        """Fact に脚注が存在するかを返す。

        Args:
            fact_id: Fact の id 属性値。
        """
    def all_footnotes(self) -> tuple[Footnote, ...]:
        """全脚注を返す。"""
    @property
    def fact_ids(self) -> tuple[str, ...]:
        """脚注が紐付けられた Fact ID の一覧を返す。"""
    def __len__(self) -> int:
        """脚注が紐付けられた Fact の数を返す。"""
    def __contains__(self, fact_id: object) -> bool:
        """Fact に脚注が存在するかの確認。"""

def parse_footnote_links(raw_links: Sequence[RawFootnoteLink]) -> FootnoteMap:
    """RawFootnoteLink 群から FootnoteMap を構築する。

    各 ``RawFootnoteLink.xml`` を再パースし、loc / footnote / footnoteArc の
    3 要素を抽出して Fact ID → Footnote のマッピングを構築する。

    複数の footnoteLink にまたがる脚注は統合される（同一 Fact ID に対する
    脚注はタプルにまとめられる）。

    Args:
        raw_links: ``ParsedXBRL.footnote_links``。

    Returns:
        構築された FootnoteMap。footnoteLink が空の場合は空の FootnoteMap を返す。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
