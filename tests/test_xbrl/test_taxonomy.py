"""TaxonomyResolver のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetConfigError, EdinetWarning
from edinet.xbrl.taxonomy import (
    ROLE_LABEL,
    ROLE_TOTAL,
    ROLE_VERBOSE,
    LabelSource,
    TaxonomyResolver,
    _extract_ns_and_prefix,
    _extract_prefix_and_local,
    _parse_lab_xml,
    _parse_lab_xml_bytes,
    _split_fragment_prefix_local,
)
from .conftest import TAXONOMY_MINI_DIR

# フィクスチャのパス
_FILER_DIR = TAXONOMY_MINI_DIR / "filer"
_JPPFS_NS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_FILER_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp030000-asr_X99001-000/2025-11-01/jpcrp030000-asr_X99001-000"


@pytest.fixture()
def resolver() -> TaxonomyResolver:
    """taxonomy_mini フィクスチャを使った TaxonomyResolver。"""
    return TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)


# =====================================================================
# P0: 必須テスト
# =====================================================================


class TestP0Init:
    """P0: 初期化テスト。"""

    def test_resolver_init_with_valid_path(self, resolver: TaxonomyResolver) -> None:
        """正常パスで初期化成功。taxonomy_version がディレクトリ名と一致する。"""
        assert resolver.taxonomy_version == "taxonomy_mini"
        assert resolver.taxonomy_path == TAXONOMY_MINI_DIR

    def test_resolver_init_raises_on_invalid_path(self) -> None:
        """存在しないパスで EdinetConfigError。"""
        with pytest.raises(EdinetConfigError):
            TaxonomyResolver("/nonexistent/path/to/taxonomy")


class TestP0Resolve:
    """P0: ラベル解決テスト。"""

    def test_resolve_japanese_standard_label(
        self, resolver: TaxonomyResolver
    ) -> None:
        """日本語標準ラベル "売上高" が返る。"""
        label = resolver.resolve("jppfs_cor", "NetSales")
        assert label.text == "売上高"
        assert label.role == ROLE_LABEL
        assert label.lang == "ja"
        assert label.source == LabelSource.STANDARD

    def test_resolve_english_standard_label(
        self, resolver: TaxonomyResolver
    ) -> None:
        """英語標準ラベル "Net sales" が返る。"""
        label = resolver.resolve("jppfs_cor", "NetSales", lang="en")
        assert label.text == "Net sales"
        assert label.role == ROLE_LABEL
        assert label.lang == "en"
        assert label.source == LabelSource.STANDARD

    def test_resolve_verbose_label(self, resolver: TaxonomyResolver) -> None:
        """ROLE_VERBOSE で冗長ラベルが返る。"""
        label = resolver.resolve("jppfs_cor", "Assets", role=ROLE_VERBOSE)
        assert label.text == "資産合計"
        assert label.role == ROLE_VERBOSE
        assert label.source == LabelSource.STANDARD

    def test_resolve_fallback_to_standard_role(
        self, resolver: TaxonomyResolver
    ) -> None:
        """存在しない role → 標準ラベルにフォールバック。"""
        label = resolver.resolve(
            "jppfs_cor",
            "NetSales",
            role="http://example.com/nonexistent/role",
        )
        assert label.text == "売上高"
        assert label.role == ROLE_LABEL
        assert label.source == LabelSource.STANDARD

    def test_resolve_fallback_to_local_name(
        self, resolver: TaxonomyResolver
    ) -> None:
        """存在しない concept → FALLBACK で local_name が返る。"""
        label = resolver.resolve("jppfs_cor", "UnknownConcept")
        assert label.text == "UnknownConcept"
        assert label.source == LabelSource.FALLBACK

    def test_resolve_clark_notation(self, resolver: TaxonomyResolver) -> None:
        """Clark notation からラベルを解決。_ns_to_prefix の構築を間接検証。"""
        label = resolver.resolve_clark(f"{{{_JPPFS_NS}}}NetSales")
        assert label.text == "売上高"
        assert label.source == LabelSource.STANDARD


class TestP0FilerLabels:
    """P0: 提出者ラベルテスト。"""

    def test_load_filer_labels(self, resolver: TaxonomyResolver) -> None:
        """提出者ラベルが追加され source=FILER で返る。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        lab_en_bytes = (_FILER_DIR / "filer_lab-en.xml").read_bytes()
        xsd_bytes = (_FILER_DIR / "filer.xsd").read_bytes()
        count = resolver.load_filer_labels(
            lab_bytes, lab_en_bytes, xsd_bytes=xsd_bytes
        )
        assert count > 0
        label = resolver.resolve(
            "jpcrp030000-asr_X99001-000", "CustomExpense"
        )
        assert label.text == "独自費用項目"
        assert label.source == LabelSource.FILER

    def test_filer_labels_take_priority(
        self, resolver: TaxonomyResolver
    ) -> None:
        """提出者ラベルが標準ラベルより優先される。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        resolver.load_filer_labels(lab_bytes)

        # 提出者が標準科目 NetSales を上書き
        label = resolver.resolve("jppfs_cor", "NetSales")
        assert label.text == "提出者カスタム売上高"
        assert label.source == LabelSource.FILER

    def test_clear_filer_labels(self, resolver: TaxonomyResolver) -> None:
        """clear_filer_labels() 後に提出者ラベルが消える。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        resolver.load_filer_labels(lab_bytes)

        # 確認: 提出者ラベルが存在する
        label = resolver.resolve(
            "jpcrp030000-asr_X99001-000", "CustomExpense"
        )
        assert label.source == LabelSource.FILER

        # クリア
        resolver.clear_filer_labels()

        # 提出者ラベルが消えて FALLBACK になる
        label = resolver.resolve(
            "jpcrp030000-asr_X99001-000", "CustomExpense"
        )
        assert label.source == LabelSource.FALLBACK


