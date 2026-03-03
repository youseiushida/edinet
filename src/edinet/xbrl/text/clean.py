"""HTML クリーニング。

TextBlock の HTML コンテンツをプレーンテキストに変換する。
LLM / RAG パイプラインの前処理として使用する。
"""

from __future__ import annotations

import re

from lxml.html import fragment_fromstring

__all__ = ["clean_html"]

_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
_REMOVE_TAGS = frozenset(("img", "svg", "style", "script"))
_BLOCK_NEWLINE_TAGS = frozenset(("table", "tr", "p"))


def clean_html(html: str) -> str:
    """HTML フラグメントをプレーンテキストに変換する。

    lxml.html の HTML パーサをベースに、テーブル構造を
    タブ/改行で保持する。

    変換ルール:
        - ``<br>``, ``<br/>`` → 改行
        - ``<p>`` → 改行
        - ``<td>``, ``<th>``（同一行の 2 番目以降）→ タブ区切り
        - ``<tr>`` → 改行
        - ``<table>`` → 改行
        - ``<img>``, ``<svg>``, ``<style>``, ``<script>`` → 除去
        - 連続する空行 → 1 つの空行に正規化
        - 先頭・末尾の空白 → strip

    Args:
        html: HTML フラグメント文字列。

    Returns:
        プレーンテキスト。空の入力には空文字列を返す。
    """
    if not html or not html.strip():
        return ""

    # create_parent="div" で常に Element を返す（タグなし入力でも安全）
    root = fragment_fromstring(html, create_parent="div")

    # 1. 不要要素を除去（tail テキストは保持）
    for tag_name in _REMOVE_TAGS:
        for elem in list(root.iter(tag_name)):
            _remove_preserving_tail(elem)

    # 2. 構造要素にテキスト区切りを挿入
    for elem in root.iter():
        tag = elem.tag
        if tag == "br":
            elem.tail = "\n" + (elem.tail or "")
        elif tag in _BLOCK_NEWLINE_TAGS:
            elem.tail = "\n" + (elem.tail or "")
        elif tag in ("td", "th"):
            # 同一 <tr> 内の 2 番目以降のセルにタブを挿入
            parent = elem.getparent()
            if parent is not None:
                siblings = list(parent)
                idx = siblings.index(elem)
                if idx > 0:
                    elem.text = "\t" + (elem.text or "")

    # 3. テキスト抽出
    text = root.text_content()

    # 4. 連続空行の正規化
    text = _MULTIPLE_NEWLINES.sub("\n\n", text)

    return text.strip()


def _remove_preserving_tail(elem) -> None:  # type: ignore[no-untyped-def]
    """要素を除去し、tail テキストを前の兄弟または親に移動する。

    Args:
        elem: 除去対象の lxml Element。
    """
    parent = elem.getparent()
    if parent is None:
        return
    tail = elem.tail or ""
    prev = elem.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or "") + tail
    else:
        parent.text = (parent.text or "") + tail
    parent.remove(elem)
