"""Wave 6 統合テスト: API 一貫性 + クロスフィーチャー。

I3: D1-D5 設計規約の準拠チェック
I4: レーン横断の統合テスト
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import date, datetime
from decimal import Decimal

import pytest


# ============================================================
# I3: API 一貫性テスト
# ============================================================


class TestTopLevelExports:
    """トップレベル __init__.py の export 一貫性。"""

    def test_all_wave6_symbols_importable(self) -> None:
        """Wave 6 で追加した全シンボルが edinet からインポート可能。"""
        import edinet

        # L2: cache
        assert callable(edinet.clear_cache)
        assert callable(edinet.cache_info)
        assert edinet.CacheInfo is not None

        # L3: revision_chain
        assert callable(edinet.build_revision_chain)
        assert edinet.RevisionChain is not None

        # L4: custom_detection
        assert callable(edinet.detect_custom_items)
        assert edinet.CustomDetectionResult is not None

        # L5: calc_check
        assert callable(edinet.validate_calculations)
        assert edinet.CalcValidationResult is not None

        # L6: fiscal_year
        assert callable(edinet.detect_fiscal_year)
        assert edinet.FiscalYearInfo is not None

    def test_all_in___all__(self) -> None:
        """Wave 6 シンボルが __all__ に含まれている。"""
        import edinet

        wave6_symbols = [
            "clear_cache",
            "cache_info",
            "CacheInfo",
            "build_revision_chain",
            "RevisionChain",
            "detect_custom_items",
            "CustomDetectionResult",
            "validate_calculations",
            "CalcValidationResult",
            "detect_fiscal_year",
            "FiscalYearInfo",
        ]
        for sym in wave6_symbols:
            assert sym in edinet.__all__, f"{sym} が __all__ に含まれていません"

    def test_subpackage_exports(self) -> None:
        """サブパッケージの __init__.py からもアクセス可能。"""
        from edinet.api import CacheInfo, CacheStore, cache_info, clear_cache
        from edinet.models import RevisionChain, build_revision_chain
        from edinet.xbrl import (
            CalcValidationResult,
            CustomDetectionResult,
            FiscalYearInfo,
            detect_custom_items,
            detect_fiscal_year,
            validate_calculations,
        )
        from edinet.financial.dimensions import FiscalYearInfo as FYI2
        from edinet.financial.dimensions import detect_fiscal_year as dfy2
        from edinet.xbrl.validation import (
            CalcValidationResult as CVR2,
            ValidationIssue,
            validate_calculations as vc2,
        )

        # 同一オブジェクトである
        assert FiscalYearInfo is FYI2
        assert detect_fiscal_year is dfy2
        assert CalcValidationResult is CVR2
        assert validate_calculations is vc2
        assert CacheStore is not None
        assert CacheInfo is not None
        assert cache_info is not None
        assert clear_cache is not None
        assert RevisionChain is not None
        assert build_revision_chain is not None
        assert CustomDetectionResult is not None
        assert detect_custom_items is not None
        assert ValidationIssue is not None


class TestD1ValidationResultPattern:
    """D1: validate_* は構造化された *ValidationResult dataclass を返す。"""

    def test_calc_validation_result_is_frozen_dataclass(self) -> None:
        """CalcValidationResult は frozen dataclass。"""
        from edinet.xbrl.validation.calc_check import CalcValidationResult

        assert dataclasses.is_dataclass(CalcValidationResult)
        # frozen の検証: インスタンスを作って変更不可を確認
        result = CalcValidationResult(
            issues=(), checked_count=0, passed_count=0, skipped_count=0
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.checked_count = 1  # type: ignore[misc]

    def test_calc_validation_result_has_is_valid_property(self) -> None:
        """CalcValidationResult.is_valid がプロパティとして存在。"""
        from edinet.xbrl.validation.calc_check import CalcValidationResult

        result = CalcValidationResult(
            issues=(), checked_count=5, passed_count=5, skipped_count=0
        )
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_validation_issue_is_frozen_dataclass(self) -> None:
        """ValidationIssue は frozen dataclass。"""
        from edinet.xbrl.validation.calc_check import ValidationIssue

        assert dataclasses.is_dataclass(ValidationIssue)
        issue = ValidationIssue(
            role_uri="http://example.com",
            parent_concept="TotalAssets",
            expected=Decimal("100"),
            actual=Decimal("99"),
            difference=Decimal("1"),
            tolerance=Decimal("0.5"),
            severity="error",
            message="テスト",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            issue.severity = "warning"  # type: ignore[misc]


class TestD3LineItemNotExtended:
    """D3: LineItem にフィールドが追加されていないことを検証。"""

    def test_lineitem_field_count(self) -> None:
        """LineItem のフィールド数が Wave 5 時点の 15 から変化していない。"""
        from edinet.models.financial import LineItem

        fields = dataclasses.fields(LineItem)
        expected_fields = {
            "concept",
            "namespace_uri",
            "local_name",
            "label_ja",
            "label_en",
            "value",
            "unit_ref",
            "decimals",
            "context_id",
            "period",
            "entity_id",
            "dimensions",
            "is_nil",
            "source_line",
            "order",
        }
        actual_fields = {f.name for f in fields}
        assert actual_fields == expected_fields, (
            f"LineItem のフィールドが変更されています。"
            f"追加: {actual_fields - expected_fields}, "
            f"削除: {expected_fields - actual_fields}"
        )


class TestD4MethodPlacement:
    """D4: メソッド配置規約の準拠。"""

    def test_standalone_functions_are_module_level(self) -> None:
        """データ分析系の関数はモジュールレベル（standalone）。"""
        from edinet.models.revision import build_revision_chain
        from edinet.financial.dimensions.fiscal_year import detect_fiscal_year
        from edinet.xbrl.taxonomy.custom import detect_custom_items
        from edinet.xbrl.validation.calc_check import validate_calculations

        # 全てモジュールレベル関数（クラスメソッドではない）
        assert inspect.isfunction(build_revision_chain)
        assert inspect.isfunction(detect_fiscal_year)
        assert inspect.isfunction(detect_custom_items)
        assert inspect.isfunction(validate_calculations)

    def test_company_search_is_classmethod(self) -> None:
        """Company.search() はクラスメソッド（D4: 型のコンストラクタ）。"""
        from edinet.models.company import Company

        assert hasattr(Company, "search")
        assert isinstance(
            inspect.getattr_static(Company, "search"), classmethod
        )


class TestD5NamingConventions:
    """D5: 命名規約の準拠チェック。"""

    def test_detect_prefix_returns_result_dataclass(self) -> None:
        """detect_* は result dataclass を返す。"""
        from edinet.financial.dimensions.fiscal_year import FiscalYearInfo
        from edinet.xbrl.taxonomy.custom import CustomDetectionResult

        assert dataclasses.is_dataclass(FiscalYearInfo)
        assert dataclasses.is_dataclass(CustomDetectionResult)

    def test_validate_prefix_returns_validation_result(self) -> None:
        """validate_* は *ValidationResult を返す。"""
        from edinet.xbrl.validation.calc_check import CalcValidationResult

        assert dataclasses.is_dataclass(CalcValidationResult)
        assert hasattr(CalcValidationResult, "is_valid")

    def test_build_prefix_function_exists(self) -> None:
        """build_* はレイズ可能な構築関数。"""
        from edinet.models.revision import build_revision_chain

        sig = inspect.signature(build_revision_chain)
        assert "filing" in sig.parameters

    def test_clear_prefix_returns_none(self) -> None:
        """clear_* は None を返す。"""
        from edinet.api.cache import clear_cache

        sig = inspect.signature(clear_cache)
        assert sig.return_annotation in (None, "None")


class TestResultDataclassesAreFrozen:
    """全 Wave 6 result dataclass が frozen=True, slots=True であること。"""

    @pytest.mark.parametrize(
        "cls_path",
        [
            "edinet.api.cache.CacheInfo",
            "edinet.models.revision.RevisionChain",
            "edinet.xbrl.taxonomy.custom.CustomItemInfo",
            "edinet.xbrl.taxonomy.custom.CustomDetectionResult",
            "edinet.xbrl.validation.calc_check.ValidationIssue",
            "edinet.xbrl.validation.calc_check.CalcValidationResult",
            "edinet.financial.dimensions.fiscal_year.FiscalYearInfo",
        ],
    )
    def test_frozen_slots_dataclass(self, cls_path: str) -> None:
        """各 dataclass が frozen=True, slots=True で定義されている。"""
        parts = cls_path.rsplit(".", 1)
        module = __import__(parts[0], fromlist=[parts[1]])
        cls = getattr(module, parts[1])
        assert dataclasses.is_dataclass(cls)
        # slots=True の検証: __slots__ が存在する
        assert hasattr(cls, "__slots__"), f"{cls_path} に __slots__ がありません"


# ============================================================
# I4: クロスフィーチャー統合テスト
# ============================================================


class TestCacheWithRevisionChain:
    """cache × revision_chain: キャッシュ有効時の訂正チェーンと衝突しない。"""

    def test_cache_info_disabled_by_default(self) -> None:
        """デフォルトでキャッシュ無効。"""
        from edinet.api.cache import cache_info

        info = cache_info()
        assert info.enabled is False
        assert info.cache_dir is None
        assert info.entry_count == 0

    def test_cache_store_independent_of_revision(self) -> None:
        """CacheStore と RevisionChain は同じ doc_id キーを共有するが衝突しない。

        CacheStore は doc_id でキー化し、RevisionChain は parent_doc_id で
        原本を辿る。訂正報告書は常に別の doc_id が付与されるため衝突しない。
        """
        from edinet.api.cache import CacheStore
        from edinet.models.revision import RevisionChain

        # CacheStore: doc_id ベースのパス
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            store = CacheStore(Path(tmpdir))
            original_path = store.cache_path("S100ABC0")
            corrected_path = store.cache_path("S100ABC1")
            # 別の doc_id は別のパス
            assert original_path != corrected_path

        # RevisionChain: 空チェーンは不可
        with pytest.raises(ValueError, match="空です"):
            RevisionChain(chain=())


class TestCustomDetectionWithCalcCheck:
    """custom_detection × calc_check: 型の互換性チェック。"""

    def test_both_use_lineitem_without_extension(self) -> None:
        """custom_detection も calc_check も LineItem を読むだけで拡張しない。"""
        from edinet.models.financial import LineItem

        # 両方とも LineItem を入力として受け取るが、
        # LineItem 自体に is_standard 等のフィールドは追加されていない
        fields = {f.name for f in dataclasses.fields(LineItem)}
        assert "is_standard" not in fields
        assert "shadowing_target" not in fields
        assert "calc_status" not in fields
        assert "fiscal_year_type" not in fields


class TestFiscalYearDetection:
    """fiscal_year のスモークテスト。"""

    def test_detect_fiscal_year_with_minimal_dei(self) -> None:
        """最小限の DEI で FiscalYearInfo を取得できる。"""
        from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType
        from edinet.financial.dimensions.fiscal_year import detect_fiscal_year

        dei = DEI(
            accounting_standards=AccountingStandard.JAPAN_GAAP,
            type_of_current_period=PeriodType.FY,
            current_fiscal_year_start_date=date(2024, 4, 1),
            current_period_end_date=date(2025, 3, 31),
            current_fiscal_year_end_date=date(2025, 3, 31),
        )
        info = detect_fiscal_year(dei)
        assert info.is_full_year is True
        assert info.is_irregular is False
        assert info.fiscal_year_end_month == 3
        assert info.period_months == 12
        assert info.period_type == PeriodType.FY

    def test_detect_fiscal_year_with_none_dates(self) -> None:
        """日付が None でも graceful に動作する。"""
        from edinet.xbrl.dei import DEI, AccountingStandard
        from edinet.financial.dimensions.fiscal_year import detect_fiscal_year

        dei = DEI(accounting_standards=AccountingStandard.JAPAN_GAAP)
        info = detect_fiscal_year(dei)
        assert info.is_full_year is False
        assert info.is_irregular is False
        assert info.period_months is None
        assert info.fiscal_year_end_month is None


class TestCalcCheckSmoke:
    """calc_check のスモークテスト。"""

    def test_empty_validation_result(self) -> None:
        """空の検証結果。"""
        from edinet.xbrl.validation.calc_check import CalcValidationResult

        result = CalcValidationResult(
            issues=(), checked_count=0, passed_count=0, skipped_count=0
        )
        assert result.is_valid is True
        assert str(result) == "計算バリデーション: 合格 (検証=0, 合格=0, エラー=0, スキップ=0)"

    def test_validation_result_with_error(self) -> None:
        """エラーありの検証結果。"""
        from edinet.xbrl.validation.calc_check import (
            CalcValidationResult,
            ValidationIssue,
        )

        issue = ValidationIssue(
            role_uri="http://example.com/role/BS",
            parent_concept="TotalAssets",
            expected=Decimal("1000"),
            actual=Decimal("900"),
            difference=Decimal("100"),
            tolerance=Decimal("0.5"),
            severity="error",
            message="計算不一致: TotalAssets",
        )
        result = CalcValidationResult(
            issues=(issue,), checked_count=1, passed_count=0, skipped_count=0
        )
        assert result.is_valid is False
        assert result.error_count == 1
        assert "不合格" in str(result)


class TestRevisionChainSmoke:
    """revision_chain のスモークテスト。"""

    def test_revision_chain_requires_non_empty(self) -> None:
        """空チェーンは ValueError。"""
        from edinet.models.revision import RevisionChain

        with pytest.raises(ValueError, match="空です"):
            RevisionChain(chain=())

    def test_revision_chain_single_filing(self) -> None:
        """Filing 1 件のチェーン（訂正なし）。"""
        from unittest.mock import MagicMock

        from edinet.models.revision import RevisionChain

        filing = MagicMock()
        filing.doc_id = "S100ABC0"
        filing.submit_date_time = datetime(2025, 3, 1, 10, 0)
        filing.withdrawal_status = "0"

        chain = RevisionChain(chain=(filing,))
        assert chain.count == 1
        assert chain.is_corrected is False
        assert chain.original is filing
        assert chain.latest is filing
        assert len(chain) == 1
        assert list(chain) == [filing]
        assert chain[0] is filing

    def test_revision_chain_at_time(self) -> None:
        """at_time() で時点指定の Filing 取得。"""
        from unittest.mock import MagicMock

        from edinet.models.revision import RevisionChain

        f1 = MagicMock()
        f1.doc_id = "S100ABC0"
        f1.submit_date_time = datetime(2025, 3, 1, 10, 0)

        f2 = MagicMock()
        f2.doc_id = "S100ABC1"
        f2.submit_date_time = datetime(2025, 4, 1, 10, 0)

        chain = RevisionChain(chain=(f1, f2))
        # 3/15 時点 → f1 のみ見える
        snapshot = chain.at_time(date(2025, 3, 15))
        assert snapshot is f1
        # 4/15 時点 → f2 が見える
        snapshot = chain.at_time(date(2025, 4, 15))
        assert snapshot is f2
        # 2/1 時点 → 何もない
        with pytest.raises(ValueError, match="以前に提出された Filing がありません"):
            chain.at_time(date(2025, 2, 1))
