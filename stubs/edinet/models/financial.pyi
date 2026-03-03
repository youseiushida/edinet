import enum
import pandas as pd
from _typeshed import Incomplete
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from decimal import Decimal
from edinet.xbrl.contexts import DimensionMember, Period
from edinet.xbrl.taxonomy import LabelInfo
from pathlib import Path
from typing import Literal

__all__ = ['LineItem', 'StatementType', 'FinancialStatement']

@dataclass(frozen=True, slots=True, kw_only=True)
class LineItem:
    '''型付き・ラベル付きの XBRL Fact。

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
            HTML タグを含む原文が必要な場合は ``RawFact.value_raw`` を参照するか、
            ``edinet.xbrl.text`` パッケージの ``extract_text_blocks()`` を使用すること。
        unit_ref: unitRef 属性値。テキスト Fact は ``None``。
        decimals: decimals 属性値。``int`` / ``"INF"`` / ``None``。
        context_id: contextRef 属性値（トレーサビリティ用）。
        period: StructuredContext から転写した期間情報。
        entity_id: StructuredContext から転写した Entity ID。
        dimensions: StructuredContext から転写した Dimension 情報。
        is_nil: xsi:nil が真かどうか。
        source_line: 元 XML の行番号。
        order: 元文書内の出現順。
    '''
    concept: str
    namespace_uri: str
    local_name: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    unit_ref: str | None
    decimals: int | Literal['INF'] | None
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    is_nil: bool
    source_line: int | None
    order: int

class StatementType(enum.Enum):
    """財務諸表の種類。"""
    INCOME_STATEMENT = 'income_statement'
    BALANCE_SHEET = 'balance_sheet'
    CASH_FLOW_STATEMENT = 'cash_flow_statement'

@dataclass(frozen=True, slots=True, kw_only=True)
class FinancialStatement:
    '''組み立て済みの財務諸表。

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
    '''
    statement_type: StatementType
    period: Period | None
    items: tuple[LineItem, ...]
    consolidated: bool
    entity_id: str
    warnings_issued: tuple[str, ...]
    def __getitem__(self, key: str) -> LineItem:
        '''科目を日本語ラベル・英語ラベル・local_name で検索する。

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
        '''
    def get(self, key: str, default: LineItem | None = None) -> LineItem | None:
        """科目を検索する。見つからなければ default を返す。

        Args:
            key: 検索キー。照合順序は ``__getitem__`` と同一。
            default: マッチしない場合の返り値。

        Returns:
            マッチした LineItem、またはマッチしなければ default。
        """
    def __contains__(self, key: object) -> bool:
        '''科目の存在確認。``"売上高" in pl`` のように使う。'''
    def __len__(self) -> int:
        """科目数を返す。"""
    def __iter__(self) -> Iterator[LineItem]:
        """科目を順に返す。"""
    def to_dict(self) -> list[dict[str, object]]:
        """辞書のリストに変換する。

        pandas 不要で科目データを取得できる。
        LLM（RAG）パイプラインや軽量なデータ変換に適している。

        各辞書は ``to_dataframe()`` と同じ 5 キーを持つ:
        ``label_ja``, ``label_en``, ``value``, ``unit``, ``concept``。

        Returns:
            科目ごとの辞書のリスト。空 statement では空リスト。
        """
    def to_dataframe(self, *, full: bool = False) -> pd.DataFrame:
        '''pandas DataFrame に変換する。

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
        '''
    def to_csv(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を CSV に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_csv()`` に渡す追加引数。
        """
    def to_parquet(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を Parquet に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_parquet()`` に渡す追加引数。
        """
    def to_excel(self, path: str | Path, **kwargs) -> None:
        """全カラム DataFrame を Excel に出力する。

        Args:
            path: 出力先ファイルパス。
            **kwargs: ``to_excel()`` に渡す追加引数。
        """
    def __rich_console__(self, console, options) -> Generator[Incomplete]:
        """Rich Console Protocol。

        ``from rich.console import Console; Console().print(pl)`` で
        フォーマットされたテーブルが表示される。

        ``_concept_set`` が設定されている場合は階層表示を使用する。
        rich がインストールされていない場合、この Protocol は呼ばれない
        （Rich Console 自体が存在しないため）。
        """
