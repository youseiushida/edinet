"""iXBRL（Inline XBRL）から Fact を抽出するパーサー。

iXBRL（XHTML 埋め込み XBRL）文書を受け取り、``ix:nonFraction`` / ``ix:nonNumeric``
要素を :class:`~edinet.xbrl.parser.RawFact` として抽出する。
出力型は従来の XBRL パーサー（:func:`~edinet.xbrl.parser.parse_xbrl_facts`）と
共通であり、下流パイプラインをそのまま適用できる。
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from io import BytesIO

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._namespaces import NS_LINK, NS_XBRLI, NS_XSI, NS_XLINK
from edinet.xbrl.parser import (
    IgnoredElement,
    ParsedXBRL,
    RawArcroleRef,
    RawContext,
    RawFact,
    RawFootnoteLink,
    RawRoleRef,
    RawSchemaRef,
    RawUnit,
    _extract_inner_xml,
    _handle_fact_issue,
    _parse_decimals,
    _resolve_xml_lang,
    _serialize_outer_xml,
)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

NS_IX = "http://www.xbrl.org/2008/inlineXBRL"
"""Inline XBRL 名前空間。"""

_IX_RESOURCES_TAG = f"{{{NS_IX}}}resources"
_IX_REFERENCES_TAG = f"{{{NS_IX}}}references"
_IX_NON_FRACTION_TAG = f"{{{NS_IX}}}nonFraction"
_IX_NON_NUMERIC_TAG = f"{{{NS_IX}}}nonNumeric"
_IX_CONTINUATION_TAG = f"{{{NS_IX}}}continuation"

_XBRLI_CONTEXT_TAG = f"{{{NS_XBRLI}}}context"
_XBRLI_UNIT_TAG = f"{{{NS_XBRLI}}}unit"
_LINK_SCHEMAREF_TAG = f"{{{NS_LINK}}}schemaRef"

_DATE_CJK_PATTERN = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
"""「2026年3月4日」→ ISO 日付変換用パターン。"""


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def merge_ixbrl_results(results: Sequence[ParsedXBRL]) -> ParsedXBRL:
    """複数の iXBRL パース結果を IXDS として統合する。

    IXDS（Inline XBRL Document Set）では1つの提出書類が複数の iXBRL
    ファイルに分割される。本関数は各ファイルの ``parse_ixbrl_facts()``
    結果を統合し、単一の ``ParsedXBRL`` を返す。

    Args:
        results: 各 iXBRL ファイルの ``parse_ixbrl_facts()`` 結果。
            入力順にファクトが連結される。

    Returns:
        統合された ``ParsedXBRL``。
        ``source_path`` は ``"(merged)"``、``source_format`` は ``"inline"``。
    """
    all_facts: list[RawFact] = []
    all_contexts: list[RawContext] = []
    all_units: list[RawUnit] = []
    all_schema_refs: list[RawSchemaRef] = []
    all_role_refs: list[RawRoleRef] = []
    all_arcrole_refs: list[RawArcroleRef] = []
    all_footnote_links: list[RawFootnoteLink] = []
    all_ignored: list[IgnoredElement] = []

    seen_ctx: set[str] = set()
    seen_unit: set[str] = set()
    seen_schema_href: set[str] = set()
    seen_role_uri: set[str] = set()
    seen_arcrole_uri: set[str] = set()

    order = 0
    for parsed in results:
        for fact in parsed.facts:
            all_facts.append(replace(fact, order=order))
            order += 1

        for ctx in parsed.contexts:
            if ctx.context_id is None:
                all_contexts.append(ctx)
            elif ctx.context_id not in seen_ctx:
                all_contexts.append(ctx)
                seen_ctx.add(ctx.context_id)

        for unit in parsed.units:
            if unit.unit_id is None:
                all_units.append(unit)
            elif unit.unit_id not in seen_unit:
                all_units.append(unit)
                seen_unit.add(unit.unit_id)

        for sr in parsed.schema_refs:
            if sr.href is None:
                all_schema_refs.append(sr)
            elif sr.href not in seen_schema_href:
                all_schema_refs.append(sr)
                seen_schema_href.add(sr.href)

        for rr in parsed.role_refs:
            if rr.role_uri is None:
                all_role_refs.append(rr)
            elif rr.role_uri not in seen_role_uri:
                all_role_refs.append(rr)
                seen_role_uri.add(rr.role_uri)

        for ar in parsed.arcrole_refs:
            if ar.arcrole_uri is None:
                all_arcrole_refs.append(ar)
            elif ar.arcrole_uri not in seen_arcrole_uri:
                all_arcrole_refs.append(ar)
                seen_arcrole_uri.add(ar.arcrole_uri)

        all_footnote_links.extend(parsed.footnote_links)
        all_ignored.extend(parsed.ignored_elements)

    return ParsedXBRL(
        source_path="(merged)",
        source_format="inline",
        facts=tuple(all_facts),
        contexts=tuple(all_contexts),
        units=tuple(all_units),
        schema_refs=tuple(all_schema_refs),
        role_refs=tuple(all_role_refs),
        arcrole_refs=tuple(all_arcrole_refs),
        footnote_links=tuple(all_footnote_links),
        ignored_elements=tuple(all_ignored),
    )


def parse_ixbrl_facts(
    ixbrl_bytes: bytes,
    *,
    source_path: str | None = None,
    strict: bool = True,
) -> ParsedXBRL:
    """iXBRL（Inline XBRL）bytes から Fact を抽出する。

    Args:
        ixbrl_bytes: iXBRL 文書（XHTML）の bytes。
        source_path: エラーメッセージに含めるソースパス（任意）。
        strict: ``True`` の場合、仕様逸脱を :class:`EdinetParseError` として扱う。
            ``False`` の場合は警告を出しつつスキップする。

    Returns:
        パース結果を保持する :class:`ParsedXBRL`。
        ``source_format`` は ``"inline"``。

    Raises:
        EdinetParseError: XML 構文エラー、非 iXBRL ルート要素、
            または strict モードでの仕様逸脱の場合。
    """
    cleaned = _strip_bom(ixbrl_bytes)
    root = _parse_xml(cleaned, source_path)
    _validate_ixbrl_root(root, source_path)

    # ix:continuation 検出チェック
    _warn_if_continuation(root, source_path)

    contexts, units, schema_refs = _collect_ixbrl_resources(root, source_path, strict)
    context_ids = frozenset(c.context_id for c in contexts if c.context_id is not None)
    unit_ids = frozenset(u.unit_id for u in units if u.unit_id is not None)

    facts = _extract_ixbrl_facts(
        root,
        source_path=source_path,
        strict=strict,
        context_ids=context_ids,
        unit_ids=unit_ids,
    )

    return ParsedXBRL(
        source_path=source_path,
        source_format="inline",
        facts=facts,
        contexts=contexts,
        units=units,
        schema_refs=schema_refs,
    )


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _strip_bom(data: bytes) -> bytes:
    """UTF-8 BOM を除去する。

    Args:
        data: 入力 bytes。

    Returns:
        BOM を除去した bytes。
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:]
    return data


