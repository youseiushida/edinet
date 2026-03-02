"""Presentation Linkbase パーサーのテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.linkbase.presentation import (
    ROLE_LABEL,
    ROLE_NEGATED_LABEL,
    ROLE_PERIOD_END_LABEL,
    ROLE_PERIOD_START_LABEL,
    ROLE_TERSE_LABEL,
    ROLE_TOTAL_LABEL,
    ROLE_VERBOSE_LABEL,
    PresentationNode,
    PresentationTree,
    merge_presentation_trees,
    parse_presentation_linkbase,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "linkbase_presentation"


def _load(name: str) -> bytes:
    """フィクスチャファイルを読み込む。"""
    return (FIXTURE_DIR / name).read_bytes()


# ============================================================
# TestParsePresentationLinkbase
# ============================================================


class TestParsePresentationLinkbase:
    """parse_presentation_linkbase のテスト。"""

    def test_basic_structure(self) -> None:
        """BS フィクスチャから正しいツリー構造がパースされる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        assert len(trees) == 1

        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        assert tree.role_uri == role
        assert len(tree.roots) == 1
        assert tree.roots[0].concept == "BalanceSheetHeading"

    def test_node_attributes(self) -> None:
        """ノードの各属性が正しく設定される。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]

        # ルートの depth は 0
        assert root.depth == 0
        assert root.order == 0.0

        # 子をたどって CashAndDeposits を見つける
        table = root.children[0]
        assert table.concept == "BalanceSheetTable"
        assert table.depth == 1

        line_items = table.children[0]
        assert line_items.concept == "BalanceSheetLineItems"
        assert line_items.depth == 2

        current_assets = line_items.children[0]
        assert current_assets.concept == "CurrentAssetsAbstract"
        assert current_assets.depth == 3

        cash = current_assets.children[0]
        assert cash.concept == "CashAndDeposits"
        assert cash.depth == 4
        assert cash.order == 1.0

    def test_order_sorting(self) -> None:
        """子ノードが order 属性でソートされる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]

        line_items = root.children[0].children[0]
        current_assets = line_items.children[0]
        orders = [child.order for child in current_assets.children]
        assert orders == [1.0, 2.0, 3.0]
        assert current_assets.children[0].concept == "CashAndDeposits"
        assert current_assets.children[1].concept == "NotesAndAccountsReceivableTrade"
        assert current_assets.children[2].concept == "TotalCurrentAssets"

    def test_total_label_identification(self) -> None:
        """preferredLabel=totalLabel のノードが is_total=True になる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]

        line_items = root.children[0].children[0]
        current_assets = line_items.children[0]
        total_current = current_assets.children[2]
        assert total_current.concept == "TotalCurrentAssets"
        assert total_current.is_total is True
        assert total_current.preferred_label == ROLE_TOTAL_LABEL

        total_assets = line_items.children[1]
        assert total_assets.concept == "TotalAssets"
        assert total_assets.is_total is True

    def test_abstract_identification(self) -> None:
        """concept が 'Abstract' で終わるノードが is_abstract=True になる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]

        line_items = root.children[0].children[0]
        current_assets = line_items.children[0]
        assert current_assets.concept == "CurrentAssetsAbstract"
        assert current_assets.is_abstract is True

        cash = current_assets.children[0]
        assert cash.concept == "CashAndDeposits"
        assert cash.is_abstract is False

    def test_heading_is_abstract(self) -> None:
        """concept が 'Heading' で終わるノードも is_abstract=True になる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]
        assert root.concept == "BalanceSheetHeading"
        assert root.is_abstract is True

    def test_multi_role(self) -> None:
        """複数 role URI を含む XML から各ロールのツリーがパースされる。"""
        trees = parse_presentation_linkbase(_load("multi_role.xml"))
        assert len(trees) == 2

        bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        assert bs_role in trees
        assert pl_role in trees

        bs = trees[bs_role]
        pl = trees[pl_role]
        assert bs.roots[0].concept == "BalanceSheetHeading"
        assert pl.roots[0].concept == "StatementOfIncomeHeading"

    def test_empty_linkbase(self) -> None:
        """空の linkbase から空の辞書が返る。"""
        trees = parse_presentation_linkbase(_load("empty.xml"))
        assert trees == {}

    def test_malformed_xml_raises(self) -> None:
        """不正な XML で EdinetParseError が発生する。"""
        with pytest.raises(EdinetParseError, match="XML 解析に失敗"):
            parse_presentation_linkbase(_load("malformed.xml"))

    def test_malformed_xml_includes_source_path(self) -> None:
        """source_path がエラーメッセージに含まれる。"""
        with pytest.raises(EdinetParseError, match="test_file.xml"):
            parse_presentation_linkbase(
                _load("malformed.xml"),
                source_path="test_file.xml",
            )

    def test_node_count(self) -> None:
        """ツリーの node_count が正しい。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        # BSHeading → BSTable → BSLineItems → CurrentAssetsAbstract
        #   → (Cash, Notes, TotalCurrent), TotalAssets
        assert tree.node_count == 8

    def test_preferred_label_full_uri(self) -> None:
        """preferredLabel が完全な URI として保持される。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]
        line_items = root.children[0].children[0]
        total_assets = line_items.children[1]
        assert total_assets.preferred_label == "http://www.xbrl.org/2003/role/totalLabel"

    def test_dimension_node_table(self) -> None:
        """Table サフィックスのノードが is_dimension_node=True になる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]
        table = root.children[0]
        assert table.concept == "BalanceSheetTable"
        assert table.is_dimension_node is True

    def test_dimension_node_line_items(self) -> None:
        """LineItems サフィックスのノードが is_dimension_node=True になる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]
        line_items = root.children[0].children[0]
        assert line_items.concept == "BalanceSheetLineItems"
        assert line_items.is_dimension_node is True

    def test_missing_href_warns(self) -> None:
        """href 欠落の loc でwarning が発行される。"""
        with pytest.warns(EdinetWarning, match="xlink:href"):
            parse_presentation_linkbase(_load("missing_attrs.xml"))

    def test_missing_order_warns(self) -> None:
        """order 欠落の arc で warning が発行され 0.0 にフォールバックする。"""
        with pytest.warns(EdinetWarning, match="order"):
            trees = parse_presentation_linkbase(_load("missing_attrs.xml"))

        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        assert tree.node_count >= 2

    def test_non_numeric_order_warns(self) -> None:
        """非数値の order で warning が発行される。"""
        with pytest.warns(EdinetWarning, match="order"):
            parse_presentation_linkbase(_load("missing_attrs.xml"))

    def test_is_total_false_for_normal_node(self) -> None:
        """通常のノードの is_total は False。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        root = trees[role].roots[0]
        line_items = root.children[0].children[0]
        cash = line_items.children[0].children[0]
        assert cash.concept == "CashAndDeposits"
        assert cash.is_total is False

    def test_cyclic_arc_warns_and_skips(self) -> None:
        """A → B → C → A の循環参照で EdinetWarning が送出されツリーが切断される。"""
        with pytest.warns(EdinetWarning, match="循環参照"):
            trees = parse_presentation_linkbase(_load("cyclic.xml"))
        # 循環ノードは skip されるが、ツリー自体はパースできる
        assert len(trees) > 0


