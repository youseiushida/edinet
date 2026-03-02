"""RawUnit の XML 断片を構造化データに変換するモジュール。

``parse_xbrl_facts()`` が抽出した :class:`~edinet.xbrl.parser.RawUnit` の
XML 文字列を再パースし、単位 (measure / divide) を型付きオブジェクトに変換する。
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Sequence
from dataclasses import dataclass

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._namespaces import NS_ISO4217, NS_UTR, NS_XBRLI
from edinet.xbrl.parser import RawUnit

__all__ = [
    "SimpleMeasure",
    "DivideMeasure",
    "Measure",
    "StructuredUnit",
    "structure_units",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_WELL_KNOWN_PREFIXES: dict[str, str] = {
    "iso4217": NS_ISO4217,
    "xbrli": NS_XBRLI,
    "utr": NS_UTR,
}
"""XML 断片内で名前空間宣言が欠落している場合のフォールバック辞書。"""

# ---------------------------------------------------------------------------
# データモデル
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SimpleMeasure:
    """単一の measure 要素を表す。

    Attributes:
        namespace_uri: 名前空間 URI（例: ``"http://www.xbrl.org/2003/iso4217"``）。
        local_name: ローカル名（例: ``"JPY"``）。
        raw_text: measure 要素のテキスト値（例: ``"iso4217:JPY"``）。
    """

    namespace_uri: str
    local_name: str
    raw_text: str


@dataclass(frozen=True, slots=True)
class DivideMeasure:
    """divide 要素（分子/分母）を表す。

    Attributes:
        numerator: 分子の SimpleMeasure。
        denominator: 分母の SimpleMeasure。
    """

    numerator: SimpleMeasure
    denominator: SimpleMeasure


Measure = SimpleMeasure | DivideMeasure
"""単位の measure 型。SimpleMeasure または DivideMeasure。"""


@dataclass(frozen=True, slots=True)
class StructuredUnit:
    """構造化された Unit。

    Attributes:
        unit_id: Unit の ID。
        measure: 単位情報。
        source_line: 元 XML の行番号。
    """

    unit_id: str
    measure: Measure
    source_line: int | None

    @property
    def is_monetary(self) -> bool:
        """通貨単位かどうかを返す。"""
        return (
            isinstance(self.measure, SimpleMeasure)
            and self.measure.namespace_uri == NS_ISO4217
        )

    @property
    def is_pure(self) -> bool:
        """純粋数値（xbrli:pure）かどうかを返す。"""
        return (
            isinstance(self.measure, SimpleMeasure)
            and self.measure.namespace_uri == NS_XBRLI
            and self.measure.local_name == "pure"
        )

    @property
    def is_shares(self) -> bool:
        """株式数（xbrli:shares）かどうかを返す。"""
        return (
            isinstance(self.measure, SimpleMeasure)
            and self.measure.namespace_uri == NS_XBRLI
            and self.measure.local_name == "shares"
        )

    @property
    def is_per_share(self) -> bool:
        """1株あたり単位（通貨/株式数）かどうかを返す。"""
        if not isinstance(self.measure, DivideMeasure):
            return False
        return (
            self.measure.numerator.namespace_uri == NS_ISO4217
            and self.measure.denominator.namespace_uri == NS_XBRLI
            and self.measure.denominator.local_name == "shares"
        )

    @property
    def currency_code(self) -> str | None:
        """通貨コードを返す。

        SimpleMeasure で iso4217 名前空間の場合はそのローカル名（例: ``"JPY"``）、
        DivideMeasure で分子が iso4217 名前空間の場合は分子のローカル名を返す。
        いずれにも該当しない場合は None。

        Note:
            ``is_monetary`` が False でも ``currency_code`` が非 None になる
            ケースがある（例: ``JPYPerShares`` は ``is_monetary=False`` だが
            ``currency_code="JPY"``）。
        """
        if isinstance(self.measure, SimpleMeasure) and self.measure.namespace_uri == NS_ISO4217:
            return self.measure.local_name
        if isinstance(self.measure, DivideMeasure) and self.measure.numerator.namespace_uri == NS_ISO4217:
            return self.measure.numerator.local_name
        return None


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def structure_units(
    raw_units: Sequence[RawUnit],
) -> dict[str, StructuredUnit]:
    """RawUnit のシーケンスを構造化して辞書で返す。

    Args:
        raw_units: ``parse_xbrl_facts()`` が抽出した RawUnit のシーケンス。

    Returns:
        unit_id をキー、StructuredUnit を値とする辞書。
        重複 unit_id は後勝ち。

    Raises:
        EdinetParseError: measure 欠落、XML 構文エラーなど
            構造解析に失敗した場合。
    """
    result: dict[str, StructuredUnit] = {}
    for raw in raw_units:
        if raw.unit_id is None:
            logger.debug(
                "unit_id が None の RawUnit をスキップします (source_line=%s)",
                raw.source_line,
            )
            continue
        structured = _parse_single_unit(raw)
        if raw.unit_id in result:
            logger.debug(
                "重複した unit_id=%r を検出しました。後勝ちで上書きします",
                raw.unit_id,
            )
        result[raw.unit_id] = structured
    return result


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _parse_single_unit(raw: RawUnit) -> StructuredUnit:
    """1 つの RawUnit を StructuredUnit に変換する。

    Args:
        raw: 変換対象の RawUnit。

    Returns:
        構造化された StructuredUnit。

    Raises:
        EdinetParseError: XML パースや構造解析に失敗した場合。
    """
    uid = raw.unit_id or "(unknown)"
    try:
        elem = etree.fromstring(raw.xml.encode("utf-8"))  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"Unit の XML パースに失敗しました (unit_id={uid!r})"
        raise EdinetParseError(msg) from exc

    # nsmap 構築（None キーをフィルタし、WELL_KNOWN をフォールバックとしてマージ）
    nsmap_str = {k: v for k, v in elem.nsmap.items() if k is not None}
    resolved_nsmap = {**_WELL_KNOWN_PREFIXES, **nsmap_str}

    # divide 要素の有無で分岐
    divide_elem = elem.find(f"{{{NS_XBRLI}}}divide")
    if divide_elem is not None:
        measure = _parse_divide(divide_elem, resolved_nsmap, uid)
    else:
        measure = _parse_simple_measure(elem, resolved_nsmap, uid)

    return StructuredUnit(
        unit_id=uid,
        measure=measure,
        source_line=raw.source_line,
    )


def _parse_simple_measure(
    parent: etree._Element,
    nsmap: dict[str, str],
    uid: str,
) -> SimpleMeasure:
    """parent 配下の measure 要素をパースして SimpleMeasure を返す。

    Args:
        parent: measure 要素の親（unit 要素または divide の子）。
        nsmap: 名前空間マッピング。
        uid: エラーメッセージ用の unit_id。

    Returns:
        SimpleMeasure インスタンス。

    Raises:
        EdinetParseError: measure 要素が見つからない、または空の場合。
    """
    measures = parent.findall(f"{{{NS_XBRLI}}}measure")
    if not measures:
        msg = f"measure 要素が見つかりません (unit_id={uid!r})"
        raise EdinetParseError(msg)

    if len(measures) > 1:
        warnings.warn(
            f"複数の measure 要素を検出しました。先頭のみ使用します "
            f"(unit_id={uid!r}, count={len(measures)})",
            EdinetWarning,
            stacklevel=4,
        )

    return _resolve_measure_text(measures[0], nsmap, uid)


def _parse_divide(
    divide_elem: etree._Element,
    nsmap: dict[str, str],
    uid: str,
) -> DivideMeasure:
    """divide 要素をパースして DivideMeasure を返す。

    Args:
        divide_elem: divide 要素。
        nsmap: 名前空間マッピング。
        uid: エラーメッセージ用の unit_id。

    Returns:
        DivideMeasure インスタンス。

    Raises:
        EdinetParseError: unitNumerator/unitDenominator が見つからない場合。
    """
    numerator_elem = divide_elem.find(f"{{{NS_XBRLI}}}unitNumerator")
    if numerator_elem is None:
        msg = f"divide に unitNumerator が見つかりません (unit_id={uid!r})"
        raise EdinetParseError(msg)

    denominator_elem = divide_elem.find(f"{{{NS_XBRLI}}}unitDenominator")
    if denominator_elem is None:
        msg = f"divide に unitDenominator が見つかりません (unit_id={uid!r})"
        raise EdinetParseError(msg)

    numerator = _parse_simple_measure(numerator_elem, nsmap, uid)
    denominator = _parse_simple_measure(denominator_elem, nsmap, uid)

    return DivideMeasure(numerator=numerator, denominator=denominator)


def _resolve_measure_text(
    measure_elem: etree._Element,
    nsmap: dict[str, str],
    uid: str,
) -> SimpleMeasure:
    """measure 要素のテキストを解析して SimpleMeasure を返す。

    Args:
        measure_elem: measure 要素。
        nsmap: 名前空間マッピング。
        uid: エラーメッセージ用の unit_id。

    Returns:
        SimpleMeasure インスタンス。

    Raises:
        EdinetParseError: テキストが空の場合。
    """
    text = measure_elem.text
    if text is None or text.strip() == "":
        msg = f"measure 要素のテキストが空です (unit_id={uid!r})"
        raise EdinetParseError(msg)

    raw_text = text.strip()

    if ":" not in raw_text:
        warnings.warn(
            f"measure にプレフィックスがありません (unit_id={uid!r})",
            EdinetWarning,
            stacklevel=4,
        )
        return SimpleMeasure(
            namespace_uri="",
            local_name=raw_text,
            raw_text=raw_text,
        )

    prefix, local_name = raw_text.split(":", 1)
    uri = nsmap.get(prefix)
    if uri is None:
        warnings.warn(
            f"measure の prefix が未定義です。raw_text をそのまま保持します "
            f"(prefix={prefix!r}, unit_id={uid!r})",
            EdinetWarning,
            stacklevel=4,
        )
        return SimpleMeasure(
            namespace_uri="",
            local_name=local_name,
            raw_text=raw_text,
        )

    return SimpleMeasure(
        namespace_uri=uri,
        local_name=local_name,
        raw_text=raw_text,
    )
