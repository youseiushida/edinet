"""正規化キーによる財務数値の抽出ユーティリティ。

会計基準（J-GAAP / IFRS / US-GAAP / JMIS）を意識せず、canonical key で
SummaryOfBusinessResults および PL/BS/CF 本体から値を取り出す。

v0.2.0 設計:
    ``Statements`` を渡すと ``_items`` 全体から SummaryOfBusinessResults
    concept を走査し、``include_statements=True``（デフォルト）の場合は
    未取得キーを PL/BS/CF 本体からも補完する。

使用例::

    from edinet.financial.extract import extract_values, extracted_to_dict
    from edinet.financial.standards.canonical_keys import CK

    # Statements → Summary + PL/BS/CF から当期・連結の値を抽出
    result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME],
                            period="current", consolidated=True)

    # pandas 連携
    row = extracted_to_dict(result)
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from edinet.exceptions import EdinetWarning
from edinet.financial.standards.statement_mappings import (
    lookup_statement_exact,
    lookup_statement_normalized,
)
from edinet.financial.standards.summary_mappings import lookup_summary
from edinet.models.financial import LineItem
from edinet.financial.statements import (
    _is_consolidated as _check_consolidated,
    _is_non_consolidated as _check_non_consolidated,
)

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
        source: 抽出元レイヤー。

            - ``"summary"``: SummaryOfBusinessResults から完全一致（信頼度最高）。
            - ``"exact"``: PL/BS/CF 本体から辞書完全一致。
            - ``"normalized"``: EDINET サフィックス剥離後に辞書引き（信頼度低）。
    """

    canonical_key: str
    value: Decimal | str | None
    item: LineItem
    source: Literal["summary", "exact", "normalized"]


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _resolve_periods(
    period: Literal["current", "prior"] | None,
    dei: Any | None,
) -> tuple[Any | None, Any | None]:
    """period 文字列を DurationPeriod/InstantPeriod に解決する。

    Args:
        period: 期間フィルタ。
        dei: DEI 情報。

    Returns:
        ``(target_duration, target_instant)`` のタプル。
    """
    if period is None:
        return None, None

    if dei is None:
        warnings.warn(
            f"period={period!r} が指定されましたが DEI 情報がないため"
            f"期間フィルタをスキップします",
            EdinetWarning,
            stacklevel=4,
        )
        return None, None

    from edinet.financial.dimensions.period_variants import classify_periods

    pc = classify_periods(dei)
    if period == "current":
        return pc.current_duration, pc.current_instant
    # period == "prior"
    return pc.prior_duration, pc.prior_instant


def _filter_item(
    item: LineItem,
    *,
    period: Literal["current", "prior"] | None,
    target_duration: Any | None,
    target_instant: Any | None,
    consolidated: bool | None,
) -> bool:
    """期間・連結フィルタを適用し、通過すれば True を返す。"""
    from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

    # 期間フィルタ
    if period is not None and (target_duration is not None or target_instant is not None):
        if isinstance(item.period, DurationPeriod):
            if target_duration is not None and item.period != target_duration:
                return False
        elif isinstance(item.period, InstantPeriod):
            if target_instant is not None and item.period != target_instant:
                return False

    # 連結フィルタ
    if consolidated is not None:
        if consolidated and not _check_consolidated(item):
            return False
        if not consolidated and not _check_non_consolidated(item):
            return False

    return True


def _extract_from_items(
    items: tuple[LineItem, ...],
    *,
    period: Literal["current", "prior"] | None,
    consolidated: bool | None,
    dei: Any | None,
) -> dict[str, LineItem]:
    """_items から SummaryOfBusinessResults concept のみ走査する。

    Args:
        items: Statements._items（全 LineItem）。
        period: 期間フィルタ。``"current"`` / ``"prior"`` / ``None``（全期間）。
        consolidated: 連結フィルタ。``True`` / ``False`` / ``None``（全て）。
        dei: DEI 情報（期間解決用）。

    Returns:
        ``{canonical_key: LineItem}`` の辞書（先頭優先）。
    """
    target_duration, target_instant = _resolve_periods(period, dei)

    ck_to_item: dict[str, LineItem] = {}
    for item in items:
        # SummaryOfBusinessResults concept のみ走査
        ck = lookup_summary(item.local_name)
        if ck is None:
            continue

        if not _filter_item(
            item,
            period=period,
            target_duration=target_duration,
            target_instant=target_instant,
            consolidated=consolidated,
        ):
            continue

        if ck not in ck_to_item:
            ck_to_item[ck] = item

    return ck_to_item


_SourcedItem = tuple[LineItem, Literal["summary", "exact", "normalized"]]
"""``(LineItem, source)`` のペア。内部でのみ使用。"""


