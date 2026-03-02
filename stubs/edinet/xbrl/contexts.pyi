import datetime
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from edinet.xbrl.parser import RawContext

__all__ = ['InstantPeriod', 'DurationPeriod', 'Period', 'DimensionMember', 'StructuredContext', 'ContextCollection', 'structure_contexts']

@dataclass(frozen=True, slots=True)
class InstantPeriod:
    """時点を表す期間。

    Attributes:
        instant: 時点の日付。
    """
    instant: datetime.date

@dataclass(frozen=True, slots=True)
class DurationPeriod:
    """期間を表す期間。

    Attributes:
        start_date: 期間の開始日。
        end_date: 期間の終了日。
    """
    start_date: datetime.date
    end_date: datetime.date
Period = InstantPeriod | DurationPeriod

@dataclass(frozen=True, slots=True)
class DimensionMember:
    '''Dimension の軸とメンバーの組。

    Attributes:
        axis: 軸の Clark notation（``"{namespace}localName"``）。
        member: メンバーの Clark notation（``"{namespace}localName"``）。
    '''
    axis: str
    member: str

@dataclass(frozen=True, slots=True)
class StructuredContext:
    """構造化された Context。

    Attributes:
        context_id: Context の ID。
        period: 期間情報。
        entity_id: Entity の identifier テキスト値。
        dimensions: Dimension メンバーのタプル。
        source_line: 元 XML の行番号。
        entity_scheme: Entity の identifier scheme 属性値。
    """
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    source_line: int | None
    entity_scheme: str | None = ...
    @property
    def is_consolidated(self) -> bool:
        """連結コンテキストかどうかを判定する。

        連結軸がない場合（デフォルト）は True を返す。
        ConsolidatedMember が明示されている場合も True を返す。
        NonConsolidatedMember が明示されている場合は False を返す。
        """
    @property
    def is_non_consolidated(self) -> bool:
        """非連結コンテキストかどうかを判定する。

        NonConsolidatedMember が明示されている場合のみ True を返す。
        """
    @property
    def is_instant(self) -> bool:
        """期間が InstantPeriod かどうかを判定する。"""
    @property
    def is_duration(self) -> bool:
        """期間が DurationPeriod かどうかを判定する。"""
    @property
    def has_dimensions(self) -> bool:
        """Dimension を持つかどうかを判定する。"""
    @property
    def dimension_dict(self) -> dict[str, str]:
        """Dimension を辞書形式で返す。

        Returns:
            軸をキー、メンバーを値とする辞書。
        """
    def has_dimension(self, axis: str) -> bool:
        """指定した軸の Dimension が存在するかを判定する。

        Args:
            axis: Clark notation の軸名。
        """
    def get_dimension_member(self, axis: str) -> str | None:
        """指定した軸に対応するメンバーを返す。

        Args:
            axis: Clark notation の軸名。

        Returns:
            メンバーの Clark notation。軸が存在しなければ None。
        """
    @property
    def has_extra_dimensions(self) -> bool:
        """連結軸以外の Dimension が存在するかを判定する。"""

def structure_contexts(raw_contexts: Sequence[RawContext]) -> dict[str, StructuredContext]:
    """RawContext のシーケンスを構造化して辞書で返す。

    Args:
        raw_contexts: ``parse_xbrl_facts()`` が抽出した RawContext のシーケンス。

    Returns:
        context_id をキー、StructuredContext を値とする辞書。
        重複 context_id は後勝ち。

    Raises:
        EdinetParseError: period 欠落、日付不正、entity 欠落など
            構造解析に失敗した場合。
    """

