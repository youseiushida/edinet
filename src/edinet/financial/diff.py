"""訂正差分・期間差分の比較ユーティリティ。

訂正前 vs 訂正後の Fact レベル差分（revision diff）と、
前期 vs 当期の科目増減（period diff）を構造化する。

使用例::

    from edinet.financial.diff import diff_revisions, diff_periods

    # --- 訂正差分 ---
    result = diff_revisions(original_stmts, corrected_stmts)
    for item in result.modified:
        print(f"{item.label_ja.text}: {item.old_value} → {item.new_value}")

    # --- 期間差分 ---
    pl_prior = stmts.income_statement(period="prior")
    pl_current = stmts.income_statement(period="current")
    period_diff = diff_periods(pl_prior, pl_current)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from edinet.exceptions import EdinetWarning
from edinet.financial.statements import Statements
from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.taxonomy import LabelInfo

__all__ = ["DiffItem", "DiffResult", "diff_revisions", "diff_periods"]


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _values_equal(
    a: Decimal | str | None,
    b: Decimal | str | None,
) -> bool:
    """2 つの値が等しいかを判定する。

    ``Decimal`` 同士は数値比較、``str`` 同士は文字列比較、
    ``None`` 同士は等しいと判定する。型が異なる場合は不等。

    Args:
        a: 値 A。
        b: 値 B。

    Returns:
        等しければ ``True``。
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, Decimal) and isinstance(b, Decimal):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    # 型不一致（Decimal vs str 等）
    return False


def _compute_difference(
    old_value: Decimal | str | None,
    new_value: Decimal | str | None,
) -> Decimal | None:
    """2 つの値の差額を計算する。

    両方が ``Decimal`` の場合のみ差額を返す。
    それ以外（``str``, ``None``, 型混在）の場合は ``None`` を返す。

    Args:
        old_value: 変更前の値。
        new_value: 変更後の値。

    Returns:
        ``new_value - old_value``。計算不可の場合は ``None``。
    """
    if isinstance(old_value, Decimal) and isinstance(new_value, Decimal):
        return new_value - old_value
    return None


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DiffItem:
    """値が変更された科目。

    Attributes:
        concept: concept のローカル名。
        label_ja: 日本語ラベル（old 側のラベルを使用）。
        label_en: 英語ラベル（old 側のラベルを使用）。
        old_value: 変更前の値。
        new_value: 変更後の値。
        difference: ``new - old``（数値の場合）。
            テキスト科目や片方が ``None`` の場合は ``None``。
    """

    concept: str
    label_ja: LabelInfo
    label_en: LabelInfo
    old_value: Decimal | str | None
    new_value: Decimal | str | None
    difference: Decimal | None


@dataclass(frozen=True, slots=True)
class DiffResult:
    """差分比較の結果。

    Attributes:
        added: new にのみ存在する科目。
        removed: old にのみ存在する科目。
        modified: 値が変更された科目。
        unchanged_count: 値が変更されていない科目の件数。
    """

    added: tuple[LineItem, ...]
    removed: tuple[LineItem, ...]
    modified: tuple[DiffItem, ...]
    unchanged_count: int

    @property
    def has_changes(self) -> bool:
        """変更があるかどうかを返す。"""
        return bool(self.added or self.removed or self.modified)

    @property
    def total_compared(self) -> int:
        """比較対象の総科目数を返す。"""
        return (
            len(self.added)
            + len(self.removed)
            + len(self.modified)
            + self.unchanged_count
        )

    def summary(self) -> str:
        """差分のサマリー文字列を返す。

        Returns:
            ``"追加: 2, 削除: 1, 変更: 3, 変更なし: 50"`` のような文字列。
        """
        return (
            f"追加: {len(self.added)}, "
            f"削除: {len(self.removed)}, "
            f"変更: {len(self.modified)}, "
            f"変更なし: {self.unchanged_count}"
        )


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def diff_revisions(
    original: Statements,
    corrected: Statements,
) -> DiffResult:
    """訂正前 vs 訂正後の Fact レベル差分を返す。

    2 つの ``Statements`` を ``LineItem`` の ``(local_name, context_id)``
    をキーに照合し、追加・削除・変更・変更なしに分類する。

    比較対象は全 ``LineItem``（PL + BS + CF + その他、全期間・全 dimension）。
    連結/個別の絞り込みが必要な場合は、事前に
    ``Statements.income_statement(consolidated=True)`` 等で
    ``FinancialStatement`` を取得し、``diff_periods()`` を使用すること。

    Args:
        original: 訂正前の ``Statements``。
        corrected: 訂正後の ``Statements``。

    Returns:
        差分比較結果。
    """
    # (local_name, context_id) → LineItem のマップを構築
    old_map: dict[tuple[str, str], LineItem] = {}
    for item in original:
        key = (item.local_name, item.context_id)
        old_map.setdefault(key, item)

    new_map: dict[tuple[str, str], LineItem] = {}
    for item in corrected:
        key = (item.local_name, item.context_id)
        new_map.setdefault(key, item)

    return _compare_maps(old_map, new_map)


