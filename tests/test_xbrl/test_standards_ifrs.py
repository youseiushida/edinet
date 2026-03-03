"""IFRS 科目定義モジュールのテスト。

Detroit 派（古典派）スタイル: 公開 API のみをテストし、
内部実装に依存しない。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from edinet.models.financial import StatementType
from edinet.financial.standards.ifrs import (
    NAMESPACE_MODULE_GROUP,
    IFRSConceptMapping,
    IFRSProfile,
    all_canonical_keys,
    all_mappings,
    canonical_key,
    get_ifrs_concept_set,
    get_profile,
    ifrs_specific_concepts,
    ifrs_to_jgaap_map,
    is_ifrs_module,
    jgaap_to_ifrs_map,
    load_ifrs_bs_concepts,
    load_ifrs_cf_concepts,
    load_ifrs_pl_concepts,
    lookup,
    mappings_for_statement,
    reverse_lookup,
)


@pytest.fixture(autouse=True)
def _clear_ifrs_cache():
    """テスト間のキャッシュ汚染を防ぐ。"""
    ifrs_to_jgaap_map.cache_clear()
    jgaap_to_ifrs_map.cache_clear()
    yield


# ===================================================================
# P0 — ルックアップ (T1-T7)
# ===================================================================


class TestLookup:
    """lookup / canonical_key / reverse_lookup のテスト。"""

    def test_lookup_revenue_ifrs(self) -> None:
        """T1: lookup("RevenueIFRS") が正しい IFRSConceptMapping を返す。"""
        m = lookup("RevenueIFRS")
        assert m is not None
        assert isinstance(m, IFRSConceptMapping)
        assert m.canonical_key == "revenue"
        assert m.statement_type == StatementType.INCOME_STATEMENT

    def test_lookup_operating_profit_loss_ifrs(self) -> None:
        """T2: lookup("OperatingProfitLossIFRS") の canonical_key が正しい。"""
        m = lookup("OperatingProfitLossIFRS")
        assert m is not None
        assert m.canonical_key == "operating_income"

    def test_lookup_unknown_returns_none(self) -> None:
        """T3: 未登録の concept は None を返す。"""
        assert lookup("UnknownConcept") is None

    def test_canonical_key_returns_string(self) -> None:
        """T4: canonical_key() が正規化キー文字列を返す。"""
        result = canonical_key("RevenueIFRS")
        assert result == "revenue"

    def test_canonical_key_unknown_returns_none(self) -> None:
        """T5: 未登録 concept の canonical_key は None。"""
        assert canonical_key("Unknown") is None

    def test_reverse_lookup_revenue(self) -> None:
        """T6: reverse_lookup("revenue") が RevenueIFRS を返す。"""
        m = reverse_lookup("revenue")
        assert m is not None
        assert isinstance(m, IFRSConceptMapping)
        assert m.concept == "RevenueIFRS"

    def test_reverse_lookup_unknown_returns_none(self) -> None:
        """T7: 未登録キーの reverse_lookup は None。"""
        assert reverse_lookup("unknown_key") is None


# ===================================================================
# P0 — 一覧取得 (T8-T12)
# ===================================================================


class TestMappingsForStatement:
    """mappings_for_statement のテスト。"""

    def test_mappings_for_pl(self) -> None:
        """T8: PL マッピングは 15 件。"""
        pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
        assert len(pl) == 15

    def test_mappings_for_bs(self) -> None:
        """T9: BS マッピングは 19 件。"""
        bs = mappings_for_statement(StatementType.BALANCE_SHEET)
        assert len(bs) == 19

    def test_mappings_for_cf(self) -> None:
        """T10: CF マッピングは 16 件（合計行 5 + 営業内訳 8 + 投資内訳 1 + 財務内訳 2）。"""
        cf = mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
        assert len(cf) == 16

    def test_concept_names_are_unique_per_statement(self) -> None:
        """T11: 同一 statement_type 内で concept 名が重複しない。"""
        for st in StatementType:
            mappings = mappings_for_statement(st)
            concepts = [m.concept for m in mappings]
            assert len(concepts) == len(set(concepts)), (
                f"{st.value} に concept 名の重複があります"
            )

    def test_mappings_for_statement_subset_of_all(self) -> None:
        """T12: 各 statement の mappings_for_statement() が all_mappings() のサブセット。"""
        all_set = set(all_mappings())
        for st in StatementType:
            mappings = mappings_for_statement(st)
            assert set(mappings).issubset(all_set), (
                f"{st.value} の mappings_for_statement() が all_mappings() のサブセットでない"
            )


# ===================================================================
# P0 — 科目セット (T13-T16)
# ===================================================================


class TestConceptSet:
    """get_ifrs_concept_set のテスト。"""

    def test_get_ifrs_concept_set_is_frozenset(self) -> None:
        """T13: 戻り値が frozenset[str]。"""
        result = get_ifrs_concept_set(StatementType.INCOME_STATEMENT)
        assert isinstance(result, frozenset)

    def test_ifrs_pl_concept_set_contains_revenue(self) -> None:
        """T14: PL の concept セットに RevenueIFRS が含まれる。"""
        pl_set = get_ifrs_concept_set(StatementType.INCOME_STATEMENT)
        assert "RevenueIFRS" in pl_set

    def test_ifrs_pl_concept_set_not_contains_ordinary_income(self) -> None:
        """T15: PL の concept セットに OrdinaryIncome（J-GAAP 固有）が含まれない。"""
        pl_set = get_ifrs_concept_set(StatementType.INCOME_STATEMENT)
        assert "OrdinaryIncome" not in pl_set

    def test_ifrs_bs_concept_set_contains_equity(self) -> None:
        """T16: BS の concept セットに EquityIFRS が含まれる。"""
        bs_set = get_ifrs_concept_set(StatementType.BALANCE_SHEET)
        assert "EquityIFRS" in bs_set


# ===================================================================
# P0 — IFRS ↔ J-GAAP マッピング (T17-T21)
# ===================================================================


class TestIFRSJGAAPMapping:
    """IFRS ↔ J-GAAP の双方向マッピングのテスト。"""

    def test_ifrs_to_jgaap_revenue(self) -> None:
        """T17: RevenueIFRS → NetSales。"""
        m = ifrs_to_jgaap_map()
        assert m["RevenueIFRS"] == "NetSales"

    def test_ifrs_to_jgaap_finance_income_is_none(self) -> None:
        """T18: FinanceIncomeIFRS → None（IFRS 固有）。"""
        m = ifrs_to_jgaap_map()
        assert m["FinanceIncomeIFRS"] is None

    def test_jgaap_to_ifrs_net_sales(self) -> None:
        """T19: NetSales → RevenueIFRS。"""
        m = jgaap_to_ifrs_map()
        assert m["NetSales"] == "RevenueIFRS"

    def test_jgaap_to_ifrs_ordinary_income_is_none(self) -> None:
        """T20: OrdinaryIncome → None（J-GAAP 固有）。"""
        m = jgaap_to_ifrs_map()
        assert m["OrdinaryIncome"] is None

    def test_mapping_bidirectional_consistency(self) -> None:
        """T21: IFRS→J-GAAP と J-GAAP→IFRS の双方向整合性。

        ifrs_to_jgaap(x) == y なら jgaap_to_ifrs(y) == x（None でない場合）。
        加えて IFRS 固有科目が jgaap_to_ifrs のキーに含まれないことも検証。
        """
        i2j = ifrs_to_jgaap_map()
        j2i = jgaap_to_ifrs_map()

        for ifrs_concept, jgaap_concept in i2j.items():
            if jgaap_concept is not None:
                assert j2i.get(jgaap_concept) == ifrs_concept, (
                    f"双方向不整合: {ifrs_concept} → {jgaap_concept} だが "
                    f"逆引きは {j2i.get(jgaap_concept)}"
                )

        # IFRS 固有科目（ifrs_to_jgaap が None）の concept 名が
        # jgaap_to_ifrs のキーに含まれないことを検証（L-3）
        ifrs_specific_concept_names = {
            c for c, j in i2j.items() if j is None
        }
        for concept_name in ifrs_specific_concept_names:
            assert concept_name not in j2i, (
                f"IFRS 固有科目 {concept_name} が jgaap_to_ifrs のキーに含まれています"
            )


# ===================================================================
# P0 — 定数・プロファイル (T22-T27)
# ===================================================================


class TestConstantsAndProfile:
    """NAMESPACE_MODULE_GROUP, is_ifrs_module, get_profile のテスト。"""

    def test_namespace_module_group_is_jpigp(self) -> None:
        """T22: NAMESPACE_MODULE_GROUP が "jpigp"。"""
        assert NAMESPACE_MODULE_GROUP == "jpigp"

    def test_is_ifrs_module_jpigp(self) -> None:
        """T23: is_ifrs_module("jpigp") → True。"""
        assert is_ifrs_module("jpigp") is True

    def test_is_ifrs_module_jppfs(self) -> None:
        """T24: is_ifrs_module("jppfs") → False。"""
        assert is_ifrs_module("jppfs") is False

    def test_profile_standard_id(self) -> None:
        """T25: プロファイルの standard_id が "ifrs"。"""
        profile = get_profile()
        assert isinstance(profile, IFRSProfile)
        assert profile.standard_id == "ifrs"

    def test_profile_has_ordinary_income_false(self) -> None:
        """T26: IFRS には経常利益がない。"""
        assert get_profile().has_ordinary_income is False

    def test_profile_has_extraordinary_items_false(self) -> None:
        """T27: IFRS には特別利益/損失がない。"""
        assert get_profile().has_extraordinary_items is False


# ===================================================================
# P1 — IFRS 構造的特徴 (T32-T36)
# ===================================================================


class TestIFRSStructuralFeatures:
    """IFRS PL/BS の構造的差異の検証。"""

    def test_ifrs_pl_no_ordinary_income_concept(self) -> None:
        """T32: IFRS PL に "Ordinary" を含む concept がない。"""
        pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
        for m in pl:
            assert "Ordinary" not in m.concept, (
                f"IFRS PL に OrdinaryIncome 系の concept があります: {m.concept}"
            )

    def test_ifrs_pl_no_extraordinary_concepts(self) -> None:
        """T33: IFRS PL に "Extraordinary" を含む concept がない。"""
        pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
        for m in pl:
            assert "Extraordinary" not in m.concept, (
                f"IFRS PL に Extraordinary 系の concept があります: {m.concept}"
            )

    def test_ifrs_pl_has_finance_income_and_costs(self) -> None:
        """T34: IFRS PL に金融収益/費用が存在し is_ifrs_specific=True。"""
        pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
        finance_income = [m for m in pl if m.canonical_key == "finance_income"]
        finance_costs = [m for m in pl if m.canonical_key == "finance_costs"]
        assert len(finance_income) == 1
        assert finance_income[0].is_ifrs_specific is True
        assert len(finance_costs) == 1
        assert finance_costs[0].is_ifrs_specific is True

    def test_ifrs_pl_has_profit_before_tax(self) -> None:
        """T35: IFRS PL に税引前利益が存在する。"""
        pl = mappings_for_statement(StatementType.INCOME_STATEMENT)
        pbt = [m for m in pl if m.canonical_key == "income_before_tax"]
        assert len(pbt) == 1
        assert pbt[0].concept == "ProfitLossBeforeTaxIFRS"

    def test_ifrs_bs_uses_equity_not_net_assets_concept(self) -> None:
        """T36: IFRS BS に EquityIFRS が存在し NetAssets concept は存在しない。"""
        bs = mappings_for_statement(StatementType.BALANCE_SHEET)
        concepts = [m.concept for m in bs]
        assert "EquityIFRS" in concepts
        assert "NetAssets" not in concepts


# ===================================================================
# P1 — データ整合性 (T37-T43)
# ===================================================================


class TestDataIntegrity:
    """マッピングデータの整合性テスト。"""

    def test_all_concepts_unique(self) -> None:
        """T37: 全 concept ローカル名がユニーク。"""
        concepts = [m.concept for m in all_mappings()]
        assert len(concepts) == len(set(concepts))

    def test_all_concepts_nonempty(self) -> None:
        """T38: 全 mapping の concept / canonical_key が空文字列でない。"""
        for m in all_mappings():
            assert m.concept, "concept が空です"
            assert m.canonical_key, f"{m.concept} の canonical_key が空です"



# ===================================================================
# P1b — CK インスタンステスト
# ===================================================================


class TestCKInstances:
    """全 canonical_key が CK StrEnum のインスタンスであることを検証する。"""

    def test_all_canonical_keys_are_ck_instances(self) -> None:
        """全マッピングの canonical_key が CK インスタンス。"""
        from edinet.financial.standards.canonical_keys import CK

        for m in all_mappings():
            assert isinstance(m.canonical_key, CK), (
                f"{m.concept} の canonical_key '{m.canonical_key}' が "
                f"CK インスタンスでない"
            )


# ===================================================================
# P1 — parametrize テスト (T44-T45)
# ===================================================================


class TestParametrized:
    """parametrize を使用したテスト。"""

    @pytest.mark.parametrize(
        "st",
        [
            StatementType.INCOME_STATEMENT,
            StatementType.BALANCE_SHEET,
            StatementType.CASH_FLOW_STATEMENT,
        ],
    )
    def test_mappings_for_all_statement_types(self, st: StatementType) -> None:
        """T44: 全 StatementType で mappings_for_statement が正しく返される。"""
        result = mappings_for_statement(st)
        assert isinstance(result, tuple)
        assert len(result) > 0
        for m in result:
            assert isinstance(m, IFRSConceptMapping)
            assert m.statement_type == st

    @pytest.mark.parametrize(
        "jgaap_concept",
        [
            # Lane 3 is_jgaap_specific=True の 5 概念
            "OrdinaryIncome",
            "NonOperatingIncome",
            "NonOperatingExpenses",
            "ExtraordinaryIncome",
            "ExtraordinaryLoss",
            # IFRS 非対応（is_jgaap_specific=False だが IFRS に独立 concept なし）
            "IncomeTaxesDeferred",
            "DeferredAssets",
            "LiabilitiesAndNetAssets",
        ],
    )
    def test_jgaap_only_concepts_map_to_none(
        self, jgaap_concept: str
    ) -> None:
        """T45: J-GAAP 固有科目が jgaap_to_ifrs_map() で None にマッピングされる。"""
        m = jgaap_to_ifrs_map()
        assert jgaap_concept in m
        assert m[jgaap_concept] is None


# ===================================================================
# P1 — CF period_type (T46-T47)
# ===================================================================


class TestCFPeriodType:
    """CF に関するテスト。"""

    def test_cash_beginning_end_not_in_ifrs(self) -> None:
        """T47: IFRS CF には cash_beginning / cash_end の canonical_key がない。

        IFRS では期首/期末の現金残高は BS の CashAndCashEquivalentsIFRS で
        表現されるため、CF セクションに独立 concept が存在しない。
        この設計判断のドキュメンテーションテスト。
        """
        cf_keys = {
            m.canonical_key
            for m in mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
        }
        assert "cash_beginning" not in cf_keys
        assert "cash_end" not in cf_keys


# ===================================================================
# 追加テスト — all_mappings / all_canonical_keys / ifrs_specific
# ===================================================================


class TestAllMappingsAndKeys:
    """all_mappings, all_canonical_keys, ifrs_specific_concepts のテスト。"""

    def test_all_mappings_count(self) -> None:
        """全マッピングの総数が PL + BS + CF + KPI/CI の合計（55 件）。"""
        total = all_mappings()
        pl_count = len(mappings_for_statement(StatementType.INCOME_STATEMENT))
        bs_count = len(mappings_for_statement(StatementType.BALANCE_SHEET))
        cf_count = len(
            mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
        )
        kpi_ci_count = len([m for m in total if m.statement_type is None])
        assert len(total) == pl_count + bs_count + cf_count + kpi_ci_count
        assert len(total) == 65  # 55 (詳細) + 10 (SummaryOfBusinessResults)

    def test_all_canonical_keys_is_frozenset(self) -> None:
        """all_canonical_keys() が frozenset を返す。"""
        keys = all_canonical_keys()
        assert isinstance(keys, frozenset)

    def test_all_canonical_keys_count(self) -> None:
        """all_canonical_keys() の数（サマリーと詳細で重複があるため mappings 数より少ない）。"""
        assert len(all_canonical_keys()) == 55  # ユニークな CK 数は変わらない
        assert len(all_mappings()) == 65  # concept 数は 65

    def test_ifrs_specific_concepts_are_marked(self) -> None:
        """ifrs_specific_concepts() が is_ifrs_specific=True のみ含む。"""
        specifics = ifrs_specific_concepts()
        assert len(specifics) > 0
        for m in specifics:
            assert m.is_ifrs_specific is True

    def test_ifrs_specific_includes_finance_income(self) -> None:
        """IFRS 固有科目に金融収益が含まれる。"""
        concepts = {m.concept for m in ifrs_specific_concepts()}
        assert "FinanceIncomeIFRS" in concepts
        assert "FinanceCostsIFRS" in concepts

    def test_profile_canonical_key_count(self) -> None:
        """プロファイルの canonical_key_count が実データと一致。"""
        profile = get_profile()
        assert profile.canonical_key_count == len(all_mappings())

    def test_profile_module_groups(self) -> None:
        """プロファイルの module_groups が frozenset({"jpigp"})。"""
        profile = get_profile()
        assert profile.module_groups == frozenset({"jpigp"})

    def test_convenience_functions_match_mappings_for_statement(self) -> None:
        """便利関数が mappings_for_statement と同じ結果を返す。"""
        assert load_ifrs_pl_concepts() == mappings_for_statement(
            StatementType.INCOME_STATEMENT
        )
        assert load_ifrs_bs_concepts() == mappings_for_statement(
            StatementType.BALANCE_SHEET
        )
        assert load_ifrs_cf_concepts() == mappings_for_statement(
            StatementType.CASH_FLOW_STATEMENT
        )


# ===========================================================================
# P2: JGAAP_ONLY_CONCEPTS クロスバリデーション
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestJGAAPOnlyConcepts:
    """_JGAAP_ONLY_CONCEPTS の整合性を検証する。"""

    def test_jgaap_only_concepts_exist_in_jgaap(self) -> None:
        """jgaap_to_ifrs_map() の None エントリが jgaap の known concepts に存在する。

        _JGAAP_ONLY_CONCEPTS のタイポ防止。
        """
        from edinet.financial.standards import jgaap as jgaap_mod

        # jgaap の全 concept を収集
        jgaap_concepts = {m.concept for m in jgaap_mod.all_mappings()}

        # jgaap_to_ifrs_map で None にマッピングされている concept が
        # jgaap の既知 concept に存在するか検証
        j2i = jgaap_to_ifrs_map()
        jgaap_only = [k for k, v in j2i.items() if v is None]
        assert len(jgaap_only) > 0, "JGAAP-only concept が 0 件"

        missing = [c for c in jgaap_only if c not in jgaap_concepts]
        assert not missing, (
            f"jgaap_to_ifrs_map で None にマッピングされているが "
            f"jgaap に存在しない concept: {missing}"
        )


# ===========================================================================
# タクソノミ実在検証（EDINET_TAXONOMY_ROOT 必須）
# ===========================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_xsd_concepts_ifrs(taxonomy_root: str) -> frozenset[str]:
    """jpigp_cor の XSD から全 concept 名を抽出する。"""
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    target = Path(taxonomy_root) / "taxonomy" / "jpigp"
    if not target.exists():
        return frozenset()
    for xsd_file in target.rglob("*.xsd"):
        for line in xsd_file.read_text(encoding="utf-8").splitlines():
            m = pattern.search(line)
            if m:
                concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.medium
@pytest.mark.integration
class TestTaxonomyExistence:
    """IFRS マッピングの全 concept がタクソノミ XSD に実在するか検証する。

    ハルシネーション防止のための品質ゲート。
    EDINET_TAXONOMY_ROOT 環境変数が設定されている場合のみ実行される。
    """

    @pytest.fixture(scope="class")
    def xsd_concepts(self) -> frozenset[str]:
        """タクソノミ XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts_ifrs(_TAXONOMY_ROOT)

    def test_all_ifrs_concepts_exist_in_taxonomy(
        self,
        xsd_concepts: frozenset[str],
    ) -> None:
        """全 IFRS concept がタクソノミ XSD に実在する。"""
        missing = [
            m.concept
            for m in all_mappings()
            if m.concept not in xsd_concepts
        ]
        assert not missing, (
            f"タクソノミ XSD に存在しない IFRS concept: {missing}"
        )

    def test_pl_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """PL concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.INCOME_STATEMENT)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"PL で不在: {missing}"

    def test_bs_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """BS concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.BALANCE_SHEET)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"BS で不在: {missing}"

    def test_cf_concepts_exist(self, xsd_concepts: frozenset[str]) -> None:
        """CF concept が全てタクソノミに実在する。"""
        missing = [
            m.concept
            for m in mappings_for_statement(StatementType.CASH_FLOW_STATEMENT)
            if m.concept not in xsd_concepts
        ]
        assert not missing, f"CF で不在: {missing}"
