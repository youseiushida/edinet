from collections.abc import Sequence
from dataclasses import dataclass
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.text.blocks import TextBlock

__all__ = ['SectionMap', 'build_section_map']

@dataclass(frozen=True, slots=True)
class SectionMap:
    '''セクション名 → TextBlock リストのマッピング。

    Attributes:
        _index: セクション名をキー、TextBlock タプルを値とする辞書。
        _unmatched: セクション名を推定できなかった TextBlock のタプル。
            ``extract_text_blocks()`` 経由で作成された TextBlock は全て
            ``"TextBlock"`` サフィックスを持つため通常は空。
            ユーザーが直接 ``TextBlock`` を構築して ``build_section_map()`` に
            渡した場合のセーフティネットとして存在する。
    '''
    @property
    def sections(self) -> tuple[str, ...]:
        """利用可能なセクション名の一覧を返す。"""
    def get(self, section_name: str) -> tuple[TextBlock, ...] | None:
        """セクション名で TextBlock を取得する。

        Args:
            section_name: セクション名（日本語ラベルまたは英語フォールバック名）。

        Returns:
            TextBlock のタプル。セクションが見つからなければ None。
        """
    def __getitem__(self, section_name: str) -> tuple[TextBlock, ...]:
        """セクション名で TextBlock を取得する。

        Args:
            section_name: セクション名。

        Returns:
            TextBlock のタプル。

        Raises:
            KeyError: セクションが見つからない場合。
        """
    def __contains__(self, section_name: object) -> bool:
        """セクションの存在確認。"""
    def __len__(self) -> int:
        """セクション数を返す。"""
    @property
    def unmatched(self) -> tuple[TextBlock, ...]:
        """セクション名を推定できなかった TextBlock を返す。"""

def build_section_map(blocks: Sequence[TextBlock], resolver: TaxonomyResolver) -> SectionMap:
    '''TextBlock 群をセクション名でグルーピングする。

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
        blocks: ``extract_text_blocks()`` が返した TextBlock のシーケンス。
        resolver: TaxonomyResolver インスタンス。

    Returns:
        SectionMap。
    '''
