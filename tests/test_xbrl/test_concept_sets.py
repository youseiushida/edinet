"""concept_sets モジュールのテスト。

Detroit 派 (モック不使用)。XML bytes → アサート。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from edinet.models.financial import StatementType
from edinet.xbrl.linkbase.presentation import (
    merge_presentation_trees,
    parse_presentation_linkbase,
)
from edinet.xbrl.taxonomy.concept_sets import (
    ConceptEntry,
    ConceptSet,
    ConceptSetRegistry,
    StatementCategory,
    _cache_path,
    classify_role_uri,
    derive_concept_sets,
    derive_concept_sets_from_trees,
    get_concept_set,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "concept_sets"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _parse(name: str) -> dict:
    return parse_presentation_linkbase(_load(name))


# ===================================================================
# TestStatementCategory
# ===================================================================


class TestStatementCategory:
    """StatementCategory の変換テスト。"""

    def test_to_statement_type_bs(self) -> None:
        assert (
            StatementCategory.BALANCE_SHEET.to_statement_type()
            == StatementType.BALANCE_SHEET
        )

    def test_to_statement_type_pl(self) -> None:
        assert (
            StatementCategory.INCOME_STATEMENT.to_statement_type()
            == StatementType.INCOME_STATEMENT
        )

    def test_to_statement_type_cf(self) -> None:
        assert (
            StatementCategory.CASH_FLOW_STATEMENT.to_statement_type()
            == StatementType.CASH_FLOW_STATEMENT
        )

    def test_to_statement_type_ss(self) -> None:
        assert (
            StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY.to_statement_type()
            == StatementType.STATEMENT_OF_CHANGES_IN_EQUITY
        )

    def test_to_statement_type_ci(self) -> None:
        assert (
            StatementCategory.COMPREHENSIVE_INCOME.to_statement_type()
            == StatementType.COMPREHENSIVE_INCOME
        )

    def test_from_statement_type_pl(self) -> None:
        assert (
            StatementCategory.from_statement_type(StatementType.INCOME_STATEMENT)
            == StatementCategory.INCOME_STATEMENT
        )

    def test_from_statement_type_bs(self) -> None:
        assert (
            StatementCategory.from_statement_type(StatementType.BALANCE_SHEET)
            == StatementCategory.BALANCE_SHEET
        )

    def test_from_statement_type_cf(self) -> None:
        assert (
            StatementCategory.from_statement_type(
                StatementType.CASH_FLOW_STATEMENT
            )
            == StatementCategory.CASH_FLOW_STATEMENT
        )


# ===================================================================
# TestClassifyRoleUri
# ===================================================================


class TestClassifyRoleUri:
    """classify_role_uri のテスト。"""

    def test_consolidated_bs(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedBalanceSheet"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.BALANCE_SHEET, True, None)

    def test_nonconsolidated_bs(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_BalanceSheet"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.BALANCE_SHEET, False, None)

    def test_consolidated_pl(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfIncome"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.INCOME_STATEMENT, True, None)

    def test_nonconsolidated_pl(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfIncome"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.INCOME_STATEMENT, False, None)

    def test_cf_indirect(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-indirect"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.CASH_FLOW_STATEMENT, True, "indirect")

    def test_cf_direct(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfCashFlows-direct"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.CASH_FLOW_STATEMENT, True, "direct")

    def test_nonconsolidated_cf(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfCashFlows-indirect"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.CASH_FLOW_STATEMENT, False, "indirect")

    def test_ss(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfChangesInNetAssets"
        result = classify_role_uri(uri)
        assert result == (
            StatementCategory.STATEMENT_OF_CHANGES_IN_EQUITY,
            True,
            None,
        )

    def test_ci(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_ConsolidatedStatementOfComprehensiveIncome"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.COMPREHENSIVE_INCOME, True, None)

    def test_semiannual_bs(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_SemiAnnualConsolidatedBalanceSheet"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.BALANCE_SHEET, True, None)

    def test_type1_semiannual_pl(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_Type1SemiAnnualConsolidatedStatementOfIncome"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.INCOME_STATEMENT, True, None)

    def test_non_financial_role_returns_none(self) -> None:
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_CoverPage"
        assert classify_role_uri(uri) is None

    def test_no_rol_prefix_returns_none(self) -> None:
        uri = "http://www.xbrl.org/2003/role/link"
        assert classify_role_uri(uri) is None

    def test_without_std_prefix(self) -> None:
        """std_ なしの role URI (個別タクソノミ等)。"""
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.BALANCE_SHEET, False, None)

    def test_income_and_retained_earnings(self) -> None:
        """損益及び剰余金計算書 (StatementOfIncomeAndRetainedEarnings)。"""
        uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_std_StatementOfIncomeAndRetainedEarnings"
        result = classify_role_uri(uri)
        assert result == (StatementCategory.INCOME_STATEMENT, False, None)


# ===================================================================
# TestDeriveConceptSetsFromTrees
# ===================================================================


class TestDeriveConceptSetsFromTrees:
    """derive_concept_sets_from_trees のテスト。"""

    def test_bs_concepts_extracted(self) -> None:
        trees = _parse("simple_bs_pre.xml")
        sets = derive_concept_sets_from_trees(trees, source_info="test")
        assert len(sets) == 1
        cs = sets[0]
        assert cs.category == StatementCategory.BALANCE_SHEET
        assert cs.is_consolidated is True
        names = cs.concept_names()
        assert "CashAndDeposits" in names
        assert "NotesAndAccountsReceivableTrade" in names
        assert "TotalAssets" in names

    def test_pl_concepts_extracted(self) -> None:
        trees = _parse("simple_pl_pre.xml")
        sets = derive_concept_sets_from_trees(trees, source_info="test")
        assert len(sets) == 1
        cs = sets[0]
        assert cs.category == StatementCategory.INCOME_STATEMENT
        names = cs.concept_names()
        assert "NetSales" in names
        assert "OperatingIncome" in names
        assert "OrdinaryIncome" in names

    def test_order_preserved(self) -> None:
        """DFS 順で order が保持される。"""
        trees = _parse("simple_bs_pre.xml")
        cs = derive_concept_sets_from_trees(trees)[0]
        concepts = [e.concept for e in cs.concepts]
        # CurrentAssetsAbstract → CashAndDeposits → NotesAndAccountsReceivableTrade → TotalCurrentAssets → TotalAssets
        ca_idx = concepts.index("CurrentAssetsAbstract")
        cd_idx = concepts.index("CashAndDeposits")
        ta_idx = concepts.index("TotalAssets")
        assert ca_idx < cd_idx < ta_idx

    def test_total_detection(self) -> None:
        """totalLabel の preferredLabel を持つ科目は is_total=True。"""
        trees = _parse("simple_bs_pre.xml")
        cs = derive_concept_sets_from_trees(trees)[0]
        totals = {e.concept for e in cs.concepts if e.is_total}
        assert "TotalCurrentAssets" in totals
        assert "TotalAssets" in totals
        assert "CashAndDeposits" not in totals

    def test_abstract_detection(self) -> None:
        """Abstract 科目は is_abstract=True。"""
        trees = _parse("simple_bs_pre.xml")
        cs = derive_concept_sets_from_trees(trees)[0]
        abstracts = {e.concept for e in cs.concepts if e.is_abstract}
        assert "CurrentAssetsAbstract" in abstracts
        assert "CashAndDeposits" not in abstracts

    def test_depth_relative_to_line_items(self) -> None:
        """depth は LineItems からの相対深さ。"""
        trees = _parse("simple_bs_pre.xml")
        cs = derive_concept_sets_from_trees(trees)[0]
        entries = {e.concept: e for e in cs.concepts}
        # CurrentAssetsAbstract は LineItems の直下 → depth=0
        assert entries["CurrentAssetsAbstract"].depth == 0
        # CashAndDeposits は CurrentAssetsAbstract の下 → depth=1
        assert entries["CashAndDeposits"].depth == 1
        # TotalAssets は LineItems の直下 → depth=0
        assert entries["TotalAssets"].depth == 0

    def test_dimension_nodes_excluded(self) -> None:
        """Heading/Table/LineItems (dimension_node) は ConceptSet に含まれない。"""
        trees = _parse("simple_bs_pre.xml")
        cs = derive_concept_sets_from_trees(trees)[0]
        names = cs.concept_names()
        assert "BalanceSheetHeading" not in names
        assert "BalanceSheetTable" not in names
        assert "BalanceSheetLineItems" not in names

    def test_non_financial_role_excluded(self) -> None:
        """非財務 role URI のツリーは結果に含まれない。"""
        trees = _parse("non_financial_roles.xml")
        sets = derive_concept_sets_from_trees(trees)
        assert len(sets) == 0

    def test_empty_linkbase(self) -> None:
        """空 linkbase からは空リスト。"""
        trees = _parse("empty_pre.xml")
        sets = derive_concept_sets_from_trees(trees)
        assert sets == []

    def test_multi_statement(self) -> None:
        """1 ファイルに複数 role → 複数 ConceptSet。"""
        trees = _parse("multi_statement.xml")
        sets = derive_concept_sets_from_trees(trees)
        categories = {cs.category for cs in sets}
        assert StatementCategory.BALANCE_SHEET in categories
        assert StatementCategory.INCOME_STATEMENT in categories

    def test_consolidated_and_nonconsolidated(self) -> None:
        """連結と個別が分離される。"""
        trees = _parse("consolidated_and_nonconsolidated.xml")
        sets = derive_concept_sets_from_trees(trees)
        consolidated = [cs for cs in sets if cs.is_consolidated]
        nonconsolidated = [cs for cs in sets if not cs.is_consolidated]
        assert len(consolidated) >= 1
        assert len(nonconsolidated) >= 1

    def test_cf_three_sections(self) -> None:
        """CF は営業/投資/財務の 3 セクションを含む。"""
        trees = _parse("cf_pre.xml")
        sets = derive_concept_sets_from_trees(trees)
        assert len(sets) == 1
        cs = sets[0]
        assert cs.category == StatementCategory.CASH_FLOW_STATEMENT
        names = cs.concept_names()
        assert "CashFlowsFromOperatingActivitiesAbstract" in names
        assert "CashFlowsFromInvestingActivitiesAbstract" in names
        assert "CashFlowsFromFinancingActivitiesAbstract" in names
        assert "NetCashProvidedByOperatingActivities" in names

    def test_source_info_propagated(self) -> None:
        """source_info が ConceptSet に伝播される。"""
        trees = _parse("simple_bs_pre.xml")
        sets = derive_concept_sets_from_trees(
            trees, source_info="my_source"
        )
        assert sets[0].source_info == "my_source"


# ===================================================================
# TestConceptSet
# ===================================================================


class TestConceptSet:
    """ConceptSet のメソッドテスト。"""

    @pytest.fixture()
    def bs_concept_set(self) -> ConceptSet:
        trees = _parse("simple_bs_pre.xml")
        return derive_concept_sets_from_trees(trees)[0]

    def test_concept_names(self, bs_concept_set: ConceptSet) -> None:
        names = bs_concept_set.concept_names()
        assert isinstance(names, frozenset)
        assert "CashAndDeposits" in names
        assert "CurrentAssetsAbstract" in names

    def test_non_abstract_concepts(
        self, bs_concept_set: ConceptSet
    ) -> None:
        na = bs_concept_set.non_abstract_concepts()
        assert "CashAndDeposits" in na
        assert "CurrentAssetsAbstract" not in na

    def test_repr(self, bs_concept_set: ConceptSet) -> None:
        r = repr(bs_concept_set)
        assert "BALANCE_SHEET" in r
        assert "連結" in r
        assert "concepts=" in r
        assert "rol_std_ConsolidatedBalanceSheet" in r


# ===================================================================
# TestConceptSetRegistry
# ===================================================================


class TestConceptSetRegistry:
    """ConceptSetRegistry のテスト。"""

    @pytest.fixture()
    def registry(self) -> ConceptSetRegistry:
        trees_bs = _parse("simple_bs_pre.xml")
        trees_pl = _parse("simple_pl_pre.xml")
        merged = merge_presentation_trees(trees_bs, trees_pl)
        all_sets = derive_concept_sets_from_trees(merged, source_info="test")
        sets_dict = {cs.role_uri: cs for cs in all_sets}
        return ConceptSetRegistry(_sets={"cai": sets_dict})

    def test_get_bs(self, registry: ConceptSetRegistry) -> None:
        cs = registry.get(StatementType.BALANCE_SHEET)
        assert cs is not None
        assert cs.category == StatementCategory.BALANCE_SHEET

    def test_get_pl(self, registry: ConceptSetRegistry) -> None:
        cs = registry.get(StatementType.INCOME_STATEMENT)
        assert cs is not None
        assert cs.category == StatementCategory.INCOME_STATEMENT

    def test_get_nonexistent_returns_none(
        self, registry: ConceptSetRegistry
    ) -> None:
        cs = registry.get(StatementType.CASH_FLOW_STATEMENT)
        assert cs is None

    def test_get_wrong_industry_returns_none(
        self, registry: ConceptSetRegistry
    ) -> None:
        cs = registry.get(
            StatementType.BALANCE_SHEET, industry_code="nonexistent"
        )
        assert cs is None

    def test_industries(self, registry: ConceptSetRegistry) -> None:
        assert "cai" in registry.industries()

    def test_all_for_industry(
        self, registry: ConceptSetRegistry
    ) -> None:
        all_sets = registry.all_for_industry("cai")
        assert len(all_sets) >= 2

    def test_all_for_industry_empty(
        self, registry: ConceptSetRegistry
    ) -> None:
        all_sets = registry.all_for_industry("nonexistent")
        assert all_sets == {}

    def test_statement_categories(
        self, registry: ConceptSetRegistry
    ) -> None:
        cats = registry.statement_categories("cai")
        assert StatementCategory.BALANCE_SHEET in cats
        assert StatementCategory.INCOME_STATEMENT in cats


# ===================================================================
# TestPLVariantMerge
# ===================================================================


class TestPLVariantMerge:
    """PL バリアントマージのテスト。"""

    def test_merge_superset(self) -> None:
        """マージ後は両方の concept を含むスーパーセット。"""
        trees_main = _parse("pl_main.xml")
        trees_variant = _parse("pl_variant_sales.xml")
        merged = merge_presentation_trees(trees_main, trees_variant)
        sets = derive_concept_sets_from_trees(merged, source_info="merge")
        assert len(sets) == 1
        cs = sets[0]
        names = cs.concept_names()
        # main のみに含まれる科目
        assert "OperatingIncome" in names
        assert "OrdinaryIncome" in names
        assert "NetIncome" in names
        # variant のみに含まれる科目
        assert "NetSales" in names
        assert "CostOfSales" in names
        assert "GrossProfit" in names

    def test_merge_preserves_depth(self) -> None:
        """マージ後も depth が保持される。"""
        trees_main = _parse("pl_main.xml")
        trees_variant = _parse("pl_variant_sales.xml")
        merged = merge_presentation_trees(trees_main, trees_variant)
        sets = derive_concept_sets_from_trees(merged)
        cs = sets[0]
        entries = {e.concept: e for e in cs.concepts}
        # SalesAbstract は LineItems 直下 → depth=0
        if "SalesAbstract" in entries:
            assert entries["SalesAbstract"].depth == 0
        # NetSales は SalesAbstract の下 → depth=1
        if "NetSales" in entries:
            assert entries["NetSales"].depth == 1

    def test_merge_preserves_total_flags(self) -> None:
        """マージ後も is_total フラグが保持される。"""
        trees_main = _parse("pl_main.xml")
        trees_variant = _parse("pl_variant_sales.xml")
        merged = merge_presentation_trees(trees_main, trees_variant)
        sets = derive_concept_sets_from_trees(merged)
        cs = sets[0]
        entries = {e.concept: e for e in cs.concepts}
        assert entries["OperatingIncome"].is_total is True
        assert entries["GrossProfit"].is_total is True

    def test_variant_lineitems_root_collected(self) -> None:
        """variant 由来の LineItems ルートの children が収集されること。

        実タクソノミでは variant file のマージ後に LineItems が
        独立ルートとして出現する (C-1 バグの再現テスト)。
        """
        trees_main = _parse("pl_main.xml")
        trees_variant = _parse("pl_variant_lineitems_root.xml")
        merged = merge_presentation_trees(trees_main, trees_variant)
        sets = derive_concept_sets_from_trees(merged)
        assert len(sets) == 1
        cs = sets[0]
        names = cs.concept_names()
        # main 由来
        assert "OperatingIncome" in names
        assert "OrdinaryIncome" in names
        # variant 由来 (LineItems ルート経由)
        assert "NetSales" in names
        assert "CostOfSales" in names
        assert "GrossProfit" in names
        assert "SalesAbstract" in names


# ===================================================================
# TestConceptSetRegistryGet
# ===================================================================


class TestConceptSetRegistryGet:
    """ConceptSetRegistry.get() の追加テスト。"""

    def test_get_returns_largest_when_multiple(self) -> None:
        """同一条件で複数ある場合、concepts 数が最大のものを返す。"""
        small = ConceptSet(
            role_uri="urn:test:small",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(
                ConceptEntry("A", 1.0, False, False, 0, "x.xsd#A"),
            ),
            source_info="small",
        )
        large = ConceptSet(
            role_uri="urn:test:large",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(
                ConceptEntry("A", 1.0, False, False, 0, "x.xsd#A"),
                ConceptEntry("B", 2.0, False, False, 0, "x.xsd#B"),
                ConceptEntry("C", 3.0, False, False, 0, "x.xsd#C"),
            ),
            source_info="large",
        )
        reg = ConceptSetRegistry(
            _sets={"cai": {"r1": small, "r2": large}}
        )
        result = reg.get(StatementType.CASH_FLOW_STATEMENT)
        assert result is not None
        assert len(result.concepts) == 3


# ===================================================================
# TestRealTaxonomy (skipif: CI 環境では skip)
# ===================================================================


_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
class TestRealTaxonomy:
    """実タクソノミを用いたスモークテスト。"""

    @pytest.fixture(scope="class")
    def registry(self) -> ConceptSetRegistry:
        assert _TAXONOMY_ROOT is not None
        return derive_concept_sets(_TAXONOMY_ROOT, use_cache=False)

    def test_multiple_industries(
        self, registry: ConceptSetRegistry
    ) -> None:
        """複数の業種が登録されている。"""
        assert len(registry.industries()) >= 5

    def test_cns_has_bs(self, registry: ConceptSetRegistry) -> None:
        """cns に BS がある。"""
        cs = registry.get(StatementType.BALANCE_SHEET)
        assert cs is not None
        assert len(cs.non_abstract_concepts()) > 10

    def test_cns_has_pl(self, registry: ConceptSetRegistry) -> None:
        """cns に PL がある。"""
        cs = registry.get(StatementType.INCOME_STATEMENT)
        assert cs is not None
        assert len(cs.non_abstract_concepts()) > 10

    def test_bs_known_concepts(
        self, registry: ConceptSetRegistry
    ) -> None:
        """BS に既知の科目が含まれている。"""
        cs = registry.get(StatementType.BALANCE_SHEET)
        assert cs is not None
        names = cs.concept_names()
        assert "CashAndDeposits" in names
        # 実タクソノミでは "Assets" (TotalAssets ではなく)
        assert "Assets" in names or "TotalAssets" in names

    def test_pl_known_concepts(
        self, registry: ConceptSetRegistry
    ) -> None:
        """PL に既知の科目が含まれている。"""
        cs = registry.get(StatementType.INCOME_STATEMENT)
        assert cs is not None
        names = cs.concept_names()
        # cns メインファイルは OperatingIncome 以降、NetSales はバリアント
        assert "OperatingIncome" in names or "NetSales" in names

    def test_cf_available(self, registry: ConceptSetRegistry) -> None:
        """CF が取得可能 (fallback 含む)。"""
        cs = registry.get(StatementType.CASH_FLOW_STATEMENT)
        assert cs is not None
        assert cs.category == StatementCategory.CASH_FLOW_STATEMENT

    def test_cf_method_indirect_filter(
        self, registry: ConceptSetRegistry
    ) -> None:
        """cf_method='indirect' で indirect のみ取得可能。"""
        cs = registry.get(
            StatementType.CASH_FLOW_STATEMENT,
            cf_method="indirect",
        )
        if cs is not None:
            assert cs.cf_method == "indirect"

    def test_cf_method_direct_filter(
        self, registry: ConceptSetRegistry
    ) -> None:
        """cf_method='direct' で direct のみ取得可能。"""
        cs = registry.get(
            StatementType.CASH_FLOW_STATEMENT,
            cf_method="direct",
        )
        if cs is not None:
            assert cs.cf_method == "direct"


# ===================================================================
# TestConceptSetCfMethod (ユニットテスト)
# ===================================================================


class TestConceptSetCfMethod:
    """ConceptSet.cf_method フィールドのテスト。"""

    def test_cf_method_default_none(self) -> None:
        """cf_method のデフォルト値は None。"""
        cs = ConceptSet(
            role_uri="test",
            category=StatementCategory.BALANCE_SHEET,
            is_consolidated=True,
            concepts=(),
            source_info="test",
        )
        assert cs.cf_method is None

    def test_cf_method_indirect(self) -> None:
        """cf_method='indirect' を設定できること。"""
        cs = ConceptSet(
            role_uri="test",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(),
            source_info="test",
            cf_method="indirect",
        )
        assert cs.cf_method == "indirect"

    def test_cf_method_direct(self) -> None:
        """cf_method='direct' を設定できること。"""
        cs = ConceptSet(
            role_uri="test",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(),
            source_info="test",
            cf_method="direct",
        )
        assert cs.cf_method == "direct"

    def test_registry_get_cf_method_filter(self) -> None:
        """ConceptSetRegistry.get() が cf_method でフィルタすること。"""
        cs_indirect = ConceptSet(
            role_uri="indirect_uri",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(
                ConceptEntry("A", 1.0, False, False, 0, "href"),
                ConceptEntry("B", 2.0, False, False, 0, "href"),
            ),
            source_info="test",
            cf_method="indirect",
        )
        cs_direct = ConceptSet(
            role_uri="direct_uri",
            category=StatementCategory.CASH_FLOW_STATEMENT,
            is_consolidated=True,
            concepts=(
                ConceptEntry("C", 1.0, False, False, 0, "href"),
            ),
            source_info="test",
            cf_method="direct",
        )
        registry = ConceptSetRegistry(
            _sets={"cai": {
                "indirect_uri": cs_indirect,
                "direct_uri": cs_direct,
            }}
        )
        # cf_method=None → 最大の indirect を返す
        result = registry.get(StatementType.CASH_FLOW_STATEMENT)
        assert result is not None
        assert result.cf_method == "indirect"

        # cf_method="indirect" → indirect のみ
        result = registry.get(
            StatementType.CASH_FLOW_STATEMENT,
            cf_method="indirect",
        )
        assert result is not None
        assert result.cf_method == "indirect"

        # cf_method="direct" → direct のみ
        result = registry.get(
            StatementType.CASH_FLOW_STATEMENT,
            cf_method="direct",
        )
        assert result is not None
        assert result.cf_method == "direct"


# ===================================================================
# TestClassifyRoleURIIFRS (T01-T05)
# ===================================================================


class TestClassifyRoleURIIFRS:
    """IFRS role URI の分類テスト。"""

    def test_classify_role_uri_ifrs_pl(self) -> None:
        """T01: StatementOfProfitOrLossIFRS → INCOME_STATEMENT。"""
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfProfitOrLossIFRS"
        )
        assert result is not None
        category, is_consolidated, cf_method = result
        assert category == StatementCategory.INCOME_STATEMENT
        assert is_consolidated is True
        assert cf_method is None

    def test_classify_role_uri_ifrs_bs(self) -> None:
        """T02: StatementOfFinancialPositionIFRS → BALANCE_SHEET。"""
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfFinancialPositionIFRS"
        )
        assert result is not None
        category, is_consolidated, cf_method = result
        assert category == StatementCategory.BALANCE_SHEET
        assert is_consolidated is True
        assert cf_method is None

    def test_classify_role_uri_ifrs_pl_without_suffix(self) -> None:
        """T03: IFRS サフィックスなし → PL として分類。"""
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfProfitOrLoss"
        )
        assert result is not None
        assert result[0] == StatementCategory.INCOME_STATEMENT

    def test_classify_role_uri_ifrs_bs_without_suffix(self) -> None:
        """T04: IFRS サフィックスなし → BS として分類。"""
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            "rol_std_ConsolidatedStatementOfFinancialPosition"
        )
        assert result is not None
        assert result[0] == StatementCategory.BALANCE_SHEET

    def test_classify_role_uri_existing_jgaap_unaffected(self) -> None:
        """T05: 既存の J-GAAP role URI が影響を受けない。"""
        # PL
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/"
            "rol_ConsolidatedStatementOfIncome"
        )
        assert result is not None
        assert result[0] == StatementCategory.INCOME_STATEMENT

        # BS
        result = classify_role_uri(
            "http://disclosure.edinet-fsa.go.jp/role/jppfs/"
            "rol_ConsolidatedBalanceSheet"
        )
        assert result is not None
        assert result[0] == StatementCategory.BALANCE_SHEET


# ===================================================================
# TestDeriveConceptSetsIFRS (T06-T07)
# ===================================================================


class TestDeriveConceptSetsIFRS:
    """IFRS (jpigp) 導出のテスト。"""

    def test_derive_concept_sets_default_module_group(
        self, tmp_path: Path,
    ) -> None:
        """T06: module_group 未指定で既存動作が維持される。

        jppfs ディレクトリが存在しない場合にエラーが発生することを確認
        （既存動作と同一）。
        """
        (tmp_path / "taxonomy").mkdir()
        with pytest.raises(Exception):
            derive_concept_sets(tmp_path, use_cache=False)

    def test_derive_concept_sets_jpigp_empty_when_no_dir(
        self, tmp_path: Path,
    ) -> None:
        """T07: jpigp ディレクトリなしで空 ConceptSetRegistry。"""
        (tmp_path / "taxonomy" / "jppfs" / "2025-11-01" / "r" / "cai").mkdir(
            parents=True,
        )
        registry = derive_concept_sets(
            tmp_path, use_cache=False, module_group="jpigp",
        )
        assert registry.industries() == frozenset()


# ===================================================================
# TestDeriveConceptSetsIFRSReal (T08-T12, T15): 実タクソノミ
# ===================================================================


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
class TestDeriveConceptSetsIFRSReal:
    """タクソノミ実物を使った IFRS 導出テスト。"""

    @pytest.fixture(scope="class")
    def registry(self) -> ConceptSetRegistry:
        """jpigp の ConceptSetRegistry を構築する。"""
        assert _TAXONOMY_ROOT is not None
        return derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jpigp",
        )

    def test_returns_ifrs_industry(
        self, registry: ConceptSetRegistry,
    ) -> None:
        """T08: industries() が 'ifrs' を含む。"""
        assert "ifrs" in registry.industries()

    def test_has_pl_bs_cf(
        self, registry: ConceptSetRegistry,
    ) -> None:
        """T09: PL/BS/CF が全て存在する。"""
        cats = registry.statement_categories("ifrs")
        assert StatementCategory.INCOME_STATEMENT in cats
        assert StatementCategory.BALANCE_SHEET in cats
        assert StatementCategory.CASH_FLOW_STATEMENT in cats

    def test_pl_has_known_ifrs_concepts(
        self, registry: ConceptSetRegistry,
    ) -> None:
        """T10: PL に既知の IFRS 概念が含まれる。"""
        cs = registry.get(
            StatementType.INCOME_STATEMENT,
            consolidated=True,
            industry_code="ifrs",
        )
        assert cs is not None
        concepts = cs.non_abstract_concepts()
        assert len(concepts) > 0
        expected = {"RevenueIFRS", "ProfitLossIFRS", "OperatingProfitLossIFRS"}
        assert expected.issubset(concepts), (
            f"期待される概念が不足: {expected - concepts}"
        )

    def test_no_jppfs_cor_in_non_abstract(
        self, registry: ConceptSetRegistry,
    ) -> None:
        """T11: 非 abstract 概念に jppfs_cor 由来がない。

        jpigp の PL/BS 概念は全て jpigp_cor 由来。
        ConceptEntry.href から jppfs_cor が含まれないことを確認。
        """
        for st in (StatementType.INCOME_STATEMENT, StatementType.BALANCE_SHEET):
            cs = registry.get(
                st, consolidated=True, industry_code="ifrs",
            )
            if cs is None:
                continue
            for entry in cs.concepts:
                if entry.is_abstract:
                    continue
                assert "jppfs_cor" not in entry.href, (
                    f"jppfs_cor 由来の非 abstract 概念: {entry.concept} "
                    f"(href={entry.href})"
                )

    def test_jppfs_and_jpigp_independent(self) -> None:
        """T12: jppfs と jpigp を同時に derive しても互いに干渉しない。"""
        assert _TAXONOMY_ROOT is not None
        jppfs_reg = derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jppfs",
        )
        jpigp_reg = derive_concept_sets(
            _TAXONOMY_ROOT, use_cache=False, module_group="jpigp",
        )
        assert "ifrs" not in jppfs_reg.industries()
        assert "cai" not in jpigp_reg.industries()

    def test_get_concept_set_with_module_group_jpigp(self) -> None:
        """T15: get_concept_set で module_group='jpigp' が動作する。"""
        assert _TAXONOMY_ROOT is not None
        cs = get_concept_set(
            _TAXONOMY_ROOT,
            StatementType.INCOME_STATEMENT,
            consolidated=True,
            industry_code="ifrs",
            use_cache=False,
            module_group="jpigp",
        )
        assert cs is not None
        assert len(cs.non_abstract_concepts()) > 0


# ===================================================================
# TestCacheIFRS (T13-T14)
# ===================================================================


class TestCacheIFRS:
    """IFRS キャッシュ分離のテスト。"""

    def test_cache_path_includes_module_group(self) -> None:
        """T13: キャッシュパスに module_group が含まれる。"""
        p = Path("/some/taxonomy/root/ALL_20251101")
        assert "jppfs" in str(_cache_path(p, "jppfs"))
        assert "jpigp" in str(_cache_path(p, "jpigp"))

    def test_cache_jppfs_and_jpigp_separate_files(self) -> None:
        """T14: jppfs と jpigp のキャッシュファイルが別。"""
        p = Path("/some/taxonomy/root/ALL_20251101")
        assert _cache_path(p, "jppfs") != _cache_path(p, "jpigp")