class TestP0Cache:
    """P0: キャッシュテスト。"""

    def test_cache_saves_and_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """キャッシュ保存・復元でラベルと _ns_to_prefix が一致する。"""
        import platformdirs

        monkeypatch.setattr(
            platformdirs, "user_cache_dir", lambda _app: str(tmp_path)
        )

        # キャッシュなし（正）
        r_no_cache = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)
        label_nc = r_no_cache.resolve("jppfs_cor", "NetSales")
        clark_nc = r_no_cache.resolve_clark(f"{{{_JPPFS_NS}}}NetSales")

        # 1 回目: パースしてキャッシュ保存
        r1 = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=True)
        label1 = r1.resolve("jppfs_cor", "NetSales")
        clark1 = r1.resolve_clark(f"{{{_JPPFS_NS}}}NetSales")

        # 2 回目: キャッシュから読み込み
        r2 = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=True)
        label2 = r2.resolve("jppfs_cor", "NetSales")
        clark2 = r2.resolve_clark(f"{{{_JPPFS_NS}}}NetSales")

        # キャッシュあり/なしで結果が同一
        assert label_nc == label1 == label2
        assert clark_nc == clark1 == clark2

    def test_cache_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """use_cache=False でキャッシュファイルが作成されない。"""
        import platformdirs

        monkeypatch.setattr(
            platformdirs, "user_cache_dir", lambda _app: str(tmp_path)
        )

        TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)

        # キャッシュファイルが存在しないことを確認
        cache_files = list(tmp_path.glob("*.pkl"))
        assert len(cache_files) == 0

    def test_cache_invalid_payload_rebuilds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """不正な形式のキャッシュファイルがあっても再構築して正常動作する。"""
        import pickle

        import platformdirs

        monkeypatch.setattr(
            platformdirs, "user_cache_dir", lambda _app: str(tmp_path)
        )

        # 正常なキャッシュを 1 回作成してファイルパスを特定
        r1 = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=True)
        cache_files = list(tmp_path.glob("*.pkl"))
        assert len(cache_files) == 1
        cache_file = cache_files[0]

        # キャッシュを不正なペイロードで上書き
        with cache_file.open("wb") as f:
            pickle.dump({"wrong_key": "bad_data"}, f)

        # 不正キャッシュでも KeyError にならず再構築される
        r2 = TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=True)
        label = r2.resolve("jppfs_cor", "NetSales")
        assert label.text == r1.resolve("jppfs_cor", "NetSales").text


