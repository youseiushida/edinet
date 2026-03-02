"""財務情報モデル定義。"""

from __future__ import annotations

import enum
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    import pandas as pd

    from edinet.xbrl.contexts import DimensionMember, Period
    from edinet.xbrl.taxonomy import LabelInfo
    from edinet.xbrl.taxonomy.concept_sets import ConceptSet

__all__ = ["LineItem", "StatementType", "FinancialStatement"]


@dataclass(frozen=True, slots=True, kw_only=True)
class LineItem:
    """型付き・ラベル付きの XBRL Fact。

    RawFact + StructuredContext + TaxonomyResolver から生成される、
    下流（Day 15 の FinancialStatement 組み立て等）が消費する主要データ型。

    Attributes:
        concept: Clark notation の QName（例: ``"{ns}NetSales"``）。
            RawFact.concept_qname をそのまま引き継ぐ。
        namespace_uri: 名前空間 URI。
        local_name: ローカル名（例: ``"NetSales"``）。
        label_ja: 日本語ラベル情報。TaxonomyResolver から取得。
        label_en: 英語ラベル情報。TaxonomyResolver から取得。
        value: 変換済みの値。数値 Fact は ``Decimal``、テキスト Fact は ``str``、
            nil Fact は ``None``。テキスト Fact の値は ``RawFact.value_raw``
            （``itertext()`` によるタグ除去済みプレーンテキスト）を使用する。
            HTML タグを含む原文が必要な場合は ``RawFact.value_inner_xml`` を
            直接参照すること（TextBlock 等、v0.2.0 の ``text_blocks`` モジュールで対応予定）。
        unit_ref: unitRef 属性値。テキスト Fact は ``None``。
        decimals: decimals 属性値。``int`` / ``"INF"`` / ``None``。
        context_id: contextRef 属性値（トレーサビリティ用）。
        period: StructuredContext から転写した期間情報。
        entity_id: StructuredContext から転写した Entity ID。
        dimensions: StructuredContext から転写した Dimension 情報。
        is_nil: xsi:nil が真かどうか。
        source_line: 元 XML の行番号。
        order: 元文書内の出現順。
    """

    concept: str
    namespace_uri: str
    local_name: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    unit_ref: str | None
    decimals: int | Literal["INF"] | None
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    is_nil: bool
    source_line: int | None
    order: int


class StatementType(enum.Enum):
    """財務諸表の種類。"""

    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW_STATEMENT = "cash_flow_statement"


STATEMENT_TYPE_LABELS: Final[dict[StatementType, str]] = {
    StatementType.INCOME_STATEMENT: "損益計算書 (Income Statement)",
    StatementType.BALANCE_SHEET: "貸借対照表 (Balance Sheet)",
    StatementType.CASH_FLOW_STATEMENT: "キャッシュ・フロー計算書 (Cash Flow Statement)",
}

_DATAFRAME_COLUMNS: Final[list[str]] = [
    "label_ja",
    "label_en",
    "value",
    "unit",
    "concept",
]