# ============================================================
# TestConceptExtractionViaPublicAPI
# ============================================================


class TestConceptExtractionViaPublicAPI:
    """concept 名正規化の公開 API 経由テスト。

    concept_variants.xml フィクスチャを使い、各種 prefix パターンからの
    concept 抽出を parse_presentation_linkbase() 経由で検証する。
    """

    @pytest.fixture()
    def tree(self) -> PresentationTree:
        """concept_variants.xml のツリーを返す。"""
        trees = parse_presentation_linkbase(_load("concept_variants.xml"))
        role = "http://example.com/role/concept_test"
        return trees[role]

    def test_standard_prefix(self, tree: PresentationTree) -> None:
        """jppfs_cor_ プレフィックスから concept 名が正しく分離される。"""
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        assert "StandardItem" in concepts

    def test_filer_prefix(self, tree: PresentationTree) -> None:
        """ハイフン含み提出者タクソノミプレフィックスから concept 名が分離される。"""
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        assert "FilerCustomItem" in concepts

    def test_bare_fragment(self, tree: PresentationTree) -> None:
        """prefix なしの bare fragment から concept 名が取得される。"""
        assert tree.roots[0].concept == "BareConceptHeading"

    def test_duplicate_label_suffix_not_leaked(self, tree: PresentationTree) -> None:
        """_2 サフィックス付き label が concept 名に漏れない。"""
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        # loc_Standard_2 は同一 concept (StandardItem) を指すため、
        # concept 名に _2 が含まれてはならない
        assert all("_2" not in c for c in concepts)

    def test_lowercase_fragment_fallback(self, tree: PresentationTree) -> None:
        """小文字のみの fragment はフォールバックでフラグメント全体が返る。"""
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        assert "alllowercasename" in concepts


