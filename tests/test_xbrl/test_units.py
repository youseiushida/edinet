"""structure_units のテスト。"""

from __future__ import annotations

import warnings

import pytest

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.parser import RawUnit, parse_xbrl_facts
from edinet.xbrl.units import (
    DivideMeasure,
    SimpleMeasure,
    StructuredUnit,
    structure_units,
)

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_raw_unit(
    unit_id: str | None,
    xml: str,
    source_line: int | None = None,
) -> RawUnit:
    """インライン RawUnit を生成する。

    Args:
        unit_id: Unit ID。
        xml: Unit の XML 文字列。
        source_line: 行番号。

    Returns:
        RawUnit インスタンス。
    """
    return RawUnit(unit_id=unit_id, xml=xml, source_line=source_line)


# ---------------------------------------------------------------------------
# XML 定数
# ---------------------------------------------------------------------------

JPY_XML = (
    '<xbrli:unit id="JPY"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
    "<xbrli:measure>iso4217:JPY</xbrli:measure>"
    "</xbrli:unit>"
)

USD_XML = (
    '<xbrli:unit id="USD"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
    "<xbrli:measure>iso4217:USD</xbrli:measure>"
    "</xbrli:unit>"
)

PURE_XML = (
    '<xbrli:unit id="pure"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
    "<xbrli:measure>xbrli:pure</xbrli:measure>"
    "</xbrli:unit>"
)

SHARES_XML = (
    '<xbrli:unit id="shares"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
    "<xbrli:measure>xbrli:shares</xbrli:measure>"
    "</xbrli:unit>"
)

DIVIDE_XML = (
    '<xbrli:unit id="JPYPerShares"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
    "<xbrli:divide>"
    "<xbrli:unitNumerator>"
    "<xbrli:measure>iso4217:JPY</xbrli:measure>"
    "</xbrli:unitNumerator>"
    "<xbrli:unitDenominator>"
    "<xbrli:measure>xbrli:shares</xbrli:measure>"
    "</xbrli:unitDenominator>"
    "</xbrli:divide>"
    "</xbrli:unit>"
)

TCO2E_XML = (
    '<xbrli:unit id="tCO2e"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:utr="http://www.xbrl.org/2009/utr">'
    "<xbrli:measure>utr:tCO2e</xbrli:measure>"
    "</xbrli:unit>"
)

NO_PREFIX_XML = (
    '<xbrli:unit id="custom"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
    "<xbrli:measure>CustomUnit</xbrli:measure>"
    "</xbrli:unit>"
)

MULTI_MEASURE_XML = (
    '<xbrli:unit id="multi"'
    '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
    '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
    "<xbrli:measure>iso4217:JPY</xbrli:measure>"
    "<xbrli:measure>iso4217:USD</xbrli:measure>"
    "</xbrli:unit>"
)


