"""RawContext の XML 断片を構造化データに変換するモジュール。

``parse_xbrl_facts()`` が抽出した :class:`~edinet.xbrl.parser.RawContext` の
XML 文字列を再パースし、期間 (period)・Entity・Dimension を型付きオブジェクトに変換する。
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from lxml import etree

from edinet.exceptions import EdinetParseError
from edinet.xbrl._namespaces import NS_XBRLI, NS_XBRLDI
from edinet.xbrl.parser import RawContext

__all__ = [
    "InstantPeriod",
    "DurationPeriod",
    "Period",
    "DimensionMember",
    "StructuredContext",
    "ContextCollection",
    "structure_contexts",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内部定数
# ---------------------------------------------------------------------------

_CONSOLIDATED_AXIS_LOCAL = "ConsolidatedOrNonConsolidatedAxis"
_NON_CONSOLIDATED_MEMBER_LOCAL = "NonConsolidatedMember"

# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


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
"""期間型。InstantPeriod または DurationPeriod。"""


@dataclass(frozen=True, slots=True)
class DimensionMember:
    """Dimension の軸とメンバーの組。

    Attributes:
        axis: 軸の Clark notation（``"{namespace}localName"``）。
        member: メンバーの Clark notation（``"{namespace}localName"``）。
    """

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
    entity_scheme: str | None = None

    @property
    def is_consolidated(self) -> bool:
        """連結コンテキストかどうかを判定する。

        連結軸がない場合（デフォルト）は True を返す。
        ConsolidatedMember が明示されている場合も True を返す。
        NonConsolidatedMember が明示されている場合は False を返す。
        """
        for dim in self.dimensions:
            if dim.axis.endswith(_CONSOLIDATED_AXIS_LOCAL):
                return not dim.member.endswith(_NON_CONSOLIDATED_MEMBER_LOCAL)
        return True

    @property
    def is_non_consolidated(self) -> bool:
        """非連結コンテキストかどうかを判定する。

        NonConsolidatedMember が明示されている場合のみ True を返す。
        """
        for dim in self.dimensions:
            if dim.axis.endswith(_CONSOLIDATED_AXIS_LOCAL):
                return dim.member.endswith(_NON_CONSOLIDATED_MEMBER_LOCAL)
        return False

    @property
    def is_instant(self) -> bool:
        """期間が InstantPeriod かどうかを判定する。"""
        return isinstance(self.period, InstantPeriod)

    @property
    def is_duration(self) -> bool:
        """期間が DurationPeriod かどうかを判定する。"""
        return isinstance(self.period, DurationPeriod)

    @property
    def has_dimensions(self) -> bool:
        """Dimension を持つかどうかを判定する。"""
        return len(self.dimensions) > 0

    @property
    def dimension_dict(self) -> dict[str, str]:
        """Dimension を辞書形式で返す。

        Returns:
            軸をキー、メンバーを値とする辞書。
        """
        return {dim.axis: dim.member for dim in self.dimensions}

    def has_dimension(self, axis: str) -> bool:
        """指定した軸の Dimension が存在するかを判定する。

        Args:
            axis: Clark notation の軸名。
        """
        return any(dim.axis == axis for dim in self.dimensions)

    def get_dimension_member(self, axis: str) -> str | None:
        """指定した軸に対応するメンバーを返す。

        Args:
            axis: Clark notation の軸名。

        Returns:
            メンバーの Clark notation。軸が存在しなければ None。
        """
        for dim in self.dimensions:
            if dim.axis == axis:
                return dim.member
        return None

    @property
    def has_extra_dimensions(self) -> bool:
        """連結軸以外の Dimension が存在するかを判定する。"""
        return any(
            not dim.axis.endswith(_CONSOLIDATED_AXIS_LOCAL)
            for dim in self.dimensions
        )


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def structure_contexts(
    raw_contexts: Sequence[RawContext],
) -> dict[str, StructuredContext]:
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
    result: dict[str, StructuredContext] = {}
    for raw in raw_contexts:
        if raw.context_id is None:
            logger.debug(
                "context_id が None の RawContext をスキップします (source_line=%s)",
                raw.source_line,
            )
            continue
        structured = _parse_single_context(raw)
        if raw.context_id in result:
            logger.debug(
                "重複した context_id=%r を検出しました。後勝ちで上書きします",
                raw.context_id,
            )
        result[raw.context_id] = structured
    return result


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _parse_single_context(raw: RawContext) -> StructuredContext:
    """1 つの RawContext を StructuredContext に変換する。

    Args:
        raw: 変換対象の RawContext。

    Returns:
        構造化された StructuredContext。

    Raises:
        EdinetParseError: XML パースや構造解析に失敗した場合。
    """
    cid = raw.context_id or "(unknown)"
    try:
        elem = etree.fromstring(raw.xml.encode("utf-8"))  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"Context の XML パースに失敗しました (context_id={cid!r})"
        raise EdinetParseError(msg) from exc

    period = _parse_period(elem, cid)
    entity_id, entity_scheme = _parse_entity_id(elem, cid)
    dimensions = _parse_dimensions(elem, cid)

    return StructuredContext(
        context_id=cid,
        period=period,
        entity_id=entity_id,
        dimensions=dimensions,
        source_line=raw.source_line,
        entity_scheme=entity_scheme,
    )


def _parse_period(
    elem: etree._Element,
    cid: str,
) -> Period:
    """``<xbrli:period>`` を解析して Period を返す。

    Args:
        elem: Context の XML 要素。
        cid: エラーメッセージ用の context_id。

    Returns:
        InstantPeriod または DurationPeriod。

    Raises:
        EdinetParseError: period 要素が見つからない場合や
            子要素が不正な場合。
    """
    period_elem = elem.find(f"{{{NS_XBRLI}}}period")
    if period_elem is None:
        msg = f"period 要素が見つかりません (context_id={cid!r})"
        raise EdinetParseError(msg)

    instant_elem = period_elem.find(f"{{{NS_XBRLI}}}instant")
    if instant_elem is not None:
        instant = _parse_date(
            instant_elem.text,
            cid,
            "instant",
        )
        return InstantPeriod(instant=instant)

    start_elem = period_elem.find(f"{{{NS_XBRLI}}}startDate")
    end_elem = period_elem.find(f"{{{NS_XBRLI}}}endDate")
    if start_elem is not None and end_elem is not None:
        start_date = _parse_date(start_elem.text, cid, "startDate")
        end_date = _parse_date(end_elem.text, cid, "endDate")
        return DurationPeriod(start_date=start_date, end_date=end_date)

    msg = (
        f"period の子要素が不正です "
        f"(instant / startDate+endDate のいずれも見つかりません, "
        f"context_id={cid!r})"
    )
    raise EdinetParseError(msg)


def _parse_date(
    text: str | None,
    cid: str,
    field_name: str,
) -> datetime.date:
    """ISO 8601 日付文字列を ``datetime.date`` に変換する。

    Args:
        text: 日付テキスト。
        cid: エラーメッセージ用の context_id。
        field_name: エラーメッセージ用のフィールド名。

    Returns:
        パースされた date。

    Raises:
        EdinetParseError: テキストが None、空、または不正な形式の場合。
    """
    if text is None:
        msg = f"{field_name} のテキストが空です (context_id={cid!r})"
        raise EdinetParseError(msg)
    stripped = text.strip()
    if stripped == "":
        msg = f"{field_name} のテキストが空です (context_id={cid!r})"
        raise EdinetParseError(msg)
    try:
        return datetime.date.fromisoformat(stripped)
    except ValueError as exc:
        msg = (
            f"{field_name} の日付形式が不正です "
            f"(value={stripped!r}, context_id={cid!r})"
        )
        raise EdinetParseError(msg) from exc


def _parse_entity_id(
    elem: etree._Element,
    cid: str,
) -> tuple[str, str | None]:
    """``<entity/identifier>`` からテキスト値と scheme 属性を抽出する。

    Args:
        elem: Context の XML 要素。
        cid: エラーメッセージ用の context_id。

    Returns:
        ``(identifier テキスト値, scheme 属性値)`` のタプル。
        scheme が未指定の場合は ``None``。

    Raises:
        EdinetParseError: entity または identifier が見つからないか空の場合。
    """
    entity_elem = elem.find(f"{{{NS_XBRLI}}}entity")
    if entity_elem is None:
        msg = f"entity 要素が見つかりません (context_id={cid!r})"
        raise EdinetParseError(msg)
    identifier_elem = entity_elem.find(f"{{{NS_XBRLI}}}identifier")
    if identifier_elem is None:
        msg = f"entity/identifier 要素が見つかりません (context_id={cid!r})"
        raise EdinetParseError(msg)
    text = identifier_elem.text
    if text is None or text.strip() == "":
        msg = f"entity/identifier のテキストが空です (context_id={cid!r})"
        raise EdinetParseError(msg)
    scheme = identifier_elem.get("scheme")
    return text.strip(), scheme


def _parse_dimensions(
    elem: etree._Element,
    cid: str,
) -> tuple[DimensionMember, ...]:
    """``<scenario/explicitMember>`` から Dimension を抽出する。

    Args:
        elem: Context の XML 要素。
        cid: エラーメッセージ用の context_id。

    Returns:
        DimensionMember のタプル。scenario がなければ空タプル。

    Raises:
        EdinetParseError: QName の解決に失敗した場合。
    """
    scenario_elem = elem.find(f"{{{NS_XBRLI}}}scenario")
    if scenario_elem is None:
        return ()

    members: list[DimensionMember] = []
    for explicit in scenario_elem.findall(f"{{{NS_XBRLDI}}}explicitMember"):
        dimension_attr = explicit.get("dimension")
        if dimension_attr is None:
            continue
        axis = _resolve_qname(dimension_attr.strip(), explicit.nsmap, cid)
        member_text = explicit.text
        if member_text is None or member_text.strip() == "":
            continue
        member = _resolve_qname(member_text.strip(), explicit.nsmap, cid)
        members.append(DimensionMember(axis=axis, member=member))

    return tuple(members)


def _resolve_qname(
    qname_str: str,
    nsmap: dict[str | None, str],
    cid: str,
) -> str:
    """``prefix:localName`` を Clark notation ``{ns}localName`` に変換する。

    Args:
        qname_str: ``prefix:localName`` 形式の QName 文字列。
        nsmap: 名前空間マッピング。
        cid: エラーメッセージ用の context_id。

    Returns:
        Clark notation の QName。

    Raises:
        EdinetParseError: prefix がないか未定義の場合。
    """
    if ":" not in qname_str:
        msg = (
            f"QName に prefix がありません "
            f"(qname={qname_str!r}, context_id={cid!r})"
        )
        raise EdinetParseError(msg)
    prefix, local_name = qname_str.split(":", 1)
    uri = nsmap.get(prefix)
    if uri is None:
        msg = (
            f"QName の prefix が未定義です "
            f"(prefix={prefix!r}, qname={qname_str!r}, context_id={cid!r})"
        )
        raise EdinetParseError(msg)
    return f"{{{uri}}}{local_name}"


# ---------------------------------------------------------------------------
# ContextCollection
# ---------------------------------------------------------------------------


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

    __slots__ = ("_contexts",)

    def __init__(self, contexts: dict[str, StructuredContext]) -> None:
        """コレクションを初期化する。

        内部では ``dict(contexts)`` で浅いコピーを作成し、
        外部からの変更を遮断する。

        Args:
            contexts: ``structure_contexts()`` の戻り値。
                ``dict[str, StructuredContext]`` のみ受け付ける。
                ``ContextCollection`` を渡す場合は ``.as_dict`` で変換すること。
        """
        self._contexts: dict[str, StructuredContext] = dict(contexts)

    # --- 基本アクセス ---

    def __len__(self) -> int:
        return len(self._contexts)

    def __iter__(self) -> Iterator[StructuredContext]:
        return iter(self._contexts.values())

    def __contains__(self, context_id: object) -> bool:
        return context_id in self._contexts

    def __getitem__(self, context_id: str) -> StructuredContext:
        return self._contexts[context_id]

    def get(
        self,
        context_id: str,
        default: StructuredContext | None = None,
    ) -> StructuredContext | None:
        """指定した context_id の StructuredContext を返す。

        Args:
            context_id: 取得対象の context_id。
            default: 見つからない場合のデフォルト値。

        Returns:
            StructuredContext。見つからなければ default。
        """
        return self._contexts.get(context_id, default)

    @property
    def as_dict(self) -> dict[str, StructuredContext]:
        """内部辞書の浅いコピーを返す。

        ``StructuredContext`` は frozen dataclass のため deep copy は不要。
        """
        return dict(self._contexts)

    def __repr__(self) -> str:
        instant_count = sum(
            1 for ctx in self._contexts.values() if ctx.is_instant
        )
        duration_count = len(self._contexts) - instant_count
        return (
            f"ContextCollection("
            f"total={len(self._contexts)}, "
            f"instant={instant_count}, "
            f"duration={duration_count})"
        )

    # --- フィルタメソッド ---

    def filter_consolidated(self) -> ContextCollection:
        """連結コンテキストのみを抽出する。"""
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if ctx.is_consolidated
        })

    def filter_non_consolidated(self) -> ContextCollection:
        """非連結コンテキストのみを抽出する。"""
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if ctx.is_non_consolidated
        })

    def filter_instant(self) -> ContextCollection:
        """InstantPeriod のコンテキストのみを抽出する。"""
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if ctx.is_instant
        })

    def filter_duration(self) -> ContextCollection:
        """DurationPeriod のコンテキストのみを抽出する。"""
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if ctx.is_duration
        })

    def filter_by_period(self, period: Period) -> ContextCollection:
        """指定した期間に一致するコンテキストのみを抽出する。

        Args:
            period: フィルタ対象の期間。
        """
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if ctx.period == period
        })

    def filter_no_extra_dimensions(self) -> ContextCollection:
        """連結/個別軸以外の Dimension がないコンテキストを返す。

        「連結/個別軸」は ``ConsolidatedOrNonConsolidatedAxis``
        （local_name 判定）のみ。セグメント軸や提出者独自軸を除外する。

        Examples:
            全社合計（連結）の典型パターン::

                main = coll.filter_consolidated().filter_no_extra_dimensions()
        """
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if not ctx.has_extra_dimensions
        })

    def filter_no_dimensions(self) -> ContextCollection:
        """Dimension が一切ないコンテキストを返す。

        Note:
            ``ConsolidatedMember`` が明示的に設定された Context も除外される。
            全社合計の抽出には :meth:`filter_no_extra_dimensions` を
            使用すること。
        """
        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if not ctx.has_dimensions
        })

    def filter_by_dimension(
        self,
        axis: str,
        member: str | None = None,
    ) -> ContextCollection:
        """指定した軸（とメンバー）を持つコンテキストのみを抽出する。

        Args:
            axis: Clark notation の軸名。
            member: Clark notation のメンバー名。None の場合は軸の存在のみ判定。
        """

        def _match(ctx: StructuredContext) -> bool:
            if member is None:
                return ctx.has_dimension(axis)
            return ctx.get_dimension_member(axis) == member

        return ContextCollection({
            cid: ctx
            for cid, ctx in self._contexts.items()
            if _match(ctx)
        })

    # --- 期間クエリ ---

    @property
    def unique_instant_periods(self) -> tuple[InstantPeriod, ...]:
        """一意な InstantPeriod を instant 降順で返す。"""
        periods: set[InstantPeriod] = set()
        for ctx in self._contexts.values():
            if isinstance(ctx.period, InstantPeriod):
                periods.add(ctx.period)
        return tuple(sorted(
            periods,
            key=lambda p: p.instant,
            reverse=True,
        ))

    @property
    def unique_duration_periods(self) -> tuple[DurationPeriod, ...]:
        """一意な DurationPeriod を end_date 降順・start_date 昇順で返す。"""
        periods: set[DurationPeriod] = set()
        for ctx in self._contexts.values():
            if isinstance(ctx.period, DurationPeriod):
                periods.add(ctx.period)
        # end_date DESC, start_date ASC（同一 end_date なら最長期間優先）
        return tuple(sorted(
            periods,
            key=lambda p: (p.end_date, -p.start_date.toordinal()),
            reverse=True,
        ))

    @property
    def latest_instant_period(self) -> InstantPeriod | None:
        """最新の InstantPeriod を返す。存在しなければ None。"""
        periods = self.unique_instant_periods
        return periods[0] if periods else None

    @property
    def latest_duration_period(self) -> DurationPeriod | None:
        """最新の DurationPeriod を返す。存在しなければ None。

        end_date が最新のものを選択し、同一の場合は最長期間を優先する。
        """
        periods = self.unique_duration_periods
        return periods[0] if periods else None

    def latest_instant_contexts(self) -> ContextCollection:
        """最新の InstantPeriod に一致するコンテキストを返す。"""
        period = self.latest_instant_period
        if period is None:
            return ContextCollection({})
        return self.filter_by_period(period)

    def latest_duration_contexts(self) -> ContextCollection:
        """最新の DurationPeriod に一致するコンテキストを返す。"""
        period = self.latest_duration_period
        if period is None:
            return ContextCollection({})
        return self.filter_by_period(period)
