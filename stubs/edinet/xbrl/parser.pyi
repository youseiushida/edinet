from dataclasses import dataclass
from edinet.exceptions import EdinetParseError as EdinetParseError, EdinetWarning as EdinetWarning
from edinet.xbrl._namespaces import NS_LINK as NS_LINK, NS_XBRLI as NS_XBRLI, NS_XLINK as NS_XLINK, NS_XML as NS_XML, NS_XSI as NS_XSI
from typing import Literal

@dataclass(frozen=True, slots=True)
class RawFact:
    '''XBRL インスタンスから抽出した生の Fact。

    Attributes:
        concept_qname: Clark notation の QName（``"{namespace}local"``）。
        namespace_uri: 名前空間 URI。
        local_name: ローカル名。
        context_ref: ``contextRef`` 属性値。
        unit_ref: ``unitRef`` 属性値。数値でない Fact は ``None``。
        decimals: ``decimals`` 属性値。``int`` / ``"INF"`` / ``None``。
        value_raw: テキスト値。``xsi:nil`` が真または空タグの場合 ``None``。
        value_inner_xml: 要素内の XML 断片（子要素タグを保持）。空要素や nil の場合は ``None``。
        is_nil: ``xsi:nil`` が真（``true`` / ``1``）かどうか。
        fact_id: ``id`` 属性値。省略時は ``None``。
        xml_lang: ``xml:lang`` 属性値。省略時は ``None``。
        source_line: 元 XML 文書の行番号（1-based）。取得不可時は ``None``。
        order: 抽出された Fact 間の出現順（0-based）。
    '''
    concept_qname: str
    namespace_uri: str
    local_name: str
    context_ref: str
    unit_ref: str | None
    decimals: int | Literal['INF'] | None
    value_raw: str | None
    is_nil: bool
    fact_id: str | None
    xml_lang: str | None
    source_line: int | None
    order: int
    value_inner_xml: str | None = ...

@dataclass(frozen=True, slots=True)
class RawContext:
    """ルート直下の xbrli:context 要素を保持する。"""
    context_id: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class RawUnit:
    """ルート直下の xbrli:unit 要素を保持する。"""
    unit_id: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class RawSchemaRef:
    """ルート直下の link:schemaRef 要素を保持する。"""
    href: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class RawFootnoteLink:
    """ルート直下の link:footnoteLink 要素を保持する。"""
    role: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class RawRoleRef:
    """ルート直下の link:roleRef 要素を保持する。"""
    role_uri: str | None
    href: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class RawArcroleRef:
    """ルート直下の link:arcroleRef 要素を保持する。"""
    arcrole_uri: str | None
    href: str | None
    source_line: int | None
    xml: str

@dataclass(frozen=True, slots=True)
class IgnoredElement:
    """Fact 化しなかったルート直下要素。"""
    concept_qname: str
    namespace_uri: str | None
    local_name: str
    reason: str
    source_line: int | None
    attributes: tuple[tuple[str, str], ...]

@dataclass(frozen=True, slots=True)
class ParsedXBRL:
    '''パース結果を保持するコンテナ。

    Attributes:
        source_path: 元ファイルのパス（任意）。
        source_format: ソース形式（現時点では ``"instance"`` 固定）。
        facts: 抽出された :class:`RawFact` のタプル。
        contexts: ルート直下の :class:`RawContext`。
        units: ルート直下の :class:`RawUnit`。
        schema_refs: ルート直下の :class:`RawSchemaRef`。
        role_refs: ルート直下の :class:`RawRoleRef`。
        arcrole_refs: ルート直下の :class:`RawArcroleRef`。
        footnote_links: ルート直下の :class:`RawFootnoteLink`。
        ignored_elements: Fact 化しなかったルート直下要素。
    '''
    source_path: str | None
    source_format: Literal['instance']
    facts: tuple[RawFact, ...]
    contexts: tuple[RawContext, ...] = ...
    units: tuple[RawUnit, ...] = ...
    schema_refs: tuple[RawSchemaRef, ...] = ...
    role_refs: tuple[RawRoleRef, ...] = ...
    arcrole_refs: tuple[RawArcroleRef, ...] = ...
    footnote_links: tuple[RawFootnoteLink, ...] = ...
    ignored_elements: tuple[IgnoredElement, ...] = ...
    @property
    def fact_count(self) -> int:
        """抽出された Fact の件数を返す。"""

@dataclass(frozen=True, slots=True)
class _RootResources:
    contexts: tuple[RawContext, ...]
    units: tuple[RawUnit, ...]
    schema_refs: tuple[RawSchemaRef, ...]
    role_refs: tuple[RawRoleRef, ...]
    arcrole_refs: tuple[RawArcroleRef, ...]
    footnote_links: tuple[RawFootnoteLink, ...]
    context_ids: frozenset[str]
    unit_ids: frozenset[str]

def parse_xbrl_facts(xbrl_bytes: bytes, *, source_path: str | None = None, strict: bool = True) -> ParsedXBRL:
    """XBRL インスタンス bytes から Fact を抽出する。

    Args:
        xbrl_bytes: XBRL インスタンス文書の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。
        strict: ``True`` の場合、Fact と判定された要素の仕様逸脱を
            :class:`EdinetParseError` として扱う。
            ``False`` の場合は警告を出しつつ ``ignored_elements`` に記録する。

    Returns:
        パース結果を保持する :class:`ParsedXBRL`。

    Raises:
        EdinetParseError: XML 構文エラー、非 XBRL ルート要素、
            または strict モードでの仕様逸脱の場合。

    Note:
        strict モードの検証スコープは ``docs/CODESCOPE.md`` §1 で定義されている。
        要約:

        - **検証する**: XML 構文、schemaRef、context/unit の id 存在・一意性、
          Fact の contextRef/unitRef/decimals 整合性、xsi:nil 整合性、
          非 nil 空値、数値 Fact の lexical 妥当性、重複 Fact 値不整合。
        - **検証しない（上位レイヤーの責務）**: context/unit の内部構造
          （entity/period/measure）、タクソノミ型検証、XBRL 2.1 v-equality、
          ネスト Fact（警告+記録のみ）。
    """