# ============================================================
# TestPresentationTree
# ============================================================


class TestPresentationTree:
    """PresentationTree のメソッドテスト。"""

    def test_line_items_roots(self) -> None:
        """line_items_roots() が LineItems の子を返す。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        li_roots = tree.line_items_roots()
        # LineItems の子: CurrentAssetsAbstract, TotalAssets
        concepts = [n.concept for n in li_roots]
        assert "CurrentAssetsAbstract" in concepts
        assert "TotalAssets" in concepts

    def test_line_items_roots_fallback(self) -> None:
        """LineItems がないツリーでは roots がそのまま返る。"""
        trees = parse_presentation_linkbase(_load("multi_role.xml"))
        bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[bs_role]
        li_roots = tree.line_items_roots()
        assert li_roots == tree.roots

    def test_flatten_all(self) -> None:
        """flatten() が全ノードを深さ優先で返す。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        flat = tree.flatten()
        assert len(flat) == tree.node_count
        concepts = [n.concept for n in flat]
        assert concepts[0] == "BalanceSheetHeading"
        assert "CashAndDeposits" in concepts

    def test_flatten_returns_tuple(self) -> None:
        """flatten() がタプルを返す。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        flat = tree.flatten()
        assert isinstance(flat, tuple)

    def test_flatten_skip_abstract(self) -> None:
        """flatten(skip_abstract=True) で Abstract/Heading ノードがスキップされる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        flat = tree.flatten(skip_abstract=True)
        concepts = [n.concept for n in flat]
        assert "CurrentAssetsAbstract" not in concepts
        assert "BalanceSheetHeading" not in concepts
        # 通常の科目は残る
        assert "CashAndDeposits" in concepts

    def test_flatten_skip_dimension(self) -> None:
        """flatten(skip_dimension=True) でディメンションノードがスキップされる。"""
        trees = parse_presentation_linkbase(_load("simple_bs.xml"))
        role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        tree = trees[role]
        flat = tree.flatten(skip_dimension=True)
        concepts = [n.concept for n in flat]
        assert "BalanceSheetTable" not in concepts
        assert "BalanceSheetLineItems" not in concepts
        assert "CashAndDeposits" in concepts


# ============================================================
# TestMergePresentationTrees
# ============================================================


