from collections.abc import Sequence
from dataclasses import dataclass
from edinet.xbrl.parser import RawUnit

__all__ = ['SimpleMeasure', 'DivideMeasure', 'Measure', 'StructuredUnit', 'structure_units']

@dataclass(frozen=True, slots=True)
class SimpleMeasure:
    '''単一の measure 要素を表す。

    Attributes:
        namespace_uri: 名前空間 URI（例: ``"http://www.xbrl.org/2003/iso4217"``）。
        local_name: ローカル名（例: ``"JPY"``）。
        raw_text: measure 要素のテキスト値（例: ``"iso4217:JPY"``）。
    '''
    namespace_uri: str
    local_name: str
    raw_text: str

@dataclass(frozen=True, slots=True)
class DivideMeasure:
    """divide 要素（分子/分母）を表す。

    Attributes:
        numerator: 分子の SimpleMeasure。
        denominator: 分母の SimpleMeasure。
    """
    numerator: SimpleMeasure
    denominator: SimpleMeasure
Measure = SimpleMeasure | DivideMeasure

@dataclass(frozen=True, slots=True)
class StructuredUnit:
    """構造化された Unit。

    Attributes:
        unit_id: Unit の ID。
        measure: 単位情報。
        source_line: 元 XML の行番号。
    """
    unit_id: str
    measure: Measure
    source_line: int | None
    @property
    def is_monetary(self) -> bool:
        """通貨単位かどうかを返す。"""
    @property
    def is_pure(self) -> bool:
        """純粋数値（xbrli:pure）かどうかを返す。"""
    @property
    def is_shares(self) -> bool:
        """株式数（xbrli:shares）かどうかを返す。"""
    @property
    def is_per_share(self) -> bool:
        """1株あたり単位（通貨/株式数）かどうかを返す。"""
    @property
    def currency_code(self) -> str | None:
        '''通貨コードを返す。

        SimpleMeasure で iso4217 名前空間の場合はそのローカル名（例: ``"JPY"``）、
        DivideMeasure で分子が iso4217 名前空間の場合は分子のローカル名を返す。
        いずれにも該当しない場合は None。

        Note:
            ``is_monetary`` が False でも ``currency_code`` が非 None になる
            ケースがある（例: ``JPYPerShares`` は ``is_monetary=False`` だが
            ``currency_code="JPY"``）。
        '''

def structure_units(raw_units: Sequence[RawUnit]) -> dict[str, StructuredUnit]:
    """RawUnit のシーケンスを構造化して辞書で返す。

    Args:
        raw_units: ``parse_xbrl_facts()`` が抽出した RawUnit のシーケンス。

    Returns:
        unit_id をキー、StructuredUnit を値とする辞書。
        重複 unit_id は後勝ち。

    Raises:
        EdinetParseError: measure 欠落、XML 構文エラーなど
            構造解析に失敗した場合。
    """
