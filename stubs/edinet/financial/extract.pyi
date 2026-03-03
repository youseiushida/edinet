from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from edinet.models.financial import LineItem
from typing import Any, Literal

__all__ = ['ExtractedValue', 'extract_values', 'extracted_to_dict']

@dataclass(frozen=True, slots=True)
class ExtractedValue:
    '''正規化キーで抽出された財務数値。

    Attributes:
        canonical_key: 正規化キー（例: ``"revenue"``）。
        value: 抽出された値。数値の場合は ``Decimal``、テキストの場合は
            ``str``、nil または欠損の場合は ``None``。
        item: 元の ``LineItem``。``source_line``、``label_ja``、
            ``namespace_uri`` 等のトレーサビリティ情報を含む。
        source: 抽出元レイヤー。

            - ``"summary"``: SummaryOfBusinessResults から完全一致（信頼度最高）。
            - ``"exact"``: PL/BS/CF 本体から辞書完全一致。
            - ``"normalized"``: EDINET サフィックス剥離後に辞書引き（信頼度低）。
    '''
    canonical_key: str
    value: Decimal | str | None
    item: LineItem
    source: Literal['summary', 'exact', 'normalized']

def extract_values(source: Any, keys: Sequence[str] | None = None, *, period: Literal['current', 'prior'] | None = None, consolidated: bool | None = None, include_statements: bool = True) -> dict[str, ExtractedValue | None]:
    '''正規化キーで財務データから値を抽出する。

    ``Statements`` を渡すと ``_items`` 全体から SummaryOfBusinessResults
    concept を走査する。``include_statements=True``（デフォルト）の場合、
    Summary で取得できなかったキーを PL/BS/CF 本体からも補完する。

    Args:
        source: 抽出対象の ``Statements``。
        keys: 抽出する正規化キーのシーケンス。
            ``CK`` enum または文字列で指定可能。
            ``None`` の場合は全マッピング可能科目を抽出する。
        period: 期間フィルタ。
            ``"current"`` で当期、``"prior"`` で前期。
            ``None`` の場合は全期間から先頭マッチ。
        consolidated: 連結フィルタ。
            ``True`` で連結、``False`` で個別。
            ``None`` の場合は全て。
        include_statements: ``True``（デフォルト）の場合、Summary で
            取得できなかったキーを PL/BS/CF 本体から補完する。

    Returns:
        ``{canonical_key: ExtractedValue | None}`` の辞書。
        ``keys`` で指定されたキーが見つからない場合は ``None``。
        ``keys=None`` の場合は見つかった科目のみを含む。

    Raises:
        TypeError: ``Statements`` 以外を渡した場合。

    Example:
        >>> from edinet.financial.standards.canonical_keys import CK
        >>> result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME],
        ...                         period="current", consolidated=True)
        >>> result["operating_income"].value
        Decimal(\'500000000\')
    '''
def extracted_to_dict(*extracted_dicts: dict[str, ExtractedValue | None]) -> dict[str, Decimal | str | None]:
    """``extract_values()`` の結果を ``{key: value}`` 辞書に変換する。

    複数の辞書を渡すとマージされる。値が見つかったキーが優先され、
    ``None`` で上書きされることはない。

    Args:
        *extracted_dicts: ``extract_values()`` の戻り値（1つ以上）。

    Returns:
        ``{canonical_key: value}`` の辞書。

    Example:
        >>> row = extracted_to_dict(
        ...     extract_values(stmts, [CK.REVENUE]),
        ...     extract_values(stmts, [CK.TOTAL_ASSETS]),
        ... )
    """
