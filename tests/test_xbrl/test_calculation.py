"""Calculation Linkbase パーサーのテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.linkbase.calculation import parse_calculation_linkbase

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "linkbase_calculation"

# ---------- 複数ロールテスト用 XML ----------

_MULTI_ROLE_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/alpha">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_ParentA" xlink:label="ParentA"/>
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_ChildA" xlink:label="ChildA"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="ParentA" xlink:to="ChildA"
        weight="1" order="1"/>
  </link:calculationLink>
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/beta">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_ParentB" xlink:label="ParentB"/>
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_ChildB" xlink:label="ChildB"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="ParentB" xlink:to="ChildB"
        weight="-1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- loc ラベルに suffix 付き XML ----------

_LOC_SUFFIX_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/suffix_test">
    <link:loc xlink:type="locator"
        xlink:href="jppfs_cor_2025-11-01.xsd#jppfs_cor_NetSales"
        xlink:label="NetSales_2"/>
    <link:loc xlink:type="locator"
        xlink:href="jppfs_cor_2025-11-01.xsd#jppfs_cor_GrossProfit"
        xlink:label="GrossProfit"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="GrossProfit" xlink:to="NetSales_2"
        weight="1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- missing loc reference XML ----------

_MISSING_LOC_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/missing">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_Parent" xlink:label="Parent"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="Parent" xlink:to="UnknownChild"
        weight="1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- role_uri 未設定 XML ----------

_NO_ROLE_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_A" xlink:label="A"/>
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_B" xlink:label="B"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="A" xlink:to="B"
        weight="1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- 不正 weight XML ----------

_INVALID_WEIGHT_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/invalid_weight">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_A" xlink:label="A"/>
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_B" xlink:label="B"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="A" xlink:to="B"
        weight="2" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- href フラグメントなし XML ----------

_NO_FRAGMENT_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/no_fragment">
    <link:loc xlink:type="locator"
        xlink:href="test.xsd" xlink:label="NoFrag"/>
    <link:loc xlink:type="locator"
        xlink:href="test.xsd#test_B" xlink:label="B"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="NoFrag" xlink:to="B"
        weight="1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""

# ---------- single arc XML ----------

_SINGLE_ARC_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
  <link:calculationLink xlink:type="extended"
      xlink:role="http://example.com/role/single">
    <link:loc xlink:type="locator"
        xlink:href="jppfs_cor_2025-11-01.xsd#jppfs_cor_Assets"
        xlink:label="Assets"/>
    <link:loc xlink:type="locator"
        xlink:href="jppfs_cor_2025-11-01.xsd#jppfs_cor_CurrentAssets"
        xlink:label="CurrentAssets"/>
    <link:calculationArc xlink:type="arc"
        xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
        xlink:from="Assets" xlink:to="CurrentAssets"
        weight="1" order="1"/>
  </link:calculationLink>
</link:linkbase>
"""


def _load_fixture(name: str) -> bytes:
    """テストフィクスチャ XML をバイト列として読み込む。

    Args:
        name: フィクスチャファイル名。

    Returns:
        XML のバイト列。
    """
    return (_FIXTURE_DIR / name).read_bytes()


# ========== P0 必須テスト ==========