class TestMergePresentationTrees:
    """merge_presentation_trees のテスト。"""

    def test_merge_same_role(self) -> None:
        """同一 role のツリーがマージされる。"""
        main = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        sales = parse_presentation_linkbase(_load("variant_pl_sales.xml"))
        merged = merge_presentation_trees(main, sales)

        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        assert pl_role in merged
        tree = merged[pl_role]
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        assert "OperatingIncome" in concepts
        assert "NetSales" in concepts

    def test_merge_different_roles(self) -> None:
        """異なる role のツリーは別々に保持される。"""
        bs = parse_presentation_linkbase(_load("simple_bs.xml"))
        pl = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        merged = merge_presentation_trees(bs, pl)

        bs_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        assert bs_role in merged
        assert pl_role in merged

    def test_merge_preserves_order(self) -> None:
        """マージ後も order 属性が保持される。"""
        main = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        sales = parse_presentation_linkbase(_load("variant_pl_sales.xml"))
        merged = merge_presentation_trees(main, sales)

        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        tree = merged[pl_role]
        flat = tree.flatten()
        for node in flat:
            assert isinstance(node.order, float)

    def test_merge_single_dict(self) -> None:
        """単一辞書の場合はコピーが返る。"""
        original = parse_presentation_linkbase(_load("simple_bs.xml"))
        merged = merge_presentation_trees(original)
        assert len(merged) == len(original)
        for role in original:
            assert role in merged

    def test_merge_depth_preserved(self) -> None:
        """マージ後に depth が 0 から正しく再計算される。"""
        main = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        sales = parse_presentation_linkbase(_load("variant_pl_sales.xml"))
        merged = merge_presentation_trees(main, sales)

        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        tree = merged[pl_role]
        for root in tree.roots:
            assert root.depth == 0
            for child in root.children:
                assert child.depth == 1

    def test_merge_first_wins_attributes(self) -> None:
        """同一 concept で先に現れたノードの属性が優先される。"""
        main = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        sales = parse_presentation_linkbase(_load("variant_pl_sales.xml"))
        merged = merge_presentation_trees(main, sales)

        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        tree = merged[pl_role]
        assert tree.roots[0].concept == "StatementOfIncomeHeading"

    def test_merge_no_args(self) -> None:
        """引数なしで空辞書が返る。"""
        result = merge_presentation_trees()
        assert result == {}

    def test_merge_empty_dicts(self) -> None:
        """空辞書のみで空辞書が返る。"""
        result = merge_presentation_trees({}, {})
        assert result == {}

    def test_merge_deep(self) -> None:
        """深い階層のノードもマージされる。"""
        main = parse_presentation_linkbase(_load("variant_pl_main.xml"))
        sales = parse_presentation_linkbase(_load("variant_pl_sales.xml"))
        merged = merge_presentation_trees(main, sales)

        pl_role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        tree = merged[pl_role]
        flat = tree.flatten()
        concepts = [n.concept for n in flat]
        assert "OperatingIncomeAbstract" in concepts
        assert "SalesAbstract" in concepts


# ============================================================
# TestLabelRoleConstants
# ============================================================


class TestLabelRoleConstants:
    """ラベルロール URI 定数のテスト。"""

    def test_role_label(self) -> None:
        assert ROLE_LABEL == "http://www.xbrl.org/2003/role/label"

    def test_role_total_label(self) -> None:
        assert ROLE_TOTAL_LABEL == "http://www.xbrl.org/2003/role/totalLabel"

    def test_role_verbose_label(self) -> None:
        assert ROLE_VERBOSE_LABEL == "http://www.xbrl.org/2003/role/verboseLabel"

    def test_role_terse_label(self) -> None:
        assert ROLE_TERSE_LABEL == "http://www.xbrl.org/2003/role/terseLabel"

    def test_role_period_start_label(self) -> None:
        assert ROLE_PERIOD_START_LABEL == "http://www.xbrl.org/2003/role/periodStartLabel"

    def test_role_period_end_label(self) -> None:
        assert ROLE_PERIOD_END_LABEL == "http://www.xbrl.org/2003/role/periodEndLabel"

    def test_role_negated_label(self) -> None:
        assert ROLE_NEGATED_LABEL == "http://www.xbrl.org/2003/role/negatedLabel"


# ============================================================
# TestPresentationNodeRepr
# ============================================================


class TestPresentationNodeRepr:
    """PresentationNode/PresentationTree の __repr__ テスト。"""

    def test_node_repr(self) -> None:
        """PresentationNode の repr に concept, depth, order, children 数が含まれる。"""
        node = PresentationNode(
            concept="CashAndDeposits",
            href="test.xsd#CashAndDeposits",
            order=1.0,
            depth=3,
        )
        r = repr(node)
        assert "CashAndDeposits" in r
        assert "depth=3" in r
        assert "order=1.0" in r

    def test_tree_repr(self) -> None:
        """PresentationTree の repr に role_uri, roots 数, node_count が含まれる。"""
        tree = PresentationTree(
            role_uri="http://example.com/role/test",
            roots=(),
            node_count=0,
        )
        r = repr(tree)
        assert "http://example.com/role/test" in r
        assert "roots=0" in r
        assert "node_count=0" in r
