"""Definition Linkbase パーサーのテスト。

デトロイト派: 公開 API ``parse_definition_linkbase`` のみテスト。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.linkbase.definition import parse_definition_linkbase

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "linkbase_definition"


def _load(name: str) -> bytes:
    """フィクスチャファイルを読み込む。"""
    return (FIXTURE_DIR / name).read_bytes()


# ---------- 基本パース ----------


@pytest.mark.unit
class TestBasicParse:
    """基本的なパース機能のテスト。"""

    def test_arcrole_extraction(self) -> None:
        """simple_bs.xml: 全 arcrole タイプの arc が正しく抽出される。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        assert len(trees) == 1
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        tree = trees[role_uri]

        arcroles = {a.arcrole for a in tree.arcs}
        assert "http://xbrl.org/int/dim/arcrole/all" in arcroles
        assert "http://xbrl.org/int/dim/arcrole/hypercube-dimension" in arcroles
        assert "http://xbrl.org/int/dim/arcrole/dimension-domain" in arcroles
        assert "http://xbrl.org/int/dim/arcrole/dimension-default" in arcroles
        assert "http://xbrl.org/int/dim/arcrole/domain-member" in arcroles

    def test_loc_resolution(self) -> None:
        """simple_bs.xml: concept ローカル名と href が正しく格納される。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        tree = trees[role_uri]

        # all arc: Heading -> Table
        all_arcs = [
            a for a in tree.arcs if a.arcrole == "http://xbrl.org/int/dim/arcrole/all"
        ]
        assert len(all_arcs) == 1
        arc = all_arcs[0]
        assert arc.from_concept == "ConsolidatedBalanceSheetHeading"
        assert arc.to_concept == "BalanceSheetTable"
        assert "jppfs_cor_ConsolidatedBalanceSheetHeading" in arc.from_href
        assert "jppfs_cor_BalanceSheetTable" in arc.to_href

    def test_duplicate_loc_suffix(self) -> None:
        """duplicate_loc.xml: _2 サフィックスが同一 concept ローカル名に解決される。"""
        trees = parse_definition_linkbase(_load("duplicate_loc.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_DuplicateTest"
        tree = trees[role_uri]

        # dimension-domain と dimension-default の両方で TestDomain が参照される
        dim_domain_arcs = [
            a
            for a in tree.arcs
            if a.arcrole == "http://xbrl.org/int/dim/arcrole/dimension-domain"
        ]
        dim_default_arcs = [
            a
            for a in tree.arcs
            if a.arcrole == "http://xbrl.org/int/dim/arcrole/dimension-default"
        ]

        assert len(dim_domain_arcs) == 1
        assert len(dim_default_arcs) == 1
        # 両方とも同じ concept ローカル名に解決
        assert dim_domain_arcs[0].to_concept == "TestDomain"
        assert dim_default_arcs[0].to_concept == "TestDomain"


# ---------- 構造化 ----------


@pytest.mark.unit
class TestHypercubeStructure:
    """ハイパーキューブ構造化のテスト。"""

    def test_hypercube_construction(self) -> None:
        """simple_bs.xml: HypercubeInfo が正しく構築される。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        tree = trees[role_uri]

        assert tree.has_hypercube
        assert len(tree.hypercubes) == 1

        hc = tree.hypercubes[0]
        assert hc.table_concept == "BalanceSheetTable"
        assert hc.heading_concept == "ConsolidatedBalanceSheetHeading"
        assert hc.closed is True
        assert hc.context_element == "scenario"
        assert hc.line_items_concept == "BalanceSheetLineItems"

    def test_axis_info(self) -> None:
        """simple_bs.xml: AxisInfo の domain, default, order が正しい。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        hc = trees[role_uri].hypercubes[0]

        assert len(hc.axes) == 2

        # Axis 2 (SequentialNumbersAxis) should come first (order=1.0)
        axis1 = hc.axes[0]
        assert axis1.axis_concept == "SequentialNumbersAxis"
        assert axis1.order == 1.0
        assert axis1.domain is not None
        assert axis1.domain.concept == "SequentialNumbersDomain"

        # Axis 1 (ConsolidatedOrNonConsolidatedAxis) should come second (order=2.0)
        axis2 = hc.axes[1]
        assert axis2.axis_concept == "ConsolidatedOrNonConsolidatedAxis"
        assert axis2.order == 2.0
        assert axis2.default_member == "ConsolidatedMember"
        assert axis2.domain is not None
        assert axis2.domain.concept == "ConsolidatedOrNonConsolidatedDomain"

    def test_member_tree_with_usable_false(self) -> None:
        """simple_ss.xml: MemberNode ツリー階層と usable=false の検証。"""
        trees = parse_definition_linkbase(_load("simple_ss.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfChangesInEquity"
        hc = trees[role_uri].hypercubes[0]

        assert len(hc.axes) == 1
        axis = hc.axes[0]
        assert axis.axis_concept == "ComponentsOfEquityAxis"
        assert axis.default_member == "NetAssetsMember"

        # ドメインルート: usable=false
        domain = axis.domain
        assert domain is not None
        assert domain.concept == "ComponentsOfEquityDomain"
        assert domain.usable is False

        # Level 1 子: ShareholdersEquityAbstract (usable=false), AccumulatedOtherComprehensiveIncome
        assert len(domain.children) == 2
        abstract_node = domain.children[0]
        assert abstract_node.concept == "ShareholdersEquityAbstract"
        assert abstract_node.usable is False

        aoci_node = domain.children[1]
        assert aoci_node.concept == "AccumulatedOtherComprehensiveIncome"
        assert aoci_node.usable is True

        # Level 2 子: ShareCapital, RetainedEarnings
        assert len(abstract_node.children) == 2
        assert abstract_node.children[0].concept == "ShareCapital"
        assert abstract_node.children[0].usable is True
        assert abstract_node.children[1].concept == "RetainedEarnings"
        assert abstract_node.children[1].usable is True
        # 葉ノードには子がない
        assert len(abstract_node.children[0].children) == 0

    def test_order_sorting(self) -> None:
        """simple_bs.xml: axes が hypercube-dimension arc の order 昇順ソート。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        hc = trees[role_uri].hypercubes[0]

        orders = [a.order for a in hc.axes]
        assert orders == sorted(orders)
        # SequentialNumbersAxis (1.0) < ConsolidatedOrNonConsolidatedAxis (2.0)
        assert hc.axes[0].axis_concept == "SequentialNumbersAxis"
        assert hc.axes[1].axis_concept == "ConsolidatedOrNonConsolidatedAxis"

    def test_domain_member_tree_under_axis(self) -> None:
        """simple_bs.xml: ドメイン配下のメンバーツリーが正しい。"""
        trees = parse_definition_linkbase(_load("simple_bs.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        hc = trees[role_uri].hypercubes[0]

        # ConsolidatedOrNonConsolidatedAxis のドメイン
        axis = hc.axes[1]  # order=2.0
        domain = axis.domain
        assert domain is not None
        assert domain.concept == "ConsolidatedOrNonConsolidatedDomain"
        assert len(domain.children) == 2
        assert domain.children[0].concept == "ConsolidatedMember"
        assert domain.children[1].concept == "NonConsolidatedMember"

    def test_line_items(self) -> None:
        """simple_ss.xml: LineItems が正しく特定される。"""
        trees = parse_definition_linkbase(_load("simple_ss.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfChangesInEquity"
        hc = trees[role_uri].hypercubes[0]

        assert hc.line_items_concept == "StatementOfChangesInEquityLineItems"


# ---------- エッジケース ----------


@pytest.mark.unit
class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_general_special_only(self) -> None:
        """general_special.xml: general-special arc のみ、has_hypercube == False。"""
        trees = parse_definition_linkbase(_load("general_special.xml"))
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ClassificationOfItems"
        tree = trees[role_uri]

        assert tree.has_hypercube is False
        assert len(tree.hypercubes) == 0
        assert len(tree.arcs) == 3

        # general-special arcrole のみ
        arcroles = {a.arcrole for a in tree.arcs}
        assert arcroles == {"http://www.xbrl.org/2003/arcrole/general-special"}

        # arc の concept 名を確認
        concepts = {(a.from_concept, a.to_concept) for a in tree.arcs}
        assert ("Assets", "CurrentAssets") in concepts
        assert ("Assets", "NoncurrentAssets") in concepts
        assert ("CurrentAssets", "CashAndDeposits") in concepts

    def test_multi_role_separation(self) -> None:
        """multi_role.xml: 複数 role + 提出者 href + general-special 共存。"""
        trees = parse_definition_linkbase(_load("multi_role.xml"))

        # 3 つの role
        assert len(trees) == 3

        # Role 1: BS hypercube (standard href)
        bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        assert trees[bs_role].has_hypercube is True
        bs_hc = trees[bs_role].hypercubes[0]
        assert bs_hc.table_concept == "BSTable"
        assert bs_hc.heading_concept == "BSHeading"

        # Role 2: PL hypercube (filer href pattern)
        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        assert trees[pl_role].has_hypercube is True
        pl_hc = trees[pl_role].hypercubes[0]
        # 提出者タクソノミの href から concept 抽出
        assert pl_hc.heading_concept == "CustomPLHeading"
        assert pl_hc.table_concept == "CustomPLTable"
        # 標準タクソノミ href のコンセプトも正しく抽出
        assert pl_hc.axes[0].axis_concept == "ConsolidatedOrNonConsolidatedAxis"

        # Role 3: general-special only
        cm_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ClassificationOfItems"
        assert trees[cm_role].has_hypercube is False
        assert len(trees[cm_role].arcs) == 1


# ---------- エラーハンドリング ----------


@pytest.mark.unit
class TestErrorHandling:
    """エラーハンドリングのテスト。"""

    def test_invalid_xml_raises_parse_error(self) -> None:
        """不正 XML → EdinetParseError。"""
        with pytest.raises(EdinetParseError, match="XML パースに失敗"):
            parse_definition_linkbase(b"<not valid xml!!!>")

    def test_invalid_xml_includes_source_path(self) -> None:
        """不正 XML + source_path → エラーメッセージにパスが含まれる。"""
        with pytest.raises(EdinetParseError, match="test_file.xml"):
            parse_definition_linkbase(b"<bad>", source_path="test_file.xml")

    def test_invalid_order_warns(self) -> None:
        """不正 order 値 → EdinetWarning + デフォルト 0.0。"""
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase
  xmlns:link="http://www.xbrl.org/2003/linkbase"
  xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:definitionLink xlink:type="extended"
    xlink:role="http://example.com/role/test">
    <link:loc xlink:type="locator"
      xlink:href="test.xsd#prefix_ConceptA"
      xlink:label="ConceptA"/>
    <link:loc xlink:type="locator"
      xlink:href="test.xsd#prefix_ConceptB"
      xlink:label="ConceptB"/>
    <link:definitionArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/general-special"
      xlink:from="ConceptA" xlink:to="ConceptB"
      order="abc"/>
  </link:definitionLink>
</link:linkbase>"""

        with pytest.warns(EdinetWarning, match="order 値 'abc' が不正です"):
            trees = parse_definition_linkbase(xml)

        arc = trees["http://example.com/role/test"].arcs[0]
        assert arc.order == 0.0

    def test_unknown_locator_warns(self) -> None:
        """不明ロケーター参照 → EdinetWarning + スキップ。"""
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase
  xmlns:link="http://www.xbrl.org/2003/linkbase"
  xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:definitionLink xlink:type="extended"
    xlink:role="http://example.com/role/test">
    <link:loc xlink:type="locator"
      xlink:href="test.xsd#prefix_ConceptA"
      xlink:label="ConceptA"/>
    <link:definitionArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/general-special"
      xlink:from="ConceptA" xlink:to="NonExistentLabel"
      order="1.0"/>
  </link:definitionLink>
</link:linkbase>"""

        with pytest.warns(EdinetWarning, match="不明なロケーター参照"):
            trees = parse_definition_linkbase(xml)

        # arc はスキップされるので arcs は空
        tree = trees["http://example.com/role/test"]
        assert len(tree.arcs) == 0

    def test_empty_linkbase(self) -> None:
        """空の定義リンクベース（definitionLink なし）→ 空辞書。"""
        xml = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase">
</link:linkbase>"""

        trees = parse_definition_linkbase(xml)
        assert trees == {}
