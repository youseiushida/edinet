from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.dei import AccountingStandard
from typing import Any

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
    '''
    canonical_key: str
    value: Decimal | str | None
    item: LineItem

def extract_values(source: FinancialStatement | Any, keys: Sequence[str] | None = None, *, standard: AccountingStandard | None = None, industry_code: str | None = None) -> dict[str, ExtractedValue | None]:
    '''正規化キーで財務データから値を抽出する。

    ``FinancialStatement``（PL/BS/CF）または ``Statements``（全 items）を
    受け付ける。``Statements`` を渡すと PL/BS/CF の区分を超えて全科目から
    検索するため、ConceptSet に含まれない概念もマッチする。

    Args:
        source: 抽出対象の ``FinancialStatement`` または ``Statements``。
        keys: 抽出する正規化キーのシーケンス。
            ``CK`` enum または文字列で指定可能。
            ``None`` の場合は全マッピング可能科目を抽出する。
        standard: 会計基準。``None`` の場合は自動判別
            （J-GAAP → IFRS → US-GAAP の順で検索）。
        industry_code: 業種コード（銀行業等のセクター固有マッピング用）。
            指定すると ``get_canonical_key_for_sector()`` を使用する。

    Returns:
        ``{canonical_key: ExtractedValue | None}`` の辞書。
        ``keys`` で指定されたキーが見つからない場合は ``None``。
        ``keys=None`` の場合は見つかった科目のみを含む。

    Example:
        >>> from edinet.financial.standards.canonical_keys import CK
        >>> result = extract_values(pl, [CK.REVENUE, CK.NET_INCOME])
        >>> result["revenue"].value
        Decimal(\'1234567000\')
    '''
def extracted_to_dict(*extracted_dicts: dict[str, ExtractedValue | None]) -> dict[str, Decimal | str | None]:
    """``extract_values()`` の結果を ``{key: value}`` 辞書に変換する。

    複数の辞書を渡すとマージされる。値が見つかったキーが優先され、
    ``None`` で上書きされることはない（PL + BS を安全にマージ可能）。

    Args:
        *extracted_dicts: ``extract_values()`` の戻り値（1つ以上）。

    Returns:
        ``{canonical_key: value}`` の辞書。

    Example:
        >>> row = extracted_to_dict(
        ...     extract_values(pl, [CK.REVENUE, CK.TOTAL_ASSETS]),
        ...     extract_values(bs, [CK.REVENUE, CK.TOTAL_ASSETS]),
        ... )
        >>> row
        {'revenue': Decimal('1234567000'), 'total_assets': Decimal('5000000000')}
    """
