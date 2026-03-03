"""脚注リンクパーサー。

XBRL インスタンス内の ``link:footnoteLink`` 要素をパースし、
Fact ID と脚注テキスト（※1, ※2 等）の紐付けを提供する。

J-GAAP の BS/PL で使用される脚注番号の解決に対応。
IFRS セクションでは footnoteLink は存在しない。

典型的な使い方::

    from edinet.xbrl.linkbase.footnotes import parse_footnote_links

    footnote_map = parse_footnote_links(parsed.footnote_links)
    notes = footnote_map.get("IdFact1234")
    for n in notes:
        print(n.text)  # "※1 減損損失の認識について..."
"""

from __future__ import annotations

import logging
import warnings
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl._namespaces import NS_LINK, NS_XLINK, NS_XML
from edinet.xbrl.parser import RawFootnoteLink

logger = logging.getLogger(__name__)

# ---------- Clark notation 定数 ----------
# footnoteLink は loc/footnote/arc の 3 種の要素で同一 XLink 属性を
# 反復参照するため、可読性と DRY の観点からモジュールレベル定数とする。

_TAG_LOC = f"{{{NS_LINK}}}loc"
_TAG_FOOTNOTE = f"{{{NS_LINK}}}footnote"
_TAG_FOOTNOTEARC = f"{{{NS_LINK}}}footnoteArc"

_ATTR_HREF = f"{{{NS_XLINK}}}href"
_ATTR_LABEL = f"{{{NS_XLINK}}}label"
_ATTR_ROLE = f"{{{NS_XLINK}}}role"
_ATTR_FROM = f"{{{NS_XLINK}}}from"
_ATTR_TO = f"{{{NS_XLINK}}}to"
_ATTR_ARCROLE = f"{{{NS_XLINK}}}arcrole"
_ATTR_LANG = f"{{{NS_XML}}}lang"

_ARCROLE_FACT_FOOTNOTE = "http://www.xbrl.org/2003/arcrole/fact-footnote"


# ========== データモデル ==========


@dataclass(frozen=True, slots=True)
class Footnote:
    """脚注。

    XBRL の ``link:footnote`` 要素から抽出した脚注情報。

    Attributes:
        label: xlink:label 属性値（アーク接続用識別子）。
        text: 脚注テキスト（例: ``"※1 当事業年度の…"``）。
        lang: xml:lang 属性値（例: ``"ja"``）。
        role: xlink:role 属性値。
    """

    label: str
    text: str
    lang: str
    role: str


@dataclass(frozen=True, slots=True)
class FootnoteMap:
    """Fact ID → 脚注のマッピング。

    ``parse_footnote_links()`` の返り値。
    Fact の id 属性値をキーに、紐付けられた脚注を検索できる。

    Attributes:
        _index: Fact ID → Footnote タプルの辞書（arc で紐付けられたもののみ）。
        _all: XML に存在する全 Footnote のタプル（arc による紐付けの有無に関わらず
              収集。重複除去済み。frozen dataclass のデフォルト ``__eq__`` による
              全フィールド一致で判定）。
    """

    _index: dict[str, tuple[Footnote, ...]]
    _all: tuple[Footnote, ...]

    def get(self, fact_id: str) -> tuple[Footnote, ...]:
        """Fact ID から脚注を取得する。

        Args:
            fact_id: Fact の id 属性値。

        Returns:
            紐付けられた Footnote のタプル。見つからなければ空タプル。
        """
        return self._index.get(fact_id, ())

    def has_footnotes(self, fact_id: str) -> bool:
        """Fact に脚注が存在するかを返す。

        Args:
            fact_id: Fact の id 属性値。
        """
        return fact_id in self._index

    def all_footnotes(self) -> tuple[Footnote, ...]:
        """全脚注を返す。"""
        return self._all

    @property
    def fact_ids(self) -> tuple[str, ...]:
        """脚注が紐付けられた Fact ID の一覧を返す。"""
        return tuple(self._index.keys())

    def __len__(self) -> int:
        """脚注が紐付けられた Fact の数を返す。"""
        return len(self._index)

    def __contains__(self, fact_id: object) -> bool:
        """Fact に脚注が存在するかの確認。"""
        return fact_id in self._index


# ========== 内部ヘルパー ==========


