"""sector クロスバリデーションテスト。

全5業種モジュール間の整合性と、sector/__init__.py ルーティング、
normalize ↔ sector 接続を横断的に検証する。
"""

from __future__ import annotations

import os

import pytest

from edinet.financial.sector import (
    SectorRegistry,
    get_sector_registry,
    supported_industry_codes,
)
from edinet.financial.sector import banking, construction, insurance, railway, securities
from edinet.financial.standards import jgaap
from edinet.xbrl.taxonomy.concept_sets import ConceptSetRegistry, derive_concept_sets


# ===================================================================
# T01-T05: ルーティング検証
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestRouting:
    """sector/__init__.py のルーティング検証。"""

    def test_t01_supported_codes_non_empty(self) -> None:
        """T01: supported_industry_codes() が空でない。"""
        codes = supported_industry_codes()
        assert isinstance(codes, frozenset)
        assert len(codes) >= 5  # bk1, bk2, in1, in2, cns, rwy, sec ...

    def test_t02_all_codes_resolve(self) -> None:
        """T02: 全コードが SectorRegistry に解決される。"""
        for code in supported_industry_codes():
            reg = get_sector_registry(code)
            assert reg is not None, f"コード {code} が解決できない"
            assert isinstance(reg, SectorRegistry)

    def test_t03_unknown_code_returns_none(self) -> None:
        """T03: 未知のコードは None。"""
        assert get_sector_registry("xxx") is None

    def test_t04_banking_codes_resolve_to_banking(self) -> None:
        """T04: bk1/bk2 が banking registry に解決される。"""
        for code in ("bk1", "bk2"):
            reg = get_sector_registry(code)
            assert reg is not None
            assert reg.get_profile().sector_id == "banking"

    def test_t05_all_five_sectors_present(self) -> None:
        """T05: 5業種が全て登録されている。"""
        sector_ids = set()
        for code in supported_industry_codes():
            reg = get_sector_registry(code)
            assert reg is not None
            sector_ids.add(reg.get_profile().sector_id)
        expected = {"banking", "insurance", "construction", "railway", "securities"}
        assert sector_ids == expected


# ===================================================================
# T06-T10: general_equivalent 検証
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestGeneralEquivalent:
    """全 sector の general_equivalent 値が jgaap に存在するかの検証。"""

    @pytest.fixture()
    def jgaap_keys(self) -> frozenset[str]:
        """J-GAAP の全 canonical_key 集合。"""
        return frozenset(jgaap.all_canonical_keys())

    def test_t06_banking_general_equivalents_valid(
        self, jgaap_keys: frozenset[str],
    ) -> None:
        """T06: banking の general_equivalent が jgaap に存在する。"""
        self._check_sector(banking.registry, jgaap_keys)

    def test_t07_insurance_general_equivalents_valid(
        self, jgaap_keys: frozenset[str],
    ) -> None:
        """T07: insurance の general_equivalent が jgaap に存在する。"""
        self._check_sector(insurance.registry, jgaap_keys)

    def test_t08_construction_general_equivalents_valid(
        self, jgaap_keys: frozenset[str],
    ) -> None:
        """T08: construction の general_equivalent が jgaap に存在する。"""
        self._check_sector(construction.registry, jgaap_keys)

    def test_t09_railway_general_equivalents_valid(
        self, jgaap_keys: frozenset[str],
    ) -> None:
        """T09: railway の general_equivalent が jgaap に存在する。"""
        self._check_sector(railway.registry, jgaap_keys)

    def test_t10_securities_general_equivalents_valid(
        self, jgaap_keys: frozenset[str],
    ) -> None:
        """T10: securities の general_equivalent が jgaap に存在する。"""
        self._check_sector(securities.registry, jgaap_keys)

    @staticmethod
    def _check_sector(
        reg: SectorRegistry,
        jgaap_keys: frozenset[str],
    ) -> None:
        """sector の general_equivalent が全て jgaap canonical_key に存在するか検証。"""
        gen_map = reg.to_general_map()
        for sk, general_key in gen_map.items():
            assert general_key in jgaap_keys, (
                f"sector_key={sk} の general_equivalent="
                f"{general_key} が jgaap に存在しない"
            )


# ===================================================================
# T11-T13: profile 一貫性
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestProfileConsistency:
    """全 sector の profile 属性の一貫性検証。"""

    def test_t11_all_profiles_have_concept_suffix(self) -> None:
        """T11: 全 sector の profile に concept_suffix が設定されている。"""
        for code in supported_industry_codes():
            reg = get_sector_registry(code)
            assert reg is not None
            profile = reg.get_profile()
            assert profile.concept_suffix, (
                f"コード {code} の concept_suffix が未設定"
            )

    def test_t12_all_profiles_have_display_names(self) -> None:
        """T12: 全 sector の profile に日英表示名が設定されている。"""
        for code in supported_industry_codes():
            reg = get_sector_registry(code)
            assert reg is not None
            profile = reg.get_profile()
            assert profile.display_name_ja, f"コード {code} の display_name_ja が未設定"
            assert profile.display_name_en, f"コード {code} の display_name_en が未設定"

    def test_t13_majority_of_concepts_have_suffix(self) -> None:
        """T13: 大多数の concept に profile の concept_suffix が含まれている。

        一般事業会社と共通の科目（OrdinaryIncome 等）はサフィックスを持たないため、
        「過半数」の概念がサフィックスを含むことで業種固有性を検証する。
        """
        for code in supported_industry_codes():
            reg = get_sector_registry(code)
            assert reg is not None
            suffix = reg.get_profile().concept_suffix
            mappings = list(reg.all_mappings())
            with_suffix = [m for m in mappings if suffix in m.concept]
            # 過半数がサフィックスを含むことを検証
            assert len(with_suffix) > len(mappings) / 2, (
                f"コード {code}: サフィックス {suffix} を含む concept が"
                f" {len(with_suffix)}/{len(mappings)} で過半数未満"
            )


