"""XBRL 関連の名前空間定数と名前空間分類機能。

parser.py / contexts.py / taxonomy.py で共用する定数に加え、
名前空間 URI を解析して標準タクソノミ vs 提出者別タクソノミを判別する
分類機能を提供する。
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from functools import lru_cache

# ============================================================
# 既存定数（変更厳禁 — parser.py / contexts.py / taxonomy で使用中）
# ============================================================

# XBRL Instance
NS_XBRLI = "http://www.xbrl.org/2003/instance"
# XBRL Dimensions
NS_XBRLDI = "http://xbrl.org/2006/xbrldi"
# XBRL Linkbase
NS_LINK = "http://www.xbrl.org/2003/linkbase"
# XLink
NS_XLINK = "http://www.w3.org/1999/xlink"
# XML Schema Instance
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
# XML (xml:lang 等の属性用)
NS_XML = "http://www.w3.org/XML/1998/namespace"

# ============================================================
# 追加定数: XBRL 標準名前空間
# ============================================================

# ISO 4217 通貨コード
NS_ISO4217 = "http://www.xbrl.org/2003/iso4217"
# XBRL Dimensions Taxonomy
NS_XBRLDT = "http://xbrl.org/2005/xbrldt"
# XBRL 数値型（DTR: Data Type Registry）
NS_NUM = "http://www.xbrl.org/dtr/type/numeric"
# XBRL 非数値型（DTR: Data Type Registry）
NS_NONNUM = "http://www.xbrl.org/dtr/type/non-numeric"
# UTR (Unit Type Registry)
NS_UTR = "http://www.xbrl.org/2009/utr"

# ============================================================
# 追加定数: EDINET URI ベースパス
# ============================================================

EDINET_BASE = "http://disclosure.edinet-fsa.go.jp/"
"""EDINET の名前空間 URI のベースドメイン。

標準タクソノミ・提出者別タクソノミの両方がこのプレフィックスで始まる。
"""

EDINET_TAXONOMY_BASE = "http://disclosure.edinet-fsa.go.jp/taxonomy/"
"""EDINET 標準タクソノミの名前空間 URI はこのプレフィックスで始まる。"""

# ============================================================
# 内部定数
# ============================================================

_XBRL_INFRASTRUCTURE_URIS: frozenset[str] = frozenset({
    NS_XBRLI,
    NS_XBRLDI,
    NS_LINK,
    NS_XLINK,
    NS_XBRLDT,
})
"""XBRL インフラストラクチャに分類される名前空間 URI のセット。"""

# ============================================================
# Enum / Dataclass
# ============================================================


class NamespaceCategory(enum.Enum):
    """名前空間の分類カテゴリ。"""

    STANDARD_TAXONOMY = "standard_taxonomy"
    """EDINET 標準タクソノミ（jppfs_cor, jpcrp_cor, jpdei_cor, jpigp_cor 等）。"""

    FILER_TAXONOMY = "filer_taxonomy"
    """提出者別タクソノミ（企業固有の拡張科目）。"""

    XBRL_INFRASTRUCTURE = "xbrl_infrastructure"
    """XBRL 標準の基盤名前空間（xbrli, xlink, link, xbrldi 等）。"""

    OTHER = "other"
    """上記に該当しない名前空間（iso4217、XML Schema 等を含む）。"""


@dataclass(frozen=True, slots=True)
class NamespaceInfo:
    """名前空間 URI の解析結果。

    Attributes:
        uri: 元の名前空間 URI。
        category: 分類カテゴリ。
        is_standard: EDINET 標準タクソノミであれば True。
            STANDARD_TAXONOMY の場合のみ True。XBRL_INFRASTRUCTURE は False。
        module_name: タクソノミモジュール名（例: "jppfs_cor"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        module_group: タクソノミモジュールグループ（例: "jppfs"）。
            STANDARD_TAXONOMY かつ正規表現マッチ時のみ値を持つ。
            後続レーン（standards/detect 等）での会計基準分岐に使用。
        taxonomy_version: タクソノミバージョン日付（例: "2025-11-01"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        edinet_code: EDINET コード（例: "E02144"）。
            FILER_TAXONOMY の場合のみ値を持つ。
    """

    uri: str
    category: NamespaceCategory
    is_standard: bool
    module_name: str | None = None
    module_group: str | None = None
    taxonomy_version: str | None = None
    edinet_code: str | None = None


# ============================================================
# 正規表現パターン
# ============================================================

_STANDARD_TAXONOMY_PATTERN = re.compile(
    r"^http://disclosure\.edinet-fsa\.go\.jp/taxonomy/"
    r"(?P<module_group>[a-z]+)/"
    r"(?P<version>\d{4}-\d{2}-\d{2})/"
    r"(?P<module_name>[a-z_]+)$"
)
"""標準タクソノミ URI のパターン。

