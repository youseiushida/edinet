"""正規化キーによる財務数値の抽出ユーティリティ。

会計基準（J-GAAP / IFRS / US-GAAP）を意識せず、canonical key で
FinancialStatement から値を取り出す。

使用例::

    from edinet.financial.extract import extract_values, extracted_to_dict
    from edinet.financial.standards.canonical_keys import CK

    pl = stmts.income_statement()
    result = extract_values(pl, [CK.REVENUE, CK.OPERATING_INCOME])

    # トレーサビリティ: 元の LineItem を辿れる
    rev = result[CK.REVENUE]
    if rev is not None:
        print(f"{rev.item.label_ja.text}: {rev.value:,}")

    # pandas 連携
    row = extracted_to_dict(result)
    # → {"revenue": Decimal("1000000"), "operating_income": Decimal("200000")}
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from edinet.financial.standards.normalize import (
    get_canonical_key,
    get_canonical_key_for_sector,
)
from edinet.models.financial import FinancialStatement, LineItem

# Statements の型は遅延で解決（循環 import 回避）

if TYPE_CHECKING:
    from edinet.xbrl.dei import AccountingStandard

__all__ = ["ExtractedValue", "extract_values", "extracted_to_dict"]


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """正規化キーで抽出された財務数値。

    Attributes:
        canonical_key: 正規化キー（例: ``"revenue"``）。
        value: 抽出された値。数値の場合は ``Decimal``、テキストの場合は
            ``str``、nil または欠損の場合は ``None``。
        item: 元の ``LineItem``。``source_line``、``label_ja``、
            ``namespace_uri`` 等のトレーサビリティ情報を含む。
    """

    canonical_key: str
    value: Decimal | str | None
    item: LineItem


def extract_values(
    source: FinancialStatement | Any,
    keys: Sequence[str] | None = None,
    *,
    standard: AccountingStandard | None = None,
    industry_code: str | None = None,
) -> dict[str, ExtractedValue | None]:
    """正規化キーで財務データから値を抽出する。

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
        Decimal('1234567000')
    """
    # Statements / FinancialStatement どちらからも items を取得
    from edinet.financial.statements import Statements as _Statements

    if isinstance(source, _Statements):
        items = source._items  # noqa: SLF001
    elif isinstance(source, FinancialStatement):
        items = source.items
    else:
        raise TypeError(
            f"FinancialStatement または Statements を渡してください（got {type(source).__name__}）"
        )

    # canonical_key → LineItem の逆引きインデックスを構築
    ck_to_item: dict[str, LineItem] = {}
    for item in items:
        if industry_code is not None:
            ck = get_canonical_key_for_sector(
                item.local_name, standard, industry_code,
            )
        else:
            ck = get_canonical_key(item.local_name, standard)
        if ck is not None and ck not in ck_to_item:
            # 同一キーが複数存在する場合は先頭（表示順）を優先
            ck_to_item[ck] = item

    if keys is None:
        # 全マッピング可能科目を返す
        return {
            ck: ExtractedValue(canonical_key=ck, value=item.value, item=item)
            for ck, item in ck_to_item.items()
        }

    # 指定キーのみ返す（未発見は None）
    result: dict[str, ExtractedValue | None] = {}
    for key in keys:
        key_str = str(key)
        item = ck_to_item.get(key_str)
        if item is not None:
            result[key_str] = ExtractedValue(
                canonical_key=key_str, value=item.value, item=item,
            )
        else:
            result[key_str] = None
    return result


def extracted_to_dict(
    *extracted_dicts: dict[str, ExtractedValue | None],
) -> dict[str, Decimal | str | None]:
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
    result: dict[str, Decimal | str | None] = {}
    for extracted in extracted_dicts:
        for k, ev in extracted.items():
            if ev is not None:
                result[k] = ev.value
            elif k not in result:
                result[k] = None
    return result