# ===================================================================
# T15: 業種コード排他性
# ===================================================================


@pytest.mark.small
@pytest.mark.unit
class TestIndustryCodeDisjointness:
    """異なる sector 間で industry_codes が重複しないことを検証する。"""

    def test_t15_industry_codes_are_disjoint(self) -> None:
        """T15: 各 sector の industry_codes が互いに排他的。"""
        all_registries = [
            banking.registry,
            insurance.registry,
            construction.registry,
            railway.registry,
            securities.registry,
        ]
        seen: dict[str, str] = {}  # code → sector_id
        for reg in all_registries:
            profile = reg.get_profile()
            for code in profile.industry_codes:
                assert code not in seen, (
                    f"業種コード {code!r} が {seen[code]} と "
                    f"{profile.sector_id} で重複"
                )
                seen[code] = profile.sector_id


# ===================================================================
# T16: concept 実在検証（タクソノミ Presentation Linkbase）
# ===================================================================

_TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT")
_SKIP_REASON = "EDINET_TAXONOMY_ROOT が未設定"


def _collect_xsd_concepts(taxonomy_root: str) -> frozenset[str]:
    """タクソノミ XSD から全 concept 名を抽出する。

    Presentation Linkbase には載らないが XSD に定義されている concept を
    カバーするためのフォールバック。
    """
    import re
    from pathlib import Path

    xsd_path = Path(taxonomy_root) / "taxonomy" / "jppfs"
    concepts: set[str] = set()
    pattern = re.compile(r'name="([^"]+)"')
    for xsd_file in xsd_path.rglob("*.xsd"):
        for line in xsd_file.read_text(encoding="utf-8").splitlines():
            m = pattern.search(line)
            if m:
                concepts.add(m.group(1))
    return frozenset(concepts)


@pytest.mark.skipif(_TAXONOMY_ROOT is None, reason=_SKIP_REASON)
@pytest.mark.medium
@pytest.mark.integration
class TestSectorConceptExistence:
    """sector モジュールの concept がタクソノミに実在するか検証する。

    Presentation Linkbase の ConceptSetRegistry を第一ソースとし、
    そこに無い場合は XSD 定義にフォールバックする（Definition Linkbase
    のみに出現する concept をカバーするため）。
    """

    @pytest.fixture(scope="class")
    def taxonomy_registry(self) -> ConceptSetRegistry:
        """タクソノミから ConceptSetRegistry を構築する。"""
        assert _TAXONOMY_ROOT is not None
        return derive_concept_sets(_TAXONOMY_ROOT)

    @pytest.fixture(scope="class")
    def xsd_concepts(self) -> frozenset[str]:
        """タクソノミ XSD の全 concept 名。"""
        assert _TAXONOMY_ROOT is not None
        return _collect_xsd_concepts(_TAXONOMY_ROOT)

    @pytest.mark.parametrize(
        "sector_name,industry_code",
        [
            ("banking", "bk1"),
            ("insurance", "in1"),
            ("construction", "cns"),
            ("railway", "rwy"),
            ("securities", "sec"),
        ],
    )
    def test_t16_all_concepts_exist_in_taxonomy(
        self,
        taxonomy_registry: ConceptSetRegistry,
        xsd_concepts: frozenset[str],
        sector_name: str,
        industry_code: str,
    ) -> None:
        """T16: 各 sector の全 concept がタクソノミに存在する。"""
        sector_reg = get_sector_registry(industry_code)
        assert sector_reg is not None

        # Presentation Linkbase から non-abstract concept を収集
        pres_concepts: set[str] = set()
        for cs in taxonomy_registry.all_for_industry(industry_code).values():
            pres_concepts |= cs.non_abstract_concepts()

        # 該当 industry_code に適用されるマッピングのみをフィルタ
        applicable = [
            m for m in sector_reg.all_mappings()
            if industry_code in m.industry_codes
        ]

        # Presentation Linkbase → XSD のフォールバックで検証
        missing = [
            m.concept
            for m in applicable
            if m.concept not in pres_concepts and m.concept not in xsd_concepts
        ]
        assert not missing, (
            f"{sector_name} ({industry_code}) でタクソノミに存在しない "
            f"concept: {missing}"
        )
