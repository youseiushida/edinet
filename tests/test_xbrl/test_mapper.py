"""test_mapper.py — mapper.py の単体テスト。

summary_mapper / statement_mapper / definition_mapper / calc_mapper /
dict_mapper の振る舞いを検証する。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.financial.mapper import (
    MapperContext,
    calc_mapper,
    definition_mapper,
    dict_mapper,
    statement_mapper,
    summary_mapper,
)
from edinet.financial.standards.canonical_keys import CK
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import DurationPeriod
from edinet.xbrl.linkbase.calculation import (
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
)
from edinet.xbrl.taxonomy import LabelInfo, LabelSource

# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

_NS_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)

_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
)

_EMPTY_CTX = MapperContext(dei=None, detected_standard=None, industry_code=None)


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.STANDARD,
    )


def _make_item(local_name: str, value: Decimal | None = Decimal("100")) -> LineItem:
    return LineItem(
        concept=f"{{{_NS_JPCRP}}}{local_name}",
        namespace_uri=_NS_JPCRP,
        local_name=local_name,
        label_ja=_make_label("テスト"),
        label_en=_make_label("test", "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6 if value is not None else None,
        context_id="CurrentYearDuration",
        period=_CUR_DURATION,
        entity_id="E00001",
        dimensions=(),
        is_nil=False,
        source_line=1,
        order=0,
    )


def _make_calc_linkbase(
    arcs: list[CalculationArc],
    role_uri: str = "http://example.com/role/PL",
) -> CalculationLinkbase:
    """テスト用 CalculationLinkbase を構築するヘルパー。"""
    # roots: 親だけで子でない概念を抽出
    parents = {a.parent for a in arcs}
    children = {a.child for a in arcs}
    roots = tuple(parents - children)
    tree = CalculationTree(role_uri=role_uri, arcs=tuple(arcs), roots=roots)
    return CalculationLinkbase(source_path=None, trees={role_uri: tree})


# ---------------------------------------------------------------------------
# TestSummaryMapper
# ---------------------------------------------------------------------------


class TestSummaryMapper:
    """summary_mapper の単体テスト。"""

    def test_summary_mapper_match(self) -> None:
        """Summary concept の CK を返す。"""
        item = _make_item("NetSalesSummaryOfBusinessResults")
        result = summary_mapper(item, _EMPTY_CTX)
        assert result == CK.REVENUE

    def test_summary_mapper_miss(self) -> None:
        """非 Summary concept で None を返す。"""
        item = _make_item("NetSales")
        result = summary_mapper(item, _EMPTY_CTX)
        assert result is None


# ---------------------------------------------------------------------------
# TestStatementMapper
# ---------------------------------------------------------------------------


class TestStatementMapper:
    """statement_mapper の単体テスト。"""

    def test_statement_mapper_exact(self) -> None:
        """PL/BS/CF concept の CK を返す（完全一致）。"""
        item = _make_item("OperatingIncome")
        result = statement_mapper(item, _EMPTY_CTX)
        assert result == CK.OPERATING_INCOME

    def test_statement_mapper_normalized(self) -> None:
        """サフィックス付き concept の CK を返す（正規化フォールバック）。"""
        item = _make_item("GoodwillIFRS")
        result = statement_mapper(item, _EMPTY_CTX)
        assert result == CK.GOODWILL

    def test_statement_mapper_miss(self) -> None:
        """未知 concept で None を返す。"""
        item = _make_item("UnknownConcept")
        result = statement_mapper(item, _EMPTY_CTX)
        assert result is None


# ---------------------------------------------------------------------------
# TestDefinitionMapper
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestDefinitionMapper:
    """definition_mapper の単体テスト。"""

    def test_definition_mapper_match(self) -> None:
        """general-special の祖先が CK にマッピングされる場合、CK を返す。"""
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            definition_parent_index={"X_CustomSales": "NetSales"},
        )
        item = _make_item("X_CustomSales")
        result = definition_mapper()(item, ctx)
        assert result == CK.REVENUE

    def test_definition_mapper_miss(self) -> None:
        """インデックスに存在しない概念で None を返す。"""
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            definition_parent_index={"X_CustomSales": "NetSales"},
        )
        item = _make_item("X_OtherConcept")
        result = definition_mapper()(item, ctx)
        assert result is None

    def test_definition_mapper_no_index(self) -> None:
        """definition_parent_index が空の場合、None を返す。"""
        item = _make_item("X_CustomSales")
        result = definition_mapper()(item, _EMPTY_CTX)
        assert result is None

    def test_definition_mapper_ancestor_unknown(self) -> None:
        """祖先がCK にマッピングされない標準概念の場合、None を返す。"""
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            definition_parent_index={"X_Custom": "SomeUnknownStandardConcept"},
        )
        item = _make_item("X_Custom")
        result = definition_mapper()(item, ctx)
        assert result is None

    def test_definition_mapper_normalized_ancestor(self) -> None:
        """祖先がサフィックス付き標準概念でも正規化で CK を返す。"""
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            definition_parent_index={"X_CustomGoodwill": "GoodwillIFRS"},
        )
        item = _make_item("X_CustomGoodwill")
        result = definition_mapper()(item, ctx)
        assert result == CK.GOODWILL


# ---------------------------------------------------------------------------
# TestCalcMapper
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestCalcMapper:
    """calc_mapper の単体テスト。"""

    def test_calc_mapper_match(self) -> None:
        """祖先に標準概念がある場合、CK を返す。"""
        # GrossProfit → NetSales (child) の構造
        # X_Custom は GrossProfit の子
        arcs = [
            CalculationArc(
                parent="GrossProfit",
                child="X_CustomItem",
                parent_href="jppfs.xsd#GrossProfit",
                child_href="filer.xsd#X_CustomItem",
                weight=1,
                order=1.0,
                role_uri="http://example.com/role/PL",
            ),
        ]
        calc_lb = _make_calc_linkbase(arcs)
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            calculation_linkbase=calc_lb,
        )
        item = _make_item("X_CustomItem")
        result = calc_mapper()(item, ctx)
        assert result == CK.GROSS_PROFIT

    def test_calc_mapper_miss(self) -> None:
        """祖先に標準概念がない場合、None を返す。"""
        arcs = [
            CalculationArc(
                parent="X_ParentUnknown",
                child="X_ChildUnknown",
                parent_href="filer.xsd#X_ParentUnknown",
                child_href="filer.xsd#X_ChildUnknown",
                weight=1,
                order=1.0,
                role_uri="http://example.com/role/PL",
            ),
        ]
        calc_lb = _make_calc_linkbase(arcs)
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            calculation_linkbase=calc_lb,
        )
        item = _make_item("X_ChildUnknown")
        result = calc_mapper()(item, ctx)
        assert result is None

    def test_calc_mapper_no_linkbase(self) -> None:
        """calculation_linkbase が None の場合、None を返す。"""
        item = _make_item("X_CustomItem")
        result = calc_mapper()(item, _EMPTY_CTX)
        assert result is None

    def test_calc_mapper_multi_hop(self) -> None:
        """2段以上の祖先遡上で CK を返す。"""
        role = "http://example.com/role/PL"
        arcs = [
            CalculationArc(
                parent="X_Intermediate",
                child="X_DeepCustom",
                parent_href="filer.xsd#X_Intermediate",
                child_href="filer.xsd#X_DeepCustom",
                weight=1,
                order=1.0,
                role_uri=role,
            ),
            CalculationArc(
                parent="OperatingIncome",
                child="X_Intermediate",
                parent_href="jppfs.xsd#OperatingIncome",
                child_href="filer.xsd#X_Intermediate",
                weight=1,
                order=1.0,
                role_uri=role,
            ),
        ]
        calc_lb = _make_calc_linkbase(arcs, role_uri=role)
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            calculation_linkbase=calc_lb,
        )
        item = _make_item("X_DeepCustom")
        result = calc_mapper()(item, ctx)
        assert result == CK.OPERATING_INCOME


# ---------------------------------------------------------------------------
# TestDictMapper
# ---------------------------------------------------------------------------


class TestDictMapper:
    """dict_mapper の単体テスト。"""

    def test_dict_mapper_basic(self) -> None:
        """辞書に存在するキーで CK を返す。"""
        m = dict_mapper({"Foo": "revenue"})
        item = _make_item("Foo")
        assert m(item, _EMPTY_CTX) == "revenue"

    def test_dict_mapper_miss(self) -> None:
        """辞書にないキーで None を返す。"""
        m = dict_mapper({"Foo": "revenue"})
        item = _make_item("Bar")
        assert m(item, _EMPTY_CTX) is None

    def test_dict_mapper_name_auto(self) -> None:
        """__name__ が "dict_mapper(N entries)" に設定される。"""
        m = dict_mapper({"A": "a", "B": "b", "C": "c"})
        assert m.__name__ == "dict_mapper(3 entries)"

    def test_dict_mapper_name_custom(self) -> None:
        """name 指定で __name__ が設定される。"""
        m = dict_mapper({"A": "a"}, name="my_rules")
        assert m.__name__ == "my_rules"


# ---------------------------------------------------------------------------
# TestCustomLookup
# ---------------------------------------------------------------------------


@pytest.mark.small
@pytest.mark.unit
class TestCustomLookup:
    """definition_mapper / calc_mapper にカスタム lookup を注入するテスト。"""

    def test_definition_mapper_custom_lookup(self) -> None:
        """カスタム lookup で独自辞書にヒットする。"""
        my_dict = {"NetSales": "my_revenue"}
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            definition_parent_index={"X_CustomSales": "NetSales"},
        )
        item = _make_item("X_CustomSales")
        result = definition_mapper(lookup=my_dict.get)(item, ctx)
        assert result == "my_revenue"

    def test_calc_mapper_custom_lookup(self) -> None:
        """カスタム lookup で独自辞書にヒットする。"""
        my_dict = {"GrossProfit": "my_gross_profit"}
        arcs = [
            CalculationArc(
                parent="GrossProfit",
                child="X_CustomItem",
                parent_href="jppfs.xsd#GrossProfit",
                child_href="filer.xsd#X_CustomItem",
                weight=1,
                order=1.0,
                role_uri="http://example.com/role/PL",
            ),
        ]
        calc_lb = _make_calc_linkbase(arcs)
        ctx = MapperContext(
            dei=None,
            detected_standard=None,
            industry_code=None,
            calculation_linkbase=calc_lb,
        )
        item = _make_item("X_CustomItem")
        result = calc_mapper(lookup=my_dict.get)(item, ctx)
        assert result == "my_gross_profit"
