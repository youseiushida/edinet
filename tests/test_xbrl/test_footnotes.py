"""脚注リンクパーサーのテスト。

デトロイト派: 公開 API ``parse_footnote_links`` のみテスト。
内部実装（``_parse_single_link`` 等）はテストしない。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.linkbase.footnotes import FootnoteMap, Footnote, parse_footnote_links
from edinet.xbrl.parser import RawFootnoteLink

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "footnotes"


def _load(name: str) -> str:
    """フィクスチャ XML を文字列として読み込む。"""
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


def _raw(
    name: str,
    role: str | None = "http://www.xbrl.org/2003/role/link",
) -> RawFootnoteLink:
    """フィクスチャから RawFootnoteLink を構築する。"""
    return RawFootnoteLink(role=role, source_line=None, xml=_load(name))


# ========== インライン XML（エッジケース用） ==========

_NON_FACT_FOOTNOTE_ARCROLE_XML = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="#IdFact999" xlink:label="loc_x"/>
  <link:footnote xlink:type="resource" xlink:label="fn_x"
      xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber"
      xml:lang="ja">※1 テスト</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-explanatoryFact"
      xlink:from="loc_x" xlink:to="fn_x"/>
</link:footnoteLink>
"""

_MISSING_ROLE_XML = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="#IdFact888" xlink:label="loc_m"/>
  <link:footnote xlink:type="resource" xlink:label="fn_m"
      xml:lang="ja">※1 role なし</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="loc_m" xlink:to="fn_m"/>
</link:footnoteLink>
"""

_EMPTY_ROLE_XML = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="#IdFact777" xlink:label="loc_e"/>
  <link:footnote xlink:type="resource" xlink:label="fn_e"
      xlink:role=""
      xml:lang="ja">※1 空role</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="loc_e" xlink:to="fn_e"/>
</link:footnoteLink>
"""

_HREF_ONLY_HASH_XML = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="#" xlink:label="loc_h"/>
  <link:footnote xlink:type="resource" xlink:label="fn_h"
      xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber"
      xml:lang="ja">※1</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="loc_h" xlink:to="fn_h"/>
</link:footnoteLink>
"""

_HREF_NO_HASH_XML = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="IdFact666" xlink:label="loc_nh"/>
  <link:footnote xlink:type="resource" xlink:label="fn_nh"
      xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber"
      xml:lang="ja">※1</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="loc_nh" xlink:to="fn_nh"/>
</link:footnoteLink>
"""


def _inline_raw(xml: str) -> RawFootnoteLink:
    """インライン XML から RawFootnoteLink を構築する。"""
    return RawFootnoteLink(
        role="http://www.xbrl.org/2003/role/link",
        source_line=None,
        xml=xml,
    )


# ========== TestParseFootnoteLinks ==========


