"""Parquet 永続化・復元のラウンドトリップテスト。"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")

from edinet.extension import export_parquet, import_parquet  # noqa: E402
from edinet.financial.statements import Statements  # noqa: E402
from edinet.models.filing import Filing  # noqa: E402
from edinet.models.financial import LineItem  # noqa: E402
from edinet.xbrl.contexts import (  # noqa: E402
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType  # noqa: E402
from edinet.xbrl.linkbase.calculation import (  # noqa: E402
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource  # noqa: E402


# ---------------------------------------------------------------------------
# テストフィクスチャ
# ---------------------------------------------------------------------------


def _make_filing(
    doc_id: str = "S100TEST",
    has_xbrl: bool = True,
) -> Filing:
    """テスト用 Filing を構築する。"""
    return Filing.from_api_response(
        {
            "seqNumber": 1,
            "docID": doc_id,
            "docTypeCode": "120",
            "ordinanceCode": "010",
            "formCode": "030000",
            "edinetCode": "E00001",
            "secCode": "12340",
            "JCN": "1234567890123",
            "filerName": "テスト株式会社",
            "fundCode": None,
            "submitDateTime": "2026-03-01 10:00",
            "periodStart": "2025-04-01",
            "periodEnd": "2026-03-31",
            "docDescription": "有価証券報告書",
            "issuerEdinetCode": None,
            "subjectEdinetCode": None,
            "subsidiaryEdinetCode": None,
            "currentReportReason": None,
            "parentDocID": None,
            "opeDateTime": None,
            "withdrawalStatus": "0",
            "docInfoEditStatus": "0",
            "disclosureStatus": "0",
            "xbrlFlag": "1" if has_xbrl else "0",
            "pdfFlag": "1",
            "attachDocFlag": "0",
            "englishDocFlag": "0",
            "csvFlag": "0",
            "legalStatus": "0",
        }
    )


def _make_label(
    text: str,
    lang: str = "ja",
    source: LabelSource = LabelSource.STANDARD,
) -> LabelInfo:
    """テスト用 LabelInfo を構築する。"""
    role = "http://www.xbrl.org/2003/role/label"
    return LabelInfo(text=text, role=role, lang=lang, source=source)


def _make_line_item(
    *,
    concept: str = "{http://example.com/jppfs}NetSales",
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    period: InstantPeriod | DurationPeriod | None = None,
    decimals: int | str | None = -6,
    dimensions: tuple[DimensionMember, ...] = (),
    order: int = 0,
    is_nil: bool = False,
    source_line: int | None = 42,
) -> LineItem:
    """テスト用 LineItem を構築する。"""
    if period is None:
        period = DurationPeriod(
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
    return LineItem(
        concept=concept,
        namespace_uri="http://example.com/jppfs",
        local_name=local_name,
        label_ja=_make_label("売上高"),
        label_en=_make_label("Net sales", lang="en"),
        value=value,
        unit_ref="JPY",
        decimals=decimals,
        context_id="CurrentYearDuration",
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=is_nil,
        source_line=source_line,
        order=order,
    )


def _make_dei() -> DEI:
    """テスト用 DEI を構築する。"""
    return DEI(
        edinet_code="E00001",
        fund_code=None,
        security_code="12340",
        filer_name_ja="テスト株式会社",
        filer_name_en="Test Corp.",
        fund_name_ja=None,
        fund_name_en=None,
        cabinet_office_ordinance="企業内容等の開示に関する内閣府令",
        document_type="第三号様式",
        accounting_standards=AccountingStandard.JAPAN_GAAP,
        has_consolidated=True,
        industry_code_consolidated="CTE",
        industry_code_non_consolidated="CTE",
        current_fiscal_year_start_date=datetime.date(2025, 4, 1),
        current_period_end_date=datetime.date(2026, 3, 31),
        type_of_current_period=PeriodType.FY,
        current_fiscal_year_end_date=datetime.date(2026, 3, 31),
        previous_fiscal_year_start_date=datetime.date(2024, 4, 1),
        comparative_period_end_date=datetime.date(2025, 3, 31),
        previous_fiscal_year_end_date=datetime.date(2025, 3, 31),
        next_fiscal_year_start_date=datetime.date(2026, 4, 1),
        end_date_of_next_semi_annual_period=datetime.date(2026, 9, 30),
        number_of_submission=1,
        amendment_flag=False,
        identification_of_document_subject_to_amendment=None,
        report_amendment_flag=False,
        xbrl_amendment_flag=False,
    )


def _make_context() -> dict[str, StructuredContext]:
    """テスト用 context マッピングを構築する。"""
    return {
        "CurrentYearDuration": StructuredContext(
            context_id="CurrentYearDuration",
            period=DurationPeriod(
                start_date=datetime.date(2025, 4, 1),
                end_date=datetime.date(2026, 3, 31),
            ),
            entity_id="E00001",
            dimensions=(),
            source_line=10,
            entity_scheme="http://disclosure.edinet-fsa.go.jp",
        ),
        "CurrentYearInstant": StructuredContext(
            context_id="CurrentYearInstant",
            period=InstantPeriod(instant=datetime.date(2026, 3, 31)),
            entity_id="E00001",
            dimensions=(
                DimensionMember(
                    axis="{http://example.com}ConsolidatedOrNonConsolidatedAxis",
                    member="{http://example.com}ConsolidatedMember",
                ),
            ),
            source_line=20,
        ),
    }


def _make_calc_linkbase() -> CalculationLinkbase:
    """テスト用 CalculationLinkbase を構築する。"""
    role = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_ProfitLoss"
    arc1 = CalculationArc(
        parent="GrossProfit",
        child="NetSales",
        parent_href="jppfs_cor.xsd#GrossProfit",
        child_href="jppfs_cor.xsd#NetSales",
        weight=1,
        order=1.0,
        role_uri=role,
    )
    arc2 = CalculationArc(
        parent="GrossProfit",
        child="CostOfSales",
        parent_href="jppfs_cor.xsd#GrossProfit",
        child_href="jppfs_cor.xsd#CostOfSales",
        weight=-1,
        order=2.0,
        role_uri=role,
    )
    tree = CalculationTree(
        role_uri=role,
        arcs=(arc1, arc2),
        roots=("GrossProfit",),
    )
    return CalculationLinkbase(
        source_path=None,
        trees={role: tree},
    )


def _make_statements(
    *,
    items: tuple[LineItem, ...] | None = None,
    dei: DEI | None = None,
    contexts: dict[str, StructuredContext] | None = None,
    calc: CalculationLinkbase | None = None,
) -> Statements:
    """テスト用 Statements を構築する。"""
    if items is None:
        items = (_make_line_item(),)
    return Statements(
        _items=items,
        _detected_standard=None,
        _dei=dei,
        _contexts=contexts,
        _calculation_linkbase=calc,
        _facts=None,
        _taxonomy_root=None,
        _industry_code=None,
        _resolver=None,
        _definition_linkbase=None,
    )


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------


class TestRoundtrip:
    """export_parquet → import_parquet のラウンドトリップテスト。"""

    def test_filing_roundtrip(self, tmp_path: Path) -> None:
        """Filing のメタデータが復元される。"""
        filing = _make_filing()
        export_parquet([(filing, None)], tmp_path)
        result = import_parquet(tmp_path)

        assert len(result) == 1
        restored_filing, stmts = result[0]
        assert stmts is None
        assert restored_filing.doc_id == filing.doc_id
        assert restored_filing.filer_name == filing.filer_name
        assert restored_filing.edinet_code == filing.edinet_code

    def test_filing_computed_fields(self, tmp_path: Path) -> None:
        """computed_field が復元後も動作する。"""
        filing = _make_filing()
        export_parquet([(filing, None)], tmp_path)
        result = import_parquet(tmp_path)
        restored = result[0][0]

        assert restored.filing_date == filing.filing_date
        assert restored.ticker == filing.ticker
        assert restored.doc_type == filing.doc_type

    def test_line_items_roundtrip(self, tmp_path: Path) -> None:
        """LineItem のフィールドが復元される。"""
        item = _make_line_item()
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        _, restored_stmts = result[0]
        assert restored_stmts is not None
        restored_items = list(restored_stmts)
        assert len(restored_items) == 1
        ri = restored_items[0]
        assert ri.concept == item.concept
        assert ri.local_name == item.local_name
        assert ri.label_ja.text == item.label_ja.text
        assert ri.label_en.text == item.label_en.text
        assert ri.entity_id == item.entity_id
        assert ri.context_id == item.context_id
        assert ri.unit_ref == item.unit_ref
        assert ri.is_nil == item.is_nil
        assert ri.source_line == item.source_line
        assert ri.order == item.order

    def test_decimal_precision(self, tmp_path: Path) -> None:
        """Decimal の精度が保持される。"""
        item = _make_line_item(value=Decimal("123456789.123456789"))
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert isinstance(ri.value, Decimal)
        assert ri.value == Decimal("123456789.123456789")

    def test_string_value(self, tmp_path: Path) -> None:
        """str 型の value が正しく復元される。"""
        item = _make_line_item(value="テキスト値")
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert isinstance(ri.value, str)
        assert ri.value == "テキスト値"

    def test_none_value(self, tmp_path: Path) -> None:
        """None の value（nil fact）が正しく復元される。"""
        item = _make_line_item(value=None, is_nil=True)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.value is None
        assert ri.is_nil is True

    def test_instant_period(self, tmp_path: Path) -> None:
        """InstantPeriod が正しく区別・復元される。"""
        period = InstantPeriod(instant=datetime.date(2026, 3, 31))
        item = _make_line_item(period=period)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert isinstance(ri.period, InstantPeriod)
        assert ri.period.instant == datetime.date(2026, 3, 31)

    def test_duration_period(self, tmp_path: Path) -> None:
        """DurationPeriod が正しく区別・復元される。"""
        period = DurationPeriod(
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        )
        item = _make_line_item(period=period)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert isinstance(ri.period, DurationPeriod)
        assert ri.period.start_date == datetime.date(2025, 4, 1)
        assert ri.period.end_date == datetime.date(2026, 3, 31)

    def test_dimensions_json_roundtrip(self, tmp_path: Path) -> None:
        """dimensions が JSON 経由で正しく復元される。"""
        dims = (
            DimensionMember(
                axis="{http://example.com}Axis1",
                member="{http://example.com}Member1",
            ),
            DimensionMember(
                axis="{http://example.com}Axis2",
                member="{http://example.com}Member2",
            ),
        )
        item = _make_line_item(dimensions=dims)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert len(ri.dimensions) == 2
        assert ri.dimensions[0].axis == dims[0].axis
        assert ri.dimensions[0].member == dims[0].member
        assert ri.dimensions[1].axis == dims[1].axis

    def test_decimals_inf(self, tmp_path: Path) -> None:
        """decimals "INF" が保持される。"""
        item = _make_line_item(decimals="INF")
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.decimals == "INF"

    def test_decimals_none(self, tmp_path: Path) -> None:
        """decimals None が保持される。"""
        item = _make_line_item(decimals=None)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.decimals is None

    def test_dei_roundtrip(self, tmp_path: Path) -> None:
        """DEI のフィールドが復元される。"""
        dei = _make_dei()
        stmts = _make_statements(dei=dei)
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        _, restored_stmts = result[0]
        assert restored_stmts is not None
        rdei = restored_stmts.dei
        assert rdei is not None
        assert rdei.edinet_code == dei.edinet_code
        assert rdei.filer_name_ja == dei.filer_name_ja
        assert rdei.accounting_standards == AccountingStandard.JAPAN_GAAP
        assert rdei.type_of_current_period == PeriodType.FY
        assert rdei.current_period_end_date == dei.current_period_end_date
        assert rdei.has_consolidated is True
        assert rdei.number_of_submission == 1
        assert rdei.amendment_flag is False

    def test_dei_detected_standard(self, tmp_path: Path) -> None:
        """DEI から DetectedStandard が再導出される。"""
        dei = _make_dei()
        stmts = _make_statements(dei=dei)
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        restored_stmts = result[0][1]
        assert restored_stmts is not None
        ds = restored_stmts.detected_standard
        assert ds is not None
        assert ds.standard == AccountingStandard.JAPAN_GAAP

    def test_contexts_roundtrip(self, tmp_path: Path) -> None:
        """context_map が復元される。"""
        contexts = _make_context()
        stmts = _make_statements(contexts=contexts)
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        restored_stmts = result[0][1]
        assert restored_stmts is not None
        rctx = restored_stmts.context_map
        assert rctx is not None
        assert "CurrentYearDuration" in rctx
        assert "CurrentYearInstant" in rctx

        dur_ctx = rctx["CurrentYearDuration"]
        assert isinstance(dur_ctx.period, DurationPeriod)
        assert dur_ctx.entity_scheme == "http://disclosure.edinet-fsa.go.jp"

        inst_ctx = rctx["CurrentYearInstant"]
        assert isinstance(inst_ctx.period, InstantPeriod)
        assert len(inst_ctx.dimensions) == 1

    def test_calc_linkbase_roundtrip(self, tmp_path: Path) -> None:
        """CalculationLinkbase が復元され children_of/parent_of が動作する。"""
        calc = _make_calc_linkbase()
        stmts = _make_statements(calc=calc)
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        restored_stmts = result[0][1]
        assert restored_stmts is not None
        rcalc = restored_stmts.calculation_linkbase
        assert rcalc is not None

        children = rcalc.children_of("GrossProfit")
        assert len(children) == 2
        child_names = {c.child for c in children}
        assert "NetSales" in child_names
        assert "CostOfSales" in child_names

        parents = rcalc.parent_of("NetSales")
        assert len(parents) == 1
        assert parents[0].parent == "GrossProfit"
        assert parents[0].weight == 1

    def test_optional_files_missing(self, tmp_path: Path) -> None:
        """オプションファイル欠落時にグレースフル動作する。"""
        filing = _make_filing()
        # filings.parquet のみ書き出す
        export_parquet([(filing, None)], tmp_path)
        result = import_parquet(tmp_path)

        assert len(result) == 1
        _, stmts = result[0]
        assert stmts is None

    def test_multiple_filings(self, tmp_path: Path) -> None:
        """複数 Filing の永続化・復元。"""
        f1 = _make_filing(doc_id="S100AAA1", has_xbrl=True)
        f2 = _make_filing(doc_id="S100AAA2", has_xbrl=False)
        s1 = _make_statements()

        export_parquet([(f1, s1), (f2, None)], tmp_path)
        result = import_parquet(tmp_path)

        assert len(result) == 2
        assert result[0][0].doc_id == "S100AAA1"
        assert result[0][1] is not None
        assert result[1][0].doc_id == "S100AAA2"
        assert result[1][1] is None

    def test_prefix(self, tmp_path: Path) -> None:
        """prefix が正しくファイル名に反映される。"""
        filing = _make_filing()
        paths = export_parquet(
            [(filing, None)], tmp_path, prefix="2026-03-01_"
        )
        assert "filings" in paths
        assert paths["filings"].name == "2026-03-01_filings.parquet"

        result = import_parquet(tmp_path, prefix="2026-03-01_")
        assert len(result) == 1

    def test_source_line_none(self, tmp_path: Path) -> None:
        """source_line=None が正しく復元される。"""
        item = _make_line_item(source_line=None)
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.source_line is None

    def test_empty_dimensions(self, tmp_path: Path) -> None:
        """空の dimensions タプルが復元される。"""
        item = _make_line_item(dimensions=())
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.dimensions == ()

    def test_label_source_filer(self, tmp_path: Path) -> None:
        """LabelSource.FILER が正しく復元される。"""
        item = LineItem(
            concept="{http://example.com/custom}CustomItem",
            namespace_uri="http://example.com/custom",
            local_name="CustomItem",
            label_ja=LabelInfo(
                text="カスタム科目",
                role="http://www.xbrl.org/2003/role/label",
                lang="ja",
                source=LabelSource.FILER,
            ),
            label_en=LabelInfo(
                text="CustomItem",
                role="http://www.xbrl.org/2003/role/label",
                lang="en",
                source=LabelSource.FALLBACK,
            ),
            value=Decimal("100"),
            unit_ref="JPY",
            decimals=0,
            context_id="CurrentYearDuration",
            period=DurationPeriod(
                start_date=datetime.date(2025, 4, 1),
                end_date=datetime.date(2026, 3, 31),
            ),
            entity_id="E00001",
            dimensions=(),
            is_nil=False,
            source_line=99,
            order=5,
        )
        stmts = _make_statements(items=(item,))
        filing = _make_filing()
        export_parquet([(filing, stmts)], tmp_path)
        result = import_parquet(tmp_path)

        ri = list(result[0][1])[0]
        assert ri.label_ja.source == LabelSource.FILER
        assert ri.label_en.source == LabelSource.FALLBACK

    def test_filings_parquet_missing(self, tmp_path: Path) -> None:
        """filings.parquet がない場合 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            import_parquet(tmp_path)

    def test_full_roundtrip_with_all_tables(self, tmp_path: Path) -> None:
        """全テーブルを含む完全なラウンドトリップ。"""
        filing = _make_filing()
        dei = _make_dei()
        contexts = _make_context()
        calc = _make_calc_linkbase()
        items = (
            _make_line_item(order=0),
            _make_line_item(
                concept="{http://example.com/jppfs}TotalAssets",
                local_name="TotalAssets",
                value=Decimal("5000000"),
                period=InstantPeriod(instant=datetime.date(2026, 3, 31)),
                order=1,
            ),
        )
        stmts = _make_statements(
            items=items, dei=dei, contexts=contexts, calc=calc
        )

        paths = export_parquet([(filing, stmts)], tmp_path)
        assert "filings" in paths
        assert "line_items" in paths
        assert "contexts" in paths
        assert "dei" in paths
        assert "calc_edges" in paths

        result = import_parquet(tmp_path)
        assert len(result) == 1
        rf, rs = result[0]

        assert rf.doc_id == filing.doc_id
        assert rs is not None
        assert len(list(rs)) == 2
        assert rs.dei is not None
        assert rs.detected_standard is not None
        assert rs.context_map is not None
        assert rs.calculation_linkbase is not None
