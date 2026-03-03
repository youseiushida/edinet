"""test_text_blocks.py — TextBlock 抽出・セクションマッピング・HTML クリーニングのテスト。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError
from edinet.xbrl.contexts import (
    DimensionMember,
    DurationPeriod,
    InstantPeriod,
    StructuredContext,
)
from edinet.xbrl.parser import RawFact
from edinet.xbrl.taxonomy import TaxonomyResolver
from edinet.xbrl.text.blocks import TextBlock, extract_text_blocks
from edinet.xbrl.text.clean import clean_html
from edinet.xbrl.text.sections import build_section_map

from .conftest import TAXONOMY_MINI_DIR

# ── 定数 ──

# taxonomy_mini に存在する名前空間（ラベル解決可能）
_NS_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
# taxonomy_mini に存在しない名前空間（フォールバック用）
_NS_UNKNOWN = "http://example.com/unknown/2025-11-01/unknown_cor"

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "text_blocks"


# ── ヘルパー（デトロイト派: オブジェクト直接構築） ──


def _make_fact(
    *,
    local_name: str = "BusinessRisksTextBlock",
    namespace_uri: str = _NS_JPPFS,
    context_ref: str = "CurrentYearDuration",
    unit_ref: str | None = None,
    decimals: int | None = None,
    value_raw: str | None = "<p>リスク情報</p>",
    is_nil: bool = False,
    fact_id: str | None = None,
    xml_lang: str | None = None,
    source_line: int | None = 1,
    order: int = 0,
    value_inner_xml: str | None = None,
) -> RawFact:
    """テスト用 RawFact を構築するヘルパー。"""
    return RawFact(
        concept_qname=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=unit_ref,
        decimals=decimals,
        value_raw=value_raw,
        is_nil=is_nil,
        fact_id=fact_id,
        xml_lang=xml_lang,
        source_line=source_line,
        order=order,
        value_inner_xml=value_inner_xml,
    )


def _make_ctx(
    *,
    context_id: str = "CurrentYearDuration",
    period: DurationPeriod | InstantPeriod | None = None,
    entity_id: str = "E00001",
    dimensions: tuple[DimensionMember, ...] = (),
    source_line: int | None = 1,
) -> StructuredContext:
    """テスト用 StructuredContext を構築するヘルパー。"""
    if period is None:
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
    return StructuredContext(
        context_id=context_id,
        period=period,
        entity_id=entity_id,
        dimensions=dimensions,
        source_line=source_line,
    )


def _make_ctx_map(
    *contexts: StructuredContext,
) -> dict[str, StructuredContext]:
    """テスト用 Context 辞書を構築するヘルパー。"""
    return {ctx.context_id: ctx for ctx in contexts}


@pytest.fixture()
def resolver() -> TaxonomyResolver:
    """taxonomy_mini フィクスチャを使った TaxonomyResolver。"""
    return TaxonomyResolver(TAXONOMY_MINI_DIR, use_cache=False)


# ---------------------------------------------------------------------------
# TestExtractTextBlocks（11 件）
# ---------------------------------------------------------------------------


class TestExtractTextBlocks:
    """extract_text_blocks() のテスト。"""

    def test_extract_single_textblock(self) -> None:
        """単一の TextBlock Fact が正しく抽出される。"""
        fact = _make_fact(fact_id="id-001")
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact], ctx_map)

        assert len(blocks) == 1
        block = blocks[0]
        assert isinstance(block, TextBlock)
        assert block.concept == "BusinessRisksTextBlock"
        assert block.namespace_uri == _NS_JPPFS
        assert block.concept_qname == f"{{{_NS_JPPFS}}}BusinessRisksTextBlock"
        assert block.html == "<p>リスク情報</p>"
        assert block.context_ref == "CurrentYearDuration"
        assert block.fact_id == "id-001"

    def test_extract_multiple_textblocks(self) -> None:
        """複数の TextBlock Fact が出現順で抽出される。"""
        fact1 = _make_fact(local_name="BusinessRisksTextBlock", order=0)
        fact2 = _make_fact(
            local_name="DescriptionOfBusinessTextBlock",
            value_raw="<p>事業の内容</p>",
            order=1,
        )
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact1, fact2], ctx_map)

        assert len(blocks) == 2
        assert blocks[0].concept == "BusinessRisksTextBlock"
        assert blocks[1].concept == "DescriptionOfBusinessTextBlock"

    def test_skip_non_textblock(self) -> None:
        """TextBlock でない Fact（monetaryItemType 等）は除外される。"""
        text_fact = _make_fact()
        numeric_fact = _make_fact(
            local_name="NetSales",
            unit_ref="JPY",
            value_raw="1000000",
        )
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([text_fact, numeric_fact], ctx_map)

        assert len(blocks) == 1
        assert blocks[0].concept == "BusinessRisksTextBlock"

    def test_skip_nil_fact(self) -> None:
        """is_nil=True の Fact は除外される。"""
        fact = _make_fact(is_nil=True, value_raw=None)
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact], ctx_map)

        assert len(blocks) == 0

    def test_skip_empty_value(self) -> None:
        """value_raw が None または空白のみの Fact は除外される。"""
        fact_none = _make_fact(value_raw=None)
        fact_blank = _make_fact(value_raw="   \n  ")
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact_none, fact_blank], ctx_map)

        assert len(blocks) == 0

    def test_html_content_preserved(self) -> None:
        """TextBlock.html に HTML コンテンツが保持される。"""
        html = "<table><tr><td>売上高</td><td>100,000</td></tr></table>"
        fact = _make_fact(value_raw=html)
        ctx = _make_ctx()
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact], ctx_map)

        assert blocks[0].html == html

    def test_period_from_context(self) -> None:
        """TextBlock.period が StructuredContext の DurationPeriod から正しく転写される。"""
        period = DurationPeriod(
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
        )
        fact = _make_fact()
        ctx = _make_ctx(period=period)
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact], ctx_map)

        assert blocks[0].period == period
        assert isinstance(blocks[0].period, DurationPeriod)

    def test_instant_period(self) -> None:
        """TextBlock.period が InstantPeriod でも正しく動作する。"""
        period = InstantPeriod(instant=date(2025, 3, 31))
        fact = _make_fact(context_ref="FilingDateInstant")
        ctx = _make_ctx(context_id="FilingDateInstant", period=period)
        ctx_map = _make_ctx_map(ctx)

        blocks = extract_text_blocks([fact], ctx_map)

        assert blocks[0].period == period
        assert isinstance(blocks[0].period, InstantPeriod)

    def test_consolidated_flag(self) -> None:
        """TextBlock.is_consolidated が正しく設定される。"""
        # ディメンションなし → 連結（デフォルト）
        fact_con = _make_fact(context_ref="ConCtx")
        ctx_con = _make_ctx(context_id="ConCtx")

        # NonConsolidatedMember → 個別
        dim = DimensionMember(
            axis="{http://example.com}ConsolidatedOrNonConsolidatedAxis",
            member="{http://example.com}NonConsolidatedMember",
        )
        fact_non = _make_fact(context_ref="NonConCtx")
        ctx_non = _make_ctx(context_id="NonConCtx", dimensions=(dim,))

        ctx_map = _make_ctx_map(ctx_con, ctx_non)
        blocks = extract_text_blocks([fact_con, fact_non], ctx_map)

        assert blocks[0].is_consolidated is True
        assert blocks[1].is_consolidated is False

    def test_empty_facts(self) -> None:
        """空の facts では空タプルが返る。"""
        blocks = extract_text_blocks([], {})

        assert blocks == ()

    def test_missing_context_raises(self) -> None:
        """context_map に存在しない contextRef で EdinetParseError が発生する。"""
        fact = _make_fact(context_ref="NonExistent")

        with pytest.raises(EdinetParseError, match="context_map に見つかりません"):
            extract_text_blocks([fact], {})


# ---------------------------------------------------------------------------
# TestSectionMap（10 件）
# ---------------------------------------------------------------------------


class TestSectionMap:
    """SectionMap および build_section_map() のテスト。"""

    def test_build_section_map_resolver_labels(
        self, resolver: TaxonomyResolver
    ) -> None:
        """TaxonomyResolver の日本語ラベルでセクション名が付与される。

        taxonomy_mini には jppfs_cor のラベルが存在するため、
        jppfs_cor 名前空間の概念名で resolver 解決パスを検証する。
        """
        # NetSales は jppfs_cor に存在（ラベル: "売上高"）
        # "TextBlock" サフィックスを付けて TextBlock として扱う
        block = TextBlock(
            concept="NetSalesTextBlock",
            namespace_uri=_NS_JPPFS,
            concept_qname=f"{{{_NS_JPPFS}}}NetSalesTextBlock",
            html="<p>test</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )
        # NetSalesTextBlock は taxonomy_mini に存在しないため
        # resolver は FALLBACK を返す → 英語フォールバック "NetSales" になる
        # 実際の jpcrp_cor では "事業等のリスク" 等の日本語ラベルが返る
        smap = build_section_map([block], resolver)

        # taxonomy_mini には NetSalesTextBlock がないため英語フォールバック
        assert len(smap) == 1
        assert "NetSales" in smap.sections

    def test_instant_and_duration_in_same_section(
        self, resolver: TaxonomyResolver
    ) -> None:
        """同一 concept の instant / duration TextBlock が同一セクションにグルーピングされる。"""
        block_dur = TextBlock(
            concept="BusinessRisksTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}BusinessRisksTextBlock",
            html="<p>duration</p>",
            context_ref="dur",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )
        block_inst = TextBlock(
            concept="BusinessRisksTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}BusinessRisksTextBlock",
            html="<p>instant</p>",
            context_ref="inst",
            period=InstantPeriod(date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block_dur, block_inst], resolver)

        assert len(smap) == 1
        blocks = smap["BusinessRisks"]
        assert len(blocks) == 2

    def test_section_map_getitem(self, resolver: TaxonomyResolver) -> None:
        """__getitem__ でセクション名から TextBlock タプルを取得できる。"""
        block = TextBlock(
            concept="CompanyHistoryTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}CompanyHistoryTextBlock",
            html="<p>沿革</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block], resolver)

        result = smap["CompanyHistory"]
        assert len(result) == 1
        assert result[0].html == "<p>沿革</p>"

    def test_section_map_get_none(self, resolver: TaxonomyResolver) -> None:
        """存在しないセクション名で get() が None を返す。"""
        smap = build_section_map([], resolver)

        assert smap.get("存在しないセクション") is None

    def test_section_map_getitem_keyerror(
        self, resolver: TaxonomyResolver
    ) -> None:
        """存在しないセクション名で __getitem__ が KeyError を発生させる。"""
        smap = build_section_map([], resolver)

        with pytest.raises(KeyError, match="見つかりません"):
            smap["存在しないセクション"]

    def test_section_map_contains(self, resolver: TaxonomyResolver) -> None:
        """__contains__ でセクションの存在確認ができる。"""
        block = TextBlock(
            concept="SomeTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}SomeTextBlock",
            html="<p>test</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block], resolver)

        assert "Some" in smap
        assert "NonExistent" not in smap

    def test_section_map_sections_property(
        self, resolver: TaxonomyResolver
    ) -> None:
        """sections プロパティでセクション名一覧が取得できる。"""
        block1 = TextBlock(
            concept="ATextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}ATextBlock",
            html="<p>a</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )
        block2 = TextBlock(
            concept="BTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}BTextBlock",
            html="<p>b</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block1, block2], resolver)

        assert set(smap.sections) == {"A", "B"}

    def test_section_map_unmatched_no_textblock_suffix(
        self, resolver: TaxonomyResolver
    ) -> None:
        """'TextBlock' サフィックスを持たない直接構築の TextBlock が unmatched に入る。

        extract_text_blocks() 経由なら発生しないセーフティネットの検証。
        """
        block = TextBlock(
            concept="SomethingElse",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}SomethingElse",
            html="<p>test</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block], resolver)

        assert len(smap) == 0
        assert len(smap.unmatched) == 1
        assert smap.unmatched[0].concept == "SomethingElse"

    def test_section_map_resolver_miss_fallback_to_english(
        self, resolver: TaxonomyResolver
    ) -> None:
        """resolver でラベルが見つからない場合、TextBlock サフィックス除去の英語名になる。"""
        block = TextBlock(
            concept="CustomFilerRiskTextBlock",
            namespace_uri=_NS_UNKNOWN,
            concept_qname=f"{{{_NS_UNKNOWN}}}CustomFilerRiskTextBlock",
            html="<p>custom</p>",
            context_ref="ctx1",
            period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
            is_consolidated=True,
        )

        smap = build_section_map([block], resolver)

        assert "CustomFilerRisk" in smap
        assert len(smap.unmatched) == 0

    def test_section_map_len(self, resolver: TaxonomyResolver) -> None:
        """__len__ がセクション数を返す。"""
        blocks = [
            TextBlock(
                concept=f"Section{i}TextBlock",
                namespace_uri=_NS_UNKNOWN,
                concept_qname=f"{{{_NS_UNKNOWN}}}Section{i}TextBlock",
                html=f"<p>{i}</p>",
                context_ref="ctx1",
                period=DurationPeriod(date(2024, 4, 1), date(2025, 3, 31)),
                is_consolidated=True,
            )
            for i in range(3)
        ]

        smap = build_section_map(blocks, resolver)

        assert len(smap) == 3


# ---------------------------------------------------------------------------
# TestCleanHtml（11 件）
# ---------------------------------------------------------------------------


class TestCleanHtml:
    """clean_html() のテスト。"""

    def test_clean_simple_text(self) -> None:
        """単純なテキスト（タグなし）がそのまま返る。"""
        result = clean_html("当社グループのリスク情報です。")

        assert result == "当社グループのリスク情報です。"

    def test_clean_paragraph_tags(self) -> None:
        """<p> タグが改行に変換される。"""
        result = clean_html("<p>段落1</p><p>段落2</p>")

        assert "段落1" in result
        assert "段落2" in result
        # p タグの間に改行がある
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 2

    def test_clean_table_structure(self) -> None:
        """テーブルがタブ区切り + 改行に変換される。"""
        html = _FIXTURE_DIR.joinpath("html_table.html").read_text(
            encoding="utf-8"
        )
        result = clean_html(html)

        # タブでセルが区切られている
        assert "\t" in result
        # 各行が改行で区切られている
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) >= 3  # ヘッダ + 3 データ行
        # 最初の行にヘッダが含まれる
        assert "科目" in lines[0]
        assert "金額" in lines[0]

    def test_clean_br_tags(self) -> None:
        """<br> タグが改行に変換される。"""
        result = clean_html("行1<br>行2<br/>行3")

        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 3
        assert lines[0] == "行1"
        assert lines[1] == "行2"
        assert lines[2] == "行3"

    def test_clean_nested_html(self) -> None:
        """ネストした HTML が正しくフラット化される。"""
        html = _FIXTURE_DIR.joinpath("html_nested.html").read_text(
            encoding="utf-8"
        )
        result = clean_html(html)

        assert "事業リスク" in result
        assert "為替変動" in result
        assert "原材料価格の高騰" in result
        # HTML タグは除去されている
        assert "<strong>" not in result
        assert "<em>" not in result

    def test_clean_broken_html(self) -> None:
        """壊れた HTML でもエラーにならない。"""
        html = _FIXTURE_DIR.joinpath("html_broken.html").read_text(
            encoding="utf-8"
        )
        result = clean_html(html)

        # クラッシュせず、テキストが抽出される
        assert isinstance(result, str)
        assert "未閉じ段落" in result
        assert "ミスマッチ" in result

    def test_clean_empty_string(self) -> None:
        """空文字列が空文字列を返す。"""
        assert clean_html("") == ""
        assert clean_html("   ") == ""
        assert clean_html("\n\n") == ""

    def test_clean_whitespace_normalization(self) -> None:
        """連続する空行が 1 つの空行に正規化される。"""
        html = "<p>段落1</p>\n\n\n\n\n<p>段落2</p>"
        result = clean_html(html)

        # 3 つ以上の連続改行は 2 つに正規化
        assert "\n\n\n" not in result
        assert "段落1" in result
        assert "段落2" in result

    def test_clean_img_svg_removed(self) -> None:
        """<img> と <svg> が除去される。"""
        html = (
            '<p>テキスト前<img src="chart.png"/>テキスト後</p>'
            "<svg><circle r='10'/></svg>"
            "<p>最終行</p>"
        )
        result = clean_html(html)

        assert "テキスト前" in result
        assert "テキスト後" in result
        assert "最終行" in result
        assert "<img" not in result
        assert "<svg" not in result
        assert "circle" not in result

    def test_clean_preserves_japanese_text(self) -> None:
        """日本語テキストが正しく保持される。"""
        html = "<div>当社グループは、自動車の製造・販売を主な事業としております。</div>"
        result = clean_html(html)

        assert result == "当社グループは、自動車の製造・販売を主な事業としております。"

    def test_clean_plain_text_without_tags(self) -> None:
        """タグなしのプレーンテキスト入力でも正常動作する。

        lxml.html.fragment_fromstring の create_parent="div" により
        ラップされるため、Element が返り text_content() が使える。
        """
        result = clean_html("タグのない純粋なテキスト")

        assert result == "タグのない純粋なテキスト"

    def test_clean_style_script_removed(self) -> None:
        """<style> と <script> が除去される。"""
        html = (
            "<style>body { color: red; }</style>"
            "<p>本文</p>"
            "<script>alert('xss')</script>"
        )
        result = clean_html(html)

        assert "本文" in result
        assert "color" not in result
        assert "alert" not in result