class ContextCollection:
    """複数の StructuredContext に対するフィルタ・クエリ操作を提供する。

    ``structure_contexts()`` の戻り値を受け取り、連結/個別・期間・
    Dimension によるフィルタリングを行う。フィルタ結果は新しい
    ``ContextCollection`` として返されるため、メソッドチェーンが可能。

    Note:
        ``__iter__`` は values（``StructuredContext``）を返す。
        ``collections.abc.Mapping`` プロトコルには準拠しない。
        キー付きアクセスには ``as_dict`` を使用すること。

    Examples:
        >>> ctx_map = structure_contexts(parsed.contexts)
        >>> coll = ContextCollection(ctx_map)
        >>> main = coll.filter_consolidated().filter_no_extra_dimensions()
        >>> for ctx in main:
        ...     print(ctx.context_id, ctx.period)
    """
    def __init__(self, contexts: dict[str, StructuredContext]) -> None:
        """コレクションを初期化する。

        内部では ``dict(contexts)`` で浅いコピーを作成し、
        外部からの変更を遮断する。

        Args:
            contexts: ``structure_contexts()`` の戻り値。
                ``dict[str, StructuredContext]`` のみ受け付ける。
                ``ContextCollection`` を渡す場合は ``.as_dict`` で変換すること。
        """
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[StructuredContext]: ...
    def __contains__(self, context_id: object) -> bool: ...
    def __getitem__(self, context_id: str) -> StructuredContext: ...
    def get(self, context_id: str, default: StructuredContext | None = None) -> StructuredContext | None:
        """指定した context_id の StructuredContext を返す。

        Args:
            context_id: 取得対象の context_id。
            default: 見つからない場合のデフォルト値。

        Returns:
            StructuredContext。見つからなければ default。
        """
    @property
    def as_dict(self) -> dict[str, StructuredContext]:
        """内部辞書の浅いコピーを返す。

        ``StructuredContext`` は frozen dataclass のため deep copy は不要。
        """
    def filter_consolidated(self) -> ContextCollection:
        """連結コンテキストのみを抽出する。"""
    def filter_non_consolidated(self) -> ContextCollection:
        """非連結コンテキストのみを抽出する。"""
    def filter_instant(self) -> ContextCollection:
        """InstantPeriod のコンテキストのみを抽出する。"""
    def filter_duration(self) -> ContextCollection:
        """DurationPeriod のコンテキストのみを抽出する。"""
    def filter_by_period(self, period: Period) -> ContextCollection:
        """指定した期間に一致するコンテキストのみを抽出する。

        Args:
            period: フィルタ対象の期間。
        """
    def filter_no_extra_dimensions(self) -> ContextCollection:
        """連結/個別軸以外の Dimension がないコンテキストを返す。

        「連結/個別軸」は ``ConsolidatedOrNonConsolidatedAxis``
        （local_name 判定）のみ。セグメント軸や提出者独自軸を除外する。

        Examples:
            全社合計（連結）の典型パターン::

                main = coll.filter_consolidated().filter_no_extra_dimensions()
        """
    def filter_no_dimensions(self) -> ContextCollection:
        """Dimension が一切ないコンテキストを返す。

        Note:
            ``ConsolidatedMember`` が明示的に設定された Context も除外される。
            全社合計の抽出には :meth:`filter_no_extra_dimensions` を
            使用すること。
        """
    def filter_by_dimension(self, axis: str, member: str | None = None) -> ContextCollection:
        """指定した軸（とメンバー）を持つコンテキストのみを抽出する。

        Args:
            axis: Clark notation の軸名。
            member: Clark notation のメンバー名。None の場合は軸の存在のみ判定。
        """
    @property
    def unique_instant_periods(self) -> tuple[InstantPeriod, ...]:
        """一意な InstantPeriod を instant 降順で返す。"""
    @property
    def unique_duration_periods(self) -> tuple[DurationPeriod, ...]:
        """一意な DurationPeriod を end_date 降順・start_date 昇順で返す。"""
    @property
    def latest_instant_period(self) -> InstantPeriod | None:
        """最新の InstantPeriod を返す。存在しなければ None。"""
    @property
    def latest_duration_period(self) -> DurationPeriod | None:
        """最新の DurationPeriod を返す。存在しなければ None。

        end_date が最新のものを選択し、同一の場合は最長期間を優先する。
        """
    def latest_instant_contexts(self) -> ContextCollection:
        """最新の InstantPeriod に一致するコンテキストを返す。"""
    def latest_duration_contexts(self) -> ContextCollection:
        """最新の DurationPeriod に一致するコンテキストを返す。"""
