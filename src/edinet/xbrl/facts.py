"""XBRL ファクト抽出ユーティリティ。

RawFact + StructuredContext + TaxonomyResolver を結合し、
型付き・ラベル付きの LineItem を生成する。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from edinet.exceptions import EdinetParseError
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import StructuredContext
from edinet.xbrl.parser import RawFact
from edinet.xbrl.taxonomy import TaxonomyResolver

logger = logging.getLogger(__name__)

__all__ = ["build_line_items"]


def build_line_items(
    facts: Sequence[RawFact],
    context_map: dict[str, StructuredContext],
    resolver: TaxonomyResolver,
) -> tuple[LineItem, ...]:
    """RawFact 群を LineItem 群に変換する。

    全 RawFact を LineItem に変換する。フィルタは行わない
    （「データは広く持ち、フィルタは遅く」の原則）。

    Args:
        facts: ``parse_xbrl_facts()`` が抽出した RawFact のシーケンス。
        context_map: ``structure_contexts()`` が返した Context 辞書。
        resolver: ラベル解決用の TaxonomyResolver。
            提出者ラベルは呼び出し側で事前に
            ``load_filer_labels()`` しておくこと。

    Returns:
        変換された LineItem のタプル。入力の facts と同じ順序を保持する。

    Raises:
        EdinetParseError: ``context_ref`` が ``context_map`` に
            見つからない RawFact が存在した場合。

    Note:
        - 数値 Fact（``unit_ref is not None`` かつ非 nil）は
          ``Decimal(value_raw)`` に変換する。parser.py S-10 で
          lexical 妥当性は検証済みのため安全に成功する前提。
        - テキスト Fact（``unit_ref is None``）は ``value_raw`` を
          そのまま ``str`` で保持する。
        - nil Fact は ``value=None`` となる。
    """
    items: list[LineItem] = []
    for fact in facts:
        # 1. Context 解決
        ctx = context_map.get(fact.context_ref)
        if ctx is None:
            raise EdinetParseError(
                f"Fact '{fact.local_name}' (line {fact.source_line}): "
                f"context_ref '{fact.context_ref}' not found in context_map"
            )

        # 2. ラベル解決
        label_ja = resolver.resolve_clark(fact.concept_qname, lang="ja")
        label_en = resolver.resolve_clark(fact.concept_qname, lang="en")

        # 3. 値の変換
        value = _convert_value(fact)

        # 4. LineItem 構築
        item = LineItem(
            concept=fact.concept_qname,
            namespace_uri=fact.namespace_uri,
            local_name=fact.local_name,
            label_ja=label_ja,
            label_en=label_en,
            value=value,
            unit_ref=fact.unit_ref,
            decimals=fact.decimals,
            context_id=fact.context_ref,
            period=ctx.period,
            entity_id=ctx.entity_id,
            dimensions=ctx.dimensions,
            is_nil=fact.is_nil,
            source_line=fact.source_line,
            order=fact.order,
        )
        items.append(item)

    logger.info("LineItem を構築: %d 件（入力 Fact: %d 件）", len(items), len(facts))
    return tuple(items)


def _convert_value(fact: RawFact) -> Decimal | str | None:
    """RawFact の値を適切な型に変換する。

    Args:
        fact: 変換対象の RawFact。

    Returns:
        - nil Fact → ``None``
        - 数値 Fact（``unit_ref is not None``）→ ``Decimal``
        - テキスト Fact（``unit_ref is None``）→ ``str``

    Raises:
        EdinetParseError: 数値 Fact の値が Decimal に変換できない場合、
            または非 nil テキスト Fact の ``value_raw`` と
            ``value_inner_xml`` が両方 ``None`` の場合。
            後者は parser.py S-9 で保証済みのため、
            到達した場合は parser.py のバグ。
    """
    # nil Fact: 数値・テキストに関わらず None
    if fact.is_nil:
        return None

    # テキスト Fact: unit_ref がなければテキストとして扱う
    if fact.unit_ref is None:
        if fact.value_raw is not None:
            return fact.value_raw
        # value_raw=None だが value_inner_xml がある場合:
        # マークアップのみの TextBlock（例: <br/>）で itertext() が
        # 空文字列を返し value_raw=None になるケース。
        # parser.py S-9 は value_inner_xml が存在すれば通すため、
        # ここでも空文字列として受け入れる。
        if fact.value_inner_xml is not None:
            return ""
        raise EdinetParseError(
            f"Fact '{fact.local_name}' (line {fact.source_line}): "
            f"non-nil text fact has value_raw=None"
        )

    # 数値 Fact: Decimal に変換
    if fact.value_raw is None:
        raise EdinetParseError(
            f"Fact '{fact.local_name}' (line {fact.source_line}): "
            f"non-nil numeric fact has value_raw=None"
        )
    try:
        return Decimal(fact.value_raw)
    except InvalidOperation as e:
        raise EdinetParseError(
            f"Fact '{fact.local_name}' (line {fact.source_line}): "
            f"failed to convert value to Decimal: {fact.value_raw!r}"
        ) from e
