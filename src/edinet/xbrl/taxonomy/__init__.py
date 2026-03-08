"""XBRL タクソノミ参照ユーティリティ。

concept（例: ``jppfs_cor:NetSales``）から人間が読めるラベル
（例: 「売上高」）を解決する :class:`TaxonomyResolver` を提供する。
"""

from __future__ import annotations

import enum
import hashlib
import logging
import pickle
import re
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import platformdirs
from lxml import etree

from edinet._version import __version__
from edinet.exceptions import EdinetConfigError, EdinetParseError, EdinetWarning
from edinet.xbrl._linkbase_utils import (
    ROLE_LABEL,
    ROLE_TOTAL_LABEL,
    ROLE_VERBOSE_LABEL,
    split_fragment_prefix_local as _split_fragment_prefix_local,
)
from edinet.xbrl._namespaces import NS_LINK, NS_XLINK, NS_XML
from edinet.xbrl.taxonomy.concept_sets import (
    ConceptEntry,
    ConceptSet,
    ConceptSetRegistry,
    StatementCategory,
    classify_role_uri,
    derive_concept_sets,
    derive_concept_sets_from_trees,
    get_concept_set,
)

__all__ = [
    "LabelInfo",
    "LabelSource",
    "TaxonomyResolver",
    "ROLE_LABEL",
    "ROLE_VERBOSE",
    "ROLE_TOTAL",
    # concept_sets (Wave 2 Lane 1)
    "ConceptEntry",
    "ConceptSet",
    "ConceptSetRegistry",
    "StatementCategory",
    "classify_role_uri",
    "derive_concept_sets",
    "derive_concept_sets_from_trees",
    "get_concept_set",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 公開型・定数
# ---------------------------------------------------------------------------

# ラベル辞書のキー: (prefix, local_name, role, lang)
type _LabelKey = tuple[str, str, str, str]

# XSD ファイル名パターン: {prefix}_{YYYY-MM-DD}.xsd
# prefix は英数字・ハイフン・アンダースコアを含みうる。
# 貪欲マッチ (.+) + 末尾固定 ($) により、最後の _YYYY-MM-DD.xsd だけが
# 日付部分にマッチし、prefix 内の _ やハイフンを正しく保持する。
_XSD_PREFIX_RE = re.compile(r"(.+)_(\d{4}-\d{2}-\d{2})\.xsd$")

# EDINET タクソノミ namespace URI のバージョン日付部分を除去する正規表現。
# 例: ".../jpcrp/2024-11-01/jpcrp_cor" → ".../jpcrp/{version}/jpcrp_cor"
# これにより異バージョン間で同一の正規化キーを得る。
_NS_VERSION_RE = re.compile(r"/\d{4}-\d{2}-\d{2}/")


class LabelSource(enum.Enum):
    """ラベルの情報源。

    Attributes:
        STANDARD: EDINET 標準タクソノミ由来。
        FILER: 提出者別タクソノミ由来。
        FALLBACK: ラベルが見つからず local name を使用。
    """

    STANDARD = "standard"
    FILER = "filer"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class LabelInfo:
    """解決されたラベル情報。

    Attributes:
        text: ラベルテキスト（例: ``"売上高"``）。
        role: ラベルロール URI。
        lang: 言語コード（``"ja"`` / ``"en"``）。
        source: ラベルの情報源。
    """

    text: str
    role: str
    lang: str
    source: LabelSource


# 標準ラベルロール（後方互換エイリアス）
ROLE_VERBOSE = ROLE_VERBOSE_LABEL
ROLE_TOTAL = ROLE_TOTAL_LABEL


# ---------------------------------------------------------------------------
# TaxonomyResolver プロセス内キャッシュ
# ---------------------------------------------------------------------------

# 同一パスの TaxonomyResolver を使い回すためのキャッシュ。
# 標準ラベル辞書は不変なので、同一 taxonomy_path なら再利用できる。
# filer_labels はインスタンスごとに load/clear するので競合しない。
_resolver_cache: dict[Path, TaxonomyResolver] = {}


def get_taxonomy_resolver(
    taxonomy_path: str | Path,
    *,
    use_cache: bool = True,
) -> TaxonomyResolver:
    """プロセス内キャッシュ付きで TaxonomyResolver を取得する。

    同一 ``taxonomy_path`` に対して 2 回目以降はインスタンスを使い回す。
    ただし ``filer_labels`` はクリアして返す。

    Args:
        taxonomy_path: タクソノミのルートディレクトリパス。
        use_cache: pickle キャッシュを使用するか。

    Returns:
        TaxonomyResolver インスタンス。
    """
    path = Path(taxonomy_path).resolve()
    cached = _resolver_cache.get(path)
    if cached is not None and use_cache:
        cached.clear_filer_labels()
        return cached
    resolver = TaxonomyResolver(taxonomy_path, use_cache=use_cache)
    if use_cache:
        _resolver_cache[path.resolve()] = resolver
    return resolver


# ---------------------------------------------------------------------------
# TaxonomyResolver
# ---------------------------------------------------------------------------


class TaxonomyResolver:
    """EDINET タクソノミのラベル解決を行うクラス。

    標準タクソノミの ``_lab.xml`` / ``_lab-en.xml`` をパースし、
    concept → ラベルの辞書を構築する。初回パース結果は pickle で
    キャッシュされ、2 回目以降は高速に読み込まれる。

    Attributes:
        taxonomy_version: タクソノミバージョン（例: ``"ALL_20251101"``）。
        taxonomy_path: タクソノミのルートパス。

    Example:
        >>> resolver = TaxonomyResolver("/path/to/ALL_20251101")
        >>> label = resolver.resolve("jppfs_cor", "NetSales")
        >>> print(label.text)
        売上高
    """

    def __init__(
        self,
        taxonomy_path: str | Path,
        *,
        use_cache: bool = True,
    ) -> None:
        """TaxonomyResolver を初期化する。

        Args:
            taxonomy_path: タクソノミのルートディレクトリパス。
                ``ALL_20251101`` 等の最上位ディレクトリを指定する。
            use_cache: pickle キャッシュを使用するか。
                ``False`` の場合は毎回パースする（テスト用）。

        Raises:
            EdinetConfigError: taxonomy_path が存在しない場合。
        """
        path = Path(taxonomy_path)
        if not path.exists():
            msg = f"タクソノミパスが存在しません: {path}"
            raise EdinetConfigError(msg)
        taxonomy_dir = path / "taxonomy"
        if not taxonomy_dir.exists():
            msg = f"taxonomy ディレクトリが見つかりません: {taxonomy_dir}"
            raise EdinetConfigError(msg)

        self._taxonomy_path = path
        self._taxonomy_version = path.name

        self._standard_labels: dict[_LabelKey, str] = {}
        self._filer_labels: dict[_LabelKey, str] = {}
        self._ns_to_prefix: dict[str, str] = {}
        self._filer_ns_keys: set[str] = set()

        loaded = False
        if use_cache:
            cache_p = _cache_path(path, self._taxonomy_version)
            cached = _load_cache(cache_p)
            if cached is not None:
                if (
                    isinstance(cached, dict)
                    and "labels" in cached
                    and "ns_to_prefix" in cached
                ):
                    self._standard_labels = cached["labels"]
                    self._ns_to_prefix = cached["ns_to_prefix"]
                    loaded = True
                else:
                    logger.warning(
                        "キャッシュ形式が不正です。再構築します: %s",
                        cache_p,
                    )

        if not loaded:
            self._standard_labels, self._ns_to_prefix = _build_label_dict(
                taxonomy_dir,
            )
            if use_cache:
                _save_cache(
                    {
                        "labels": self._standard_labels,
                        "ns_to_prefix": self._ns_to_prefix,
                    },
                    _cache_path(path, self._taxonomy_version),
                )

        # バージョン違い namespace URI のフォールバック用逆引き辞書を構築する。
        # EDINET タクソノミの namespace URI にはバージョン日付
        # (例: 2024-11-01) が含まれるため、タクソノミパッケージと異なる
        # バージョンの XBRL インスタンスではラベルが FALLBACK になる。
        # 正規化キー（日付部分を除去）→ prefix のマッピングで吸収する。
        self._normalized_ns_to_prefix: dict[str, str] = {}
        for ns, prefix in self._ns_to_prefix.items():
            normalized = _NS_VERSION_RE.sub("//", ns)
            self._normalized_ns_to_prefix[normalized] = prefix

    @property
    def taxonomy_version(self) -> str:
        """タクソノミバージョン文字列（例: ``"ALL_20251101"``）。"""
        return self._taxonomy_version

    @property
    def taxonomy_path(self) -> Path:
        """タクソノミのルートパス。"""
        return self._taxonomy_path

    def resolve(
        self,
        prefix: str,
        local_name: str,
        *,
        role: str = ROLE_LABEL,
        lang: str = "ja",
    ) -> LabelInfo:
        """concept のラベルを解決する。

        Args:
            prefix: 名前空間プレフィックス（例: ``"jppfs_cor"``）。
            local_name: ローカル名（例: ``"NetSales"``）。
            role: ラベルロール URI。デフォルトは標準ラベル。
            lang: 言語コード。``"ja"`` または ``"en"``。

        Returns:
            解決された LabelInfo。ラベルが見つからない場合は
            指定 role → 標準ラベル → local name の順でフォールバック。

        Note:
            フォールバック時の LabelInfo は ``source=LabelSource.FALLBACK``、
            ``text=local_name`` となる。
        """
        key: _LabelKey = (prefix, local_name, role, lang)

        # 1. 提出者ラベル
        text = self._filer_labels.get(key)
        if text is not None:
            return LabelInfo(text=text, role=role, lang=lang, source=LabelSource.FILER)

        # 2. 標準ラベル
        text = self._standard_labels.get(key)
        if text is not None:
            return LabelInfo(
                text=text, role=role, lang=lang, source=LabelSource.STANDARD
            )

        # 3. role != 標準ラベルなら標準ラベル role でフォールバック（lang 引き継ぎ）
        if role != ROLE_LABEL:
            fallback_key: _LabelKey = (prefix, local_name, ROLE_LABEL, lang)
            text = self._filer_labels.get(fallback_key)
            if text is not None:
                return LabelInfo(
                    text=text,
                    role=ROLE_LABEL,
                    lang=lang,
                    source=LabelSource.FILER,
                )
            text = self._standard_labels.get(fallback_key)
            if text is not None:
                return LabelInfo(
                    text=text,
                    role=ROLE_LABEL,
                    lang=lang,
                    source=LabelSource.STANDARD,
                )

        # 4. FALLBACK
        return LabelInfo(
            text=local_name, role=role, lang=lang, source=LabelSource.FALLBACK
        )

    def resolve_clark(
        self,
        concept_qname: str,
        *,
        role: str = ROLE_LABEL,
        lang: str = "ja",
    ) -> LabelInfo:
        """Clark notation の concept QName からラベルを解決する。

        Args:
            concept_qname: Clark notation の QName
                （例: ``"{http://...jppfs_cor}NetSales"``）。
            role: ラベルロール URI。
            lang: 言語コード。

        Returns:
            解決された LabelInfo。
        """
        if not concept_qname.startswith("{") or "}" not in concept_qname:
            return LabelInfo(
                text=concept_qname,
                role=role,
                lang=lang,
                source=LabelSource.FALLBACK,
            )
        ns, local = concept_qname[1:].split("}", 1)
        prefix = self._ns_to_prefix.get(ns)
        if prefix is None:
            # バージョン違いフォールバック: namespace URI の日付部分を除去して再検索
            normalized = _NS_VERSION_RE.sub("//", ns)
            prefix = self._normalized_ns_to_prefix.get(normalized)
        if prefix is None:
            return LabelInfo(
                text=local, role=role, lang=lang, source=LabelSource.FALLBACK
            )
        return self.resolve(prefix, local, role=role, lang=lang)

    def load_filer_labels(
        self,
        lab_xml_bytes: bytes | None = None,
        lab_en_xml_bytes: bytes | None = None,
        *,
        xsd_bytes: bytes | None = None,
    ) -> int:
        """提出者別タクソノミのラベルを追加読み込みする。

        Args:
            lab_xml_bytes: 提出者の ``_lab.xml``（日本語）の bytes。
            lab_en_xml_bytes: 提出者の ``_lab-en.xml``（英語）の bytes。
            xsd_bytes: 提出者の ``.xsd`` の bytes。渡された場合、
                ``targetNamespace`` を抽出して ``_ns_to_prefix`` に
                追加する。

        Returns:
            追加されたラベル数。

        Warns:
            EdinetWarning: ``_filer_labels`` が空でない状態で呼ばれた場合。
        """
        if self._filer_labels:
            warnings.warn(
                "前回の filer ラベルがクリアされていません。"
                "clear_filer_labels() を先に呼んでください",
                EdinetWarning,
                stacklevel=2,
            )

        count_before = len(self._filer_labels)

        if lab_xml_bytes is not None:
            labels = _parse_lab_xml_bytes(lab_xml_bytes)
            self._filer_labels.update(labels)

        if lab_en_xml_bytes is not None:
            labels = _parse_lab_xml_bytes(lab_en_xml_bytes)
            self._filer_labels.update(labels)

        if xsd_bytes is not None:
            pair = _extract_ns_and_prefix(xsd_bytes)
            if pair is not None:
                ns, prefix = pair
                self._ns_to_prefix[ns] = prefix
                normalized = _NS_VERSION_RE.sub("//", ns)
                self._normalized_ns_to_prefix[normalized] = prefix
                self._filer_ns_keys.add(ns)
            else:
                warnings.warn(
                    "提出者 XSD bytes から targetNamespace/prefix を"
                    "抽出できませんでした。_ns_to_prefix への追加をスキップします",
                    EdinetWarning,
                    stacklevel=2,
                )

        added = len(self._filer_labels) - count_before
        logger.info("提出者ラベルを追加: %d 件", added)
        return added

    def clear_filer_labels(self) -> None:
        """提出者別ラベルをクリアし、提出者由来の ``_ns_to_prefix`` エントリも除去する。

        次の filing を処理する前に呼び出す。
        """
        self._filer_labels.clear()
        for ns_key in self._filer_ns_keys:
            self._ns_to_prefix.pop(ns_key, None)
            normalized = _NS_VERSION_RE.sub("//", ns_key)
            # 正規化辞書は標準タクソノミ由来のエントリが残っている可能性がある。
            # 提出者由来のもののみ除去するため、標準タクソノミ側の ns と
            # 一致しないことを確認する。
            if not any(
                _NS_VERSION_RE.sub("//", ns) == normalized
                for ns in self._ns_to_prefix
            ):
                self._normalized_ns_to_prefix.pop(normalized, None)
        self._filer_ns_keys.clear()

    def fork(self) -> TaxonomyResolver:
        """不変データを共有し可変データを独立コピーした新インスタンスを返す。

        大量の Filing を並列処理する際、``get_taxonomy_resolver()`` で
        取得した共有インスタンスに ``load_filer_labels()`` した後、
        ``fork()`` で Filing ごとの独立コピーを作成する。
        これにより次の filing の ``clear_filer_labels()`` が
        ``Statements._resolver`` のラベルを破壊しなくなる。

        Returns:
            ``_standard_labels`` を参照共有し、
            ``_filer_labels`` / ``_ns_to_prefix`` 等を独立コピーした
            新しい TaxonomyResolver。
        """
        forked = object.__new__(TaxonomyResolver)
        # 不変 → 参照共有
        forked._taxonomy_path = self._taxonomy_path
        forked._taxonomy_version = self._taxonomy_version
        forked._standard_labels = self._standard_labels
        # 可変 → 独立コピー
        forked._filer_labels = dict(self._filer_labels)
        forked._ns_to_prefix = dict(self._ns_to_prefix)
        forked._normalized_ns_to_prefix = dict(self._normalized_ns_to_prefix)
        forked._filer_ns_keys = set(self._filer_ns_keys)
        return forked


# ---------------------------------------------------------------------------
# 内部: _lab.xml パース
# ---------------------------------------------------------------------------


def _extract_prefix_and_local(href: str) -> tuple[str, str] | None:
    """xlink:href から (prefix, local_name) を抽出する。

    標準タクソノミの XSD ファイル名パターン ``{prefix}_{YYYY-MM-DD}.xsd``
    を優先し、マッチしない場合（提出者タクソノミ等）は fragment の
    ``_[A-Z]`` パターンで分割するフォールバックを使用する。

    Args:
        href: 例 ``"../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"``

    Returns:
        ``("jppfs_cor", "NetSales")`` または抽出失敗時 ``None``。
    """
    if "#" not in href:
        return None
    path_part, fragment = href.rsplit("#", 1)
    basename = path_part.rsplit("/", 1)[-1]

    # Strategy 1: 標準タクソノミパターン {prefix}_{YYYY-MM-DD}.xsd
    m = _XSD_PREFIX_RE.match(basename)
    if m is not None:
        prefix = m.group(1)
        expected_prefix = prefix + "_"
        if fragment.startswith(expected_prefix):
            local_name = fragment[len(expected_prefix):]
            return (prefix, local_name)

    # Strategy 2: 提出者タクソノミ等、ファイル名 prefix と fragment prefix が不一致
    # EDINET 慣例では fragment = {prefix}_{LocalName} で LocalName は大文字始まり
    return _split_fragment_prefix_local(fragment)


def _parse_lab_xml(
    lab_path: Path,
    *,
    xsd_collector: dict[str, tuple[Path, str]] | None = None,
) -> dict[_LabelKey, str]:
    """_lab.xml ファイルをパースしてラベル辞書を返す。

    Args:
        lab_path: _lab.xml ファイルのパス。
        xsd_collector: 指定された場合、loc の xlink:href から抽出した
            XSD basename → (xsd_path, prefix) のマッピングを追加する。

    Returns:
        ``(prefix, local_name, role, lang) → text`` の辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
    try:
        tree = etree.parse(str(lab_path))  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = f"_lab.xml の XML パースに失敗しました: {lab_path}"
        raise EdinetParseError(msg) from exc

    if xsd_collector is not None:
        _collect_xsd_refs(tree.getroot(), lab_path.parent, xsd_collector)

    result = _parse_lab_xml_tree(tree.getroot())
    logger.info("ラベルをロード: %s (%d 件)", lab_path.name, len(result))
    return result


def _parse_lab_xml_bytes(xml_bytes: bytes) -> dict[_LabelKey, str]:
    """_lab.xml の bytes をパースしてラベル辞書を返す。

    Args:
        xml_bytes: _lab.xml の bytes。

    Returns:
        ``(prefix, local_name, role, lang) → text`` の辞書。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
    try:
        root = etree.fromstring(xml_bytes)  # noqa: S320
    except etree.XMLSyntaxError as exc:
        msg = "_lab.xml bytes の XML パースに失敗しました"
        raise EdinetParseError(msg) from exc
    return _parse_lab_xml_tree(root)


def _parse_lab_xml_tree(root: etree._Element) -> dict[_LabelKey, str]:
    """パース済みの XML ルートからラベル辞書を構築する。

    Args:
        root: _lab.xml のルート要素。

    Returns:
        ``(prefix, local_name, role, lang) → text`` の辞書。
    """
    tag_loc = f"{{{NS_LINK}}}loc"
    tag_label = f"{{{NS_LINK}}}label"
    tag_label_arc = f"{{{NS_LINK}}}labelArc"
    attr_xlink_label = f"{{{NS_XLINK}}}label"
    attr_xlink_href = f"{{{NS_XLINK}}}href"
    attr_xlink_role = f"{{{NS_XLINK}}}role"
    attr_xlink_from = f"{{{NS_XLINK}}}from"
    attr_xlink_to = f"{{{NS_XLINK}}}to"
    attr_xml_lang = f"{{{NS_XML}}}lang"

    # Step 1: loc のキー → (prefix, local_name)
    loc_map: dict[str, tuple[str, str]] = {}
    for loc in root.iter(tag_loc):
        key = loc.get(attr_xlink_label)
        href = loc.get(attr_xlink_href)
        if key is None or href is None:
            continue
        result = _extract_prefix_and_local(href)
        if result is not None:
            loc_map[key] = result

    # Step 2: label のキー → (role, lang, text)
    label_map: dict[str, tuple[str, str, str]] = {}
    for label in root.iter(tag_label):
        key = label.get(attr_xlink_label)
        role = label.get(attr_xlink_role)
        lang = label.get(attr_xml_lang)
        text = label.text or ""
        if key and role and lang:
            label_map[key] = (role, lang, text.strip())

    # Step 3: labelArc で接続
    result: dict[_LabelKey, str] = {}
    for arc in root.iter(tag_label_arc):
        # prohibited/priority 検出
        if arc.get("use") == "prohibited" or arc.get("priority") is not None:
            warnings.warn(
                "labelArc に use='prohibited' または priority 属性が検出されました。"
                "v0.1.0 では arc override の完全処理は行いません",
                EdinetWarning,
                stacklevel=2,
            )
        from_key = arc.get(attr_xlink_from)
        to_key = arc.get(attr_xlink_to)
        if from_key in loc_map and to_key in label_map:
            prefix, local = loc_map[from_key]
            role, lang, text = label_map[to_key]
            result[(prefix, local, role, lang)] = text

    return result


# ---------------------------------------------------------------------------
# 内部: XSD targetNamespace 読み取り
# ---------------------------------------------------------------------------


def _read_target_namespace(xsd_path: Path) -> str | None:
    """XSD ファイルの targetNamespace 属性を読み取る。

    Args:
        xsd_path: XSD ファイルのパス。

    Returns:
        targetNamespace の値。取得できなければ None。
    """
    try:
        tree = etree.parse(str(xsd_path))  # noqa: S320
        return tree.getroot().get("targetNamespace")
    except (etree.Error, OSError):
        logger.debug("XSD の targetNamespace 読み取りに失敗: %s", xsd_path)
        return None


def _extract_ns_and_prefix(xsd_bytes: bytes) -> tuple[str, str] | None:
    """XSD bytes から (targetNamespace, prefix) を直接抽出する。

    XSD ルート要素の xmlns 宣言から、targetNamespace と一致する
    名前空間プレフィックスを探す。

    EDINET 仕様根拠:
        提出者別タクソノミ作成ガイドライン §4-5-2「名前空間プレフィックス
        の命名規約」で prefix の命名ルールが規定されており、提出者 XSD は
        必ず ``xmlns:{prefix}="{targetNamespace}"`` を宣言する。
        設定規約書 §2-2-7「不要な名前空間宣言は行わない」により、
        宣言の存在は仕様上保証される。
        サンプルインスタンス全 112 XSD で 100% 一致を確認済み。

    Args:
        xsd_bytes: XSD ファイルの bytes。

    Returns:
        ``(targetNamespace, prefix)`` のタプル。抽出失敗時は ``None``。
    """
    try:
        root = etree.fromstring(xsd_bytes)  # noqa: S320
    except etree.Error:
        return None
    target_ns = root.get("targetNamespace")
    if target_ns is None:
        return None
    for ns_prefix, uri in root.nsmap.items():
        if uri == target_ns and isinstance(ns_prefix, str):
            return (target_ns, ns_prefix)
    return None


# ---------------------------------------------------------------------------
# 内部: _ns_to_prefix 構築
# ---------------------------------------------------------------------------


def _collect_xsd_refs(
    root: etree._Element,
    lab_dir: Path,
    xsd_collector: dict[str, tuple[Path, str]],
) -> None:
    """_lab.xml のルートから loc の xlink:href を走査し XSD パスと prefix を収集する。

    Args:
        root: _lab.xml のルート要素。
        lab_dir: _lab.xml の親ディレクトリ。
        xsd_collector: 結果を格納する辞書
            (xsd_basename → (lab_dir, relative_path_part)) に prefix を付与。
    """
    tag_loc = f"{{{NS_LINK}}}loc"
    attr_xlink_href = f"{{{NS_XLINK}}}href"

    seen_basenames: set[str] = set()
    for loc in root.iter(tag_loc):
        href = loc.get(attr_xlink_href)
        if href is None or "#" not in href:
            continue
        path_part = href.rsplit("#", 1)[0]
        basename = path_part.rsplit("/", 1)[-1]
        if basename in seen_basenames:
            continue
        seen_basenames.add(basename)
        result = _extract_prefix_and_local(href)
        if result is None:
            continue
        prefix = result[0]
        # basename をキーにして重複を避ける（同じ XSD が複数の loc で参照される）
        if basename not in xsd_collector:
            xsd_collector[basename] = (lab_dir / path_part, prefix)


def _build_ns_to_prefix_from_xsd(
    xsd_info: dict[str, tuple[Path, str]],
) -> dict[str, str]:
    """XSD パスと prefix のマッピングから namespace → prefix 辞書を構築する。

    Args:
        xsd_info: ``{basename: (xsd_path, prefix)}`` の辞書。

    Returns:
        ``{namespace_uri: prefix}`` の辞書。
    """
    ns_to_prefix: dict[str, str] = {}
    for _basename, (xsd_path, prefix) in xsd_info.items():
        ns = _read_target_namespace(xsd_path)
        if ns is not None:
            ns_to_prefix[ns] = prefix
    return ns_to_prefix


# ---------------------------------------------------------------------------
# 内部: ラベル辞書構築
# ---------------------------------------------------------------------------


def _build_label_dict(
    taxonomy_dir: Path,
) -> tuple[dict[_LabelKey, str], dict[str, str]]:
    """taxonomy ディレクトリ配下の全 _lab.xml をパースしてラベル辞書を構築する。

    Args:
        taxonomy_dir: ``taxonomy/`` ディレクトリのパス。

    Returns:
        ``(labels, ns_to_prefix)`` のタプル。
    """
    t0 = time.perf_counter()

    # Glob: *_lab.xml は _lab-en.xml にマッチしない（末尾が _lab.xml で終わるもののみ）
    lab_paths = sorted(taxonomy_dir.glob("*/[0-9]*/label/*_lab.xml"))
    lab_en_paths = sorted(taxonomy_dir.glob("*/[0-9]*/label/*_lab-en.xml"))
    all_lab_paths = lab_paths + lab_en_paths

    if not all_lab_paths:
        logger.warning("_lab.xml が見つかりません: %s", taxonomy_dir)

    labels: dict[_LabelKey, str] = {}
    xsd_info: dict[str, tuple[Path, str]] = {}
    for p in all_lab_paths:
        parsed = _parse_lab_xml(p, xsd_collector=xsd_info)
        # sorted() により同一モジュールの複数バージョンは日付昇順で処理され、
        # 最新バージョンのラベルが後勝ちで採用される。
        # v0.2.0 taxonomy/versioning でバージョン別解決に移行する際は
        # この上書きを廃止し、バージョン修飾付きキーに変更すること。
        if logger.isEnabledFor(logging.DEBUG):
            overwritten = parsed.keys() & labels.keys()
            if overwritten:
                logger.debug(
                    "ラベルキー上書き: %d 件 (%s)", len(overwritten), p.name
                )
        labels.update(parsed)

    ns_to_prefix = _build_ns_to_prefix_from_xsd(xsd_info)

    elapsed = time.perf_counter() - t0
    logger.info(
        "タクソノミラベル辞書を構築しました (%d 件, %.3f秒)",
        len(labels),
        elapsed,
    )
    return labels, ns_to_prefix


# ---------------------------------------------------------------------------
# 内部: キャッシュ
# ---------------------------------------------------------------------------


def _cache_path(taxonomy_path: Path, taxonomy_version: str) -> Path:
    """キャッシュファイルのパスを構築する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        taxonomy_version: タクソノミバージョン文字列。

    Returns:
        キャッシュファイルの Path。
    """
    path_hash = hashlib.sha256(str(taxonomy_path).encode()).hexdigest()[:8]
    cache_dir = Path(platformdirs.user_cache_dir("edinet"))
    return (
        cache_dir
        / f"taxonomy_labels_v{__version__}_{taxonomy_version}_{path_hash}.pkl"
    )


def _load_cache(path: Path) -> dict | None:
    """pickle キャッシュを読み込む。失敗時は None。

    Args:
        path: キャッシュファイルのパス。

    Returns:
        キャッシュデータ辞書。失敗時は None。
    """
    if not path.exists():
        return None
    try:
        t0 = time.perf_counter()
        with path.open("rb") as f:
            data = pickle.load(f)  # noqa: S301
        elapsed = time.perf_counter() - t0
        logger.info(
            "タクソノミキャッシュを読み込みました (%.3f秒, %s)", elapsed, path
        )
        return data
    except Exception:
        warnings.warn(
            f"タクソノミキャッシュの読み込みに失敗しました。再構築します: {path}",
            EdinetWarning,
            stacklevel=2,
        )
        return None


def _save_cache(data: dict, path: Path) -> None:
    """pickle キャッシュを保存する。失敗時は警告して続行。

    Args:
        data: 保存するデータ辞書。
        path: キャッシュファイルのパス。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        with path.open("wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        elapsed = time.perf_counter() - t0
        logger.info(
            "タクソノミキャッシュを保存しました (%.3f秒, %s)", elapsed, path
        )
    except Exception:
        warnings.warn(
            f"タクソノミキャッシュの保存に失敗しました: {path}",
            EdinetWarning,
            stacklevel=2,
        )
