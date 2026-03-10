"""adump_to_parquet() のテスト。"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from edinet.extension import (  # noqa: E402
    DumpResult,
    adump_to_parquet,
    import_parquet,
)
from edinet.financial.statements import Statements  # noqa: E402
from edinet.models.filing import Filing  # noqa: E402
from edinet.models.financial import LineItem  # noqa: E402
from edinet.xbrl.contexts import DurationPeriod  # noqa: E402
from edinet.xbrl.dei import DEI, AccountingStandard, PeriodType  # noqa: E402
from edinet.xbrl.taxonomy import LabelInfo, LabelSource  # noqa: E402


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_filing(
    doc_id: str = "S100DUMP",
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
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=source,
    )


def _make_line_item(*, order: int = 0) -> LineItem:
    """テスト用 LineItem を構築する。"""
    return LineItem(
        concept="{http://example.com/jppfs}NetSales",
        namespace_uri="http://example.com/jppfs",
        local_name="NetSales",
        label_ja=_make_label("売上高"),
        label_en=_make_label("Net sales", lang="en"),
        value=Decimal("1000000"),
        unit_ref="JPY",
        decimals=-6,
        context_id="CurrentYearDuration",
        period=DurationPeriod(
            start_date=datetime.date(2025, 4, 1),
            end_date=datetime.date(2026, 3, 31),
        ),
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=42,
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


def _make_statements(
    *,
    items: tuple[LineItem, ...] | None = None,
    dei: DEI | None = None,
) -> Statements:
    """テスト用 Statements を構築する。"""
    if items is None:
        items = (_make_line_item(),)
    return Statements(
        _items=items,
        _detected_standard=None,
        _dei=dei,
        _contexts=None,
        _calculation_linkbase=None,
        _facts=None,
        _taxonomy_root=None,
        _industry_code=None,
        _resolver=None,
        _definition_linkbase=None,
    )


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------


class TestAdumpToParquet:
    """adump_to_parquet のテスト。"""

    @pytest.fixture()
    def _patch_adocuments(self, monkeypatch):
        """adocuments をパッチして API 呼び出しを回避する。"""

        async def _fake_adocuments(*args, **kwargs):
            xbrl_filing = _make_filing(doc_id="S100XBRL", has_xbrl=True)
            non_xbrl_filing = _make_filing(doc_id="S100NOXB", has_xbrl=False)
            return [xbrl_filing, non_xbrl_filing]

        monkeypatch.setattr(
            "edinet.public_api.adocuments", _fake_adocuments
        )

    @pytest.fixture()
    def _patch_axbrl(self, monkeypatch):
        """Filing.axbrl をパッチして XBRL パースを回避する。"""
        stmts = _make_statements(dei=_make_dei())

        async def _fake_axbrl(self, *, taxonomy_path=None, strict=True):
            return stmts

        monkeypatch.setattr(Filing, "axbrl", _fake_axbrl)

    @pytest.fixture()
    def _patch_axbrl_error(self, monkeypatch):
        """Filing.axbrl をパッチしてエラーを発生させる。"""

        async def _fake_axbrl(self, *, taxonomy_path=None, strict=True):
            raise RuntimeError("テスト用パースエラー")

        monkeypatch.setattr(Filing, "axbrl", _fake_axbrl)

    @pytest.mark.asyncio()
    @pytest.mark.usefixtures("_patch_adocuments", "_patch_axbrl")
    async def test_adump_basic_roundtrip(self, tmp_path: Path) -> None:
        """dump → import_parquet で復元できることを検証する。"""
        result = await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        assert isinstance(result, DumpResult)
        assert "filings" in result.paths

        # import_parquet で復元
        restored = import_parquet(tmp_path)
        assert len(restored) == 2

        doc_ids = {f.doc_id for f, _ in restored}
        assert "S100XBRL" in doc_ids
        assert "S100NOXB" in doc_ids

        # XBRL 書類は Statements あり
        xbrl_pairs = [(f, s) for f, s in restored if f.doc_id == "S100XBRL"]
        assert xbrl_pairs[0][1] is not None

        # non-XBRL 書類は Statements なし
        noxb_pairs = [(f, s) for f, s in restored if f.doc_id == "S100NOXB"]
        assert noxb_pairs[0][1] is None

    @pytest.mark.asyncio()
    @pytest.mark.usefixtures("_patch_adocuments", "_patch_axbrl")
    async def test_adump_result_counts(self, tmp_path: Path) -> None:
        """DumpResult のフィールドが正しいことを検証する。"""
        result = await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        assert result.total_filings == 2
        assert result.xbrl_count == 1
        assert result.xbrl_ok == 1
        assert result.errors == 0

    @pytest.mark.asyncio()
    async def test_adump_non_xbrl_only(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """XBRL なし書類のみ → filings.parquet だけ生成される。"""

        async def _fake_adocuments(*args, **kwargs):
            return [
                _make_filing(doc_id="S100NOX1", has_xbrl=False),
                _make_filing(doc_id="S100NOX2", has_xbrl=False),
            ]

        monkeypatch.setattr(
            "edinet.public_api.adocuments", _fake_adocuments
        )

        result = await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        assert result.total_filings == 2
        assert result.xbrl_count == 0
        assert result.xbrl_ok == 0
        assert result.errors == 0
        assert "filings" in result.paths
        assert "line_items" not in result.paths

    @pytest.mark.asyncio()
    @pytest.mark.usefixtures("_patch_adocuments", "_patch_axbrl_error")
    async def test_adump_xbrl_error_continues(self, tmp_path: Path) -> None:
        """axbrl エラー時も中断せず続行し、errors カウントが増える。"""
        result = await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        assert result.total_filings == 2
        assert result.xbrl_count == 1
        assert result.xbrl_ok == 0
        assert result.errors == 1
        # filings は non-XBRL + エラーの XBRL 両方含む
        assert "filings" in result.paths

    @pytest.mark.asyncio()
    @pytest.mark.usefixtures("_patch_adocuments", "_patch_axbrl")
    async def test_adump_explicit_schema_applied(
        self, tmp_path: Path
    ) -> None:
        """Parquet メタデータで dictionary encoding が適用されていることを検証する。"""
        await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        li_path = tmp_path / "line_items.parquet"
        assert li_path.exists()

        import pyarrow.parquet as pq_mod

        schema = pq_mod.read_schema(li_path)

        # concept カラムが dictionary 型であること
        concept_field = schema.field("concept")
        assert "dictionary" in str(concept_field.type).lower()

        # namespace_uri も dictionary 型
        ns_field = schema.field("namespace_uri")
        assert "dictionary" in str(ns_field.type).lower()

    @pytest.mark.asyncio()
    @pytest.mark.usefixtures("_patch_adocuments", "_patch_axbrl")
    async def test_adump_compression_zstd(self, tmp_path: Path) -> None:
        """デフォルト圧縮が zstd であることを確認する。"""
        await adump_to_parquet(
            "2026-03-01",
            output_dir=tmp_path,
        )

        import pyarrow.parquet as pq_mod

        meta = pq_mod.read_metadata(tmp_path / "filings.parquet")
        codec = meta.row_group(0).column(0).compression
        assert codec.lower() == "zstd"

    @pytest.mark.asyncio()
    async def test_adump_per_document_row_groups(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """ドキュメント単位で row group が書かれることを検証する。"""

        async def _fake_adocuments(*args, **kwargs):
            return [
                _make_filing(doc_id="S100AAA1", has_xbrl=True),
                _make_filing(doc_id="S100AAA2", has_xbrl=True),
                _make_filing(doc_id="S100AAA3", has_xbrl=True),
            ]

        monkeypatch.setattr(
            "edinet.public_api.adocuments", _fake_adocuments
        )

        stmts = _make_statements(dei=_make_dei())

        async def _fake_axbrl(self, *, taxonomy_path=None, strict=True):
            return stmts

        monkeypatch.setattr(Filing, "axbrl", _fake_axbrl)

        await adump_to_parquet("2026-03-01", output_dir=tmp_path)

        import pyarrow.parquet as pq_mod

        # line_items: 3ドキュメント → 3 row groups
        meta = pq_mod.read_metadata(tmp_path / "line_items.parquet")
        assert meta.num_row_groups == 3

        # filings: non-XBRL 0件（バッチなし）+ XBRL 3件（各1 row group）= 3
        f_meta = pq_mod.read_metadata(tmp_path / "filings.parquet")
        assert f_meta.num_row_groups == 3

        # import で復元できること
        restored = import_parquet(tmp_path)
        assert len(restored) == 3
        assert all(s is not None for _, s in restored)