class TestP0ClarkFiler:
    """P0: Clark notation + 提出者ラベルテスト。"""

    def test_resolve_clark_after_load_filer_labels(
        self, resolver: TaxonomyResolver
    ) -> None:
        """提出者ラベルロード後に Clark notation で FILER ラベルが返る。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        xsd_bytes = (_FILER_DIR / "filer.xsd").read_bytes()
        resolver.load_filer_labels(lab_bytes, xsd_bytes=xsd_bytes)

        label = resolver.resolve_clark(
            f"{{{_FILER_NS}}}CustomExpense"
        )
        assert label.text == "独自費用項目"
        assert label.source == LabelSource.FILER


class TestP0PrefixExtraction:
    """P0: prefix 抽出テスト。"""

    def test_prefix_extraction_with_hyphen(self) -> None:
        """ハイフン入り prefix が正しく抽出される。"""
        result = _extract_prefix_and_local(
            "../jpcrp030000-asr_X99001-000_2025-11-01.xsd"
            "#jpcrp030000-asr_X99001-000_SomeCustomItem"
        )
        assert result == ("jpcrp030000-asr_X99001-000", "SomeCustomItem")

    def test_prefix_extraction_standard(self) -> None:
        """標準的な prefix が正しく抽出される。"""
        result = _extract_prefix_and_local(
            "../jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"
        )
        assert result == ("jppfs_cor", "NetSales")

    def test_prefix_extraction_no_fragment(self) -> None:
        """# がない href は None を返す。"""
        result = _extract_prefix_and_local("../jppfs_cor_2025-11-01.xsd")
        assert result is None

    def test_prefix_extraction_submitter_xsd(self) -> None:
        """提出者 XSD ファイル名形式でも prefix が正しく抽出される。"""
        result = _extract_prefix_and_local(
            "jpcrp030000-asr-001_E02144-000_2025-03-31_01_2025-06-18.xsd"
            "#jpcrp030000-asr_E02144-000_CustomItem"
        )
        assert result == ("jpcrp030000-asr_E02144-000", "CustomItem")

    def test_split_fragment_prefix_local(self) -> None:
        """_split_fragment_prefix_local が正しく分割する。"""
        assert _split_fragment_prefix_local(
            "jpcrp030000-asr_E02144-000_CustomExpense"
        ) == ("jpcrp030000-asr_E02144-000", "CustomExpense")
        assert _split_fragment_prefix_local(
            "jppfs_cor_NetSales"
        ) == ("jppfs_cor", "NetSales")
        # 分割不能（大文字なし）
        assert _split_fragment_prefix_local("nouppercase") is None

    def test_split_fragment_underscore_in_local_name(self) -> None:
        """LocalName 内に _[A-Z] がある場合、最後の _[A-Z] で分割される。

        EDINET では PascalCase が仕様上強制されるため実害はないが、
        IFRS 拡張対応時に再検証が必要（ガイドライン §5-2-1-1 LC3 方式）。
        """
        # "Custom_SpecialExpense" → 最後の _S で分割される
        assert _split_fragment_prefix_local(
            "prefix_Custom_SpecialExpense"
        ) == ("prefix_Custom", "SpecialExpense")

    def test_extract_ns_and_prefix_from_xsd(self) -> None:
        """xmlns 宣言から (targetNamespace, prefix) を直接抽出する。"""
        xsd_bytes = (
            b'<xsd:schema'
            b' targetNamespace="http://example.com/ns/my_prefix/2025"'
            b' xmlns:my_prefix="http://example.com/ns/my_prefix/2025"'
            b' xmlns:xsd="http://www.w3.org/2001/XMLSchema"/>'
        )
        result = _extract_ns_and_prefix(xsd_bytes)
        assert result == ("http://example.com/ns/my_prefix/2025", "my_prefix")

    def test_extract_ns_and_prefix_no_xmlns_match(self) -> None:
        """targetNamespace に一致する xmlns がない場合は None。"""
        xsd_bytes = (
            b'<xsd:schema'
            b' targetNamespace="http://example.com/ns"'
            b' xmlns:xsd="http://www.w3.org/2001/XMLSchema"/>'
        )
        result = _extract_ns_and_prefix(xsd_bytes)
        assert result is None

    def test_extract_ns_and_prefix_malformed_xml(self) -> None:
        """不正な XML は None。"""
        assert _extract_ns_and_prefix(b"<not valid xml") is None

    def test_extract_ns_and_prefix_filer_fixture(self) -> None:
        """フィクスチャ filer.xsd から正しく抽出する。"""
        xsd_bytes = (_FILER_DIR / "filer.xsd").read_bytes()
        result = _extract_ns_and_prefix(xsd_bytes)
        assert result == (_FILER_NS, "jpcrp030000-asr_X99001-000")


# =====================================================================
# P1: 推奨テスト
# =====================================================================