class TestParseFootnoteLinks:
    """parse_footnote_links() のテスト。"""

    def test_parse_single_footnote(self) -> None:
        """1 Fact : 1 脚注の基本パースが正しく動作する。"""
        fm = parse_footnote_links([_raw("simple.xml")])

        assert len(fm) == 1
        notes = fm.get("IdFact001")
        assert len(notes) == 1
        assert notes[0].text == "※1 減損損失の認識について"
        assert notes[0].lang == "ja"

    def test_parse_multiple_facts(self) -> None:
        """複数 Fact への脚注がそれぞれ正しく紐付けられる。"""
        fm = parse_footnote_links([_raw("multiple_facts.xml")])

        assert len(fm) == 3
        assert fm.get("IdFact100")[0].text == "※1 棚卸資産の評価"
        assert fm.get("IdFact200")[0].text == "※2 減価償却方法の変更"
        assert fm.get("IdFact300")[0].text == "※3 担保資産"

    def test_parse_multi_footnotes_per_fact(self) -> None:
        """1 つの Fact に複数の脚注（※1, ※2）が紐付けられる。"""
        fm = parse_footnote_links([_raw("multi_footnotes_per_fact.xml")])

        assert len(fm) == 1
        notes = fm.get("IdFact500")
        assert len(notes) == 2
        texts = {n.text for n in notes}
        assert "※1 有形固定資産の減損" in texts
        assert "※2 前期末における再評価" in texts

    def test_parse_shared_footnote(self) -> None:
        """N 個の loc が同一 label を共有 → 1 arc → 1 footnote。

        全 Fact ID から同じ脚注が取得できる。
        """
        fm = parse_footnote_links([_raw("shared_footnote.xml")])

        assert len(fm) == 3
        for fid in ("IdFactAAA", "IdFactBBB", "IdFactCCC"):
            notes = fm.get(fid)
            assert len(notes) == 1
            assert notes[0].text == "※1"

    def test_parse_multiple_footnote_links(self) -> None:
        """複数の footnoteLink 要素の脚注が統合される。"""
        raw1 = _raw(
            "multiple_links.xml",
            role="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet",
        )
        raw2 = _raw(
            "multiple_links_2.xml",
            role="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome",
        )
        fm = parse_footnote_links([raw1, raw2])

        # BS1, Both(BS), PL1, Both(PL) の 3 ユニーク Fact
        assert "IdFactBS1" in fm
        assert "IdFactPL1" in fm
        assert "IdFactBoth" in fm

    def test_parse_empty_sequence(self) -> None:
        """空のシーケンスで空の FootnoteMap が返る。"""
        fm = parse_footnote_links([])

        assert len(fm) == 0
        assert fm.all_footnotes() == ()
        assert fm.fact_ids == ()

    def test_parse_empty_footnote_link(self) -> None:
        """子要素のない footnoteLink で空の FootnoteMap が返る。"""
        fm = parse_footnote_links([_raw("empty.xml")])

        assert len(fm) == 0
        assert fm.all_footnotes() == ()

    def test_parse_no_arcs(self) -> None:
        """arc がない footnoteLink では _index は空だが、all_footnotes() には脚注が含まれる。"""
        fm = parse_footnote_links([_raw("no_arcs.xml")])

        assert len(fm) == 0
        assert not fm.has_footnotes("IdFactOrphan")
        all_fn = fm.all_footnotes()
        assert len(all_fn) == 1
        assert all_fn[0].text == "※1 紐付けなし脚注"

    def test_footnote_text_extracted(self) -> None:
        """脚注テキストが正しく抽出される。"""
        fm = parse_footnote_links([_raw("simple.xml")])
        notes = fm.get("IdFact001")
        assert notes[0].text == "※1 減損損失の認識について"

    def test_footnote_lang(self) -> None:
        """xml:lang 属性が正しく取得される。"""
        fm = parse_footnote_links([_raw("simple.xml")])
        assert fm.get("IdFact001")[0].lang == "ja"

    def test_footnote_role(self) -> None:
        """xlink:role 属性が正しく取得される。"""
        fm = parse_footnote_links([_raw("simple.xml")])
        expected_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber"
        assert fm.get("IdFact001")[0].role == expected_role

    def test_href_fragment_parsing(self) -> None:
        """#IdFact001 形式の href から Fact ID が正しく抽出される。"""
        fm = parse_footnote_links([_raw("simple.xml")])
        assert fm.has_footnotes("IdFact001")
        # "#" 付きでは見つからない
        assert not fm.has_footnotes("#IdFact001")

    def test_ignore_non_fact_footnote_arcrole(self) -> None:
        """fact-footnote 以外の arcrole は無視される。"""
        fm = parse_footnote_links([_inline_raw(_NON_FACT_FOOTNOTE_ARCROLE_XML)])

        # arc が無視されるため index は空
        assert len(fm) == 0
        # footnote 自体は all_footnotes に含まれる
        assert len(fm.all_footnotes()) == 1

    def test_malformed_xml_raises_parse_error(self) -> None:
        """不正な XML で EdinetParseError が発生する。"""
        with pytest.raises(EdinetParseError, match="XML パースに失敗"):
            parse_footnote_links([_raw("malformed.xml")])

    def test_missing_footnote_role_warns(self) -> None:
        """footnote に xlink:role が欠落している場合に EdinetWarning が発生しスキップされる。"""
        with pytest.warns(EdinetWarning, match="xlink:role が未設定"):
            fm = parse_footnote_links([_inline_raw(_MISSING_ROLE_XML)])

        # role なし footnote はスキップされるので arc 解決も失敗
        assert len(fm) == 0

    def test_empty_footnote_role_warns(self) -> None:
        """footnote の xlink:role が空文字列の場合に EdinetWarning が発生しスキップされる。"""
        with pytest.warns(EdinetWarning, match="xlink:role が未設定"):
            fm = parse_footnote_links([_inline_raw(_EMPTY_ROLE_XML)])

        assert len(fm) == 0

    def test_href_fragment_only_hash(self) -> None:
        """xlink:href が '#' のみの場合に EdinetWarning が発生し無視される。"""
        with pytest.warns(EdinetWarning, match="Fact ID が空"):
            fm = parse_footnote_links([_inline_raw(_HREF_ONLY_HASH_XML)])

        assert len(fm) == 0

    def test_href_no_hash_warns(self) -> None:
        """xlink:href が '#' で始まらない場合に EdinetWarning が発生し無視される。"""
        with pytest.warns(EdinetWarning, match="フラグメント形式ではありません"):
            fm = parse_footnote_links([_inline_raw(_HREF_NO_HASH_XML)])

        assert len(fm) == 0

    def test_footnote_text_with_html_tags(self) -> None:
        """脚注テキストに HTML タグが含まれる場合に itertext() で全テキストが抽出される。"""
        fm = parse_footnote_links([_raw("html_in_text.xml")])

        notes = fm.get("IdFactHTML")
        assert len(notes) == 1
        # itertext() は全テキストノードを結合
        assert "※1" in notes[0].text
        assert "重要な" in notes[0].text
        assert "注記" in notes[0].text
        assert "追加情報あり" in notes[0].text

    def test_same_fact_across_multiple_links(self) -> None:
        """同一 Fact ID が複数の footnoteLink にまたがって紐付けられた場合に脚注がマージされる。"""
        raw1 = _raw("multiple_links.xml")
        raw2 = _raw("multiple_links_2.xml")
        fm = parse_footnote_links([raw1, raw2])

        # IdFactBoth は両方のリンクで参照される
        notes = fm.get("IdFactBoth")
        assert len(notes) == 2
        texts = {n.text for n in notes}
        assert "※1 BS脚注" in texts
        assert "※2 PL脚注" in texts


