"""iXBRL パーサーのテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.ixbrl_parser import merge_ixbrl_results, parse_ixbrl_facts
from edinet.xbrl.parser import (
    IgnoredElement,
    ParsedXBRL,
    RawArcroleRef,
    RawContext,
    RawFact,
    RawFootnoteLink,
    RawRoleRef,
    RawSchemaRef,
    RawUnit,
)

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ixbrl"


def _load(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


# -----------------------------------------------------------------------
# P0: 基本テスト
# -----------------------------------------------------------------------


class TestBasicNumericFact:
    """nonFraction の基本パースを検証する。"""

    def test_basic_numeric_fact(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        assert result.source_format == "inline"
        assert result.fact_count >= 2

        # scale=6, format=numdotdecimal の Fact を検索
        net_sales = [f for f in result.facts if f.local_name == "NetSales"]
        assert len(net_sales) == 1
        fact = net_sales[0]
        assert fact.namespace_uri == "http://www.tse.or.jp/2024/taxonomy/tse-ed-t"
        assert fact.context_ref == "CurrentYearDuration"
        assert fact.unit_ref == "JPY"
        assert fact.decimals == -6

    def test_scale_application(self) -> None:
        """scale=6, text="8,225" → value_raw="8225000000"."""
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        net_sales = [f for f in result.facts if f.local_name == "NetSales"][0]
        assert net_sales.value_raw == "8225000000"

    def test_no_scale_numeric(self) -> None:
        """scale=0 の場合はそのままの値。"""
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        cash = [f for f in result.facts if f.local_name == "CashAndDeposits"][0]
        assert cash.value_raw == "500000"

    def test_format_numdotdecimal(self) -> None:
        """カンマが除去される。"""
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        net_sales = [f for f in result.facts if f.local_name == "NetSales"][0]
        # 8,225 → 8225 → ×10^6 → 8225000000
        assert net_sales.value_raw == "8225000000"

    def test_concept_qname_clark_notation(self) -> None:
        """concept_qname が Clark notation である。"""
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        net_sales = [f for f in result.facts if f.local_name == "NetSales"][0]
        assert net_sales.concept_qname == "{http://www.tse.or.jp/2024/taxonomy/tse-ed-t}NetSales"


class TestSignNegative:
    """sign="-" の検証。"""

    def test_sign_negative(self) -> None:
        """sign="-" で負値になる。"""
        ixbrl = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2008/inlineXBRL"
      xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2020-02-12"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:link="http://www.xbrl.org/2003/linkbase"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:jppfs_cor="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
      xml:lang="ja">
<head><title>Test</title></head>
<body>
  <ix:header>
    <ix:references><link:schemaRef xlink:type="simple" xlink:href="t.xsd"/></ix:references>
    <ix:resources>
      <xbrli:context id="ctx"><xbrli:entity><xbrli:identifier scheme="http://example.com">X</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="JPY"><xbrli:measure>iso4217:JPY</xbrli:measure></xbrli:unit>
    </ix:resources>
  </ix:header>
  <ix:nonFraction name="jppfs_cor:AllowanceForDoubtfulAccounts" contextRef="ctx"
                  unitRef="JPY" decimals="0" scale="3" sign="-"
                  format="ixt:numdotdecimal">500</ix:nonFraction>
</body>
</html>"""
        result = parse_ixbrl_facts(ixbrl)
        fact = result.facts[0]
        assert fact.value_raw == "-500000"