例: http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor
→ module_group="jppfs", version="2025-11-01", module_name="jppfs_cor"
"""

_FILER_TAXONOMY_PATTERN = re.compile(
    r"^http://disclosure\.edinet-fsa\.go\.jp/"
    r"(?!taxonomy/)"  # /taxonomy/ を含まない
    r"[^/]+/[^/]+/[^/]+/"
    r"(?P<edinet_code>[A-Z0-9]+)-(?P<branch>\d+)/"
)
"""提出者別タクソノミ URI のパターン。

例: http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E02144-000/2025-03-31/01/2025-06-18
→ edinet_code="E02144", branch="000"
"""


# ============================================================
# 分類関数
# ============================================================


@lru_cache(maxsize=256)
def classify_namespace(uri: str) -> NamespaceInfo:
    """名前空間 URI を解析し、分類結果を返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        解析結果の NamespaceInfo。
    """
    # 1. 標準タクソノミ（正規表現マッチ）
    m = _STANDARD_TAXONOMY_PATTERN.match(uri)
    if m:
        return NamespaceInfo(
            uri=uri,
            category=NamespaceCategory.STANDARD_TAXONOMY,
            is_standard=True,
            module_name=m.group("module_name"),
            module_group=m.group("module_group"),
            taxonomy_version=m.group("version"),
        )

    # 1b. 標準タクソノミ（フォールバック: EDINET_TAXONOMY_BASE で始まるが正規表現不一致）
    if uri.startswith(EDINET_TAXONOMY_BASE):
        return NamespaceInfo(
            uri=uri,
            category=NamespaceCategory.STANDARD_TAXONOMY,
            is_standard=True,
        )

    # 2. 提出者別タクソノミ（EDINET_BASE で始まり EDINET_TAXONOMY_BASE で始まらない）
    if uri.startswith(EDINET_BASE):
        m_filer = _FILER_TAXONOMY_PATTERN.match(uri)
        edinet_code = m_filer.group("edinet_code") if m_filer else None
        return NamespaceInfo(
            uri=uri,
            category=NamespaceCategory.FILER_TAXONOMY,
            is_standard=False,
            edinet_code=edinet_code,
        )

    # 3. XBRL インフラ名前空間
    if uri in _XBRL_INFRASTRUCTURE_URIS:
        return NamespaceInfo(
            uri=uri,
            category=NamespaceCategory.XBRL_INFRASTRUCTURE,
            is_standard=False,
        )

    # 4. その他
    return NamespaceInfo(
        uri=uri,
        category=NamespaceCategory.OTHER,
        is_standard=False,
    )


# ============================================================
# 便利関数（すべて classify_namespace に委譲しキャッシュの恩恵を受ける）
# ============================================================


def is_standard_taxonomy(uri: str) -> bool:
    """名前空間 URI が EDINET 標準タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        標準タクソノミであれば True。
    """
    return classify_namespace(uri).is_standard


def is_filer_namespace(uri: str) -> bool:
    """名前空間 URI が提出者別タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        提出者別タクソノミであれば True。
    """
    return classify_namespace(uri).category == NamespaceCategory.FILER_TAXONOMY


def extract_taxonomy_module(uri: str) -> str | None:
    """名前空間 URI からタクソノミモジュール名を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        モジュール名（例: "jppfs_cor"）。標準タクソノミでない場合 None。
    """
    return classify_namespace(uri).module_name


def extract_taxonomy_version(uri: str) -> str | None:
    """名前空間 URI からタクソノミバージョン日付を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        バージョン日付（例: "2025-11-01"）。標準タクソノミでない場合 None。
    """
    return classify_namespace(uri).taxonomy_version