def _parse_xml(
    data: bytes,
    source_path: str | None,
) -> etree._Element:
    """bytes を XML としてパースし、ルート要素を返す。

    Args:
        data: XML 文書の bytes。
        source_path: エラーメッセージ用のソースパス。

    Returns:
        ルート要素。

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
        tree = etree.parse(BytesIO(data), parser)  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"XML の解析に失敗しました: {source_path or '(unknown)'}"
        raise EdinetParseError(msg) from exc
    return tree.getroot()


def _validate_ixbrl_root(
    root: etree._Element,
    source_path: str | None,
) -> None:
    """ルート要素が iXBRL（XHTML + ix 名前空間）であることを検証する。

    Args:
        root: XML のルート要素。
        source_path: エラーメッセージ用のソースパス。

    Raises:
        EdinetParseError: ルートが html でないか ix 名前空間が未定義の場合。
    """
    tag = root.tag
    # <html> or <{xhtml_ns}html>
    local_name = etree.QName(tag).localname if isinstance(tag, str) else ""
    if local_name != "html":
        msg = (
            f"iXBRL ルート要素が見つかりません "
            f"(期待: html, 実際: {tag}): "
            f"{source_path or '(unknown)'}"
        )
        raise EdinetParseError(msg)

    # ix 名前空間の存在チェック
    nsmap = root.nsmap
    if NS_IX not in nsmap.values():
        msg = (
            f"ix 名前空間 ({NS_IX}) が定義されていません: "
            f"{source_path or '(unknown)'}"
        )
        raise EdinetParseError(msg)


def _warn_if_continuation(
    root: etree._Element,
    source_path: str | None,
) -> None:
    """ix:continuation が存在する場合に警告を発行する。

    Args:
        root: XML のルート要素。
        source_path: エラーメッセージ用のソースパス。
    """
    continuation = root.find(f".//{_IX_CONTINUATION_TAG}")
    if continuation is not None:
        location = f"{source_path or '(unknown)'}:{continuation.sourceline or '?'}"
        warnings.warn(
            f"ix:continuation は現在未対応です（検出位置: {location}）",
            EdinetWarning,
            stacklevel=3,
        )


def _collect_ixbrl_resources(
    root: etree._Element,
    source_path: str | None,
    strict: bool,
) -> tuple[tuple[RawContext, ...], tuple[RawUnit, ...], tuple[RawSchemaRef, ...]]:
    """ix:header 内の context / unit / schemaRef を収集する。

    Args:
        root: ルート要素。
        source_path: エラーメッセージ用のソースパス。
        strict: strict モードかどうか。

    Returns:
        (contexts, units, schema_refs) のタプル。
    """
    contexts: list[RawContext] = []
    units: list[RawUnit] = []
    schema_refs: list[RawSchemaRef] = []

    # ix:resources 内の context / unit
    for resources_elem in root.iter(_IX_RESOURCES_TAG):
        for child in resources_elem:
            if not isinstance(child.tag, str):
                continue
            if child.tag == _XBRLI_CONTEXT_TAG:
                context_id = child.get("id")
                if context_id is not None:
                    context_id = context_id.strip() or None
                contexts.append(
                    RawContext(
                        context_id=context_id,
                        source_line=child.sourceline,
                        xml=_serialize_outer_xml(child),
                    )
                )
            elif child.tag == _XBRLI_UNIT_TAG:
                unit_id = child.get("id")
                if unit_id is not None:
                    unit_id = unit_id.strip() or None
                units.append(
                    RawUnit(
                        unit_id=unit_id,
                        source_line=child.sourceline,
                        xml=_serialize_outer_xml(child),
                    )
                )

    # ix:references 内の schemaRef
    for references_elem in root.iter(_IX_REFERENCES_TAG):
        for child in references_elem:
            if not isinstance(child.tag, str):
                continue
            if child.tag == _LINK_SCHEMAREF_TAG:
                href = child.get(f"{{{NS_XLINK}}}href")
                if href is not None:
                    href = href.strip() or None
                schema_refs.append(
                    RawSchemaRef(
                        href=href,
                        source_line=child.sourceline,
                        xml=_serialize_outer_xml(child),
                    )
                )

    return tuple(contexts), tuple(units), tuple(schema_refs)


def _resolve_ixbrl_name(
    element: etree._Element,
    name_attr: str,
    source_path: str | None,
) -> tuple[str, str, str]:
    """name 属性を Clark notation に変換する。

    iXBRL の ``name="prefix:localName"`` を
    ``("{namespace}localName", namespace_uri, localName)`` に変換する。

    Args:
        element: name 属性を持つ要素（名前空間解決に使用）。
        name_attr: ``name`` 属性の値。
        source_path: エラーメッセージ用のソースパス。

    Returns:
        (concept_qname, namespace_uri, local_name)。

    Raises:
        EdinetParseError: プレフィクスが未定義の場合。
    """
    prefix, _, local = name_attr.partition(":")
    if not local:
        # コロンなし → 全体が local_name、デフォルト名前空間を使用
        local = prefix
        prefix = None  # type: ignore[assignment]
        ns_uri = element.nsmap.get(None)
    else:
        ns_uri = element.nsmap.get(prefix)

    if ns_uri is None:
        msg = (
            f"名前空間プレフィクス '{prefix}' が未定義: "
            f"{name_attr}: {source_path or '(unknown)'}"
        )
        raise EdinetParseError(msg)

    return f"{{{ns_uri}}}{local}", ns_uri, local


def _extract_ixbrl_facts(
    root: etree._Element,
    *,
    source_path: str | None,
    strict: bool,
    context_ids: frozenset[str],
    unit_ids: frozenset[str],
) -> tuple[RawFact, ...]:
    """ix:nonFraction / ix:nonNumeric を全走査して Fact を抽出する。

    Args:
        root: ルート要素。
        source_path: エラーメッセージ用のソースパス。
        strict: strict モードかどうか。
        context_ids: 定義済み context ID の集合。
        unit_ids: 定義済み unit ID の集合。

    Returns:
        RawFact のタプル。
    """
    facts: list[RawFact] = []
    order = 0

    for elem in root.iter(_IX_NON_FRACTION_TAG, _IX_NON_NUMERIC_TAG):
        is_non_fraction = elem.tag == _IX_NON_FRACTION_TAG

        # name 属性（必須）
        name_attr = elem.get("name")
        if name_attr is None:
            _handle_fact_issue(
                message="name 属性がない iXBRL Fact を検出しました",
                source_path=source_path,
                source_line=elem.sourceline,
                strict=strict,
            )
            continue

        # 名前空間解決
        try:
            concept_qname, namespace_uri, local_name = _resolve_ixbrl_name(
                elem, name_attr, source_path
            )
        except EdinetParseError:
            if strict:
                raise
            continue

        # contextRef（必須）
        context_ref = elem.get("contextRef")
        if context_ref is None:
            _handle_fact_issue(
                message=f"contextRef がない iXBRL Fact を検出しました (name={name_attr})",
                source_path=source_path,
                source_line=elem.sourceline,
                strict=strict,
            )
            continue
        context_ref = context_ref.strip()

        # xsi:nil 判定
        nil_attr = elem.get(f"{{{NS_XSI}}}nil")
        is_nil = nil_attr is not None and nil_attr.strip().lower() in {"true", "1"}

        # fact_id
        fact_id = elem.get("id")
        if fact_id is not None:
            fact_id = fact_id.strip() or None

        # xml:lang
        xml_lang = _resolve_xml_lang(elem)

        if is_non_fraction:
            fact = _process_non_fraction(
                elem,
                concept_qname=concept_qname,
                namespace_uri=namespace_uri,
                local_name=local_name,
                context_ref=context_ref,
                is_nil=is_nil,
                fact_id=fact_id,
                xml_lang=xml_lang,
                order=order,
                source_path=source_path,
                strict=strict,
            )
        else:
            fact = _process_non_numeric(
                elem,
                concept_qname=concept_qname,
                namespace_uri=namespace_uri,
                local_name=local_name,
                context_ref=context_ref,
                is_nil=is_nil,
                fact_id=fact_id,
                xml_lang=xml_lang,
                order=order,
                source_path=source_path,
                strict=strict,
            )

        if fact is not None:
            facts.append(fact)
            order += 1

    return tuple(facts)


def _process_non_fraction(
    elem: etree._Element,
    *,
    concept_qname: str,
    namespace_uri: str,
    local_name: str,
    context_ref: str,
    is_nil: bool,
    fact_id: str | None,
    xml_lang: str | None,
    order: int,
    source_path: str | None,
    strict: bool,
) -> RawFact | None:
    """ix:nonFraction 要素を RawFact に変換する。

    Args:
        elem: ix:nonFraction 要素。
        concept_qname: Clark notation の QName。
        namespace_uri: 名前空間 URI。
        local_name: ローカル名。
        context_ref: contextRef 属性値。
        is_nil: xsi:nil が真かどうか。
        fact_id: id 属性値。
        xml_lang: xml:lang 属性値。
        order: 出現順。
        source_path: ソースパス。
        strict: strict モード。

    Returns:
        RawFact。変換に失敗した場合は None。
    """
    unit_ref = elem.get("unitRef")
    if unit_ref is not None:
        unit_ref = unit_ref.strip() or None

    # decimals
    decimals_raw = elem.get("decimals")
    try:
        decimals = _parse_decimals(decimals_raw, concept_qname, source_path)
    except EdinetParseError:
        if strict:
            raise
        return None

    if is_nil:
        value_raw = None
    else:
        # テキスト取得 → format 適用 → scale/sign 適用
        display_text = "".join(elem.itertext()).strip()
        if display_text == "":
            # 空値は "0" ではないため、値なしとして扱う
            _handle_fact_issue(
                message=f"非 nil の nonFraction の値が空です (name={local_name})",
                source_path=source_path,
                source_line=elem.sourceline,
                strict=strict,
            )
            return None

        format_attr = elem.get("format")
        try:
            numeric_str = _apply_format(format_attr, display_text)
        except ValueError as exc:
            _handle_fact_issue(
                message=f"iXBRL format 変換に失敗: {exc} (name={local_name})",
                source_path=source_path,
                source_line=elem.sourceline,
                strict=strict,
            )
            return None

        try:
            value_raw = _apply_scale_sign(elem, numeric_str)
        except (InvalidOperation, ValueError) as exc:
            _handle_fact_issue(
                message=f"iXBRL scale/sign 適用に失敗: {exc} (name={local_name})",
                source_path=source_path,
                source_line=elem.sourceline,
                strict=strict,
            )
            return None

    return RawFact(
        concept_qname=concept_qname,
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=decimals,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=fact_id,
        xml_lang=xml_lang,
        source_line=elem.sourceline,
        order=order,
    )


def _process_non_numeric(
    elem: etree._Element,
    *,
    concept_qname: str,
    namespace_uri: str,
    local_name: str,
    context_ref: str,
    is_nil: bool,
    fact_id: str | None,
    xml_lang: str | None,
    order: int,
    source_path: str | None,
    strict: bool,
) -> RawFact | None:
    """ix:nonNumeric 要素を RawFact に変換する。

    Args:
        elem: ix:nonNumeric 要素。
        concept_qname: Clark notation の QName。
        namespace_uri: 名前空間 URI。
        local_name: ローカル名。
        context_ref: contextRef 属性値。
        is_nil: xsi:nil が真かどうか。
        fact_id: id 属性値。
        xml_lang: xml:lang 属性値。
        order: 出現順。
        source_path: ソースパス。
        strict: strict モード。

    Returns:
        RawFact。変換に失敗した場合は None。
    """
    if is_nil:
        value_raw = None
        value_inner_xml = None
    else:
        format_attr = elem.get("format")
        if format_attr is not None:
            # format 付き nonNumeric（日付・真偽値）
            display_text = "".join(elem.itertext())
            try:
                value_raw = _apply_non_numeric_format(format_attr, display_text)
            except ValueError as exc:
                _handle_fact_issue(
                    message=f"iXBRL format 変換に失敗: {exc} (name={local_name})",
                    source_path=source_path,
                    source_line=elem.sourceline,
                    strict=strict,
                )
                return None
        else:
            # format なし: テキスト連結
            text_content = "".join(elem.itertext())
            value_raw = text_content if text_content != "" else None

        # value_inner_xml: 子要素がある場合
        if any(isinstance(child.tag, str) for child in elem):
            inner_xml = _extract_inner_xml(elem)
            value_inner_xml = inner_xml if inner_xml != "" else None
        else:
            value_inner_xml = None

    return RawFact(
        concept_qname=concept_qname,
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=fact_id,
        xml_lang=xml_lang,
        source_line=elem.sourceline,
        order=order,
        value_inner_xml=value_inner_xml,
    )


# ---------------------------------------------------------------------------
# format 変換
# ---------------------------------------------------------------------------

def _normalize_format_name(format_attr: str) -> str:
    """format 属性値を正規化する。

    ``"ixt:numdotdecimal"`` → ``"numdotdecimal"`` のようにプレフィクスを除去する。

    Args:
        format_attr: format 属性の値。

    Returns:
        正規化されたフォーマット名。
    """
    _, _, local = format_attr.rpartition(":")
    return local.lower() if local else format_attr.lower()


def _apply_format(format_attr: str | None, display_text: str) -> str:
    """nonFraction のフォーマットを適用して数値文字列を返す。

    Args:
        format_attr: format 属性値（None の場合は無変換）。
        display_text: 表示テキスト。

    Returns:
        数値文字列。

    Raises:
        ValueError: 変換に失敗した場合。
    """
    if format_attr is None:
        return display_text.strip()

    name = _normalize_format_name(format_attr)

    if name == "numdotdecimal":
        return _format_numdotdecimal(display_text)
    if name == "numcommadecimal":
        return _format_numcommadecimal(display_text)
    if name in {"booleantrue", "booleanfalse"}:
        # 真偽値が nonFraction に現れるケースは稀だが対応
        return "1" if name == "booleantrue" else "0"

    # 未知の format はそのまま返す
    return display_text.strip()


def _apply_non_numeric_format(format_attr: str, display_text: str) -> str:
    """nonNumeric のフォーマットを適用して XBRL 値文字列を返す。

    Args:
        format_attr: format 属性値。
        display_text: 表示テキスト。

    Returns:
        XBRL 値文字列。

    Raises:
        ValueError: 変換に失敗した場合。
    """
    name = _normalize_format_name(format_attr)

    if name == "dateyearmonthdaycjk":
        return _format_dateyearmonthdaycjk(display_text)
    if name == "booleantrue":
        return "true"
    if name == "booleanfalse":
        return "false"

    # 未知の format はそのまま返す
    return display_text


def _format_numdotdecimal(text: str) -> str:
    """ixt:numdotdecimal のフォーマットを適用する。

    カンマを除去し、ドットを小数点として扱う。

    Args:
        text: 表示テキスト（例: ``"8,225"`` や ``"1,234.56"``）。

    Returns:
        数値文字列（例: ``"8225"`` や ``"1234.56"``）。
    """
    return text.replace(",", "").replace(" ", "").strip()


def _format_numcommadecimal(text: str) -> str:
    """ixt:numcommadecimal のフォーマットを適用する。

    ドットを桁区切り、カンマを小数点として扱う。

    Args:
        text: 表示テキスト。

    Returns:
        数値文字列。
    """
    result = text.replace(" ", "").replace(".", "").replace(",", ".").strip()
    return result


def _format_dateyearmonthdaycjk(text: str) -> str:
    """ixt:dateyearmonthdaycjk のフォーマットを適用する。

    「2026年3月4日」→ ``"2026-03-04"`` に変換する。

    Args:
        text: 日本語日付文字列。

    Returns:
        ISO 8601 日付文字列。

    Raises:
        ValueError: パースに失敗した場合。
    """
    m = _DATE_CJK_PATTERN.search(text)
    if m is None:
        raise ValueError(f"CJK 日付のパースに失敗: {text!r}")
    year, month, day = m.group(1), m.group(2), m.group(3)
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _apply_scale_sign(elem: etree._Element, numeric_str: str) -> str:
    """scale と sign 属性を適用して最終的な値文字列を返す。

    Args:
        elem: ix:nonFraction 要素。
        numeric_str: format 適用後の数値文字列。

    Returns:
        scale / sign を適用した値文字列。

    Raises:
        InvalidOperation: Decimal 変換に失敗した場合。
        ValueError: 不正な scale 値の場合。
    """
    value = Decimal(numeric_str)
    scale_raw = elem.get("scale")
    if scale_raw is not None:
        scale = int(scale_raw)
        if scale != 0:
            value = value * Decimal(10) ** scale
    if elem.get("sign") == "-":
        value = -value

    # 整数であれば整数表記にする（"8225000000" not "8.225E+9"）
    return _format_decimal(value)


def _format_decimal(value: Decimal) -> str:
    """Decimal を固定小数点表記の文字列に変換する。

    指数表記を避け、trailing zeros を適切に処理する。

    Args:
        value: Decimal 値。

    Returns:
        文字列表現。
    """
    # normalize して指数部が正なら整数
    normalized = value.normalize()
    if normalized == Decimal("0"):
        return "0"
    exponent = normalized.as_tuple().exponent
    # exponent が 0 以上 → 整数（exponent は int | str だが int のみ比較）
    if isinstance(exponent, int) and exponent >= 0:
        return str(int(normalized))
    # 小数部あり
    return str(normalized)