class TestTextFact:
    """nonNumeric の基本パースを検証する。"""

    def test_text_fact(self) -> None:
        result = parse_ixbrl_facts(_load("simple_text.htm"))
        doc = [f for f in result.facts if f.local_name == "DocumentName"][0]
        assert doc.value_raw == "決算短信"
        assert doc.unit_ref is None
        assert doc.decimals is None

    def test_format_dateyearmonthdaycjk(self) -> None:
        result = parse_ixbrl_facts(_load("simple_text.htm"))
        date_fact = [f for f in result.facts if f.local_name == "FilingDate"][0]
        assert date_fact.value_raw == "2026-03-04"

    def test_format_booleantrue(self) -> None:
        result = parse_ixbrl_facts(_load("simple_text.htm"))
        bt = [f for f in result.facts if f.local_name == "BooleanTrue"][0]
        assert bt.value_raw == "true"

    def test_format_booleanfalse(self) -> None:
        result = parse_ixbrl_facts(_load("simple_text.htm"))
        bf = [f for f in result.facts if f.local_name == "BooleanFalse"][0]
        assert bf.value_raw == "false"


class TestHiddenFacts:
    """ix:hidden 内の Fact 抽出を検証する。"""

    def test_hidden_facts_extracted(self) -> None:
        result = parse_ixbrl_facts(_load("hidden_facts.htm"))
        edinet_code = [f for f in result.facts if f.local_name == "EDINETCodeDEI"]
        assert len(edinet_code) == 1
        assert edinet_code[0].value_raw == "E05070"

    def test_hidden_numeric_extracted(self) -> None:
        result = parse_ixbrl_facts(_load("hidden_facts.htm"))
        cash = [f for f in result.facts if f.local_name == "CashAndDeposits"]
        assert len(cash) == 1
        assert cash[0].value_raw == "100000"

    def test_total_facts_include_body_and_hidden(self) -> None:
        result = parse_ixbrl_facts(_load("hidden_facts.htm"))
        # 2 hidden + 1 body = 3
        assert result.fact_count == 3


