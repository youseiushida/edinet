"""taxonomy/custom_detection のテスト。

detect_custom_items() の公開 API のみテストする（デトロイト派）。
内部関数 (_is_standard_href, _build_parent_index, _find_standard_ancestor) は
公開関数経由で間接的に検証する。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from edinet.models.financial import LineItem
from edinet.xbrl._namespaces import (
    NamespaceCategory,
    NamespaceInfo,
    classify_namespace,
)
from edinet.xbrl.contexts import DimensionMember, DurationPeriod, InstantPeriod
from edinet.xbrl.linkbase.definition import DefinitionArc, DefinitionTree
from edinet.financial.statements import build_statements
from edinet.xbrl.taxonomy import LabelInfo, LabelSource
from edinet.xbrl.taxonomy.custom import detect_custom_items

# ============================================================
# テスト用定数
# ============================================================

# 標準タクソノミ URI（_STANDARD_TAXONOMY_PATTERN にマッチする）
_NS_STANDARD_JPPFS = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor"
)
_NS_STANDARD_JPCRP = (
    "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
)

# 提出者別タクソノミ URI（EDINET_BASE で始まるが /taxonomy/ を含まない）
# _namespaces.py の分類ロジックにより FILER_TAXONOMY と判定される。
# 注意: test_statements.py の _NS_FILER_JPCRP は /taxonomy/ 配下にあり
# 1b フォールバックで STANDARD_TAXONOMY と判定されるため使用不可。
_NS_FILER_E02144 = (
    "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/"
    "E02144-000/2025-03-31/01/2025-06-18"
)
_NS_FILER_E99999 = (
    "http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/"
    "E99999-000/2025-03-31/01/2025-06-18"
)

# general-special arcrole 定数
_ARCROLE_GS = "http://www.xbrl.org/2003/arcrole/general-special"

# テスト用 XSD パス定数（_is_standard_href() の判定を制御する）
_STANDARD_XSD = "../jppfs_cor_2025-11-01.xsd"
_FILER_XSD = "jpcrp030000-asr-001_E02144-000.xsd"

# 共通期間
_CUR_DURATION = DurationPeriod(
    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31)
)
_PREV_DURATION = DurationPeriod(
    start_date=date(2023, 4, 1), end_date=date(2024, 3, 31)
)


# ============================================================
# フィクスチャ
# ============================================================


@pytest.fixture(autouse=True)
def _clear_namespace_cache():
    """テスト間のキャッシュ汚染を防ぐ。"""
    classify_namespace.cache_clear()
    yield
    classify_namespace.cache_clear()


# ============================================================
# テスト用ヘルパー
# ============================================================


def _make_label(text: str, lang: str = "ja") -> LabelInfo:
    """テスト用 LabelInfo を構築するヘルパー。"""
    return LabelInfo(
        text=text,
        role="http://www.xbrl.org/2003/role/label",
        lang=lang,
        source=LabelSource.FALLBACK,
    )


def _make_line_item(
    *,
    namespace_uri: str = _NS_STANDARD_JPPFS,
    local_name: str = "NetSales",
    value: Decimal | str | None = Decimal("1000000"),
    period: DurationPeriod | InstantPeriod | None = None,
    order: int = 0,
    context_id: str = "CurrentYearDuration",
    dimensions: tuple[DimensionMember, ...] = (),
) -> LineItem:
    """テスト用の最小限 LineItem を生成する。"""
    if period is None:
        period = _CUR_DURATION
    return LineItem(
        concept=f"{{{namespace_uri}}}{local_name}",
        namespace_uri=namespace_uri,
        local_name=local_name,
        label_ja=_make_label(local_name, "ja"),
        label_en=_make_label(local_name, "en"),
        value=value,
        unit_ref="JPY",
        decimals=-6,
        context_id=context_id,
        period=period,
        entity_id="E00001",
        dimensions=dimensions,
        is_nil=False,
        source_line=1,
        order=order,
    )


def _make_statements(items: list[LineItem]):
    """テスト用 Statements を build_statements() 経由で構築する。

    detect_custom_items() は Statements の __iter__ 経由で LineItem に
    アクセスするため、_detected_standard 等の他フィールドは不要。
    """
    return build_statements(items)


def _make_gs_tree(
    arcs: list[tuple[str, str]],
    *,
    filer_concepts: set[str] | None = None,
) -> dict[str, DefinitionTree]:
    """テスト用の general-special DefinitionTree を構築する。

    Args:
        arcs: (parent, child) タプルのリスト。
        filer_concepts: 提出者別タクソノミとして扱う concept 名の集合。
            指定しない場合、全ての from_href は標準タクソノミ XSD を参照する。
            指定した場合、集合に含まれる concept の href は提出者別 XSD を参照する。
    """
    if filer_concepts is None:
        filer_concepts = set()

    def _href_for(concept: str) -> str:
        xsd = _FILER_XSD if concept in filer_concepts else _STANDARD_XSD
        return f"{xsd}#{concept}"

    def_arcs = tuple(
        DefinitionArc(
            from_concept=parent,
            to_concept=child,
            from_href=_href_for(parent),
            to_href=_href_for(child),
            arcrole=_ARCROLE_GS,
            order=float(i),
        )
        for i, (parent, child) in enumerate(arcs)
    )
    tree = DefinitionTree(
        role_uri="http://example.com/role/test",
        arcs=def_arcs,
        hypercubes=(),
    )
    return {"http://example.com/role/test": tree}


# ============================================================
# テストクラス
# ============================================================


class TestDetectCustomItems:
    """detect_custom_items() の単体テスト群。"""

    # --- 基本分類 ---

    def test_all_standard_items(self):
        """全科目が標準タクソノミの場合。custom_items は空、custom_ratio は 0.0。"""
        items = [
            _make_line_item(local_name="NetSales", order=0),
            _make_line_item(local_name="OperatingIncome", order=1),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.custom_items) == 0
        assert len(result.standard_items) == 2
        assert result.custom_ratio == 0.0
        assert result.total_count == 2

    def test_all_custom_items(self):
        """全科目が提出者別タクソノミの場合。standard_items は空、custom_ratio は 1.0。"""
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomExpense",
                order=1,
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.custom_items) == 2
        assert len(result.standard_items) == 0
        assert result.custom_ratio == 1.0
        assert result.total_count == 2

    def test_mixed_standard_custom(self):
        """標準と拡張が混在する場合。正しく分類されること。"""
        items = [
            _make_line_item(local_name="NetSales", order=0),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                order=1,
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.standard_items) == 1
        assert result.standard_items[0].local_name == "NetSales"
        assert len(result.custom_items) == 1
        assert result.custom_items[0].item.local_name == "CustomSales"

    def test_custom_ratio_calculation(self):
        """custom_ratio が正しく計算されること（3 標準 + 2 拡張 → 0.4）。"""
        items = [
            _make_line_item(local_name=f"Standard{i}", order=i)
            for i in range(3)
        ] + [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name=f"Custom{i}",
                order=3 + i,
            )
            for i in range(2)
        ]
        result = detect_custom_items(_make_statements(items))

        assert result.custom_ratio == pytest.approx(0.4)
        assert result.total_count == 5

    def test_empty_statements(self):
        """空の Statements の場合。total_count=0, custom_ratio=0.0。"""
        result = detect_custom_items(_make_statements([]))

        assert result.total_count == 0
        assert result.custom_ratio == 0.0
        assert len(result.custom_items) == 0
        assert len(result.standard_items) == 0

    def test_total_count_equals_sum(self):
        """total_count == len(custom_items) + len(standard_items) であること。"""
        items = [
            _make_line_item(local_name="NetSales", order=0),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                order=1,
            ),
            _make_line_item(local_name="OperatingIncome", order=2),
        ]
        result = detect_custom_items(_make_statements(items))

        assert result.total_count == len(result.custom_items) + len(
            result.standard_items
        )

    # --- Fact 単位カウント ---

    def test_same_concept_multiple_periods(self):
        """同一拡張科目が当期・前期の両方に存在する場合。

        custom_items に 2 件含まれ、custom_ratio は Fact 単位で計算されること。
        例: 拡張科目 CustomSales が当期・前期に 1 件ずつ + 標準科目 1 件 → ratio = 2/3。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                period=_CUR_DURATION,
                context_id="CurrentYearDuration",
                order=0,
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                period=_PREV_DURATION,
                context_id="PriorYearDuration",
                order=1,
            ),
            _make_line_item(local_name="NetSales", order=2),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.custom_items) == 2
        assert result.custom_ratio == pytest.approx(2 / 3)

    def test_same_concept_consolidated_and_individual(self):
        """同一拡張科目が連結・個別の両方に存在する場合。

        custom_items に 2 件含まれること。
        is_standard の判定は連結/個別に依存しないことの確認。
        """
        cons_dim = (
            DimensionMember(
                axis=f"{{{_NS_STANDARD_JPPFS}}}ConsolidatedOrNonConsolidatedAxis",
                member=f"{{{_NS_STANDARD_JPPFS}}}ConsolidatedMember",
            ),
        )
        non_cons_dim = (
            DimensionMember(
                axis=f"{{{_NS_STANDARD_JPPFS}}}ConsolidatedOrNonConsolidatedAxis",
                member=f"{{{_NS_STANDARD_JPPFS}}}NonConsolidatedMember",
            ),
        )
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                dimensions=cons_dim,
                order=0,
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
                dimensions=non_cons_dim,
                order=1,
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.custom_items) == 2
        assert result.custom_ratio == 1.0

    # --- CustomItemInfo フィールド ---

    def test_custom_item_info_fields(self):
        """CustomItemInfo の各フィールドが正しく設定されること。

        item が元の LineItem を参照、namespace_info が NamespaceInfo、
        parent_standard_concept が None（linkbase 未指定時）。
        """
        original = _make_line_item(
            namespace_uri=_NS_FILER_E02144,
            local_name="CustomSales",
        )
        result = detect_custom_items(_make_statements([original]))

        assert len(result.custom_items) == 1
        ci = result.custom_items[0]
        assert ci.item is original  # 同一オブジェクト参照
        assert isinstance(ci.namespace_info, NamespaceInfo)
        assert ci.parent_standard_concept is None

    def test_namespace_info_populated(self):
        """CustomItemInfo.namespace_info が正しく設定されること。

        FILER_TAXONOMY カテゴリ、edinet_code の抽出等。
        """
        result = detect_custom_items(
            _make_statements(
                [
                    _make_line_item(
                        namespace_uri=_NS_FILER_E02144,
                        local_name="CustomSales",
                    ),
                ]
            )
        )

        ci = result.custom_items[0]
        assert ci.namespace_info.category == NamespaceCategory.FILER_TAXONOMY
        assert ci.namespace_info.is_standard is False
        assert ci.namespace_info.edinet_code == "E02144"

    def test_multiple_custom_namespaces(self):
        """複数の異なる提出者別名前空間が混在する場合。

        それぞれの namespace_info が正しいこと。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomA",
                order=0,
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E99999,
                local_name="CustomB",
                order=1,
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert len(result.custom_items) == 2
        edinet_codes = {
            ci.namespace_info.edinet_code for ci in result.custom_items
        }
        assert edinet_codes == {"E02144", "E99999"}

    # --- 順序保持 ---

    def test_standard_items_preserve_order(self):
        """standard_items の並び順が Statements のイテレーション順と一致すること。"""
        items = [
            _make_line_item(local_name="NetSales", order=0),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomA",
                order=1,
            ),
            _make_line_item(local_name="OperatingIncome", order=2),
            _make_line_item(local_name="OrdinaryIncome", order=3),
        ]
        result = detect_custom_items(_make_statements(items))

        assert [it.local_name for it in result.standard_items] == [
            "NetSales",
            "OperatingIncome",
            "OrdinaryIncome",
        ]

    def test_custom_items_preserve_order(self):
        """custom_items の並び順が Statements のイテレーション順と一致すること。"""
        items = [
            _make_line_item(local_name="NetSales", order=0),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomA",
                order=1,
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomB",
                order=2,
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert [ci.item.local_name for ci in result.custom_items] == [
            "CustomA",
            "CustomB",
        ]

    # --- parent_standard_concept 推定 ---

    def test_parent_standard_concept_found(self):
        """DefinitionLinkbase を指定し、general-special arcrole で
        親標準科目が見つかる場合。parent_standard_concept が設定されること。"""
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerSpecificCA",
            ),
        ]
        tree = _make_gs_tree(
            [("OtherCA", "FilerSpecificCA")],
            filer_concepts={"FilerSpecificCA"},
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase=tree,
        )

        assert len(result.custom_items) == 1
        assert result.custom_items[0].parent_standard_concept == "OtherCA"

    def test_parent_standard_concept_none_without_linkbase(self):
        """DefinitionLinkbase を指定しない場合、
        全ての parent_standard_concept が None であること。"""
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerSpecificCA",
            ),
        ]
        result = detect_custom_items(_make_statements(items))

        assert result.custom_items[0].parent_standard_concept is None

    def test_parent_standard_concept_chain(self):
        """general-special が 2 段以上のチェーン（Standard→Filer→Filer）の場合。

        最も近い標準科目の祖先が返されること。
        例: StandardA → FilerB → FilerC の場合、
        FilerC の parent は StandardA、FilerB の parent も StandardA。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerC",
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerB",
                order=1,
            ),
        ]
        tree = _make_gs_tree(
            [("StandardA", "FilerB"), ("FilerB", "FilerC")],
            filer_concepts={"FilerB", "FilerC"},
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase=tree,
        )

        parents = {
            ci.item.local_name: ci.parent_standard_concept
            for ci in result.custom_items
        }
        assert parents["FilerC"] == "StandardA"
        assert parents["FilerB"] == "StandardA"

    def test_parent_standard_concept_mid_chain(self):
        """標準科目間の general-special を挟むチェーンの場合。

        最も近い標準科目が返されること。
        例: StandardA → StandardB → FilerC の場合、
        FilerC の parent は StandardB（StandardA ではなく最も近い標準親）。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerC",
            ),
        ]
        tree = _make_gs_tree(
            [("StandardA", "StandardB"), ("StandardB", "FilerC")],
            filer_concepts={"FilerC"},
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase=tree,
        )

        assert result.custom_items[0].parent_standard_concept == "StandardB"

    def test_definition_linkbase_no_general_special(self):
        """DefinitionLinkbase を指定するが general-special arc がない場合。

        全ての parent_standard_concept が None であること。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
            ),
        ]
        # all arcrole を使って general-special でない arc を作る
        non_gs_arc = DefinitionArc(
            from_concept="Heading",
            to_concept="Table",
            from_href=f"{_STANDARD_XSD}#Heading",
            to_href=f"{_STANDARD_XSD}#Table",
            arcrole="http://xbrl.org/int/dim/arcrole/all",
            order=0.0,
        )
        tree = DefinitionTree(
            role_uri="http://example.com/role/test",
            arcs=(non_gs_arc,),
            hypercubes=(),
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase={"http://example.com/role/test": tree},
        )

        assert result.custom_items[0].parent_standard_concept is None

    # --- エッジケース ---

    def test_circular_general_special(self):
        """general-special の循環参照がある場合（仕様違反の防御）。

        _visited による循環検出で無限再帰せず None が返ること。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerA",
            ),
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerB",
                order=1,
            ),
        ]
        # A → B → A の循環
        tree = _make_gs_tree(
            [("FilerA", "FilerB"), ("FilerB", "FilerA")],
            filer_concepts={"FilerA", "FilerB"},
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase=tree,
        )

        # 循環があるため標準科目に到達できず None
        for ci in result.custom_items:
            assert ci.parent_standard_concept is None

    def test_chain_no_standard_root(self):
        """全ノードが提出者別タクソノミの孤立チェーンの場合。

        標準科目に到達できず parent_standard_concept が None であること。
        例: FilerA → FilerB（from_href が全て提出者別 XSD を参照）。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="FilerB",
            ),
        ]
        tree = _make_gs_tree(
            [("FilerA", "FilerB")],
            filer_concepts={"FilerA", "FilerB"},
        )
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase=tree,
        )

        assert result.custom_items[0].parent_standard_concept is None

    def test_empty_dict_definition_linkbase(self):
        """definition_linkbase={} の場合。

        None と同様に全ての parent_standard_concept が None であること。
        空の dict は有効な入力であり、エラーにならないこと。
        """
        items = [
            _make_line_item(
                namespace_uri=_NS_FILER_E02144,
                local_name="CustomSales",
            ),
        ]
        result = detect_custom_items(
            _make_statements(items),
            definition_linkbase={},
        )

        assert result.custom_items[0].parent_standard_concept is None