# ========== TestFootnoteMap ==========


class TestFootnoteMap:
    """FootnoteMap のデータ構造テスト。"""

    @pytest.fixture()
    def sample_map(self) -> FootnoteMap:
        """テスト用の FootnoteMap を直接構築する。"""
        fn1 = Footnote(
            label="fn_1",
            text="※1 テスト脚注",
            lang="ja",
            role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber",
        )
        fn2 = Footnote(
            label="fn_2",
            text="※2 別の脚注",
            lang="ja",
            role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber",
        )
        return FootnoteMap(
            _index={
                "FactA": (fn1,),
                "FactB": (fn1, fn2),
            },
            _all=(fn1, fn2),
        )

    def test_get_existing(self, sample_map: FootnoteMap) -> None:
        """存在する Fact ID で Footnote タプルが取得できる。"""
        notes = sample_map.get("FactA")
        assert len(notes) == 1
        assert notes[0].text == "※1 テスト脚注"

    def test_get_nonexistent(self, sample_map: FootnoteMap) -> None:
        """存在しない Fact ID で空タプルが返る。"""
        assert sample_map.get("NonExistent") == ()

    def test_has_footnotes_true(self, sample_map: FootnoteMap) -> None:
        """脚注がある Fact ID で True が返る。"""
        assert sample_map.has_footnotes("FactA")

    def test_has_footnotes_false(self, sample_map: FootnoteMap) -> None:
        """脚注がない Fact ID で False が返る。"""
        assert not sample_map.has_footnotes("NonExistent")

    def test_all_footnotes(self, sample_map: FootnoteMap) -> None:
        """全脚注が取得できる。"""
        all_fn = sample_map.all_footnotes()
        assert len(all_fn) == 2

    def test_all_footnotes_deduplication(self) -> None:
        """all_footnotes() が重複を除去する（frozen dataclass の __eq__ で判定）。"""
        fn = Footnote(label="fn", text="※1", lang="ja", role="role")
        # parse_footnote_links 経由で作られる _all は重複除去済み
        fm = FootnoteMap(_index={}, _all=(fn, fn))
        # 直接構築では重複除去されない（parse_footnote_links が除去する）
        # ここでは parse_footnote_links の動作を検証
        # → no_arcs.xml で footnote が 1 つだけ含まれることで間接的に検証済み
        assert len(fm.all_footnotes()) == 2  # 直接構築なのでそのまま

        # parse_footnote_links 経由の重複除去を検証
        raw_xml = """\
<link:footnoteLink xmlns:link="http://www.xbrl.org/2003/linkbase"
                   xmlns:xlink="http://www.w3.org/1999/xlink"
                   xlink:type="extended"
                   xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="#IdFact1" xlink:label="loc1"/>
  <link:footnote xlink:type="resource" xlink:label="fn_dup"
      xlink:role="http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber"
      xml:lang="ja">※1</link:footnote>
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="loc1" xlink:to="fn_dup"/>
</link:footnoteLink>
"""
        # 同一 XML を 2 回渡す → 同一 Footnote が 2 回収集 → 重複除去で 1 つ
        raw = RawFootnoteLink(role=None, source_line=None, xml=raw_xml)
        fm2 = parse_footnote_links([raw, raw])
        assert len(fm2.all_footnotes()) == 1

    def test_fact_ids(self, sample_map: FootnoteMap) -> None:
        """脚注が紐付けられた Fact ID の一覧が取得できる。"""
        ids = sample_map.fact_ids
        assert set(ids) == {"FactA", "FactB"}

    def test_len(self, sample_map: FootnoteMap) -> None:
        """__len__ が脚注付き Fact 数を返す。"""
        assert len(sample_map) == 2

    def test_contains(self, sample_map: FootnoteMap) -> None:
        """__contains__ が正しく動作する。"""
        assert "FactA" in sample_map
        assert "FactB" in sample_map
        assert "NonExistent" not in sample_map
