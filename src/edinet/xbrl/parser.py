"""XBRL インスタンスから Fact を抽出するパーサー。

XBRL インスタンス文書（bytes）を受け取り、ルート直下の Fact 要素を
:class:`RawFact` として抽出する。Fact 化しない要素も一部を保持し、
後続処理（contexts / units / footnotes / source linking）の土台に使えるようにする。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from typing import Literal
import warnings

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._namespaces import NS_LINK, NS_XBRLI, NS_XSI, NS_XLINK, NS_XML

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_XBRL_ROOT_TAG = f"{{{NS_XBRLI}}}xbrl"
_XBRLI_CONTEXT_TAG = f"{{{NS_XBRLI}}}context"
_XBRLI_UNIT_TAG = f"{{{NS_XBRLI}}}unit"
_LINK_SCHEMEREF_TAG = f"{{{NS_LINK}}}schemaRef"
_LINK_ROLEREF_TAG = f"{{{NS_LINK}}}roleRef"
_LINK_ARCROLEREF_TAG = f"{{{NS_LINK}}}arcroleRef"
_LINK_FOOTNOTELINK_TAG = f"{{{NS_LINK}}}footnoteLink"

_EXCLUDED_NAMESPACES: frozenset[str] = frozenset({NS_XBRLI, NS_LINK})
_QNAME_PREFIX_PATTERN = re.compile(r"(?<![\w.-])([A-Za-z_][\w.-]*):[A-Za-z_][\w.-]*")

# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RawFact:
    """XBRL インスタンスから抽出した生の Fact。

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
    """

    concept_qname: str
    namespace_uri: str
    local_name: str
    context_ref: str
    unit_ref: str | None
    decimals: int | Literal["INF"] | None
    value_raw: str | None
    is_nil: bool
    fact_id: str | None
    xml_lang: str | None
    source_line: int | None
    order: int
    value_inner_xml: str | None = None


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
    """パース結果を保持するコンテナ。

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
    """

    source_path: str | None
    source_format: Literal["instance", "inline"]
    facts: tuple[RawFact, ...]
    contexts: tuple[RawContext, ...] = ()
    units: tuple[RawUnit, ...] = ()
    schema_refs: tuple[RawSchemaRef, ...] = ()
    role_refs: tuple[RawRoleRef, ...] = ()
    arcrole_refs: tuple[RawArcroleRef, ...] = ()
    footnote_links: tuple[RawFootnoteLink, ...] = ()
    ignored_elements: tuple[IgnoredElement, ...] = ()

    @property
    def fact_count(self) -> int:
        """抽出された Fact の件数を返す。"""
        return len(self.facts)


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


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def parse_xbrl_facts(
    xbrl_bytes: bytes,
    *,
    source_path: str | None = None,
    strict: bool = True,
) -> ParsedXBRL:
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
    root = _parse_xml(xbrl_bytes, source_path)
    _validate_root(root, source_path)
    resources = _collect_root_resources(root, source_path=source_path, strict=strict)
    facts, ignored_elements = _extract_facts(
        root,
        source_path,
        strict=strict,
        context_ids=resources.context_ids,
        unit_ids=resources.unit_ids,
    )
    return ParsedXBRL(
        source_path=source_path,
        source_format="instance",
        facts=facts,
        contexts=resources.contexts,
        units=resources.units,
        schema_refs=resources.schema_refs,
        role_refs=resources.role_refs,
        arcrole_refs=resources.arcrole_refs,
        footnote_links=resources.footnote_links,
        ignored_elements=ignored_elements,
    )


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _parse_xml(
    xbrl_bytes: bytes,
    source_path: str | None,
) -> etree._Element:
    """bytes を XML としてパースし、ルート要素を返す。

    Args:
        xbrl_bytes: XML 文書の bytes。
        source_path: エラーメッセージ用のソースパス。

    Returns:
        ルート :class:`~lxml.etree._Element`。

    Raises:
        EdinetParseError: XML 構文エラーの場合。
    """
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=True,
    )
    try:
        tree = etree.parse(BytesIO(xbrl_bytes), parser)  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"XML の解析に失敗しました: {source_path or '(unknown)'}"
        raise EdinetParseError(msg) from exc
    return tree.getroot()


def _validate_root(
    root: etree._Element,
    source_path: str | None,
) -> None:
    """ルート要素が ``xbrli:xbrl`` であることを検証する。

    Args:
        root: XML のルート要素。
        source_path: エラーメッセージ用のソースパス。

    Raises:
        EdinetParseError: ルートタグが XBRL でない場合。
    """
    if root.tag != _XBRL_ROOT_TAG:
        msg = (
            f"XBRL ルート要素が見つかりません "
            f"(期待: {_XBRL_ROOT_TAG}, 実際: {root.tag}): "
            f"{source_path or '(unknown)'}"
        )
        raise EdinetParseError(msg)


def _collect_root_resources(
    root: etree._Element,
    *,
    source_path: str | None,
    strict: bool,
) -> _RootResources:
    """ルート直下の context / unit / schemaRef / footnoteLink を収集する。"""
    contexts: list[RawContext] = []
    units: list[RawUnit] = []
    schema_refs: list[RawSchemaRef] = []
    role_refs: list[RawRoleRef] = []
    arcrole_refs: list[RawArcroleRef] = []
    footnote_links: list[RawFootnoteLink] = []

    context_ids: set[str] = set()
    unit_ids: set[str] = set()
    seen_context_lines: dict[str, int | None] = {}
    seen_unit_lines: dict[str, int | None] = {}

    for child in root:
        if not isinstance(child.tag, str):
            continue

        if child.tag == _XBRLI_CONTEXT_TAG:
            context_id = _normalize_optional_attr(child.get("id"))
            if context_id is None:
                _handle_fact_issue(
                    message="id がない context を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            elif context_id in seen_context_lines:
                first_line = seen_context_lines[context_id]
                first_line_label = first_line if first_line is not None else "?"
                _handle_fact_issue(
                    message=(
                        "重複した context id を検出しました "
                        f"(id={context_id!r}, first_line={first_line_label})"
                    ),
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            else:
                seen_context_lines[context_id] = child.sourceline
                context_ids.add(context_id)

            contexts.append(
                RawContext(
                    context_id=context_id,
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

        if child.tag == _XBRLI_UNIT_TAG:
            unit_id = _normalize_optional_attr(child.get("id"))
            if unit_id is None:
                _handle_fact_issue(
                    message="id がない unit を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            elif unit_id in seen_unit_lines:
                first_line = seen_unit_lines[unit_id]
                first_line_label = first_line if first_line is not None else "?"
                _handle_fact_issue(
                    message=(
                        "重複した unit id を検出しました "
                        f"(id={unit_id!r}, first_line={first_line_label})"
                    ),
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            else:
                seen_unit_lines[unit_id] = child.sourceline
                unit_ids.add(unit_id)

            units.append(
                RawUnit(
                    unit_id=unit_id,
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

        if child.tag == _LINK_SCHEMEREF_TAG:
            href = _normalize_optional_attr(child.get(f"{{{NS_XLINK}}}href"))
            if href is None:
                _handle_fact_issue(
                    message="href がない schemaRef を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            schema_refs.append(
                RawSchemaRef(
                    href=href,
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

        if child.tag == _LINK_ROLEREF_TAG:
            role_uri = _normalize_optional_attr(child.get("roleURI"))
            href = _normalize_optional_attr(child.get(f"{{{NS_XLINK}}}href"))
            if role_uri is None:
                _handle_fact_issue(
                    message="roleURI がない roleRef を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            if href is None:
                _handle_fact_issue(
                    message="href がない roleRef を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            role_refs.append(
                RawRoleRef(
                    role_uri=role_uri,
                    href=href,
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

        if child.tag == _LINK_ARCROLEREF_TAG:
            arcrole_uri = _normalize_optional_attr(child.get("arcroleURI"))
            href = _normalize_optional_attr(child.get(f"{{{NS_XLINK}}}href"))
            if arcrole_uri is None:
                _handle_fact_issue(
                    message="arcroleURI がない arcroleRef を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            if href is None:
                _handle_fact_issue(
                    message="href がない arcroleRef を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            arcrole_refs.append(
                RawArcroleRef(
                    arcrole_uri=arcrole_uri,
                    href=href,
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

        if child.tag == _LINK_FOOTNOTELINK_TAG:
            footnote_links.append(
                RawFootnoteLink(
                    role=child.get(f"{{{NS_XLINK}}}role"),
                    source_line=child.sourceline,
                    xml=_serialize_outer_xml(child),
                ),
            )
            continue

    if not schema_refs:
        _handle_fact_issue(
            message="schemaRef が見つかりません",
            source_path=source_path,
            source_line=root.sourceline,
            strict=strict,
        )
    elif len(schema_refs) > 1:
        _handle_fact_issue(
            message=f"schemaRef が複数存在します (count={len(schema_refs)})",
            source_path=source_path,
            source_line=root.sourceline,
            strict=strict,
        )

    return _RootResources(
        contexts=tuple(contexts),
        units=tuple(units),
        schema_refs=tuple(schema_refs),
        role_refs=tuple(role_refs),
        arcrole_refs=tuple(arcrole_refs),
        footnote_links=tuple(footnote_links),
        context_ids=frozenset(context_ids),
        unit_ids=frozenset(unit_ids),
    )


def _extract_facts(
    root: etree._Element,
    source_path: str | None,
    *,
    strict: bool,
    context_ids: frozenset[str],
    unit_ids: frozenset[str],
) -> tuple[tuple[RawFact, ...], tuple[IgnoredElement, ...]]:
    """ルート直下の子要素から Fact を抽出する。"""
    facts: list[RawFact] = []
    ignored_elements: list[IgnoredElement] = []
    order = 0
    seen_fact_ids: dict[str, int | None] = {}
    seen_fact_signatures: dict[
        tuple[str, str, str | None, str | None],
        tuple[tuple[object, str | None, bool], int | Literal["INF"] | None, int | None],
    ] = {}

    for child in root:
        # コメント・PI を除外
        if not isinstance(child.tag, str):
            continue

        tag: str = child.tag
        ns, local = _split_clark_qname(tag)
        if ns is None:
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="名前空間なし要素のため Fact として扱いません",
                source_path=source_path,
                warn=True,
            )
            continue

        # ルートリソースは別レーンで保持済み
        if tag in {
            _XBRLI_CONTEXT_TAG,
            _XBRLI_UNIT_TAG,
            _LINK_SCHEMEREF_TAG,
            _LINK_ROLEREF_TAG,
            _LINK_ARCROLEREF_TAG,
            _LINK_FOOTNOTELINK_TAG,
        }:
            continue

        # xbrli / link のその他要素は Fact 対象外（記録のみ行う）
        if ns in _EXCLUDED_NAMESPACES:
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="xbrli/link 名前空間の管理要素のため Fact として扱いません",
                source_path=source_path,
                warn=False,
            )
            continue

        nested_fact_found = _contains_nested_fact_candidate(child)
        if nested_fact_found:
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason=(
                    "ネストされた Fact 候補を検出しました "
                    "(v0.1 はルート直下の Fact のみ抽出)"
                ),
                source_path=source_path,
                warn=True,
            )
            continue

        context_ref_raw = child.get("contextRef")
        if context_ref_raw is None:
            _handle_fact_issue(
                message="contextRef がない Fact を検出しました",
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="contextRef がないため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        context_ref = context_ref_raw.strip()
        if context_ref == "":
            _handle_fact_issue(
                message="contextRef が空文字の Fact を検出しました",
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="contextRef が空文字のため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        if context_ref not in context_ids:
            _handle_fact_issue(
                message=f"未定義の contextRef を持つ Fact を検出しました (contextRef={context_ref!r})",
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason=f"未定義の contextRef={context_ref!r} のため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        # xsi:nil 判定
        nil_attr = child.get(f"{{{NS_XSI}}}nil")
        try:
            is_nil = _parse_xsi_nil(
                nil_attr,
                element_tag=tag,
                source_path=source_path,
            )
        except EdinetParseError:
            _handle_fact_issue(
                message=(
                    "不正な xsi:nil 属性値を持つ Fact を検出しました "
                    f"(xsi:nil={nil_attr!r})"
                ),
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason=f"不正な xsi:nil={nil_attr!r} のため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        # 値の取得: mixed-content の場合も子孫要素の text/tail を落とさない。
        if is_nil:
            has_non_whitespace_text = any(
                text.strip() != "" for text in child.itertext() if text is not None
            )
            has_element_children = _has_element_children(child)
            if has_non_whitespace_text or has_element_children:
                _handle_fact_issue(
                    message="xsi:nil が真なのに値を持つ Fact を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
                _record_ignored_element(
                    ignored_elements=ignored_elements,
                    element=child,
                    reason="xsi:nil が真なのに値を持つため Fact として抽出しません",
                    source_path=source_path,
                    warn=False,
                )
                continue
            value_raw = None
            value_inner_xml = None
        else:
            text_content = "".join(child.itertext())
            value_raw = text_content if text_content != "" else None
            if _has_element_children(child):
                inner_xml = _extract_inner_xml(child)
                value_inner_xml = inner_xml if inner_xml != "" else None
            else:
                value_inner_xml = None

        unit_ref_raw = child.get("unitRef")
        decimals_raw = child.get("decimals")

        if unit_ref_raw is None and decimals_raw is not None:
            _handle_fact_issue(
                message=(
                    "unitRef がないのに decimals が設定された Fact を検出しました "
                    f"(decimals={decimals_raw!r})"
                ),
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="unitRef がないのに decimals が設定されているため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        # decimals
        try:
            decimals = _parse_decimals(decimals_raw, tag, source_path)
        except EdinetParseError:
            _handle_fact_issue(
                message=(
                    "不正な decimals 属性値を持つ Fact を検出しました "
                    f"(decimals={decimals_raw!r})"
                ),
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason=f"不正な decimals={decimals_raw!r} のため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        # unitRef（存在する場合のみ参照整合性を検証）
        unit_ref: str | None
        if unit_ref_raw is not None:
            unit_ref = unit_ref_raw.strip()
            if unit_ref == "":
                _handle_fact_issue(
                    message="unitRef が空文字の Fact を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
                _record_ignored_element(
                    ignored_elements=ignored_elements,
                    element=child,
                    reason="unitRef が空文字のため Fact として抽出しません",
                    source_path=source_path,
                    warn=False,
                )
                continue
            if decimals is None and not is_nil:
                _handle_fact_issue(
                    message="decimals がない数値 Fact を検出しました (unitRef が存在)",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
                _record_ignored_element(
                    ignored_elements=ignored_elements,
                    element=child,
                    reason="unitRef があるのに decimals がないため Fact として抽出しません",
                    source_path=source_path,
                    warn=False,
                )
                continue
            if unit_ref not in unit_ids:
                _handle_fact_issue(
                    message=f"未定義の unitRef を持つ Fact を検出しました (unitRef={unit_ref!r})",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
                _record_ignored_element(
                    ignored_elements=ignored_elements,
                    element=child,
                    reason=f"未定義の unitRef={unit_ref!r} のため Fact として抽出しません",
                    source_path=source_path,
                    warn=False,
                )
                continue
        else:
            unit_ref = None

        if not is_nil and value_inner_xml is None and (value_raw is None or value_raw.strip() == ""):
            _handle_fact_issue(
                message="非 nil Fact の値が空です",
                source_path=source_path,
                source_line=child.sourceline,
                strict=strict,
            )
            _record_ignored_element(
                ignored_elements=ignored_elements,
                element=child,
                reason="非 nil Fact の値が空のため Fact として抽出しません",
                source_path=source_path,
                warn=False,
            )
            continue

        # 数値 Fact の lexical 妥当性検証（S-10）
        if unit_ref is not None and not is_nil and value_inner_xml is None and value_raw is not None:
            if _normalize_numeric_lexical(value_raw) is None:
                _handle_fact_issue(
                    message=(
                        "数値 Fact の値が数値として解釈できません "
                        f"(value={value_raw!r})"
                    ),
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
                _record_ignored_element(
                    ignored_elements=ignored_elements,
                    element=child,
                    reason=f"数値 Fact の値 {value_raw!r} が数値として解釈できないため Fact として抽出しません",
                    source_path=source_path,
                    warn=False,
                )
                continue

        # xml:lang（継承解決を含む）
        xml_lang = _resolve_xml_lang(child)

        fact_signature_key = (tag, context_ref, unit_ref, xml_lang)
        fact_signature_value = _build_fact_signature_value(
            value_raw=value_raw,
            value_inner_xml=value_inner_xml,
            is_nil=is_nil,
            unit_ref=unit_ref,
        )
        if fact_signature_key in seen_fact_signatures:
            existing_signature, existing_decimals, first_line = seen_fact_signatures[fact_signature_key]
            if existing_signature != fact_signature_value:
                first_line_label = first_line if first_line is not None else "?"
                _handle_fact_issue(
                    message=(
                        "不整合な重複 Fact を検出しました "
                        "(同一 concept/contextRef/unitRef/xml:lang で値が不一致) "
                        f"(concept={tag!r}, contextRef={context_ref!r}, "
                        f"unitRef={unit_ref!r}, xml:lang={xml_lang!r}, "
                        f"first_line={first_line_label})"
                    ),
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            elif existing_decimals != decimals:
                first_line_label = first_line if first_line is not None else "?"
                _handle_fact_issue(
                    message=(
                        "重複 Fact の decimals が不一致です "
                        "(同一 concept/contextRef/unitRef/xml:lang で decimals が不一致) "
                        f"(concept={tag!r}, contextRef={context_ref!r}, "
                        f"unitRef={unit_ref!r}, xml:lang={xml_lang!r}, "
                        f"first_line={first_line_label}, "
                        f"first_decimals={existing_decimals!r}, decimals={decimals!r})"
                    ),
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
        else:
            seen_fact_signatures[fact_signature_key] = (
                fact_signature_value,
                decimals,
                child.sourceline,
            )

        fact_id_raw = child.get("id")
        fact_id: str | None = None
        if fact_id_raw is not None:
            normalized_fact_id = fact_id_raw.strip()
            if normalized_fact_id == "":
                _handle_fact_issue(
                    message="id が空文字の Fact を検出しました",
                    source_path=source_path,
                    source_line=child.sourceline,
                    strict=strict,
                )
            else:
                fact_id = normalized_fact_id
                if normalized_fact_id in seen_fact_ids:
                    first_line = seen_fact_ids[normalized_fact_id]
                    first_line_label = first_line if first_line is not None else "?"
                    _handle_fact_issue(
                        message=(
                            "重複した Fact id を検出しました "
                            f"(id={normalized_fact_id!r}, first_line={first_line_label})"
                        ),
                        source_path=source_path,
                        source_line=child.sourceline,
                        strict=strict,
                    )
                else:
                    seen_fact_ids[normalized_fact_id] = child.sourceline

        fact = RawFact(
            concept_qname=tag,
            namespace_uri=ns,
            local_name=local,
            context_ref=context_ref,
            unit_ref=unit_ref,
            decimals=decimals,
            value_raw=value_raw,
            is_nil=is_nil,
            fact_id=fact_id,
            xml_lang=xml_lang,
            source_line=child.sourceline,
            order=order,
            value_inner_xml=value_inner_xml,
        )
        facts.append(fact)
        order += 1

    return tuple(facts), tuple(ignored_elements)


def _normalize_optional_attr(raw: str | None) -> str | None:
    """属性値を正規化して返す。None/空文字は None。"""
    if raw is None:
        return None
    normalized = raw.strip()
    if normalized == "":
        return None
    return normalized


def _serialize_outer_xml(element: etree._Element) -> str:
    """要素全体（開始/終了タグを含む）を XML 文字列として返す。

    lxml の ``tostring`` は in-scope namespace 宣言を自動的に
    出力するため、子要素の deepcopy を伴う再構築は不要。
    """
    return etree.tostring(element, encoding="unicode", with_tail=False)


def _split_clark_qname(tag: str) -> tuple[str | None, str]:
    """Clark notation を (namespace_uri, local_name) に分解する。"""
    if not tag.startswith("{"):
        return None, tag
    ns_end = tag.find("}")
    if ns_end <= 1:
        return None, tag
    return tag[1:ns_end], tag[ns_end + 1 :]


def _record_ignored_element(
    *,
    ignored_elements: list[IgnoredElement],
    element: etree._Element,
    reason: str,
    source_path: str | None,
    warn: bool,
) -> None:
    """Fact 化しなかった要素を記録し、必要なら warning を出す。"""
    assert isinstance(element.tag, str)
    ns, local = _split_clark_qname(element.tag)
    attrs = tuple(sorted((key, value) for key, value in element.attrib.items()))
    ignored_elements.append(
        IgnoredElement(
            concept_qname=element.tag,
            namespace_uri=ns,
            local_name=local,
            reason=reason,
            source_line=element.sourceline,
            attributes=attrs,
        ),
    )
    if warn:
        _warn_issue(
            message=f"{reason} (要素={element.tag})",
            source_path=source_path,
            source_line=element.sourceline,
        )


def _warn_issue(
    *,
    message: str,
    source_path: str | None,
    source_line: int | None,
) -> None:
    """strict に依存しない warning を発行する。"""
    location = f"{source_path or '(unknown)'}:{source_line or '?'}"
    warnings.warn(f"{message}: {location}", EdinetWarning, stacklevel=3)


def _parse_xsi_nil(
    raw: str | None,
    *,
    element_tag: str,
    source_path: str | None,
) -> bool:
    """xsi:nil 属性値をパースして真偽値を返す。"""
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    msg = (
        "不正な xsi:nil 属性値です "
        f"(xsi:nil={raw!r}, 要素={element_tag}): "
        f"{source_path or '(unknown)'}"
    )
    raise EdinetParseError(msg)


def _contains_nested_fact_candidate(element: etree._Element) -> bool:
    """要素配下に contextRef を持つ Fact 候補があるかを判定する。"""
    for descendant in element.iterdescendants():
        if not isinstance(descendant.tag, str):
            continue
        tag = descendant.tag
        if not tag.startswith("{"):
            continue
        ns_end = tag.find("}")
        if ns_end <= 1:
            continue
        ns = tag[1:ns_end]
        if ns in _EXCLUDED_NAMESPACES:
            continue
        if descendant.get("contextRef") is not None:
            return True
    return False


def _has_element_children(element: etree._Element) -> bool:
    """要素子ノード（コメント/PI 除く）が存在するかを返す。"""
    return any(isinstance(child.tag, str) for child in element)


def _resolve_xml_lang(element: etree._Element) -> str | None:
    """xml:lang を継承解決して返す。"""
    current: etree._Element | None = element
    while current is not None:
        raw = current.get(f"{{{NS_XML}}}lang")
        if raw is not None:
            normalized = raw.strip()
            if normalized == "":
                return None
            return normalized
        current = current.getparent()
    return None


def _build_fact_signature_value(
    *,
    value_raw: str | None,
    value_inner_xml: str | None,
    is_nil: bool,
    unit_ref: str | None,
) -> tuple[object, str | None, bool]:
    """重複 Fact 判定用の値シグネチャを構築する。"""
    if unit_ref is not None and not is_nil and value_inner_xml is None and value_raw is not None:
        numeric = _normalize_numeric_lexical(value_raw)
        if numeric is not None:
            return (numeric, value_inner_xml, is_nil)
    return (value_raw, value_inner_xml, is_nil)


def _normalize_numeric_lexical(raw: str) -> Decimal | None:
    """数値 lexical 表現を Decimal に正規化する。"""
    normalized = raw.strip()
    if normalized == "":
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _extract_inner_xml(element: etree._Element) -> str:
    """要素内の XML 断片（子要素タグ込み）を返す。

    子要素は ``deepcopy`` + ``cleanup_namespaces`` で不要な名前空間宣言を除去する。
    テキストブロック Fact でのみ呼ばれるため影響は限定的。
    """
    parts: list[str] = []
    if element.text is not None:
        parts.append(element.text)
    for child in element:
        child_copy = deepcopy(child)
        etree.cleanup_namespaces(child_copy)

        required_prefixes = _collect_qname_prefixes(child)
        missing_ns: dict[str, str] = {}
        for prefix in required_prefixes:
            if prefix in child_copy.nsmap:
                continue
            uri = element.nsmap.get(prefix)
            if uri is None:
                continue
            missing_ns[prefix] = uri
        if missing_ns:
            child_nsmap = dict(child_copy.nsmap)
            child_nsmap.update(missing_ns)
            wrapped = etree.Element(child_copy.tag, nsmap=child_nsmap)
            for key, value in child_copy.attrib.items():
                wrapped.set(key, value)
            wrapped.text = child_copy.text
            for grandchild in child_copy:
                wrapped.append(deepcopy(grandchild))
            child_copy = wrapped

        parts.append(
            etree.tostring(
                child_copy,
                encoding="unicode",
                with_tail=False,
            ),
        )
        if child.tail is not None:
            parts.append(child.tail)
    return "".join(parts)


def _collect_qname_prefixes(element: etree._Element) -> set[str]:
    """QName lexical 値に含まれる prefix を収集する。"""
    prefixes: set[str] = set()
    for node in element.iter():
        for attr_value in node.attrib.values():
            prefixes.update(_extract_qname_prefixes_from_text(attr_value))
        if node.text:
            prefixes.update(_extract_qname_prefixes_from_text(node.text))
    return prefixes


def _extract_qname_prefixes_from_text(text: str) -> set[str]:
    """文字列中の ``prefix:local`` 形式から prefix を抽出する。"""
    return {match.group(1) for match in _QNAME_PREFIX_PATTERN.finditer(text)}


def _parse_decimals(
    raw: str | None,
    element_tag: str,
    source_path: str | None,
) -> int | Literal["INF"] | None:
    """decimals 属性値をパースする。

    Args:
        raw: ``decimals`` 属性の生の文字列値。``None`` は属性なし。
        element_tag: エラーメッセージ用の要素タグ。
        source_path: エラーメッセージ用のソースパス。

    Returns:
        ``int`` / ``"INF"`` / ``None``。

    Raises:
        EdinetParseError: 不正な値の場合。
    """
    if raw is None:
        return None
    normalized = raw.strip()
    if normalized.upper() == "INF":
        return "INF"
    try:
        return int(normalized)
    except ValueError:
        msg = (
            f"不正な decimals 属性値です "
            f"(decimals={raw!r}, 要素={element_tag}): "
            f"{source_path or '(unknown)'}"
        )
        raise EdinetParseError(msg) from None


def _handle_fact_issue(
    *,
    message: str,
    source_path: str | None,
    source_line: int | None,
    strict: bool,
) -> None:
    """Fact 抽出中の仕様逸脱を strict/lenient で処理する。"""
    location = f"{source_path or '(unknown)'}:{source_line or '?'}"
    full_message = f"{message}: {location}"
    if strict:
        raise EdinetParseError(full_message)
    warnings.warn(full_message, EdinetWarning, stacklevel=3)