def _display_width(s: str) -> int:
    """文字列の端末表示幅を返す。

    CJK 全角文字は 2 カラム、それ以外は 1 カラムとして計算する。

    Args:
        s: 表示幅を計算する文字列。

    Returns:
        端末上の表示幅（カラム数）。
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def format_period(period: Period) -> str:
    """Period を表示用文字列に変換する。

    Args:
        period: 変換対象の期間オブジェクト。

    Returns:
        InstantPeriod → ``"2025-03-31"``、
        DurationPeriod → ``"2024-04-01〜2025-03-31"``。
    """
    from edinet.xbrl.contexts import DurationPeriod, InstantPeriod

    if isinstance(period, InstantPeriod):
        return str(period.instant)
    if isinstance(period, DurationPeriod):
        return f"{period.start_date}〜{period.end_date}"
    return str(period)


@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialStatement:
    """組み立て済みの財務諸表。

    LineItem 群を選択ルール（期間・連結・dimension フィルタ）で
    絞り込み、JSON データファイルの order に従って並べたもの。

    ``items`` 内の各 ``LineItem.label_ja`` / ``LineItem.label_en`` は
    常に非 None（``LabelInfo`` 型）。TaxonomyResolver のフォールバック
    チェーン（T-7: 指定 role → 標準ラベル → 冗長ラベル → local_name）
    により保証される。

    Attributes:
        statement_type: 財務諸表の種類（PL / BS / CF）。
        period: この財務諸表が対象とする期間。BS の場合は
            ``InstantPeriod``、PL / CF の場合は ``DurationPeriod``。
            該当する Fact が 0 件の場合は ``None``。
        items: 並び順が確定した LineItem のタプル。
        consolidated: 連結（True）か個別（False）か。
        entity_id: Entity ID（トレーサビリティ用）。1 filing 内で
            entity_id は統一されるため単一値。空の statement
            （``items=()``）では空文字列 ``""``。
        warnings_issued: 組み立て中に発行された警告メッセージ一覧。
    """

    statement_type: StatementType
    period: Period | None
    items: tuple[LineItem, ...]
    consolidated: bool
    entity_id: str
    warnings_issued: tuple[str, ...]
    _concept_set: ConceptSet | None = field(default=None, compare=False, repr=False)
    _taxonomy_root: Path | None = field(default=None, compare=False, repr=False)

    def __getitem__(self, key: str) -> LineItem:
        """科目を日本語ラベル・英語ラベル・local_name で検索する。

        Args:
            key: 検索キー。以下の順で照合する:
                1. ``label_ja.text``（例: ``"売上高"``）
                2. ``label_en.text``（例: ``"Net sales"``）
                3. ``local_name``（例: ``"NetSales"``）

        Returns:
            最初にマッチした LineItem。同一ラベルの科目が
            複数存在する場合は、items 内で最初に見つかったものを返す。

        Raises:
            KeyError: マッチする科目が見つからない場合。
        """
        for item in self.items:
            if key in (item.label_ja.text, item.label_en.text, item.local_name):
                return item
        raise KeyError(key)

    def get(
        self, key: str, default: LineItem | None = None
    ) -> LineItem | None:
        """科目を検索する。見つからなければ default を返す。

        Args:
            key: 検索キー。照合順序は ``__getitem__`` と同一。
            default: マッチしない場合の返り値。

        Returns:
            マッチした LineItem、またはマッチしなければ default。
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key: object) -> bool:
        """科目の存在確認。``"売上高" in pl`` のように使う。"""
        if not isinstance(key, str):
            return False
        try:
            self[key]
        except KeyError:
            return False
        return True

    def __len__(self) -> int:
        """科目数を返す。"""
        return len(self.items)

    def __iter__(self) -> Iterator[LineItem]:
        """科目を順に返す。"""
        return iter(self.items)

    def __repr__(self) -> str:
        """簡潔な表現を返す。"""
        return (
            f"FinancialStatement(type={self.statement_type.value}, "
            f"period={self.period}, items={len(self.items)}, "
            f"consolidated={self.consolidated})"
        )

    def __str__(self) -> str:
        """プレーンテキスト表示。

        Rich なしでも ``print(pl)`` で読みやすいテーブルを出力する。
        科目名（日本語ラベル）と金額をカンマ区切り・右寄せで表示する。
        CJK 全角文字の表示幅を考慮して列を揃える。

        Note:
            value は ``build_statements()`` 経由で数値 Fact のみ含まれる前提。
            ``Decimal('Infinity')`` / ``Decimal('NaN')`` は来ない想定。
        """
        header = STATEMENT_TYPE_LABELS.get(
            self.statement_type, self.statement_type.value
        )
        scope = "連結" if self.consolidated else "個別"
        period_str = format_period(self.period) if self.period else "(期間なし)"

        lines: list[str] = [f"{header}  [{scope}] {period_str}", ""]

        if not self.items:
            lines.append("  (科目なし)")
            return "\n".join(lines)

        # ラベル幅を動的計算（最大 40 カラム幅でクリップ）
        max_width = min(
            max(
                (_display_width(item.label_ja.text) for item in self.items),
                default=0,
            ),
            40,
        )

        for item in self.items:
            label = item.label_ja.text
            label_width = _display_width(label)
            padding = max_width - label_width
            if isinstance(item.value, Decimal):
                # Note: 値幅は固定 20 カラム。混合精度の科目が入る場合は動的幅計算を検討
                value_str = f"{item.value:>20,}"
            elif item.value is None:
                value_str = f"{'—':>20}"
            else:
                value_str = f"{item.value!s:>20}"
            lines.append(f"  {label}{' ' * padding}  {value_str}")

        lines.append(f"\n  ({len(self.items)} 科目)")
        return "\n".join(lines)

    def to_dict(self) -> list[dict[str, object]]:
        """辞書のリストに変換する。

        pandas 不要で科目データを取得できる。
        LLM（RAG）パイプラインや軽量なデータ変換に適している。

        各辞書は ``to_dataframe()`` と同じ 5 キーを持つ:
        ``label_ja``, ``label_en``, ``value``, ``unit``, ``concept``。

        Returns:
            科目ごとの辞書のリスト。空 statement では空リスト。
        """
        return [
            {
                "label_ja": item.label_ja.text,
                "label_en": item.label_en.text,
                "value": item.value,
                "unit": item.unit_ref,
                "concept": item.local_name,
            }
            for item in self.items
        ]

    def to_dataframe(self, *, full: bool = False) -> pd.DataFrame:
        """pandas DataFrame に変換する。

        Args:
            full: True の場合、全カラム（context_id, period_type, dimensions 等）を
                含む DataFrame を返す。False（デフォルト）の場合は従来の 5 カラム。

        デフォルト（full=False）のカラム:

        - ``label_ja``: 日本語ラベル（``str``）
        - ``label_en``: 英語ラベル（``str``）
        - ``value``: 値（``Decimal | str | None``）
        - ``unit``: 単位（``str | None``）
        - ``concept``: concept のローカル名（``str``）

        ``value`` 列は ``Decimal`` のまま保持される（``object`` 型）。
        集計が必要な場合は ``df["value"].astype(float)`` で変換すること。

        返却される DataFrame の ``attrs`` に statement レベルのメタデータ
        （``statement_type``, ``consolidated``, ``period``, ``entity_id``）
        を付与する。

        Returns:
            科目名・金額等を含む DataFrame。

        Raises:
            ImportError: pandas がインストールされていない場合。
                ``pip install edinet[analysis]`` でインストールできる。

        Examples:
            >>> df = pl.to_dataframe()
            >>> df[df["value"] > 0]  # 正の値のみ抽出
            >>> df_full = pl.to_dataframe(full=True)  # 全カラム
        """
        if full:
            from edinet.dataframe.facts import line_items_to_dataframe

            return line_items_to_dataframe(
                self.items,
                metadata={
                    "statement_type": self.statement_type.value,
                    "consolidated": self.consolidated,
                    "period": format_period(self.period) if self.period else None,
                    "entity_id": self.entity_id,
                },
            )

        try:
            import pandas as pd_
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install edinet[analysis]"
            ) from None

        rows: list[dict[str, object]] = []
        for item in self.items:
            rows.append({
                "label_ja": item.label_ja.text,
                "label_en": item.label_en.text,
                "value": item.value,
                "unit": item.unit_ref,
                "concept": item.local_name,
            })

        if not rows:
            df = pd_.DataFrame(columns=_DATAFRAME_COLUMNS)
        else:
            df = pd_.DataFrame(rows)

        df.attrs["statement_type"] = self.statement_type.value
        df.attrs["consolidated"] = self.consolidated
        df.attrs["period"] = format_period(self.period) if self.period else None
        df.attrs["entity_id"] = self.entity_id
        return df

    def to_csv(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を CSV に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_csv()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_csv

        to_csv(self.to_dataframe(full=True), path, **kwargs)

    def to_parquet(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を Parquet に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_parquet()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_parquet

        to_parquet(self.to_dataframe(full=True), path, **kwargs)

    def to_excel(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を Excel に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_excel()`` に渡す追加引数。
        """
        from edinet.dataframe.export import to_excel

        to_excel(self.to_dataframe(full=True), path, **kwargs)

    def __rich_console__(self, console, options):  # noqa: ANN001
        """Rich Console Protocol。

        ``from rich.console import Console; Console().print(pl)`` で
        フォーマットされたテーブルが表示される。

        ``_concept_set`` が設定されている場合は階層表示を使用する。
        rich がインストールされていない場合、この Protocol は呼ばれない
        （Rich Console 自体が存在しないため）。
        """
        try:
            if self._concept_set is not None:
                from edinet.display.statements import (
                    _resolve_abstract_labels,
                    render_hierarchical_statement,
                )

                labels = _resolve_abstract_labels(
                    self._concept_set, self._taxonomy_root,
                )
                yield render_hierarchical_statement(
                    self, self._concept_set, abstract_labels=labels,
                )
            else:
                from edinet.display.rich import render_statement

                yield render_statement(self)
        except ImportError:
            yield str(self)
