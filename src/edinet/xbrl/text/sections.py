"""セクション名マッピング。

TextBlock の concept 名から日本語セクション名を推定し、
セクション単位でグルーピングする。

セクション名の解決には ``TaxonomyResolver`` を使用し、
全 689 個の jpcrp_cor textBlockItemType concept の日本語ラベルを
動的に取得する（ハードコードゼロ）。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from edinet.xbrl.taxonomy import LabelSource, TaxonomyResolver
from edinet.xbrl.text.blocks import TextBlock, _TEXTBLOCK_SUFFIX

__all__ = ["SectionMap", "build_section_map"]


def _resolve_section_source(
    source: Sequence[TextBlock] | Any,
    resolver: TaxonomyResolver | None,
) -> tuple[Sequence[TextBlock], TaxonomyResolver]:
    """Statements または低レベル引数から (blocks, resolver) を取得する。

    ``Statements`` を渡すと内部で ``extract_text_blocks()`` を実行し、
    TextBlock を自動抽出する。

    Args:
        source: ``Statements`` または ``Sequence[TextBlock]``。
        resolver: TaxonomyResolver。Statements 時は None 可。

    Returns:
        ``(blocks, resolver)`` のタプル。

    Raises:
        TypeError: 低レベル呼び出し時に ``resolver`` が ``None`` の場合。
        ValueError: Statements に facts / resolver が設定されていない場合。
    """
    from edinet.financial.statements import Statements as _Statements

    if isinstance(source, _Statements):
        res = resolver or source._resolver  # noqa: SLF001
        if res is None:
            raise ValueError(
                "Statements に resolver が設定されていません。"
                "taxonomy_root を指定して xbrl() を実行してください。"
            )
        if source._facts is None:  # noqa: SLF001
            raise ValueError(
                "Statements に facts が設定されていません。"
                "facts を指定して build_statements() を実行してください。"
            )
        from edinet.xbrl.text.blocks import extract_text_blocks

        blocks = extract_text_blocks(source)
        return blocks, res

    if resolver is None:
        raise TypeError(
            "Sequence[TextBlock] を渡す場合は resolver が必須です"
        )
    return source, resolver


@dataclass(frozen=True, slots=True)
class SectionMap:
    """セクション名 → TextBlock リストのマッピング。

    Attributes:
        _index: セクション名をキー、TextBlock タプルを値とする辞書。
        _unmatched: セクション名を推定できなかった TextBlock のタプル。
            ``extract_text_blocks()`` 経由で作成された TextBlock は全て
            ``"TextBlock"`` サフィックスを持つため通常は空。
            ユーザーが直接 ``TextBlock`` を構築して ``build_section_map()`` に
            渡した場合のセーフティネットとして存在する。
    """

    _index: dict[str, tuple[TextBlock, ...]]
    _unmatched: tuple[TextBlock, ...]

    @property
    def sections(self) -> tuple[str, ...]:
        """利用可能なセクション名の一覧を返す。"""
        return tuple(self._index.keys())

    def get(self, section_name: str) -> tuple[TextBlock, ...] | None:
        """セクション名で TextBlock を取得する。

        Args:
            section_name: セクション名（日本語ラベルまたは英語フォールバック名）。

        Returns:
            TextBlock のタプル。セクションが見つからなければ None。
        """
        return self._index.get(section_name)

    def __getitem__(self, section_name: str) -> tuple[TextBlock, ...]:
        """セクション名で TextBlock を取得する。

        Args:
            section_name: セクション名。

        Returns:
            TextBlock のタプル。

        Raises:
            KeyError: セクションが見つからない場合。
        """
        if section_name not in self._index:
            available = ", ".join(self._index.keys())
            raise KeyError(
                f"セクション '{section_name}' が見つかりません。"
                f"利用可能なセクション: {available}"
            )
        return self._index[section_name]

    def __contains__(self, section_name: object) -> bool:
        """セクションの存在確認。"""
        return section_name in self._index

    def __len__(self) -> int:
        """セクション数を返す。"""
        return len(self._index)

    @property
    def unmatched(self) -> tuple[TextBlock, ...]:
        """セクション名を推定できなかった TextBlock を返す。"""
        return self._unmatched


def _resolve_section_name(
    block: TextBlock,
    resolver: TaxonomyResolver,
) -> str | None:
    """TaxonomyResolver で concept の日本語ラベルをセクション名として取得する。

    ``facts.py`` の ``build_line_items()`` と同じパターンで
    ``resolver.resolve_clark()`` に Clark notation QName を渡す。

    Args:
        block: TextBlock。``concept_qname`` を使用。
        resolver: TaxonomyResolver インスタンス。

    Returns:
        日本語セクション名、またはラベル未解決時は None。
    """
    info = resolver.resolve_clark(block.concept_qname, lang="ja")
    if info.source == LabelSource.FALLBACK:
        return None
    return info.text


def _fallback_section_name(concept: str) -> str | None:
    """concept 名から ``"TextBlock"`` サフィックスを除去してフォールバック名を生成する。

    resolver でラベルが取得できなかった場合に使用。

    Args:
        concept: concept のローカル名（例: ``"BusinessRisksTextBlock"``）。

    Returns:
        サフィックス除去後の英語名。
        ``"TextBlock"`` サフィックスを持たない場合は None（_unmatched 行き）。
    """
    if concept.endswith(_TEXTBLOCK_SUFFIX):
        return concept.removesuffix(_TEXTBLOCK_SUFFIX)
    return None


def build_section_map(
    source: Sequence[TextBlock] | Any,
    resolver: TaxonomyResolver | None = None,
) -> SectionMap:
    """TextBlock 群をセクション名でグルーピングする。

    ``Statements`` を渡す場合は ``resolver`` は不要（内部で自動取得）。
    内部で ``extract_text_blocks()`` を呼び出してから
    セクション名のグルーピングを行う。

    セクション名の解決は以下の優先順位で行う:

    1. **TaxonomyResolver**: concept の標準ラベル（日本語）を取得。
       全 689 個の jpcrp_cor textBlockItemType concept に対応。
    2. **英語フォールバック**: resolver でラベルが見つからない場合、
       concept 名から ``"TextBlock"`` サフィックスを除去した英語名を使用。
       提出者独自の TextBlock concept（filer namespace）はこのパスを通る。
    3. **_unmatched**: ``"TextBlock"`` サフィックスすら持たない異常ケース。
       ``extract_text_blocks()`` 経由なら発生しないが、ユーザーが直接
       ``TextBlock`` を構築した場合のセーフティネット。

    Args:
        source: ``Statements``、``extract_text_blocks()`` が返した
            TextBlock のシーケンス。
        resolver: TaxonomyResolver インスタンス。
            ``Statements`` を渡す場合は省略可。

    Returns:
        SectionMap。

    Raises:
        TypeError: 低レベル呼び出し時に ``resolver`` が ``None`` の場合。
        ValueError: Statements に facts / resolver が設定されていない場合。
    """
    blocks, resolved_resolver = _resolve_section_source(source, resolver)

    index: dict[str, list[TextBlock]] = defaultdict(list)
    unmatched: list[TextBlock] = []

    for block in blocks:
        # 優先順位 1: TaxonomyResolver
        section_name = _resolve_section_name(block, resolved_resolver)

        # 優先順位 2: 英語フォールバック
        if section_name is None:
            section_name = _fallback_section_name(block.concept)

        # 優先順位 3: unmatched
        if section_name is None:
            unmatched.append(block)
            continue

        index[section_name].append(block)

    # list → tuple に変換
    frozen_index = {k: tuple(v) for k, v in index.items()}
    return SectionMap(
        _index=frozen_index,
        _unmatched=tuple(unmatched),
    )
