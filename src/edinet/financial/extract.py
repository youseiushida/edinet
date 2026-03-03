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
from typing import TYPE_CHECKING

from edinet.financial.standards.normalize import (
    get_canonical_key,
    get_canonical_key_for_sector,
)
from edinet.models.financial import FinancialStatement, LineItem

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
    fs: FinancialStatement,
    keys: Sequence[str] | None = None,
    *,
    standard: AccountingStandard | None = None,
    industry_code: str | None = None,
) -> dict[str, ExtractedValue | None]:
    """正規化キーで FinancialStatement から値を抽出する。

    ``fs.items`` を走査し、各 ``LineItem`` の ``local_name`` を
    canonical key に変換して照合する。会計基準は ``standard`` で
    明示するか、``None`` で自動判別（J-GAAP → IFRS → US-GAAP）。

    Args:
        fs: 抽出対象の ``FinancialStatement``。
            ``stmts.income_statement()`` 等で取得したもの。
        keys: 抽出する正規化キーのシーケンス。
            ``CK`` enum または文字列で指定可能。
            ``None`` の場合は ``fs.items`` に存在する全マッピング可能
            科目を抽出する。
        standard: 会計基準。``None`` の場合は自動判別
            （J-GAAP → IFRS → US-GAAP の順で検索）。
        industry_code: 業種コード（銀行業等のセクター固有マッピング用）。
            指定すると ``get_canonical_key_for_sector()`` を使用する。

    Returns:
        ``{canonical_key: ExtractedValue | None}`` の辞書。
        ``keys`` で指定されたキーが ``fs.items`` に見つからない場合は
        ``None``。``keys=None`` の場合は見つかった科目のみを含む。

    Example:
        >>> from edinet.financial.standards.canonical_keys import CK
        >>> result = extract_values(pl, [CK.REVENUE, CK.NET_INCOME])
        >>> result["revenue"].value
        Decimal('1234567000')
    """
    # canonical_key → LineItem の逆引きインデックスを構築
    ck_to_item: dict[str, LineItem] = {}
    for item in fs.items:
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
    extracted: dict[str, ExtractedValue | None],
) -> dict[str, Decimal | str | None]:
    """``extract_values()`` の結果を ``{key: value}`` 辞書に変換する。

    pandas の ``DataFrame`` 構築や JSON シリアライズ向けの軽量変換。

    Args:
        extracted: ``extract_values()`` の戻り値。

    Returns:
        ``{canonical_key: value}`` の辞書。
        ``ExtractedValue`` が ``None`` のキーは値も ``None``。

    Example:
        >>> row = extracted_to_dict(extract_values(pl, [CK.REVENUE]))
        >>> row
        {'revenue': Decimal('1234567000')}
    """
    return {
        k: (ev.value if ev is not None else None)
        for k, ev in extracted.items()
    }
