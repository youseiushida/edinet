from collections.abc import Sequence
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import StructuredContext
from edinet.xbrl.parser import RawFact
from edinet.xbrl.taxonomy import TaxonomyResolver

__all__ = ['build_line_items']

def build_line_items(facts: Sequence[RawFact], context_map: dict[str, StructuredContext], resolver: TaxonomyResolver) -> tuple[LineItem, ...]:
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
