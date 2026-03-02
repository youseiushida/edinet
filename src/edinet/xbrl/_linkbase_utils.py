"""リンクベースパーサー共通ユーティリティ。

Presentation / Calculation / Definition の各リンクベースパーサーが共用する
href → concept 名抽出ロジックとラベルロール定数を提供する。
"""

from __future__ import annotations

import re

# ============================================================
# ラベルロール URI 定数
# ============================================================

ROLE_LABEL = "http://www.xbrl.org/2003/role/label"
"""標準ラベル。"""

ROLE_TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"
"""合計ラベル。"""

ROLE_VERBOSE_LABEL = "http://www.xbrl.org/2003/role/verboseLabel"
"""冗長ラベル。"""

ROLE_TERSE_LABEL = "http://www.xbrl.org/2003/role/terseLabel"
"""簡潔ラベル。"""

ROLE_PERIOD_START_LABEL = "http://www.xbrl.org/2003/role/periodStartLabel"
"""期首ラベル。"""

ROLE_PERIOD_END_LABEL = "http://www.xbrl.org/2003/role/periodEndLabel"
"""期末ラベル。"""

ROLE_NEGATED_LABEL = "http://www.xbrl.org/2003/role/negatedLabel"
"""符号反転ラベル。"""

# ============================================================
# href → concept 名抽出
# ============================================================

_XSD_PREFIX_RE = re.compile(r"^(.+)_\d{4}-\d{2}-\d{2}\.xsd$")
"""標準タクソノミの XSD ファイル名パターン（greedy マッチ）。"""


def extract_concept_from_href(href: str) -> str | None:
    """xlink:href のフラグメントから concept ローカル名を抽出する。

    2 段階の戦略で prefix を除去する:

    1. XSD ファイル名ベース: ``{prefix}_{YYYY-MM-DD}.xsd`` から prefix を推定し、
       フラグメント先頭の ``{prefix}_`` を除去する（標準タクソノミで有効）。
    2. ``_[A-Z]`` 後方スキャン: フラグメント末尾から逆走査し、
       最後の ``_[A-Z]`` 位置で分割する（提出者タクソノミで有効）。
    3. フォールバック: フラグメント全体を返す。

    Args:
        href: xlink:href 属性値。

    Returns:
        concept ローカル名。フラグメントが見つからない、または空の場合は ``None``。
    """
    if "#" not in href:
        return None
    path_part, fragment = href.rsplit("#", 1)
    if not fragment:
        return None
    basename = path_part.rsplit("/", 1)[-1]

    # Strategy 1: 標準タクソノミ {prefix}_{YYYY-MM-DD}.xsd
    m = _XSD_PREFIX_RE.match(basename)
    if m is not None:
        prefix = m.group(1)
        expected = prefix + "_"
        if fragment.startswith(expected):
            return fragment[len(expected):]

    # Strategy 2: _[A-Z] 後方スキャン（末尾から逆走査し最後の _[A-Z] で分割）
    for i in range(len(fragment) - 1, 0, -1):
        if (
            fragment[i - 1] == "_"
            and fragment[i].isascii()
            and fragment[i].isupper()
        ):
            return fragment[i:]

    # フォールバック: フラグメント全体を返す
    return fragment


# ============================================================
# fragment → (prefix, local_name) 分離
# ============================================================


def split_fragment_prefix_local(fragment: str) -> tuple[str, str] | None:
    """fragment 文字列から (prefix, local_name) を分離する。

    EDINET の命名慣例では LocalName は大文字始まりの PascalCase
    （ガイドライン §5-2-1-1 の LC3 方式）。
    fragment 末尾から逆走査し、最後の ``_[A-Z]`` 位置で分割する。

    Note:
        LocalName 内にアンダースコア + 大文字が含まれるケース
        （例: ``Custom_SpecialExpense``）では誤分割が発生しうるが、
        EDINET では PascalCase が仕様上強制されるため実害はない。
        IFRS 拡張対応時に再検証が必要。

    Args:
        fragment: 例 ``"jpcrp030000-asr_E02144-000_CustomExpense"``

    Returns:
        ``("jpcrp030000-asr_E02144-000", "CustomExpense")``
        または分割できない場合 ``None``。
    """
    for i in range(len(fragment) - 1, 0, -1):
        if (
            fragment[i - 1] == "_"
            and fragment[i].isascii()
            and fragment[i].isupper()
        ):
            return (fragment[: i - 1], fragment[i:])
    return None
