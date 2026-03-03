from collections.abc import Sequence
from dataclasses import dataclass
from edinet.xbrl.contexts import Period, StructuredContext
from edinet.xbrl.parser import RawFact

__all__ = ['TextBlock', 'extract_text_blocks']

@dataclass(frozen=True, slots=True)
class TextBlock:
    '''テキストブロック Fact。

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
    '''
    concept: str
    namespace_uri: str
    concept_qname: str
    html: str
    context_ref: str
    period: Period
    is_consolidated: bool
    fact_id: str | None = ...

def extract_text_blocks(facts: Sequence[RawFact], context_map: dict[str, StructuredContext]) -> tuple[TextBlock, ...]:
    '''RawFact 群から textBlockItemType の Fact を抽出する。

    textBlockItemType の判定は concept のローカル名が ``"TextBlock"`` で
    終わることを条件とする（EDINET タクソノミの命名慣例）。

    Args:
        facts: ``parse_xbrl_facts()`` が返した RawFact のシーケンス。
        context_map: ``structure_contexts()`` が返した Context 辞書。

    Returns:
        TextBlock のタプル。元の facts の出現順を保持する。

    Raises:
        EdinetParseError: ``context_ref`` が ``context_map`` に
            見つからない RawFact が存在した場合。
            既存の ``build_line_items()`` と同一の動作。
    '''
