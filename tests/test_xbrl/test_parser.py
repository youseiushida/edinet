"""parse_xbrl_facts のテスト。"""

from __future__ import annotations

import pytest
from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.parser import ParsedXBRL, parse_xbrl_facts
from .conftest import load_xbrl_bytes

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

_JPPFS_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"


def _wrap_xbrl(body: str, *, extra_ns: str = "") -> bytes:
    """最小限の XBRL ラッパーで *body* を囲んだ bytes を返す。

    Args:
        body: ルート直下に挿入する XML フラグメント。
        extra_ns: 追加の名前空間宣言。

    Returns:
        UTF-8 エンコードされた XBRL インスタンス bytes。
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<xbrli:xbrl"
        '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
        '  xmlns:link="http://www.xbrl.org/2003/linkbase"'
        '  xmlns:xlink="http://www.w3.org/1999/xlink"'
        '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        '  xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor"'
        '  xmlns:jpdei_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2023-11-01/jpdei_cor"'
        f"  {extra_ns}>"
        '<link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>'
        '<xbrli:context id="ctx1">'
        "<xbrli:entity>"
        '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier>'
        "</xbrli:entity>"
        "<xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>"
        "</xbrli:context>"
        '<xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>'
        f"{body}"
        "</xbrli:xbrl>"
    ).encode()


# ===========================================================================
# P0 テスト（8 件）
# ===========================================================================


@pytest.mark.unit
class TestParseXbrlP0:
    """P0: 必須テスト群。"""

    @pytest.mark.medium
    def test_parse_xbrl_extracts_all_facts(self) -> None:
        """simple_pl.xbrl から 20 件の Fact を抽出する。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        result = parse_xbrl_facts(data, source_path="simple_pl.xbrl")
        assert isinstance(result, ParsedXBRL)
        assert result.fact_count == 20
        assert len(result.facts) == 20
        assert result.source_format == "instance"
        assert len(result.contexts) == 4
        assert len(result.units) == 1
        assert len(result.schema_refs) == 1
        assert len(result.role_refs) == 0
        assert len(result.arcrole_refs) == 0
        assert len(result.footnote_links) == 0
        assert len(result.ignored_elements) == 0

    @pytest.mark.medium
    def test_parse_xbrl_preserves_full_value_for_mixed_content_fact(self) -> None:
        """子要素を含む Fact でも value_raw が途中で欠落しない。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        result = parse_xbrl_facts(data, source_path="simple_pl.xbrl")
        mixed_fact = next(
            fact
            for fact in result.facts
            if fact.local_name == "NotesRegardingConsolidatedFinancialStatementsTextBlock"
        )
        assert mixed_fact.value_raw == "前期の業績は注記参照の通りです。"
        assert mixed_fact.value_inner_xml is not None
        assert "<sub>注記参照</sub>" in mixed_fact.value_inner_xml

    @pytest.mark.small
    def test_parse_xbrl_allows_large_text_node_fact(self) -> None:
        """10MB 超の textBlock Fact を正常にパースできる。"""
        large_text = "A" * (11 * 1024 * 1024)
        body = (
            '<jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock '
            f'contextRef="ctx1">{large_text}'
            "</jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock>"
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.fact_count == 1
        assert result.facts[0].value_raw is not None
        assert len(result.facts[0].value_raw) == len(large_text)

    @pytest.mark.small
    def test_parse_xbrl_uses_root_children_only_for_fact_detection(self) -> None:
        """ルート直下の子要素のみが Fact として抽出され、孫要素は含まれない。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">'
            "1000"
            "</jppfs_cor:NetSales>"
            "<jppfs_cor:Wrapper>"
            '<jppfs_cor:Nested contextRef="ctx1" unitRef="JPY" decimals="-6">999</jppfs_cor:Nested>'
            "</jppfs_cor:Wrapper>"
        )
        with pytest.warns(EdinetWarning) as caught:
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        messages = [str(warning.message) for warning in caught]
        assert any("ネストされた Fact 候補" in message for message in messages)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "NetSales"
        assert len(result.ignored_elements) == 1
        assert "ネストされた Fact 候補" in result.ignored_elements[0].reason

    @pytest.mark.small
    def test_parse_xbrl_parses_decimals_negative_and_inf_literal(self) -> None:
        """decimals="-6" は int(-6)、"INF" は文字列 "INF" として解析される。"""
        body = (
            '<jppfs_cor:A contextRef="ctx1" unitRef="JPY" decimals="-6">1</jppfs_cor:A>'
            '<jppfs_cor:B contextRef="ctx1" unitRef="JPY" decimals="INF">2</jppfs_cor:B>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.facts[0].decimals == -6
        assert isinstance(result.facts[0].decimals, int)
        assert result.facts[1].decimals == "INF"

    @pytest.mark.small
    def test_parse_xbrl_parses_decimals_inf_with_whitespace_and_lowercase(self) -> None:
        """decimals=" inf " は "INF" として正規化される。"""
        body = '<jppfs_cor:A contextRef="ctx1" unitRef="JPY" decimals=" inf ">1</jppfs_cor:A>'
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.facts[0].decimals == "INF"

    @pytest.mark.small
    def test_parse_xbrl_handles_xsi_nil_fact(self) -> None:
        """xsi:nil="true" の Fact は value_raw=None, is_nil=True。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" '
            'decimals="-6" xsi:nil="true"/>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        fact = result.facts[0]
        assert fact.value_raw is None
        assert fact.is_nil is True

    @pytest.mark.small
    def test_parse_xbrl_raises_on_empty_non_nil_text_fact_in_strict_mode(self) -> None:
        """strict=True では非 nil 空値のテキスト Fact をエラーにする。"""
        body = '<jpdei_cor:X contextRef="ctx1"></jpdei_cor:X>'
        with pytest.raises(EdinetParseError, match="非 nil Fact の値が空"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    @pytest.mark.small
    def test_parse_xbrl_warns_and_skips_empty_non_nil_text_fact_in_lenient_mode(self) -> None:
        """strict=False では非 nil 空値のテキスト Fact を警告してスキップする。"""
        body = (
            '<jpdei_cor:X contextRef="ctx1"></jpdei_cor:X>'
            '<jpdei_cor:Y contextRef="ctx1">ok</jpdei_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="非 nil Fact の値が空"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"
        assert len(result.ignored_elements) == 1
        assert "非 nil Fact の値が空" in result.ignored_elements[0].reason

    @pytest.mark.medium
    def test_parse_xbrl_raises_parse_error_on_invalid_xml(self) -> None:
        """壊れた XML に対して EdinetParseError が送出される。"""
        data = load_xbrl_bytes("invalid_xml.xbrl")
        with pytest.raises(EdinetParseError) as exc_info:
            parse_xbrl_facts(data, source_path="invalid_xml.xbrl")
        assert exc_info.value.__cause__ is not None

    @pytest.mark.medium
    def test_parse_xbrl_rejects_non_xbrl_root(self) -> None:
        """ルートが xbrli:xbrl でない XML は EdinetParseError。"""
        data = load_xbrl_bytes("non_xbrl_root.xbrl")
        with pytest.raises(EdinetParseError):
            parse_xbrl_facts(data, source_path="non_xbrl_root.xbrl")

    @pytest.mark.medium
    def test_parse_xbrl_error_message_includes_source_path(self) -> None:
        """エラーメッセージに source_path が含まれる。"""
        data = load_xbrl_bytes("non_xbrl_root.xbrl")
        with pytest.raises(EdinetParseError, match="non_xbrl_root.xbrl"):
            parse_xbrl_facts(data, source_path="non_xbrl_root.xbrl")

    @pytest.mark.medium
    def test_parse_xbrl_keeps_ifrs_namespace_facts_without_jppfs_assumption(
        self,
    ) -> None:
        """IFRS namespace (jpigp_cor) の Fact も正しく抽出される。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        result = parse_xbrl_facts(data)
        ifrs_facts = [f for f in result.facts if "jpigp" in f.namespace_uri]
        assert len(ifrs_facts) >= 1
        assert ifrs_facts[0].local_name == "Revenue"

    @pytest.mark.medium
    def test_parse_xbrl_sets_source_line_on_facts(self) -> None:
        """各 Fact に元 XML の行番号が付与される。"""
        data = load_xbrl_bytes("simple_pl.xbrl")
        result = parse_xbrl_facts(data, source_path="simple_pl.xbrl")
        assert result.fact_count > 0
        assert all(fact.source_line is not None and fact.source_line > 0 for fact in result.facts)


# ===========================================================================
# P1 テスト（7 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestParseXbrlP1:
    """P1: 推奨テスト群。"""

    def test_parse_xbrl_handles_text_fact_without_unitref(self) -> None:
        """テキスト Fact は unit_ref=None。"""
        body = '<jpdei_cor:X contextRef="ctx1">hello</jpdei_cor:X>'
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.facts[0].unit_ref is None

    def test_parse_xbrl_preserves_duplicate_facts(self) -> None:
        """同一 concept が複数回出現しても全件保持する。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.fact_count == 2
        assert result.facts[0].local_name == "NetSales"
        assert result.facts[1].local_name == "NetSales"
        assert result.facts[0].value_raw == "100"
        assert result.facts[1].value_raw == "100"

    def test_parse_xbrl_is_prefix_independent(self) -> None:
        """prefix が異なっても namespace URI で正しく抽出される。"""
        xbrl = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<xbrli:xbrl"
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:link="http://www.xbrl.org/2003/linkbase"'
            '  xmlns:xlink="http://www.w3.org/1999/xlink"'
            '  xmlns:custom="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">'
            '<link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>'
            '<xbrli:context id="ctx1">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier>'
            "</xbrli:entity>"
            "<xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>"
            "</xbrli:context>"
            '<xbrli:unit id="JPY"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>'
            '<custom:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">999</custom:NetSales>'
            "</xbrli:xbrl>"
        ).encode()
        result = parse_xbrl_facts(xbrl)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "NetSales"
        assert _JPPFS_NS in result.facts[0].namespace_uri

    def test_parse_xbrl_rejects_invalid_decimals_with_attribute_context(self) -> None:
        """decimals="abc" はエラーになり、メッセージに decimals と abc が含まれる。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="abc">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="decimals") as exc_info:
            parse_xbrl_facts(_wrap_xbrl(body))
        assert "abc" in str(exc_info.value)

    def test_parse_xbrl_warns_and_skips_fact_with_invalid_decimals_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では不正 decimals を警告して当該 Fact をスキップする。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="abc">1</jppfs_cor:X>'
            '<jppfs_cor:Y contextRef="ctx1" unitRef="JPY" decimals="0">2</jppfs_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="不正な decimals 属性値"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"
        assert len(result.ignored_elements) == 1
        assert "decimals" in result.ignored_elements[0].reason

    def test_parse_xbrl_raises_on_decimals_without_unitref_in_strict_mode(self) -> None:
        """strict=True では unitRef なし + decimals ありをエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="unitRef がないのに decimals"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_and_skips_decimals_without_unitref_in_lenient_mode(self) -> None:
        """strict=False では unitRef なし + decimals ありを警告してスキップする。"""
        body = '<jppfs_cor:X contextRef="ctx1" decimals="-6">1</jppfs_cor:X>'
        with pytest.warns(EdinetWarning, match="unitRef がないのに decimals"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 0
        assert len(result.ignored_elements) == 1
        assert "unitRef" in result.ignored_elements[0].reason

    def test_parse_xbrl_raises_on_missing_decimals_for_numeric_fact_in_strict_mode(self) -> None:
        """strict=True では unitRef がある非 nil Fact の decimals 欠落をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="decimals がない数値 Fact"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_and_skips_missing_decimals_for_numeric_fact_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では unitRef あり + decimals なしを警告してスキップする。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY">1</jppfs_cor:X>'
            '<jppfs_cor:Y contextRef="ctx1" unitRef="JPY" decimals="0">2</jppfs_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="decimals がない数値 Fact"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"
        assert len(result.ignored_elements) == 1
        assert "decimals" in result.ignored_elements[0].reason

    def test_parse_xbrl_returns_empty_tuple_when_no_fact(self) -> None:
        """Fact が 0 件でもエラーにならず空 tuple を返す。"""
        result = parse_xbrl_facts(_wrap_xbrl(""))
        assert result.facts == ()
        assert result.fact_count == 0

    def test_parse_xbrl_handles_utf8_bom(self) -> None:
        """BOM 付き bytes がエラーにならない。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0">42</jppfs_cor:X>'
        bom = b"\xef\xbb\xbf"
        data = bom + _wrap_xbrl(body)
        result = parse_xbrl_facts(data)
        assert result.fact_count == 1

    def test_parse_xbrl_handles_xsi_nil_numeric_one(self) -> None:
        """xsi:nil="1" も nil として扱う。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" '
            'decimals="-6" xsi:nil="1"/>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        fact = result.facts[0]
        assert fact.is_nil is True
        assert fact.value_raw is None

    def test_parse_xbrl_raises_on_invalid_xsi_nil_value_in_strict_mode(self) -> None:
        """strict=True では不正な xsi:nil 値をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0" xsi:nil="maybe"/>'
        with pytest.raises(EdinetParseError, match="不正な xsi:nil"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_and_skips_fact_with_invalid_xsi_nil_value_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では不正な xsi:nil 値を警告して当該 Fact をスキップする。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0" xsi:nil="maybe"/>'
            '<jppfs_cor:Y contextRef="ctx1" unitRef="JPY" decimals="0">2</jppfs_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="不正な xsi:nil"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"
        assert len(result.ignored_elements) == 1
        assert "xsi:nil" in result.ignored_elements[0].reason

    def test_parse_xbrl_raises_on_nil_fact_with_non_empty_value_in_strict_mode(self) -> None:
        """strict=True では xsi:nil=true なのに値を持つ Fact をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" xsi:nil="true">123</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="xsi:nil が真なのに値を持つ Fact"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_raises_on_empty_non_nil_numeric_fact_in_strict_mode(self) -> None:
        """strict=True では unitRef がある非 nil 空値 Fact をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0"></jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="非 nil Fact の値が空"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_raises_on_non_numeric_value_in_numeric_fact_in_strict_mode(self) -> None:
        """strict=True では数値 Fact の値が数値でない場合エラーにする（S-10）。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0">abc</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="数値 Fact の値が数値として解釈できません"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_and_skips_non_numeric_value_in_numeric_fact_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では数値 Fact の非数値の値を警告しつつスキップする（S-10）。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY" decimals="0">abc</jppfs_cor:X>'
        with pytest.warns(EdinetWarning, match="数値 Fact の値が数値として解釈できません"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 0
        assert len(result.ignored_elements) == 1

    def test_parse_xbrl_defaults_to_strict_mode_and_raises_on_missing_contextref(self) -> None:
        """strict 指定なし（既定値）では contextRef 欠落 Fact をエラーにする。"""
        body = '<jppfs_cor:X unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="contextRef がない Fact"):
            parse_xbrl_facts(_wrap_xbrl(body))

    def test_parse_xbrl_warns_on_duplicate_fact_id_in_lenient_mode(self) -> None:
        """strict=False では重複 Fact id を警告しつつ Fact は保持する。"""
        body = (
            '<jpdei_cor:A contextRef="ctx1" id="dup">a</jpdei_cor:A>'
            '<jpdei_cor:B contextRef="ctx1" id="dup">b</jpdei_cor:B>'
        )
        with pytest.warns(EdinetWarning, match="重複した Fact id"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 2
        assert result.facts[0].fact_id == "dup"
        assert result.facts[1].fact_id == "dup"

    def test_parse_xbrl_raises_on_duplicate_context_id_in_strict_mode(self) -> None:
        """strict=True では重複 context id をエラーにする。"""
        body = "<xbrli:context id=\"ctx1\"/>"
        with pytest.raises(EdinetParseError, match="重複した context id"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_inner_xml_keeps_namespace_declarations(self) -> None:
        """value_inner_xml が名前空間付き要素でも単体再パース可能。"""
        body = (
            "<jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock "
            "contextRef=\"ctx1\">before<xhtml:p>abc</xhtml:p>after"
            "</jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock>"
        )
        result = parse_xbrl_facts(
            _wrap_xbrl(
                body,
                extra_ns='xmlns:xhtml="http://www.w3.org/1999/xhtml"',
            ),
        )
        inner_xml = result.facts[0].value_inner_xml
        assert inner_xml is not None
        assert "<xhtml:p" in inner_xml
        etree.fromstring(f"<root>{inner_xml}</root>")

    def test_parse_xbrl_warns_and_skips_fact_without_contextref_in_lenient_mode(self) -> None:
        """strict=False では contextRef 欠落要素を警告してスキップする。"""
        body = '<jppfs_cor:X unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.warns(EdinetWarning, match="contextRef がない Fact"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 0
        assert len(result.ignored_elements) == 1
        assert result.ignored_elements[0].local_name == "X"

    def test_parse_xbrl_warns_and_skips_fact_with_empty_contextref_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では空文字 contextRef の Fact を警告してスキップする。"""
        body = '<jppfs_cor:X contextRef="" unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.warns(EdinetWarning, match="contextRef が空文字"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 0

    def test_parse_xbrl_raises_on_missing_contextref_in_strict_mode(self) -> None:
        """strict=True では contextRef 欠落 Fact をエラーにする。"""
        body = '<jppfs_cor:X unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="contextRef がない Fact"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_raises_on_empty_contextref_in_strict_mode(self) -> None:
        """strict=True では空文字 contextRef をエラーにする。"""
        body = '<jppfs_cor:X contextRef="" unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="contextRef が空文字"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_on_nested_fact_candidate_in_strict_mode(self) -> None:
        """strict=True でもネストされた Fact 候補は警告+記録に回す。"""
        body = (
            "<jppfs_cor:Wrapper>"
            '<jppfs_cor:Nested contextRef="ctx1" unitRef="JPY" decimals="-6">999</jppfs_cor:Nested>'
            "</jppfs_cor:Wrapper>"
        )
        with pytest.warns(EdinetWarning, match="ネストされた Fact 候補"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=True)
        assert result.fact_count == 0
        assert len(result.ignored_elements) == 1

    def test_parse_xbrl_warns_and_skips_fact_with_undefined_contextref_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では未定義 contextRef の Fact を警告してスキップする。"""
        body = (
            '<jppfs_cor:X contextRef="ctx_missing" unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
            '<jppfs_cor:Y contextRef="ctx1" unitRef="JPY" decimals="-6">2</jppfs_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="未定義の contextRef"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"

    def test_parse_xbrl_raises_on_undefined_contextref_in_strict_mode(self) -> None:
        """strict=True では未定義 contextRef をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx_missing" unitRef="JPY" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="未定義の contextRef"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_and_skips_fact_with_undefined_unitref_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では未定義 unitRef の Fact を警告してスキップする。"""
        body = (
            '<jppfs_cor:X contextRef="ctx1" unitRef="JPY_MISSING" decimals="-6">1</jppfs_cor:X>'
            '<jppfs_cor:Y contextRef="ctx1" unitRef="JPY" decimals="-6">2</jppfs_cor:Y>'
        )
        with pytest.warns(EdinetWarning, match="未定義の unitRef"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 1
        assert result.facts[0].local_name == "Y"

    def test_parse_xbrl_raises_on_undefined_unitref_in_strict_mode(self) -> None:
        """strict=True では未定義 unitRef をエラーにする。"""
        body = '<jppfs_cor:X contextRef="ctx1" unitRef="JPY_MISSING" decimals="-6">1</jppfs_cor:X>'
        with pytest.raises(EdinetParseError, match="未定義の unitRef"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_raises_on_missing_schemaref_in_strict_mode(self) -> None:
        """strict=True では schemaRef 欠落をエラーにする。"""
        with_schema = _wrap_xbrl('<jpdei_cor:X contextRef="ctx1">ok</jpdei_cor:X>')
        without_schema = with_schema.replace(
            b'<link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>',
            b"",
        )
        with pytest.raises(EdinetParseError, match="schemaRef が見つかりません"):
            parse_xbrl_facts(without_schema, strict=True)

    def test_parse_xbrl_warns_on_missing_schemaref_in_lenient_mode(self) -> None:
        """strict=False では schemaRef 欠落を警告しつつ継続する。"""
        with_schema = _wrap_xbrl('<jpdei_cor:X contextRef="ctx1">ok</jpdei_cor:X>')
        without_schema = with_schema.replace(
            b'<link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>',
            b"",
        )
        with pytest.warns(EdinetWarning, match="schemaRef が見つかりません"):
            result = parse_xbrl_facts(without_schema, strict=False)
        assert result.fact_count == 1
        assert len(result.schema_refs) == 0

    def test_parse_xbrl_raises_on_multiple_schemarefs_in_strict_mode(self) -> None:
        """strict=True では schemaRef 複数をエラーにする。"""
        body = (
            '<link:schemaRef xlink:type="simple" xlink:href="another.xsd"/>'
            '<jpdei_cor:X contextRef="ctx1">ok</jpdei_cor:X>'
        )
        with pytest.raises(EdinetParseError, match="schemaRef が複数存在します"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_records_unknown_xbrli_and_link_elements_as_ignored(self) -> None:
        """未知の xbrli/link 要素を ignored_elements に記録する。"""
        body = (
            "<xbrli:foo/>"
            '<link:bar xlink:type="simple"/>'
            '<jpdei_cor:X contextRef="ctx1">ok</jpdei_cor:X>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body), strict=True)
        assert result.fact_count == 1
        assert len(result.ignored_elements) == 2
        assert all(
            "xbrli/link 名前空間の管理要素" in ignored.reason
            for ignored in result.ignored_elements
        )

    def test_parse_xbrl_collects_role_and_arcrole_refs(self) -> None:
        """roleRef / arcroleRef を別レーンで保持する。"""
        body = (
            '<link:roleRef roleURI="http://example.com/role/Statement" '
            'xlink:type="simple" xlink:href="example.xsd#role_Statement"/>'
            '<link:arcroleRef arcroleURI="http://example.com/arcrole/parent-child" '
            'xlink:type="simple" xlink:href="example.xsd#arcrole_parent_child"/>'
            '<jpdei_cor:X contextRef="ctx1">ok</jpdei_cor:X>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body))
        assert result.fact_count == 1
        assert len(result.role_refs) == 1
        assert result.role_refs[0].role_uri == "http://example.com/role/Statement"
        assert result.role_refs[0].href == "example.xsd#role_Statement"
        assert len(result.arcrole_refs) == 1
        assert result.arcrole_refs[0].arcrole_uri == "http://example.com/arcrole/parent-child"
        assert result.arcrole_refs[0].href == "example.xsd#arcrole_parent_child"

    def test_parse_xbrl_preserves_namespace_declarations_in_raw_context_and_unit_xml(
        self,
    ) -> None:
        """RawContext/RawUnit の XML で in-scope 名前空間宣言を保持する。"""
        body = (
            '<xbrli:context id="ctx2">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier>'
            "</xbrli:entity>"
            "<xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>"
            "<xbrli:scenario>"
            '<xbrldi:explicitMember dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">'
            "jppfs_cor:NonConsolidatedMember"
            "</xbrldi:explicitMember>"
            "</xbrli:scenario>"
            "</xbrli:context>"
            '<jppfs_cor:X contextRef="ctx2" unitRef="JPY" decimals="0">1</jppfs_cor:X>'
        )
        result = parse_xbrl_facts(
            _wrap_xbrl(
                body,
                extra_ns=(
                    'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
                    'xmlns:iso4217="http://www.xbrl.org/2003/iso4217"'
                ),
            ),
        )
        context = next(ctx for ctx in result.contexts if ctx.context_id == "ctx2")
        assert "xmlns:xbrldi=" in context.xml
        assert "xmlns:jppfs_cor=" in context.xml
        assert "xmlns:iso4217=" in result.units[0].xml

    def test_parse_xbrl_raises_on_inconsistent_duplicate_fact_in_strict_mode(self) -> None:
        """strict=True では不整合な重複 Fact をエラーにする。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">200</jppfs_cor:NetSales>'
        )
        with pytest.raises(EdinetParseError, match="不整合な重複 Fact"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_allows_numeric_lexical_variant_duplicates(self) -> None:
        """100 と 100.0 は同値として重複エラーにしない。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100.0</jppfs_cor:NetSales>'
        )
        result = parse_xbrl_facts(_wrap_xbrl(body), strict=True)
        assert result.fact_count == 2
        assert result.facts[0].value_raw == "100"
        assert result.facts[1].value_raw == "100.0"

    def test_parse_xbrl_warns_on_inconsistent_duplicate_fact_in_lenient_mode(self) -> None:
        """strict=False では不整合な重複 Fact を警告しつつ保持する。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">200</jppfs_cor:NetSales>'
        )
        with pytest.warns(EdinetWarning, match="不整合な重複 Fact"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 2

    def test_parse_xbrl_raises_on_duplicate_fact_with_mismatched_decimals_in_strict_mode(
        self,
    ) -> None:
        """strict=True では重複 Fact の decimals 不一致をエラーにする。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="0">100.0</jppfs_cor:NetSales>'
        )
        with pytest.raises(EdinetParseError, match="重複 Fact の decimals が不一致"):
            parse_xbrl_facts(_wrap_xbrl(body), strict=True)

    def test_parse_xbrl_warns_on_duplicate_fact_with_mismatched_decimals_in_lenient_mode(
        self,
    ) -> None:
        """strict=False では重複 Fact の decimals 不一致を警告しつつ保持する。"""
        body = (
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="-6">100</jppfs_cor:NetSales>'
            '<jppfs_cor:NetSales contextRef="ctx1" unitRef="JPY" decimals="0">100.0</jppfs_cor:NetSales>'
        )
        with pytest.warns(EdinetWarning, match="重複 Fact の decimals が不一致"):
            result = parse_xbrl_facts(_wrap_xbrl(body), strict=False)
        assert result.fact_count == 2

    def test_parse_xbrl_resolves_inherited_xml_lang_for_fact_signature(self) -> None:
        """xml:lang が親要素で宣言されていても継承解決して取得する。"""
        xbrl = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xbrli:xbrl'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:link="http://www.xbrl.org/2003/linkbase"'
            '  xmlns:xlink="http://www.w3.org/1999/xlink"'
            '  xmlns:jpdei_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2023-11-01/jpdei_cor"'
            '  xml:lang="ja">'
            '<link:schemaRef xlink:type="simple" xlink:href="example.xsd"/>'
            '<xbrli:context id="ctx1">'
            "<xbrli:entity>"
            '<xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier>'
            "</xbrli:entity>"
            "<xbrli:period><xbrli:instant>2025-03-31</xbrli:instant></xbrli:period>"
            "</xbrli:context>"
            '<jpdei_cor:X contextRef="ctx1">a</jpdei_cor:X>'
            '<jpdei_cor:X contextRef="ctx1">b</jpdei_cor:X>'
            "</xbrli:xbrl>"
        ).encode()
        with pytest.raises(EdinetParseError, match="不整合な重複 Fact"):
            parse_xbrl_facts(xbrl, strict=True)

    def test_parse_xbrl_inner_xml_preserves_prefixes_used_in_qname_values(self) -> None:
        """value_inner_xml で QName値に必要な prefix 宣言を保持する。"""
        body = (
            "<jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock "
            "contextRef=\"ctx1\">"
            "<xbrli:scenario>"
            '<xbrldi:explicitMember dimension="jppfs_cor:ConsolidatedOrNonConsolidatedAxis">'
            "jppfs_cor:NonConsolidatedMember"
            "</xbrldi:explicitMember>"
            "</xbrli:scenario>"
            "</jppfs_cor:NotesRegardingConsolidatedFinancialStatementsTextBlock>"
        )
        result = parse_xbrl_facts(
            _wrap_xbrl(
                body,
                extra_ns='xmlns:xbrldi="http://xbrl.org/2006/xbrldi"',
            ),
        )
        inner_xml = result.facts[0].value_inner_xml
        assert inner_xml is not None
        assert "xmlns:xbrldi=" in inner_xml
        assert "xmlns:jppfs_cor=" in inner_xml