def _extract_from_raw_items(
    items: tuple[LineItem, ...],
    missing_keys: set[str] | None,
    *,
    period: Literal["current", "prior"] | None,
    target_duration: Any | None,
    target_instant: Any | None,
    consolidated: bool | None,
) -> dict[str, _SourcedItem]:
    """_items を直接走査して statement_mappings の CK を抽出する。

    PL/BS/CF メソッドを経由せず ``_items`` を走査するため:
        - ConceptSet 構築コストがゼロ
        - 注記セクション（R&D 費等）の科目も取得可能

    信頼度を維持するため 2 パスで走査する:
        1. 辞書完全一致（``lookup_statement_exact``）→ source="exact"
        2. 正規化フォールバック（``lookup_statement_normalized``、
           パス 1 で未取得のキーのみ）→ source="normalized"

    Args:
        items: ``Statements._items``（全 LineItem）。
        missing_keys: 取得対象のキー集合。
            ``None`` の場合はキーフィルタなし（全科目走査）。
        period: 期間フィルタ。
        target_duration: 解決済み DurationPeriod。
        target_instant: 解決済み InstantPeriod。
        consolidated: 連結フィルタ。

    Returns:
        ``{canonical_key: (LineItem, source)}`` の辞書。
        辞書完全一致が正規化フォールバックより常に優先される。
    """
    ck_to_item: dict[str, _SourcedItem] = {}

    # パス 1: 辞書完全一致（信頼度高）
    for item in items:
        ck = lookup_statement_exact(item.local_name)
        if ck is None:
            continue
        if missing_keys is not None and ck not in missing_keys:
            continue
        if not _filter_item(
            item,
            period=period,
            target_duration=target_duration,
            target_instant=target_instant,
            consolidated=consolidated,
        ):
            continue
        if ck not in ck_to_item:
            ck_to_item[ck] = (item, "exact")

    # パス 2: 正規化フォールバック（パス 1 で未取得のキーのみ）
    remaining = (
        missing_keys - set(ck_to_item) if missing_keys is not None else None
    )
    if remaining is not None and not remaining:
        return ck_to_item  # 全キー取得済み

    for item in items:
        ck = lookup_statement_normalized(item.local_name)
        if ck is None:
            continue
        if remaining is not None and ck not in remaining:
            continue
        if ck in ck_to_item:
            continue  # パス 1 の結果を上書きしない
        if not _filter_item(
            item,
            period=period,
            target_duration=target_duration,
            target_instant=target_instant,
            consolidated=consolidated,
        ):
            continue
        ck_to_item[ck] = (item, "normalized")

    return ck_to_item


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def extract_values(
    source: Any,
    keys: Sequence[str] | None = None,
    *,
    period: Literal["current", "prior"] | None = None,
    consolidated: bool | None = None,
    include_statements: bool = True,
) -> dict[str, ExtractedValue | None]:
    """正規化キーで財務データから値を抽出する。

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
        Decimal('500000000')
    """
    from edinet.financial.statements import Statements as _Statements

    if not isinstance(source, _Statements):
        raise TypeError(
            f"Statements を渡してください（got {type(source).__name__}）"
        )

    # Summary 走査 → source="summary"
    summary_items = _extract_from_items(
        source._items,  # noqa: SLF001
        period=period,
        consolidated=consolidated,
        dei=source._dei,  # noqa: SLF001
    )
    ck_sourced: dict[str, _SourcedItem] = {
        ck: (item, "summary") for ck, item in summary_items.items()
    }

    # _items 直接走査で PL/BS/CF + 注記科目を補完
    if include_statements:
        if keys is not None:
            missing: set[str] | None = {str(k) for k in keys} - set(ck_sourced)
        else:
            missing = None  # keys=None: 全科目を追加走査

        if missing is None or missing:
            target_duration, target_instant = _resolve_periods(
                period, source._dei,  # noqa: SLF001
            )
            raw_sourced = _extract_from_raw_items(
                source._items,  # noqa: SLF001
                missing,
                period=period,
                target_duration=target_duration,
                target_instant=target_instant,
                consolidated=consolidated,
            )
            for ck, sourced in raw_sourced.items():
                if ck not in ck_sourced:
                    ck_sourced[ck] = sourced

    if keys is None:
        return {
            ck: ExtractedValue(
                canonical_key=ck, value=item.value, item=item, source=src,
            )
            for ck, (item, src) in ck_sourced.items()
        }

    result: dict[str, ExtractedValue | None] = {}
    for key in keys:
        key_str = str(key)
        sourced = ck_sourced.get(key_str)
        if sourced is not None:
            item, src = sourced
            result[key_str] = ExtractedValue(
                canonical_key=key_str, value=item.value, item=item, source=src,
            )
        else:
            result[key_str] = None
    return result


def extracted_to_dict(
    *extracted_dicts: dict[str, ExtractedValue | None],
) -> dict[str, Decimal | str | None]:
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
    result: dict[str, Decimal | str | None] = {}
    for extracted in extracted_dicts:
        for k, ev in extracted.items():
            if ev is not None:
                result[k] = ev.value
            elif k not in result:
                result[k] = None
    return result