def _parse_single_link(
    root: etree._Element,
) -> tuple[
    dict[str, list[Footnote]],
    list[Footnote],
]:
    """1 つの footnoteLink 要素をパースする。

    Args:
        root: ``link:footnoteLink`` のルート要素。

    Returns:
        (fact_id → Footnote リスト, 全 Footnote リスト) のタプル。
    """
    # 1. loc 走査: label → Fact ID リスト（1:N）
    loc_map: dict[str, list[str]] = defaultdict(list)
    for loc_elem in root.findall(_TAG_LOC):
        label = loc_elem.get(_ATTR_LABEL)
        href = loc_elem.get(_ATTR_HREF)
        if not label or not href:
            continue

        if not href.startswith("#"):
            warnings.warn(
                f"脚注リンク: loc の href がフラグメント形式ではありません: '{href}'",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        fact_id = href[1:]
        if not fact_id:
            warnings.warn(
                "脚注リンク: loc の href が '#' のみで Fact ID が空です",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        loc_map[label].append(fact_id)

    # 2. footnote 走査: label → Footnote
    fn_map: dict[str, Footnote] = {}
    all_footnotes: list[Footnote] = []
    for fn_elem in root.findall(_TAG_FOOTNOTE):
        label = fn_elem.get(_ATTR_LABEL)
        if not label:
            continue

        role = fn_elem.get(_ATTR_ROLE)
        if not role:
            warnings.warn(
                "脚注リンク: footnote に xlink:role が未設定のためスキップします",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        text = "".join(fn_elem.itertext())
        lang = fn_elem.get(_ATTR_LANG) or ""

        fn = Footnote(label=label, text=text, lang=lang, role=role)
        fn_map[label] = fn
        all_footnotes.append(fn)

    # 3. arc 走査: from(loc label) → to(footnote label)
    index: dict[str, list[Footnote]] = defaultdict(list)
    for arc_elem in root.findall(_TAG_FOOTNOTEARC):
        arcrole = arc_elem.get(_ATTR_ARCROLE)
        if arcrole != _ARCROLE_FACT_FOOTNOTE:
            continue

        from_label = arc_elem.get(_ATTR_FROM)
        to_label = arc_elem.get(_ATTR_TO)

        if not from_label or not to_label:
            warnings.warn(
                "脚注リンク: footnoteArc の from/to が未設定のためスキップします",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        fact_ids = loc_map.get(from_label)
        if not fact_ids:
            warnings.warn(
                f"脚注リンク: loc ラベル '{from_label}' が見つかりません",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        footnote = fn_map.get(to_label)
        if footnote is None:
            warnings.warn(
                f"脚注リンク: footnote ラベル '{to_label}' が見つかりません",
                EdinetWarning,
                stacklevel=3,
            )
            continue

        for fid in fact_ids:
            index[fid].append(footnote)

    logger.debug(
        "footnoteLink パース: loc=%d, footnote=%d, arc 解決=%d Fact",
        len(loc_map),
        len(fn_map),
        len(index),
    )

    return dict(index), all_footnotes


# ========== 公開 API ==========


def parse_footnote_links(
    raw_links: Sequence[RawFootnoteLink],
) -> FootnoteMap:
    """RawFootnoteLink 群から FootnoteMap を構築する。

    各 ``RawFootnoteLink.xml`` を再パースし、loc / footnote / footnoteArc の
    3 要素を抽出して Fact ID → Footnote のマッピングを構築する。

    複数の footnoteLink にまたがる脚注は統合される（同一 Fact ID に対する
    脚注はタプルにまとめられる）。

    Args:
        raw_links: ``ParsedXBRL.footnote_links``。

    Returns:
        構築された FootnoteMap。footnoteLink が空の場合は空の FootnoteMap を返す。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
    if not raw_links:
        return FootnoteMap(_index={}, _all=())

    merged_index: dict[str, list[Footnote]] = defaultdict(list)
    all_collected: list[Footnote] = []

    for raw in raw_links:
        try:
            root = etree.fromstring(raw.xml.encode("utf-8"))  # noqa: S320
        except etree.XMLSyntaxError as e:
            raise EdinetParseError(
                "脚注リンクの XML パースに失敗しました"
            ) from e

        index_part, all_part = _parse_single_link(root)

        for fact_id, footnotes in index_part.items():
            merged_index[fact_id].extend(footnotes)
        all_collected.extend(all_part)

    # _index: list → tuple
    final_index = {
        fid: tuple(fns) for fid, fns in merged_index.items()
    }

    # _all: 重複除去（frozen dataclass の __eq__/__hash__ で判定）
    final_all = tuple(dict.fromkeys(all_collected))

    logger.info(
        "脚注リンクのパース完了: %d Fact に脚注, 全 %d 脚注",
        len(final_index),
        len(final_all),
    )

    return FootnoteMap(_index=final_index, _all=final_all)
