from dataclasses import dataclass
from decimal import Decimal
from edinet.financial.statements import Statements
from edinet.models.financial import FinancialStatement, LineItem
from edinet.xbrl.taxonomy import LabelInfo

__all__ = ['DiffItem', 'DiffResult', 'diff_revisions', 'diff_periods']

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
    @property
    def total_compared(self) -> int:
        """比較対象の総科目数を返す。"""
    def summary(self) -> str:
        '''差分のサマリー文字列を返す。

        Returns:
            ``"追加: 2, 削除: 1, 変更: 3, 変更なし: 50"`` のような文字列。
        '''

def diff_revisions(original: Statements, corrected: Statements) -> DiffResult:
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
def diff_periods(prior: FinancialStatement, current: FinancialStatement) -> DiffResult:
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