@pytest.mark.unit
class TestP0Essential:
    """P0: 正常系・基本機能テスト。"""

    def test_parse_standard_pl(self) -> None:
        """標準 PL の計算木をパースできる。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        assert len(lb.trees) == 1

        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        tree = lb.get_tree(role)
        assert tree is not None
        assert len(tree.arcs) == 19
        assert tree.roots == ("ProfitLoss",)

        # weight の検証: 全アークの weight は 1 または -1
        for arc in tree.arcs:
            assert arc.weight in (1, -1)

    def test_parse_standard_bs(self) -> None:
        """標準 BS の計算木をパースできる（全 weight=+1、2 ルート）。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_bs.xml"))
        tree = lb.get_tree(
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedBalanceSheet"
        )
        assert tree is not None
        assert len(tree.arcs) == 8

        # 全 weight が +1
        for arc in tree.arcs:
            assert arc.weight == 1

        # 2 ルート: Assets, LiabilitiesAndNetAssets
        assert set(tree.roots) == {"Assets", "LiabilitiesAndNetAssets"}

    def test_children_of(self) -> None:
        """children_of で子アークを order 順に取得できる。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        children = lb.children_of("GrossProfit", role_uri=role)

        assert len(children) == 2
        assert children[0].child == "NetSales"
        assert children[0].weight == 1
        assert children[1].child == "CostOfSales"
        assert children[1].weight == -1

    def test_parent_of(self) -> None:
        """parent_of で親アークを取得できる。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        parents = lb.parent_of("NetSales", role_uri=role)

        assert len(parents) == 1
        assert parents[0].parent == "GrossProfit"
        assert parents[0].weight == 1

    def test_ancestors_of(self) -> None:
        """ancestors_of で根まで祖先を辿れる。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        ancestors = lb.ancestors_of("InterestIncomeNOI", role_uri=role)

        # InterestIncomeNOI → NonOperatingIncome → OrdinaryIncome
        #   → IncomeBeforeIncomeTaxes → ProfitLoss
        assert len(ancestors) == 4
        assert ancestors[0] == "NonOperatingIncome"
        assert ancestors[-1] == "ProfitLoss"

    def test_multiple_roles(self) -> None:
        """複数ロールを正しくパースできる。"""
        lb = parse_calculation_linkbase(_MULTI_ROLE_XML)
        assert len(lb.trees) == 2
        assert len(lb.role_uris) == 2
        assert "http://example.com/role/alpha" in lb.role_uris
        assert "http://example.com/role/beta" in lb.role_uris

    def test_filer_custom_concepts(self) -> None:
        """提出者独自科目を正しくパースできる。"""
        lb = parse_calculation_linkbase(_load_fixture("filer_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        children = lb.children_of(
            "SellingGeneralAndAdministrativeExpenses", role_uri=role
        )

        assert len(children) == 1
        assert children[0].child == "ProvisionForBonuses"
        assert children[0].weight == 1

    def test_order_sorting(self) -> None:
        """children_of が order 昇順で返す。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        children = lb.children_of("IncomeBeforeIncomeTaxes", role_uri=role)

        assert len(children) == 3
        orders = [c.order for c in children]
        assert orders == sorted(orders)
        assert children[0].child == "OrdinaryIncome"
        assert children[1].child == "ExtraordinaryIncome"
        assert children[2].child == "ExtraordinaryLoss"

    def test_negative_weight_pl(self) -> None:
        """PL の控除項目が weight=-1 を持つ。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        tree = lb.get_tree(role)
        assert tree is not None

        negative_children = {
            arc.child for arc in tree.arcs if arc.weight == -1
        }
        expected_negatives = {
            "CostOfSales",
            "SellingGeneralAndAdministrativeExpenses",
            "NonOperatingExpenses",
            "ExtraordinaryLoss",
            "IncomeTaxes",
        }
        assert expected_negatives == negative_children

    def test_children_of_cross_role(self) -> None:
        """role_uri=None で全ロール横断の children_of が動作する。"""
        lb = parse_calculation_linkbase(_MULTI_ROLE_XML)
        # ParentA は alpha role にのみ存在
        children = lb.children_of("ParentA")
        assert len(children) == 1
        assert children[0].child == "ChildA"

    def test_parent_of_cross_role(self) -> None:
        """role_uri=None で全ロール横断の parent_of が動作する。"""
        lb = parse_calculation_linkbase(_MULTI_ROLE_XML)
        parents_a = lb.parent_of("ChildA")
        parents_b = lb.parent_of("ChildB")
        assert len(parents_a) == 1
        assert parents_a[0].parent == "ParentA"
        assert len(parents_b) == 1
        assert parents_b[0].parent == "ParentB"

    def test_arc_has_role_uri(self) -> None:
        """各 arc の role_uri が calculationLink の xlink:role と一致する。"""
        lb = parse_calculation_linkbase(_MULTI_ROLE_XML)
        for role_uri, tree in lb.trees.items():
            for arc in tree.arcs:
                assert arc.role_uri == role_uri

    def test_ancestors_of_root_concept(self) -> None:
        """ルート concept の ancestors_of は空タプルを返す。"""
        lb = parse_calculation_linkbase(_load_fixture("standard_pl.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ConsolidatedStatementOfIncome"
        ancestors = lb.ancestors_of("ProfitLoss", role_uri=role)
        assert ancestors == ()

    def test_loc_with_suffix(self) -> None:
        """loc ラベルに _2 等の suffix があっても href 由来の concept 名が使われる。"""
        lb = parse_calculation_linkbase(_LOC_SUFFIX_XML)
        role = "http://example.com/role/suffix_test"
        children = lb.children_of("GrossProfit", role_uri=role)

        assert len(children) == 1
        assert children[0].child == "NetSales"


# ========== P1 境界・異常系テスト ==========


@pytest.mark.unit
class TestP1EdgeCases:
    """P1: 境界条件・エラーハンドリングテスト。"""

    def test_empty_linkbase(self) -> None:
        """空の linkbase で trees が空辞書になる。"""
        lb = parse_calculation_linkbase(_load_fixture("empty.xml"))
        assert lb.trees == {}
        assert lb.role_uris == ()

    def test_malformed_xml(self) -> None:
        """不正な XML で EdinetParseError が送出される。"""
        with pytest.raises(EdinetParseError):
            parse_calculation_linkbase(_load_fixture("malformed.xml"))

    def test_missing_loc_reference(self) -> None:
        """存在しない loc 参照で EdinetWarning が出て arc がスキップされる。"""
        with pytest.warns(EdinetWarning, match="不明なロケーター参照"):
            lb = parse_calculation_linkbase(_MISSING_LOC_XML)

        role = "http://example.com/role/missing"
        tree = lb.get_tree(role)
        assert tree is not None
        assert len(tree.arcs) == 0

    def test_single_arc(self) -> None:
        """1 件の arc で正常にパースできる。"""
        lb = parse_calculation_linkbase(_SINGLE_ARC_XML)
        role = "http://example.com/role/single"
        tree = lb.get_tree(role)
        assert tree is not None
        assert len(tree.arcs) == 1
        assert tree.arcs[0].parent == "Assets"
        assert tree.arcs[0].child == "CurrentAssets"

    def test_role_uri_missing(self) -> None:
        """xlink:role 未設定で EdinetWarning が出て link がスキップされる。"""
        with pytest.warns(EdinetWarning, match="xlink:role が未設定"):
            lb = parse_calculation_linkbase(_NO_ROLE_XML)

        assert lb.trees == {}

    def test_ancestors_of_circular_reference(self) -> None:
        """循環参照があっても無限ループしない。"""
        lb = parse_calculation_linkbase(_load_fixture("circular.xml"))
        role = "http://example.com/role/circular"

        # A → B → A の循環: ancestors_of("ConceptB") は ["ConceptA"] で停止
        ancestors = lb.ancestors_of("ConceptB", role_uri=role)
        assert "ConceptA" in ancestors
        # 無限ループしないことの検証（テストが終了すれば OK）

        # C → C 自己参照: ancestors_of("ConceptC") は空
        ancestors_c = lb.ancestors_of("ConceptC", role_uri=role)
        # ConceptC は自分自身が親だが visited で弾かれる
        assert len(ancestors_c) == 0

    def test_invalid_weight_skipped_with_warning(self) -> None:
        """weight=2 で EdinetWarning が出て arc がスキップされる。"""
        with pytest.warns(EdinetWarning, match="1 または -1"):
            lb = parse_calculation_linkbase(_INVALID_WEIGHT_XML)

        role = "http://example.com/role/invalid_weight"
        tree = lb.get_tree(role)
        assert tree is not None
        assert len(tree.arcs) == 0

    def test_href_without_fragment(self) -> None:
        """href にフラグメントがない loc で EdinetWarning が出てスキップされる。"""
        with pytest.warns(EdinetWarning, match="フラグメント"):
            lb = parse_calculation_linkbase(_NO_FRAGMENT_XML)

        role = "http://example.com/role/no_fragment"
        tree = lb.get_tree(role)
        assert tree is not None
        # NoFrag loc がスキップされ、arc も from 解決できずスキップ
        assert len(tree.arcs) == 0