class TestResources:
    """context / unit / schemaRef の収集を検証する。"""

    def test_context_collection(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        assert len(result.contexts) == 1
        assert result.contexts[0].context_id == "CurrentYearDuration"

    def test_unit_collection(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        assert len(result.units) == 1
        assert result.units[0].unit_id == "JPY"

    def test_schema_ref_collection(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        assert len(result.schema_refs) == 1
        assert result.schema_refs[0].href == "test.xsd"


class TestSourceFormat:
    """source_format が "inline" であることを検証する。"""

    def test_source_format_inline(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        assert result.source_format == "inline"


class TestNilFact:
    """xsi:nil="true" の Fact を検証する。"""

    def test_nil_non_numeric(self) -> None:
        result = parse_ixbrl_facts(_load("nil_facts.htm"))
        nil_facts = [f for f in result.facts if f.local_name == "AccountingStandardDEI"]
        assert len(nil_facts) == 1
        assert nil_facts[0].is_nil is True
        assert nil_facts[0].value_raw is None

    def test_nil_non_fraction(self) -> None:
        result = parse_ixbrl_facts(_load("nil_facts.htm"))
        nil_facts = [f for f in result.facts if f.local_name == "CashAndDeposits"]
        assert len(nil_facts) == 1
        assert nil_facts[0].is_nil is True
        assert nil_facts[0].value_raw is None


class TestErrorHandling:
    """エラーケースを検証する。"""

    def test_malformed_xml_raises(self) -> None:
        with pytest.raises(EdinetParseError, match="XML の解析に失敗しました"):
            parse_ixbrl_facts(_load("malformed.htm"))

    def test_non_ixbrl_root_raises(self) -> None:
        """xbrli:xbrl ルートの従来 XBRL を渡すとエラー。"""
        xbrl_bytes = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
</xbrli:xbrl>"""
        with pytest.raises(EdinetParseError, match="iXBRL ルート要素が見つかりません"):
            parse_ixbrl_facts(xbrl_bytes)

    def test_html_without_ix_namespace_raises(self) -> None:
        """ix 名前空間のない html を渡すとエラー。"""
        html_bytes = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Not iXBRL</title></head>
<body></body>
</html>"""
        with pytest.raises(EdinetParseError, match="ix 名前空間.*が定義されていません"):
            parse_ixbrl_facts(html_bytes)


# -----------------------------------------------------------------------
# P1: 推奨テスト
# -----------------------------------------------------------------------


class TestNamespaceResolution:
    """プレフィクス → URI 解決を検証する。"""

    def test_namespace_resolution(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        net_sales = [f for f in result.facts if f.local_name == "NetSales"][0]
        assert net_sales.namespace_uri == "http://www.tse.or.jp/2024/taxonomy/tse-ed-t"

    def test_edinet_namespace_resolution(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        cash = [f for f in result.facts if f.local_name == "CashAndDeposits"][0]
        assert cash.namespace_uri == "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"


class TestOrderPreservation:
    """出現順 order フィールドを検証する。"""

    def test_order_preservation(self) -> None:
        result = parse_ixbrl_facts(_load("simple_numeric.htm"))
        orders = [f.order for f in result.facts]
        assert orders == list(range(len(orders)))


class TestXmlLangInheritance:
    """xml:lang 継承を検証する。"""

    def test_xml_lang_inheritance(self) -> None:
        result = parse_ixbrl_facts(_load("simple_text.htm"))
        # html 要素に xml:lang="ja" が設定されている
        for fact in result.facts:
            assert fact.xml_lang == "ja"


class TestEmptyIxbrl:
    """Fact 0 件の iXBRL を検証する。"""

    def test_empty_ixbrl(self) -> None:
        result = parse_ixbrl_facts(_load("empty.htm"))
        assert result.fact_count == 0
        assert result.source_format == "inline"


class TestDecimalsInf:
    """decimals="INF" を検証する。"""

    def test_decimals_inf(self) -> None:
        ixbrl = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2008/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:link="http://www.xbrl.org/2003/linkbase"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:ns="http://example.com/ns"
      xml:lang="ja">
<head><title>T</title></head>
<body>
  <ix:header>
    <ix:references><link:schemaRef xlink:type="simple" xlink:href="t.xsd"/></ix:references>
    <ix:resources>
      <xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://example.com">X</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="u"><xbrli:measure>pure</xbrli:measure></xbrli:unit>
    </ix:resources>
  </ix:header>
  <ix:nonFraction name="ns:Ratio" contextRef="c" unitRef="u" decimals="INF" scale="0">3.14</ix:nonFraction>
</body>
</html>"""
        result = parse_ixbrl_facts(ixbrl)
        assert result.facts[0].decimals == "INF"
        assert result.facts[0].value_raw == "3.14"


class TestContinuationWarning:
    """ix:continuation 検出時に警告が出ることを検証する。"""

    def test_continuation_warning(self) -> None:
        with pytest.warns(EdinetWarning, match="ix:continuation は現在未対応です"):
            parse_ixbrl_facts(_load("continuation.htm"))


class TestScaleVariations:
    """scale の各種パターンを検証する。"""

    def _make_ixbrl(self, scale: str, text: str) -> bytes:
        return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2008/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:link="http://www.xbrl.org/2003/linkbase"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:ns="http://example.com/ns"
      xml:lang="ja">
<head><title>T</title></head>
<body>
  <ix:header>
    <ix:references><link:schemaRef xlink:type="simple" xlink:href="t.xsd"/></ix:references>
    <ix:resources>
      <xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://example.com">X</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="u"><xbrli:measure>pure</xbrli:measure></xbrli:unit>
    </ix:resources>
  </ix:header>
  <ix:nonFraction name="ns:Val" contextRef="c" unitRef="u" decimals="0" scale="{scale}">{text}</ix:nonFraction>
</body>
</html>""".encode()

    def test_scale_zero(self) -> None:
        result = parse_ixbrl_facts(self._make_ixbrl("0", "42"))
        assert result.facts[0].value_raw == "42"

    def test_scale_negative(self) -> None:
        """scale=-2 → 75 × 10^(-2) = 0.75."""
        result = parse_ixbrl_facts(self._make_ixbrl("-2", "75"))
        assert result.facts[0].value_raw == "0.75"


class TestValueInnerXml:
    """nonNumeric 内の子要素（value_inner_xml）を検証する。"""

    def test_value_inner_xml(self) -> None:
        ixbrl = """\
<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2008/inlineXBRL"
      xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:link="http://www.xbrl.org/2003/linkbase"
      xmlns:xlink="http://www.w3.org/1999/xlink"
      xmlns:ns="http://example.com/ns"
      xml:lang="ja">
<head><title>T</title></head>
<body>
  <ix:header>
    <ix:references><link:schemaRef xlink:type="simple" xlink:href="t.xsd"/></ix:references>
    <ix:resources>
      <xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://example.com">X</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
    </ix:resources>
  </ix:header>
  <ix:nonNumeric name="ns:Note" contextRef="c">Part1<br/>Part2</ix:nonNumeric>
</body>
</html>""".encode()
        result = parse_ixbrl_facts(ixbrl)
        fact = result.facts[0]
        assert fact.value_raw == "Part1Part2"
        assert fact.value_inner_xml is not None
        assert "br" in fact.value_inner_xml


class TestBomHandling:
    """UTF-8 BOM 付きファイルの処理を検証する。"""

    def test_bom_stripped(self) -> None:
        data = b"\xef\xbb\xbf" + _load("empty.htm")
        result = parse_ixbrl_facts(data)
        assert result.source_format == "inline"


# -----------------------------------------------------------------------
# merge_ixbrl_results テスト
# -----------------------------------------------------------------------


def _make_fact(
    local_name: str = "Item",
    order: int = 0,
    *,
    context_ref: str = "ctx",
    value_raw: str | None = "100",
) -> RawFact:
    """テスト用の最小 RawFact を作る。"""
    return RawFact(
        concept_qname=f"{{http://example.com}}{local_name}",
        namespace_uri="http://example.com",
        local_name=local_name,
        context_ref=context_ref,
        unit_ref=None,
        decimals=None,
        value_raw=value_raw,
        is_nil=False,
        fact_id=None,
        xml_lang="ja",
        source_line=1,
        order=order,
    )


def _make_parsed(
    facts: tuple[RawFact, ...] = (),
    contexts: tuple[RawContext, ...] = (),
    units: tuple[RawUnit, ...] = (),
    schema_refs: tuple[RawSchemaRef, ...] = (),
    role_refs: tuple[RawRoleRef, ...] = (),
    arcrole_refs: tuple[RawArcroleRef, ...] = (),
    footnote_links: tuple[RawFootnoteLink, ...] = (),
    ignored_elements: tuple[IgnoredElement, ...] = (),
) -> ParsedXBRL:
    """テスト用の最小 ParsedXBRL を作る。"""
    return ParsedXBRL(
        source_path="test.htm",
        source_format="inline",
        facts=facts,
        contexts=contexts,
        units=units,
        schema_refs=schema_refs,
        role_refs=role_refs,
        arcrole_refs=arcrole_refs,
        footnote_links=footnote_links,
        ignored_elements=ignored_elements,
    )


class TestMergeIxbrlResults:
    """merge_ixbrl_results() の検証。"""

    def test_merge_empty_input(self) -> None:
        """空リスト入力で全フィールド空の ParsedXBRL を返す。"""
        result = merge_ixbrl_results([])
        assert result.fact_count == 0
        assert result.source_path == "(merged)"
        assert result.source_format == "inline"
        assert result.contexts == ()
        assert result.units == ()
        assert result.schema_refs == ()

    def test_merge_single_preserves_data(self) -> None:
        """1件入力で全データが保持される。"""
        fact = _make_fact("Sales", order=0)
        ctx = RawContext(context_id="ctx1", source_line=1, xml="<ctx/>")
        unit = RawUnit(unit_id="JPY", source_line=1, xml="<unit/>")
        sr = RawSchemaRef(href="test.xsd", source_line=1, xml="<sr/>")

        parsed = _make_parsed(
            facts=(fact,),
            contexts=(ctx,),
            units=(unit,),
            schema_refs=(sr,),
        )
        result = merge_ixbrl_results([parsed])

        assert result.fact_count == 1
        assert result.facts[0].local_name == "Sales"
        assert len(result.contexts) == 1
        assert len(result.units) == 1
        assert len(result.schema_refs) == 1

    def test_merge_concatenates_facts(self) -> None:
        """2件入力で fact_count が合計になる。"""
        p1 = _make_parsed(facts=(_make_fact("A"), _make_fact("B", order=1)))
        p2 = _make_parsed(facts=(_make_fact("C"),))
        result = merge_ixbrl_results([p1, p2])
        assert result.fact_count == 3

    def test_merge_order_renumbered(self) -> None:
        """統合後の facts[i].order == i。"""
        p1 = _make_parsed(facts=(_make_fact("A", order=0), _make_fact("B", order=1)))
        p2 = _make_parsed(facts=(_make_fact("C", order=0),))
        result = merge_ixbrl_results([p1, p2])
        for i, fact in enumerate(result.facts):
            assert fact.order == i

    def test_merge_file_order_preserved(self) -> None:
        """file1 の facts が file2 より前に並ぶ。"""
        p1 = _make_parsed(facts=(_make_fact("First"),))
        p2 = _make_parsed(facts=(_make_fact("Second"),))
        result = merge_ixbrl_results([p1, p2])
        assert result.facts[0].local_name == "First"
        assert result.facts[1].local_name == "Second"

    def test_merge_contexts_deduplicated(self) -> None:
        """同一 context_id は1つだけ残る。"""
        ctx = RawContext(context_id="ctx1", source_line=1, xml="<ctx/>")
        p1 = _make_parsed(contexts=(ctx,))
        p2 = _make_parsed(contexts=(ctx,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.contexts) == 1

    def test_merge_units_deduplicated(self) -> None:
        """同一 unit_id は1つだけ残る。"""
        unit = RawUnit(unit_id="JPY", source_line=1, xml="<unit/>")
        p1 = _make_parsed(units=(unit,))
        p2 = _make_parsed(units=(unit,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.units) == 1

    def test_merge_schema_refs_deduplicated(self) -> None:
        """同一 href は1つだけ残る。"""
        sr = RawSchemaRef(href="test.xsd", source_line=1, xml="<sr/>")
        p1 = _make_parsed(schema_refs=(sr,))
        p2 = _make_parsed(schema_refs=(sr,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.schema_refs) == 1

    def test_merge_different_schema_refs_kept(self) -> None:
        """異なる href は両方残る。"""
        sr1 = RawSchemaRef(href="a.xsd", source_line=1, xml="<sr/>")
        sr2 = RawSchemaRef(href="b.xsd", source_line=2, xml="<sr/>")
        p1 = _make_parsed(schema_refs=(sr1,))
        p2 = _make_parsed(schema_refs=(sr2,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.schema_refs) == 2

    def test_merge_none_id_always_included(self) -> None:
        """context_id=None の要素は常に追加される。"""
        ctx_none = RawContext(context_id=None, source_line=1, xml="<ctx/>")
        p1 = _make_parsed(contexts=(ctx_none,))
        p2 = _make_parsed(contexts=(ctx_none,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.contexts) == 2

    def test_merge_source_format_inline(self) -> None:
        """source_format が "inline" である。"""
        result = merge_ixbrl_results([])
        assert result.source_format == "inline"

    def test_merge_ignored_elements_concatenated(self) -> None:
        """全入力の ignored_elements が連結される。"""
        ig1 = IgnoredElement(
            concept_qname="{http://example.com}X",
            namespace_uri="http://example.com",
            local_name="X",
            reason="test",
            source_line=1,
            attributes=(),
        )
        ig2 = IgnoredElement(
            concept_qname="{http://example.com}Y",
            namespace_uri="http://example.com",
            local_name="Y",
            reason="test",
            source_line=2,
            attributes=(),
        )
        p1 = _make_parsed(ignored_elements=(ig1,))
        p2 = _make_parsed(ignored_elements=(ig2,))
        result = merge_ixbrl_results([p1, p2])
        assert len(result.ignored_elements) == 2
