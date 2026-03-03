"""テキストブロック抽出。

RawFact から textBlockItemType の Fact を抽出し、
HTML コンテンツ付きの TextBlock を構築する。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from edinet.exceptions import EdinetParseError
from edinet.xbrl.contexts import Period, StructuredContext
from edinet.xbrl.parser import RawFact

logger = logging.getLogger(__name__)


def _resolve_text_source(
    source: Sequence[RawFact] | Any,
    context_map: dict[str, StructuredContext] | None,
) -> tuple[Sequence[RawFact], dict[str, StructuredContext]]:
    """Statements または低レベル引数から (facts, context_map) を取得する。

    Args:
        source: ``Statements`` または ``Sequence[RawFact]``。
        context_map: コンテキストマッピング。Statements 時は None 可。

    Returns:
        ``(facts, context_map)`` のタプル。

    Raises:
        TypeError: 低レベル呼び出し時に必須引数が欠落した場合。
        ValueError: Statements に facts が設定されていない場合。
    """
    from edinet.financial.statements import Statements as _Statements

    if isinstance(source, _Statements):
        if source._facts is None:  # noqa: SLF001
            raise ValueError(
                "Statements に facts が設定されていません。"
                "facts を指定して build_statements() を実行してください。"
            )
        return source._facts, source._contexts or {}  # noqa: SLF001

    if context_map is None:
        raise TypeError(
            "Sequence[RawFact] を渡す場合は context_map が必須です"
        )
    return source, context_map

__all__ = ["TextBlock", "extract_text_blocks"]

_TEXTBLOCK_SUFFIX = "TextBlock"


@dataclass(frozen=True, slots=True)
class TextBlock:
    """テキストブロック Fact。

    textBlockItemType の Fact から抽出された HTML テキストブロック。
    有価証券報告書の注記・MD&A 等の非数値セクションを表す。

    Attributes:
        concept: concept のローカル名（例: ``"BusinessRisksTextBlock"``）。
        namespace_uri: 名前空間 URI。
        concept_qname: Clark notation の QName（例:
            ``"{http://...}BusinessRisksTextBlock"``）。
            ``TaxonomyResolver.resolve_clark()`` にそのまま渡せる形式。
        html: HTML コンテンツ。``RawFact.value_raw`` から取得
            （.xbrl のエンティティエスケープ HTML を lxml が自動デコード済み）。
        context_ref: contextRef 属性値。
        period: 期間情報。
        is_consolidated: 連結コンテキストかどうか。
        fact_id: Fact の id 属性値。
    """

    concept: str
    namespace_uri: str
    concept_qname: str
    html: str
    context_ref: str
    period: Period
    is_consolidated: bool
    fact_id: str | None = None


def extract_text_blocks(
    source: Sequence[RawFact] | Any,
    context_map: dict[str, StructuredContext] | None = None,
) -> tuple[TextBlock, ...]:
    """RawFact 群から textBlockItemType の Fact を抽出する。

    ``Statements`` を渡す場合は ``context_map`` は不要（内部で自動取得）。

    textBlockItemType の判定は concept のローカル名が ``"TextBlock"`` で
    終わることを条件とする（EDINET タクソノミの命名慣例）。

    Args:
        source: ``Statements`` または ``parse_xbrl_facts()`` が返した
            RawFact のシーケンス。
        context_map: ``structure_contexts()`` が返した Context 辞書。
            ``Statements`` を渡す場合は省略可。

    Returns:
        TextBlock のタプル。元の facts の出現順を保持する。

    Raises:
        EdinetParseError: ``context_ref`` が ``context_map`` に
            見つからない RawFact が存在した場合。
        TypeError: 低レベル呼び出し時に ``context_map`` が ``None`` の場合。
    """
    facts, resolved_ctx = _resolve_text_source(source, context_map)

    blocks: list[TextBlock] = []
    for fact in facts:
        # TextBlock 判定（4 条件）
        if not fact.local_name.endswith(_TEXTBLOCK_SUFFIX):
            continue
        if fact.unit_ref is not None:
            continue
        if fact.is_nil:
            continue
        if fact.value_raw is None or not fact.value_raw.strip():
            continue

        # Context 解決（build_line_items と同一パターン）
        ctx = resolved_ctx.get(fact.context_ref)
        if ctx is None:
            raise EdinetParseError(
                f"TextBlock '{fact.local_name}' (line {fact.source_line}): "
                f"context_ref '{fact.context_ref}' が context_map に見つかりません"
            )

        blocks.append(
            TextBlock(
                concept=fact.local_name,
                namespace_uri=fact.namespace_uri,
                concept_qname=fact.concept_qname,
                html=fact.value_raw,
                context_ref=fact.context_ref,
                period=ctx.period,
                is_consolidated=ctx.is_consolidated,
                fact_id=fact.fact_id,
            ),
        )

    logger.info(
        "TextBlock を抽出: %d 件（入力 Fact: %d 件）",
        len(blocks),
        len(facts),
    )
    return tuple(blocks)