class TestP1Additional:
    """P1: 追加テスト。"""

    def test_resolve_total_label(self, resolver: TaxonomyResolver) -> None:
        """ROLE_TOTAL で合計ラベルが返る。"""
        label = resolver.resolve("jppfs_cor", "Assets", role=ROLE_TOTAL)
        assert label.text == "資産合計"
        assert label.role == ROLE_TOTAL
        assert label.source == LabelSource.STANDARD

    def test_load_filer_returns_count(
        self, resolver: TaxonomyResolver
    ) -> None:
        """load_filer_labels() の返り値が追加ラベル数。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        count = resolver.load_filer_labels(lab_bytes)
        assert count == 3  # CustomExpense, CustomRevenue, OverrideNetSales

    def test_resolve_after_clear_and_reload(
        self, resolver: TaxonomyResolver
    ) -> None:
        """load → clear → reload のサイクルが正しく動作する。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()

        resolver.load_filer_labels(lab_bytes)
        assert (
            resolver.resolve(
                "jpcrp030000-asr_X99001-000", "CustomExpense"
            ).source
            == LabelSource.FILER
        )

        resolver.clear_filer_labels()
        assert (
            resolver.resolve(
                "jpcrp030000-asr_X99001-000", "CustomExpense"
            ).source
            == LabelSource.FALLBACK
        )

        # 再ロード
        resolver.load_filer_labels(lab_bytes)
        assert (
            resolver.resolve(
                "jpcrp030000-asr_X99001-000", "CustomExpense"
            ).source
            == LabelSource.FILER
        )

    def test_multiple_roles_same_concept(
        self, resolver: TaxonomyResolver
    ) -> None:
        """同一 concept に標準 + 冗長 + 合計ラベルが共存する。"""
        standard = resolver.resolve("jppfs_cor", "Assets", role=ROLE_LABEL)
        verbose = resolver.resolve("jppfs_cor", "Assets", role=ROLE_VERBOSE)
        total = resolver.resolve("jppfs_cor", "Assets", role=ROLE_TOTAL)

        assert standard.text == "資産"
        assert verbose.text == "資産合計"
        assert total.text == "資産合計"
        assert standard.role == ROLE_LABEL
        assert verbose.role == ROLE_VERBOSE
        assert total.role == ROLE_TOTAL

    def test_empty_lab_xml(self, resolver: TaxonomyResolver) -> None:
        """labelLink がない空の _lab.xml でもエラーにならない。"""
        empty_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"/>"""
        result = _parse_lab_xml_bytes(empty_xml)
        assert result == {}

    def test_parse_lab_xml_loc_arc_label_connection(self) -> None:
        """loc→arc→label 接続が正しく行われる。_2 サフィックスケースも含む。"""
        lab_path = (
            TAXONOMY_MINI_DIR
            / "taxonomy"
            / "jppfs"
            / "2025-11-01"
            / "label"
            / "jppfs_2025-11-01_lab.xml"
        )
        result = _parse_lab_xml(lab_path)

        # 標準ラベル
        assert result[("jppfs_cor", "NetSales", ROLE_LABEL, "ja")] == "売上高"
        # 冗長ラベル
        assert (
            result[("jppfs_cor", "Assets", ROLE_VERBOSE, "ja")] == "資産合計"
        )
        # _2 サフィックス loc 経由の totalLabel
        assert (
            result[("jppfs_cor", "Assets", ROLE_TOTAL, "ja")] == "資産合計"
        )

    def test_prohibited_arc_warns(self) -> None:
        """use='prohibited' の labelArc で EdinetWarning が発行される。"""
        xml_str = """\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
    <link:loc xlink:type="locator" xlink:label="Item1"
      xlink:href="test_2025-01-01.xsd#test_Item1"/>
    <link:label xlink:type="resource" xlink:label="label_Item1"
      xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="ja"
      xmlns:xml="http://www.w3.org/XML/1998/namespace">test</link:label>
    <link:labelArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label"
      xlink:from="Item1" xlink:to="label_Item1" use="prohibited"/>
  </link:labelLink>
</link:linkbase>"""
        with pytest.warns(EdinetWarning, match="prohibited"):
            _parse_lab_xml_bytes(xml_str.encode("utf-8"))

    def test_load_filer_labels_warns_without_clear(
        self, resolver: TaxonomyResolver
    ) -> None:
        """clear なしで 2 回 load_filer_labels() を呼ぶと EdinetWarning。"""
        lab_bytes = (_FILER_DIR / "filer_lab.xml").read_bytes()
        resolver.load_filer_labels(lab_bytes)

        with pytest.warns(EdinetWarning, match="クリアされていません"):
            resolver.load_filer_labels(lab_bytes)

    def test_resolve_clark_version_fallback(
        self, resolver: TaxonomyResolver
    ) -> None:
        """異バージョンの namespace URI でもラベルが解決されること。"""
        # taxonomy_mini は 2025-11-01 版だが、2023-11-01 版の namespace でも解決する
        old_ns = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"
        old_qname = f"{{{old_ns}}}NetSales"
        label = resolver.resolve_clark(old_qname, lang="ja")
        assert label.text == "売上高"
        assert label.source == LabelSource.STANDARD

    def test_resolve_clark_version_fallback_different_year(
        self, resolver: TaxonomyResolver
    ) -> None:
        """2024-11-01 版の namespace URI でもラベルが解決されること。"""
        ns_2024 = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2024-11-01/jppfs_cor"
        qname = f"{{{ns_2024}}}OperatingIncome"
        label = resolver.resolve_clark(qname, lang="ja")
        assert label.text == "営業利益"
        assert label.source == LabelSource.STANDARD
