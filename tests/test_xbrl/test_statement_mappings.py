"""statement_mappings モジュールのテスト。

PL/BS/CF 本体の CK マッピング・正規化レイヤー・データ整合性を検証する。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from edinet.financial.standards.canonical_keys import CK
from edinet.financial.standards.statement_mappings import (
    lookup_statement,
    lookup_statement_exact,
    lookup_statement_normalized,
    normalize_concept,
    statement_concepts,
)


# ===========================================================================
# lookup_statement テスト
# ===========================================================================


class TestLookupStatement:
    """lookup_statement() の 2 段マッチングテスト。"""

    def test_jgaap_pl_exact(self) -> None:
        """J-GAAP PL の辞書完全一致。"""
        assert lookup_statement("OperatingIncome") == CK.OPERATING_INCOME
        assert lookup_statement("NetSales") == CK.REVENUE
        assert lookup_statement("GrossProfit") == CK.GROSS_PROFIT

    def test_jgaap_bs_exact(self) -> None:
        """J-GAAP BS の辞書完全一致。"""
        assert lookup_statement("Assets") == CK.TOTAL_ASSETS
        assert lookup_statement("Goodwill") == CK.GOODWILL
        assert lookup_statement("ShortTermLoansPayable") == CK.SHORT_TERM_LOANS

    def test_jgaap_cf_exact(self) -> None:
        """J-GAAP CF の辞書完全一致。"""
        assert lookup_statement("DepreciationAndAmortizationOpeCF") == CK.DEPRECIATION_CF
        assert lookup_statement("NetCashProvidedByUsedInOperatingActivities") == CK.OPERATING_CF

    def test_ifrs_pl_exact(self) -> None:
        """IFRS PL の辞書完全一致。"""
        assert lookup_statement("OperatingProfitLossIFRS") == CK.OPERATING_INCOME
        assert lookup_statement("RevenueIFRS") == CK.REVENUE

    def test_ifrs_bs_exact(self) -> None:
        """IFRS BS の辞書完全一致。"""
        assert lookup_statement("GoodwillIFRS") == CK.GOODWILL
        assert lookup_statement("AssetsIFRS") == CK.TOTAL_ASSETS

    def test_unknown_returns_none(self) -> None:
        """未登録 concept で None を返す。"""
        assert lookup_statement("CompletelyUnknownConcept") is None

    def test_summary_concept_returns_none(self) -> None:
        """SummaryOfBusinessResults 概念名は statement_mappings では返さない。"""
        assert lookup_statement_exact("NetSalesSummaryOfBusinessResults") is None


# ===========================================================================
# lookup_statement_exact / _normalized テスト
# ===========================================================================


class TestLookupStatementLayers:
    """exact / normalized レイヤーの分離テスト。"""

    def test_exact_returns_registered(self) -> None:
        """辞書に登録済みの概念名は exact で返る。"""
        assert lookup_statement_exact("OperatingIncome") == CK.OPERATING_INCOME

    def test_exact_returns_none_for_suffixed(self) -> None:
        """辞書未登録の IFRS 概念名は exact では None。"""
        # "CashAndDepositsIFRS" は辞書にない（J-GAAP は CashAndDeposits）
        # ただし CashAndCashEquivalentsIFRS は辞書にある
        assert lookup_statement_exact("SomeNewConceptIFRS") is None

    def test_normalized_strips_ifrs(self) -> None:
        """normalized は IFRS サフィックスを剥離して辞書引きする。"""
        # Goodwill は辞書にある → GoodwillIFRS は normalized で解決
        assert lookup_statement_normalized("GoodwillIFRS") == CK.GOODWILL

    def test_normalized_returns_none_for_exact_match(self) -> None:
        """辞書に完全一致する概念名は normalized では返さない。"""
        # OperatingIncome は辞書にそのままある → 剥離不要 → None
        assert lookup_statement_normalized("OperatingIncome") is None

    def test_exact_priority_over_normalized(self) -> None:
        """exact の結果は normalized に勝つ（同一 CK の場合）。"""
        # GoodwillIFRS は辞書にある（exact でヒット）
        assert lookup_statement_exact("GoodwillIFRS") == CK.GOODWILL
        # normalized でも Goodwill → CK.GOODWILL
        assert lookup_statement_normalized("GoodwillIFRS") == CK.GOODWILL
        # 両方同じ CK → exact が先に取れるので実害なし


# ===========================================================================
# normalize_concept テスト
# ===========================================================================


class TestNormalizeConcept:
    """normalize_concept() のサフィックス剥離テスト。"""

    def test_strip_ifrs(self) -> None:
        """IFRS サフィックスを剥離。"""
        assert normalize_concept("GoodwillIFRS") == "Goodwill"
        assert normalize_concept("ProfitLossIFRS") == "ProfitLoss"

    def test_strip_position_tag(self) -> None:
        """ポジションタグ（CA, CL 等）を 2 段目で剥離。"""
        assert normalize_concept("InventoriesCAIFRS") == "Inventories"
        assert normalize_concept("TradeAndOtherPayablesCLIFRS") == "TradeAndOtherPayables"

    def test_preserve_opecf(self) -> None:
        """OpeCF / InvCF / FinCF は CF 科目名の一部なので剥離しない。"""
        assert normalize_concept("DepreciationAndAmortizationOpeCFIFRS") == "DepreciationAndAmortizationOpeCF"
        assert normalize_concept("SubtotalOpeCF") == "SubtotalOpeCF"

    def test_no_suffix(self) -> None:
        """サフィックスがなければそのまま返す。"""
        assert normalize_concept("OperatingIncome") == "OperatingIncome"
        assert normalize_concept("Assets") == "Assets"

    def test_strip_summary(self) -> None:
        """SummaryOfBusinessResults サフィックスを剥離。"""
        assert normalize_concept("NetSalesSummaryOfBusinessResults") == "NetSales"
        assert normalize_concept("TotalAssetsIFRSSummaryOfBusinessResults") == "TotalAssets"

    def test_empty_string_guard(self) -> None:
        """サフィックスと完全一致する文字列は剥離しない（空文字列防止）。"""
        assert normalize_concept("IFRS") == "IFRS"
        assert normalize_concept("JGAAP") == "JGAAP"
        assert normalize_concept("USGAAP") == "USGAAP"
        assert normalize_concept("SummaryOfBusinessResults") == "SummaryOfBusinessResults"
        assert normalize_concept("CA") == "CA"


# ===========================================================================
# statement_concepts テスト
# ===========================================================================


class TestStatementConcepts:
    """statement_concepts() のテスト。"""

    def test_jgaap_pl_order(self) -> None:
        """J-GAAP PL の概念名が順序付きで返る。"""
        pl = statement_concepts("jgaap", "pl")
        assert len(pl) > 0
        assert pl[0] == "NetSales"
        assert "OperatingIncome" in pl

    def test_jgaap_bs(self) -> None:
        """J-GAAP BS の概念名が非空。"""
        bs = statement_concepts("jgaap", "bs")
        assert len(bs) > 0
        assert "Assets" in bs

    def test_ifrs_pl(self) -> None:
        """IFRS PL の概念名が非空。"""
        pl = statement_concepts("ifrs", "pl")
        assert len(pl) > 0

    def test_unknown_returns_empty(self) -> None:
        """未知の組み合わせは空タプル。"""
        assert statement_concepts("unknown", "pl") == ()
        assert statement_concepts("jgaap", "unknown") == ()


# ===========================================================================
# データ整合性テスト
# ===========================================================================


class TestDataIntegrity:
    """マッピングデータの整合性テスト。"""

    def test_all_ck_values_are_valid(self) -> None:
        """全マッピングの CK 値が CK インスタンス。"""
        from edinet.financial.standards.statement_mappings import _CONCEPT_INDEX

        for concept, ck in _CONCEPT_INDEX.items():
            assert isinstance(ck, CK), (
                f"{concept} の CK '{ck}' が CK インスタンスでない"
            )

    def test_no_duplicate_concepts_within_standard(self) -> None:
        """同一基準内で concept が重複しない。"""
        for std in ("jgaap", "ifrs"):
            for st in ("pl", "bs", "cf"):
                concepts = statement_concepts(std, st)
                assert len(concepts) == len(set(concepts)), (
                    f"{std}_{st} に重複 concept がある"
                )

    def test_jgaap_covers_core_pl(self) -> None:
        """J-GAAP PL に最低限必要な科目が含まれる。"""
        pl = set(statement_concepts("jgaap", "pl"))
        for required in ("NetSales", "CostOfSales", "GrossProfit",
                         "OperatingIncome", "OrdinaryIncome",
                         "ProfitLoss", "ProfitLossAttributableToOwnersOfParent"):
            assert required in pl, f"J-GAAP PL に {required} がない"

    def test_jgaap_covers_core_bs(self) -> None:
        """J-GAAP BS に最低限必要な科目が含まれる。"""
        bs = set(statement_concepts("jgaap", "bs"))
        for required in ("Assets", "Liabilities", "NetAssets",
                         "CurrentAssets", "NoncurrentAssets",
                         "CapitalStock", "RetainedEarnings"):
            assert required in bs, f"J-GAAP BS に {required} がない"

    def test_jgaap_covers_core_cf(self) -> None:
        """J-GAAP CF に最低限必要な科目が含まれる。"""
        cf = set(statement_concepts("jgaap", "cf"))
        for required in ("NetCashProvidedByUsedInOperatingActivities",
                         "NetCashProvidedByUsedInInvestmentActivities",
                         "NetCashProvidedByUsedInFinancingActivities",
                         "DepreciationAndAmortizationOpeCF"):
            assert required in cf, f"J-GAAP CF に {required} がない"


# ===========================================================================
# タクソノミ XSD 実在検証（EDINET_TAXONOMY_ROOT 必須）
# ===========================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_xsd_concepts(taxonomy_root: str, module_group: str) -> frozenset[str]:
    """指定モジュールグループの XSD から全 concept 名を抽出する。"""
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    root = Path(taxonomy_root) / "taxonomy" / module_group
    if not root.exists():
        return frozenset()
    for xsd_file in root.rglob("*.xsd"):
        for line in xsd_file.read_text(encoding="utf-8").splitlines():
            m = pattern.search(line)
            if m:
                concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.integration
class TestTaxonomyExistence:
    """全 statement_mappings の concept がタクソノミ XSD に実在するか検証する。

    J-GAAP は jppfs_cor、IFRS は jpigp_cor の XSD を突合する。
    ハルシネーション防止の品質ゲート。
    """

    @pytest.fixture(scope="class")
    def jppfs_concepts(self) -> frozenset[str]:
        """jppfs_cor XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts(_TAXONOMY_ROOT, "jppfs")

    @pytest.fixture(scope="class")
    def jpigp_concepts(self) -> frozenset[str]:
        """jpigp_cor XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts(_TAXONOMY_ROOT, "jpigp")

    def test_jgaap_pl_concepts_exist(self, jppfs_concepts: frozenset[str]) -> None:
        """J-GAAP PL の全 concept が jppfs_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("jgaap", "pl") if c not in jppfs_concepts]
        assert not missing, f"jppfs_cor XSD に存在しない J-GAAP PL concept: {missing}"

    def test_jgaap_bs_concepts_exist(self, jppfs_concepts: frozenset[str]) -> None:
        """J-GAAP BS の全 concept が jppfs_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("jgaap", "bs") if c not in jppfs_concepts]
        assert not missing, f"jppfs_cor XSD に存在しない J-GAAP BS concept: {missing}"

    def test_jgaap_cf_concepts_exist(self, jppfs_concepts: frozenset[str]) -> None:
        """J-GAAP CF の全 concept が jppfs_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("jgaap", "cf") if c not in jppfs_concepts]
        assert not missing, f"jppfs_cor XSD に存在しない J-GAAP CF concept: {missing}"

    def test_ifrs_pl_concepts_exist(self, jpigp_concepts: frozenset[str]) -> None:
        """IFRS PL の全 concept が jpigp_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("ifrs", "pl") if c not in jpigp_concepts]
        assert not missing, f"jpigp_cor XSD に存在しない IFRS PL concept: {missing}"

    def test_ifrs_bs_concepts_exist(self, jpigp_concepts: frozenset[str]) -> None:
        """IFRS BS の全 concept が jpigp_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("ifrs", "bs") if c not in jpigp_concepts]
        assert not missing, f"jpigp_cor XSD に存在しない IFRS BS concept: {missing}"

    def test_ifrs_cf_concepts_exist(self, jpigp_concepts: frozenset[str]) -> None:
        """IFRS CF の全 concept が jpigp_cor XSD に実在する。"""
        missing = [c for c in statement_concepts("ifrs", "cf") if c not in jpigp_concepts]
        assert not missing, f"jpigp_cor XSD に存在しない IFRS CF concept: {missing}"