# ===========================================================================
# P0 テスト（12 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestStructureUnitsP0:
    """P0: 必須テスト群。"""

    def test_simple_measure_jpy(self) -> None:
        """iso4217:JPY が SimpleMeasure として正しく変換される。"""
        result = structure_units([_make_raw_unit("JPY", JPY_XML)])
        unit = result["JPY"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == "http://www.xbrl.org/2003/iso4217"
        assert unit.measure.local_name == "JPY"
        assert unit.measure.raw_text == "iso4217:JPY"

    def test_simple_measure_pure(self) -> None:
        """xbrli:pure が SimpleMeasure として正しく変換される。"""
        result = structure_units([_make_raw_unit("pure", PURE_XML)])
        unit = result["pure"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == "http://www.xbrl.org/2003/instance"
        assert unit.measure.local_name == "pure"

    def test_simple_measure_shares(self) -> None:
        """xbrli:shares が SimpleMeasure として正しく変換される。"""
        result = structure_units([_make_raw_unit("shares", SHARES_XML)])
        unit = result["shares"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == "http://www.xbrl.org/2003/instance"
        assert unit.measure.local_name == "shares"

    def test_divide_measure_jpy_per_shares(self) -> None:
        """divide 要素が DivideMeasure として正しく変換される。"""
        result = structure_units([_make_raw_unit("JPYPerShares", DIVIDE_XML)])
        unit = result["JPYPerShares"]
        assert isinstance(unit.measure, DivideMeasure)
        assert unit.measure.numerator.namespace_uri == "http://www.xbrl.org/2003/iso4217"
        assert unit.measure.numerator.local_name == "JPY"
        assert unit.measure.denominator.namespace_uri == "http://www.xbrl.org/2003/instance"
        assert unit.measure.denominator.local_name == "shares"

    def test_structure_units_returns_dict(self) -> None:
        """返り値が unit_id をキーとする dict。"""
        result = structure_units([_make_raw_unit("JPY", JPY_XML)])
        assert isinstance(result, dict)
        assert "JPY" in result
        assert isinstance(result["JPY"], StructuredUnit)

    def test_structure_units_multiple(self) -> None:
        """複数の Unit を同時に処理できる。"""
        raws = [
            _make_raw_unit("JPY", JPY_XML),
            _make_raw_unit("pure", PURE_XML),
            _make_raw_unit("shares", SHARES_XML),
        ]
        result = structure_units(raws)
        assert len(result) == 3
        assert "JPY" in result
        assert "pure" in result
        assert "shares" in result

    def test_structure_units_empty(self) -> None:
        """空リストを渡すと空辞書が返る。"""
        result = structure_units([])
        assert result == {}

    def test_convenience_properties(self) -> None:
        """StructuredUnit の便利プロパティが正しく動作する。"""
        raws = [
            _make_raw_unit("JPY", JPY_XML),
            _make_raw_unit("pure", PURE_XML),
            _make_raw_unit("shares", SHARES_XML),
            _make_raw_unit("JPYPerShares", DIVIDE_XML),
        ]
        result = structure_units(raws)

        jpy = result["JPY"]
        assert jpy.is_monetary is True
        assert jpy.is_pure is False
        assert jpy.is_shares is False
        assert jpy.is_per_share is False
        assert jpy.currency_code == "JPY"

        pure = result["pure"]
        assert pure.is_monetary is False
        assert pure.is_pure is True
        assert pure.is_shares is False
        assert pure.currency_code is None

        shares = result["shares"]
        assert shares.is_monetary is False
        assert shares.is_pure is False
        assert shares.is_shares is True
        assert shares.currency_code is None

        per_share = result["JPYPerShares"]
        assert per_share.is_monetary is False
        assert per_share.is_pure is False
        assert per_share.is_shares is False
        assert per_share.is_per_share is True
        assert per_share.currency_code == "JPY"

    def test_xml_syntax_error_raises(self) -> None:
        """不正な XML で EdinetParseError が送出される。"""
        bad_xml = "<not-valid-xml"
        with pytest.raises(EdinetParseError, match="XML パースに失敗しました"):
            structure_units([_make_raw_unit("bad", bad_xml)])

    def test_no_measure_element_raises(self) -> None:
        """measure 要素がない Unit で EdinetParseError が送出される。"""
        xml = (
            '<xbrli:unit id="empty"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "</xbrli:unit>"
        )
        with pytest.raises(EdinetParseError, match="measure 要素が見つかりません"):
            structure_units([_make_raw_unit("empty", xml)])

    def test_divide_missing_numerator_raises(self) -> None:
        """divide に unitNumerator がない場合 EdinetParseError が送出される。"""
        xml = (
            '<xbrli:unit id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:divide>"
            "<xbrli:unitDenominator>"
            "<xbrli:measure>xbrli:shares</xbrli:measure>"
            "</xbrli:unitDenominator>"
            "</xbrli:divide>"
            "</xbrli:unit>"
        )
        with pytest.raises(EdinetParseError, match="unitNumerator が見つかりません"):
            structure_units([_make_raw_unit("bad", xml)])

    def test_divide_missing_denominator_raises(self) -> None:
        """divide に unitDenominator がない場合 EdinetParseError が送出される。"""
        xml = (
            '<xbrli:unit id="bad"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
            "<xbrli:divide>"
            "<xbrli:unitNumerator>"
            "<xbrli:measure>iso4217:JPY</xbrli:measure>"
            "</xbrli:unitNumerator>"
            "</xbrli:divide>"
            "</xbrli:unit>"
        )
        with pytest.raises(EdinetParseError, match="unitDenominator が見つかりません"):
            structure_units([_make_raw_unit("bad", xml)])


# ===========================================================================
# P1 テスト（9 件）
# ===========================================================================


@pytest.mark.small
@pytest.mark.unit
class TestStructureUnitsP1:
    """P1: 推奨テスト群。"""

    def test_simple_measure_usd(self) -> None:
        """iso4217:USD が正しく変換される。"""
        result = structure_units([_make_raw_unit("USD", USD_XML)])
        unit = result["USD"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.local_name == "USD"
        assert unit.currency_code == "USD"

    def test_simple_measure_tco2e(self) -> None:
        """UTR の tCO2e が正しく変換される。"""
        result = structure_units([_make_raw_unit("tCO2e", TCO2E_XML)])
        unit = result["tCO2e"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == "http://www.xbrl.org/2009/utr"
        assert unit.measure.local_name == "tCO2e"
        assert unit.is_monetary is False
        assert unit.is_pure is False

    def test_structure_units_skip_none_id(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """unit_id が None の RawUnit はスキップされる。"""
        xml = (
            '<xbrli:unit'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
            "<xbrli:measure>iso4217:JPY</xbrli:measure>"
            "</xbrli:unit>"
        )
        with caplog.at_level("DEBUG", logger="edinet.xbrl.units"):
            result = structure_units([_make_raw_unit(None, xml)])
        assert result == {}
        assert "None" in caplog.text

    def test_structure_units_duplicate_id(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """重複 unit_id は後勝ちで上書きされ、ログに記録される。"""
        jpy_xml_2 = (
            '<xbrli:unit id="JPY"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance"'
            '  xmlns:iso4217="http://www.xbrl.org/2003/iso4217">'
            "<xbrli:measure>iso4217:USD</xbrli:measure>"
            "</xbrli:unit>"
        )
        with caplog.at_level("DEBUG", logger="edinet.xbrl.units"):
            result = structure_units([
                _make_raw_unit("JPY", JPY_XML),
                _make_raw_unit("JPY", jpy_xml_2),
            ])
        assert len(result) == 1
        # 後勝ち: USD になっている
        assert result["JPY"].measure.local_name == "USD"  # type: ignore[union-attr]
        assert "重複" in caplog.text

    def test_source_line_preserved(self) -> None:
        """source_line が StructuredUnit に保持される。"""
        result = structure_units([_make_raw_unit("JPY", JPY_XML, source_line=42)])
        assert result["JPY"].source_line == 42

    def test_unknown_prefix_warns(self) -> None:
        """未定義の prefix で EdinetWarning が発行される。"""
        xml = (
            '<xbrli:unit id="unknown"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:measure>unknown_ns:SomeUnit</xbrli:measure>"
            "</xbrli:unit>"
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = structure_units([_make_raw_unit("unknown", xml)])
        assert any(issubclass(x.category, EdinetWarning) for x in w)
        unit = result["unknown"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == ""
        assert unit.measure.local_name == "SomeUnit"

    def test_no_prefix_measure(self) -> None:
        """prefix なしの measure テキストで EdinetWarning が発行される。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = structure_units([_make_raw_unit("custom", NO_PREFIX_XML)])
        assert any(issubclass(x.category, EdinetWarning) for x in w)
        unit = result["custom"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.namespace_uri == ""
        assert unit.measure.local_name == "CustomUnit"
        assert unit.measure.raw_text == "CustomUnit"

    def test_multiple_measure_elements_warns(self) -> None:
        """複数の measure 要素で EdinetWarning が発行される。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = structure_units([_make_raw_unit("multi", MULTI_MEASURE_XML)])
        assert any(issubclass(x.category, EdinetWarning) for x in w)
        # 先頭の JPY が使用される
        unit = result["multi"]
        assert isinstance(unit.measure, SimpleMeasure)
        assert unit.measure.local_name == "JPY"

    def test_empty_measure_text_raises(self) -> None:
        """measure 要素のテキストが空の場合 EdinetParseError が送出される。"""
        xml = (
            '<xbrli:unit id="empty"'
            '  xmlns:xbrli="http://www.xbrl.org/2003/instance">'
            "<xbrli:measure>   </xbrli:measure>"
            "</xbrli:unit>"
        )
        with pytest.raises(EdinetParseError, match="テキストが空です"):
            structure_units([_make_raw_unit("empty", xml)])


# ===========================================================================
# 結合テスト（1 件）
# ===========================================================================


@pytest.mark.medium
@pytest.mark.integration
class TestStructureUnitsIntegration:
    """結合テスト: parse_xbrl_facts → structure_units のラウンドトリップ。"""

    def test_roundtrip_with_parse_xbrl_facts(self) -> None:
        """XBRL bytes リテラルから Unit を構造化できる。"""
        xbrl_bytes = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
    xmlns:xbrli="http://www.xbrl.org/2003/instance"
    xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
    xmlns:link="http://www.xbrl.org/2003/linkbase"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:jppfs="http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-11-01/jppfs_cor">
  <link:schemaRef
      xlink:type="simple"
      xlink:href="dummy.xsd"/>
  <xbrli:context id="ctx">
    <xbrli:entity>
      <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">E00001</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2025-03-31</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <xbrli:unit id="JPY">
    <xbrli:measure>iso4217:JPY</xbrli:measure>
  </xbrli:unit>
  <xbrli:unit id="shares">
    <xbrli:measure>xbrli:shares</xbrli:measure>
  </xbrli:unit>
  <xbrli:unit id="JPYPerShares">
    <xbrli:divide>
      <xbrli:unitNumerator>
        <xbrli:measure>iso4217:JPY</xbrli:measure>
      </xbrli:unitNumerator>
      <xbrli:unitDenominator>
        <xbrli:measure>xbrli:shares</xbrli:measure>
      </xbrli:unitDenominator>
    </xbrli:divide>
  </xbrli:unit>
  <jppfs:Assets contextRef="ctx" unitRef="JPY" decimals="0">1000000</jppfs:Assets>
</xbrli:xbrl>
"""
        parsed = parse_xbrl_facts(xbrl_bytes)
        result = structure_units(parsed.units)

        assert len(result) == 3

        jpy = result["JPY"]
        assert jpy.is_monetary is True
        assert jpy.currency_code == "JPY"

        shares = result["shares"]
        assert shares.is_shares is True

        per_share = result["JPYPerShares"]
        assert per_share.is_per_share is True
        assert isinstance(per_share.measure, DivideMeasure)
        assert per_share.measure.numerator.local_name == "JPY"
        assert per_share.measure.denominator.local_name == "shares"