def diff_periods(
    prior: FinancialStatement,
    current: FinancialStatement,
) -> DiffResult:
    """前期 vs 当期の科目増減を返す。

    2 つの ``FinancialStatement`` を ``LineItem`` の ``local_name``
    をキーに照合し、追加・削除・変更・変更なしに分類する。

    同一 Filing 内の current vs prior を比較するのがデフォルトの
    ユースケース。異なる年度の Filing を比較する場合、概念名の改廃により
    不正確な結果になる可能性がある（v0.1.0 では非推奨概念のマッピングなし）。

    Args:
        prior: 前期の ``FinancialStatement``。
        current: 当期の ``FinancialStatement``。

    Returns:
        差分比較結果。
    """
    prior_map = _build_local_name_map(prior, "prior")
    current_map = _build_local_name_map(current, "current")

    return _compare_maps(prior_map, current_map)


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _build_local_name_map(
    fs: FinancialStatement,
    label: str,
) -> dict[str, LineItem]:
    """FinancialStatement から local_name → LineItem の辞書を構築する。

    同一 ``local_name`` が複数存在する場合は先頭を使用し、警告を発行する。

    Args:
        fs: 対象の ``FinancialStatement``。
        label: 警告メッセージ用のラベル（``"prior"`` / ``"current"``）。

    Returns:
        ``local_name`` → ``LineItem`` の辞書。
    """
    result: dict[str, LineItem] = {}
    for item in fs.items:
        if item.local_name in result:
            msg = (
                f"diff_periods: {label} に同一 local_name の科目が"
                f"複数存在します: {item.local_name!r}（先頭を使用）"
            )
            warnings.warn(msg, EdinetWarning, stacklevel=3)
        else:
            result[item.local_name] = item
    return result


def _compare_maps(
    old_map: dict[Any, LineItem],
    new_map: dict[Any, LineItem],
) -> DiffResult:
    """2 つのマップを比較して DiffResult を返す。

    キーは ``str``（diff_periods）または ``tuple[str, str]``
    （diff_revisions）のいずれか。``sorted()`` 可能であること。

    Args:
        old_map: old 側のキー → LineItem マップ。
        new_map: new 側のキー → LineItem マップ。

    Returns:
        差分比較結果。
    """
    old_keys = set(old_map)
    new_keys = set(new_map)

    # added: new にのみ存在
    added = tuple(new_map[k] for k in sorted(new_keys - old_keys))

    # removed: old にのみ存在
    removed = tuple(old_map[k] for k in sorted(old_keys - new_keys))

    # modified / unchanged: 両方に存在
    modified_items: list[DiffItem] = []
    unchanged_count = 0

    for key in sorted(old_keys & new_keys):
        old_item = old_map[key]
        new_item = new_map[key]

        if _values_equal(old_item.value, new_item.value):
            unchanged_count += 1
        else:
            modified_items.append(
                DiffItem(
                    concept=old_item.local_name,
                    label_ja=old_item.label_ja,
                    label_en=old_item.label_en,
                    old_value=old_item.value,
                    new_value=new_item.value,
                    difference=_compute_difference(
                        old_item.value, new_item.value
                    ),
                )
            )

    return DiffResult(
        added=added,
        removed=removed,
        modified=tuple(modified_items),
        unchanged_count=unchanged_count,
    )
