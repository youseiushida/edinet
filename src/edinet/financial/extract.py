"""正規化キーによる財務数値の抽出ユーティリティ。

会計基準（J-GAAP / IFRS / US-GAAP / JMIS）を意識せず、canonical key で
SummaryOfBusinessResults および PL/BS/CF 本体から値を取り出す。

v0.3.0 設計:
    ``Statements`` を渡すと ``_items`` 全体をパイプラインマッパーで 1 パス走査する。
    デフォルトパイプライン
    ``[summary_mapper, statement_mapper, definition_mapper(), calc_mapper()]``
    で名寄せを行う。

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
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from edinet.financial.statements import Statements

from edinet.exceptions import EdinetWarning
from edinet.financial.mapper import (
    ConceptMapper,
    MapperContext,
    calc_mapper,
    definition_mapper,
    statement_mapper,
    summary_mapper,
)
from edinet.financial.standards.canonical_keys import CK
from edinet.models.financial import LineItem
from edinet.financial.statements import (
    _is_consolidated as _check_consolidated,
    _is_non_consolidated as _check_non_consolidated,
)

__all__ = ["ExtractedValue", "extract_values", "extracted_to_dict"]

_CK_MEMBERS: frozenset[str] = frozenset(CK)
"""CK enum メンバー集合。typo 警告の O(1) ルックアップ用。"""


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """正規化キーで抽出された財務数値。

    Attributes:
        canonical_key: 正規化キー（例: ``"revenue"``）。
        value: 抽出された値。数値の場合は ``Decimal``、テキストの場合は
            ``str``、nil または欠損の場合は ``None``。
        item: 元の ``LineItem``。``source_line``、``label_ja``、
            ``namespace_uri`` 等のトレーサビリティ情報を含む。
        mapper_name: 値を採用したマッパー関数の名前。
            ``getattr(mapper_fn, "__name__", None)`` で自動取得される。
            例: ``"summary_mapper"``、``"statement_mapper"``、
            ``"dict_mapper(3 entries)"``。
    """

    canonical_key: str
    value: Decimal | str | None
    item: LineItem
    mapper_name: str | None


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


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def extract_values(
    source: Statements,
    keys: Sequence[str] | None = None,
    *,
    period: Literal["current", "prior"] | None = None,
    consolidated: bool | None = None,
    mapper: ConceptMapper | Sequence[ConceptMapper] | None = None,
) -> dict[str, ExtractedValue | None]:
    """正規化キーで財務データから値を抽出する。

    ``Statements`` を渡すと ``_items`` 全体をパイプラインマッパーで
    1 パス走査する。

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
        mapper: マッパーまたはマッパーのシーケンス。
            ``None``（デフォルト）の場合は
            ``[summary_mapper, statement_mapper, definition_mapper(), calc_mapper()]``。
            単一 callable の場合は ``[callable]`` と同義。

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

    # マッパーパイプライン解決
    if mapper is None:
        pipeline: list[ConceptMapper] = [
            summary_mapper, statement_mapper,
            definition_mapper(), calc_mapper(),
        ]
    elif callable(mapper):
        pipeline = [mapper]
    else:
        pipeline = list(mapper)

    # MapperContext 構築
    from edinet.xbrl.taxonomy.custom import _build_parent_index

    ctx = MapperContext(
        dei=source.dei,
        detected_standard=source.detected_standard,
        industry_code=source.industry_code,
        definition_parent_index=_build_parent_index(
            source.definition_linkbase,
        ),
        calculation_linkbase=source.calculation_linkbase,
    )

    # 期間解決（1回のみ）
    target_duration, target_instant = _resolve_periods(
        period, source.dei,
    )

    # キーフィルタ
    target_keys: set[str] | None = (
        {str(k) for k in keys} if keys is not None else None
    )

    # 1パスマッパーループ
    # ck_to_item: {canonical_key: (LineItem, pipeline_position, mapper_name)}
    ck_to_item: dict[str, tuple[LineItem, int, str | None]] = {}

    for item in source:
        if not _filter_item(
            item,
            period=period,
            target_duration=target_duration,
            target_instant=target_instant,
            consolidated=consolidated,
        ):
            continue

        for idx, mapper_fn in enumerate(pipeline):
            ck = mapper_fn(item, ctx)
            if ck is None:
                continue
            if target_keys is not None and ck not in target_keys:
                continue
            # CK typo 警告（keys=None 時のみ）
            if target_keys is None and ck not in _CK_MEMBERS:
                warnings.warn(
                    f"マッパーが未知の CK '{ck}' を返しました。"
                    f"タイポの可能性があります。",
                    UserWarning,
                    stacklevel=2,
                )
            name = getattr(mapper_fn, "__name__", None)
            existing = ck_to_item.get(ck)
            if existing is None or idx < existing[1]:
                ck_to_item[ck] = (item, idx, name)
            break  # 1 item に対して最初にマッチしたマッパーを採用

    # 結果構築
    if keys is None:
        return {
            ck: ExtractedValue(
                canonical_key=ck, value=item.value, item=item,
                mapper_name=name,
            )
            for ck, (item, _idx, name) in ck_to_item.items()
        }

    result: dict[str, ExtractedValue | None] = {}
    for key in keys:
        key_str = str(key)
        entry = ck_to_item.get(key_str)
        if entry is not None:
            item, _idx, name = entry
            result[key_str] = ExtractedValue(
                canonical_key=key_str, value=item.value, item=item,
                mapper_name=name,
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
