"""パイプラインマッパー — concept → canonical key の名寄せロジック。

``extract_values()`` が使用するマッパーの型定義・デフォルト実装・ヘルパーを提供する。

設計原則:
    - マッパーは ``Callable[[LineItem, MapperContext], str | None]`` シグネチャ
    - ``str`` を返すとマッチ（canonical key）、``None`` で次のマッパーへ
    - パイプライン（リスト）の先頭マッパーほど高優先

デフォルトパイプライン::

    [summary_mapper, statement_mapper, definition_mapper(), calc_mapper()]

    1. summary_mapper: SummaryOfBusinessResults（経営指標）
    2. statement_mapper: PL/BS/CF の辞書引き
    3. definition_mapper(): Definition Linkbase の general-special で
       独自科目 → 標準科目に遡上
    4. calc_mapper(): Calculation Linkbase の summation-item で
       独自科目 → 親標準科目に遡上

典型的な使用例::

    from edinet.financial.mapper import summary_mapper, statement_mapper, dict_mapper

    # デフォルト: [summary_mapper, statement_mapper, definition_mapper(), calc_mapper()]
    # カスタム辞書を最優先に追加
    my_mapper = dict_mapper({"MyRevenue": "revenue"}, name="my_rules")
    pipeline = [my_mapper, summary_mapper, statement_mapper]

    # カスタム lookup を使う例（独自辞書でリンクベース解決）
    my_map = {"NetSales": "売上高", "OperatingIncome": "営業利益"}
    pipeline = [
        dict_mapper(my_map),
        definition_mapper(lookup=my_map.get),
        calc_mapper(lookup=my_map.get),
    ]
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edinet.financial.standards.statement_mappings import (
    lookup_statement_exact,
    lookup_statement_normalized,
)
from edinet.financial.standards.summary_mappings import lookup_summary

if TYPE_CHECKING:
    from edinet.financial.standards.detect import DetectedStandard
    from edinet.models.financial import LineItem
    from edinet.xbrl.dei import DEI
    from edinet.xbrl.linkbase.calculation import CalculationLinkbase

__all__ = [
    "ConceptMapper",
    "MapperContext",
    "calc_mapper",
    "definition_mapper",
    "dict_mapper",
    "statement_mapper",
    "summary_mapper",
]

ConceptMapper = Callable[["LineItem", "MapperContext"], str | None]
"""concept → canonical key マッパーの型。

Args:
    item: 走査中の LineItem。
    ctx: マッパーコンテキスト（DEI・会計基準・業種コード・リンクベース）。

Returns:
    マッチした canonical key（``str``）。マッチしない場合は ``None``。
"""


@dataclass(frozen=True, slots=True)
class MapperContext:
    """マッパーに渡されるコンテキスト情報。

    ``extract_values()`` が ``Statements`` から自動構築する。
    ユニットテスト時は直接構築可能。

    Attributes:
        dei: DEI（Document and Entity Information）。
            会計基準、企業名、EDINET コード、決算期、報告期間種別等を含む。
            DEI が取得できなかった場合は ``None``。
        detected_standard: 判別された会計基準（J-GAAP / IFRS / US-GAAP / JMIS）。
            判別方法（DEI / namespace）と詳細度（DETAILED / BLOCK_ONLY）を含む。
        industry_code: 業種コード（例: ``"bk1"``）。
            ``None`` は一般事業会社。
        definition_parent_index: Definition Linkbase の general-special arcrole
            による逆引きインデックス。``{独自科目local_name: 標準祖先local_name}``。
            ``definition_mapper`` が使用する。``None`` の場合は
            ``definition_mapper`` は常に ``None`` を返す。
        calculation_linkbase: 提出者の Calculation Linkbase。
            ``calc_mapper`` が ``ancestors_of()`` で祖先を辿る。
            ``None`` の場合は ``calc_mapper`` は常に ``None`` を返す。
    """

    dei: DEI | None
    detected_standard: DetectedStandard | None
    industry_code: str | None
    definition_parent_index: dict[str, str] = field(default_factory=dict)
    calculation_linkbase: CalculationLinkbase | None = None


def summary_mapper(item: LineItem, ctx: MapperContext) -> str | None:
    """SummaryOfBusinessResults（経営成績の概況）から名寄せするマッパー。

    開示府令で記載が義務付けられた標準コンセプトを対象とする。
    全社・全会計基準で安定して取得できる。

    Args:
        item: 走査中の LineItem。
        ctx: マッパーコンテキスト（未使用だがシグネチャ統一のため受け取る）。

    Returns:
        マッチした canonical key。マッチしない場合は ``None``。
    """
    return lookup_summary(item.local_name)


def statement_mapper(item: LineItem, ctx: MapperContext) -> str | None:
    """財務諸表本体（PL/BS/CF）から名寄せするマッパー。

    summary で取得できなかった項目を補完する。
    完全一致 → サフィックス除去後一致の順で試行する。

    Args:
        item: 走査中の LineItem。
        ctx: マッパーコンテキスト（未使用だがシグネチャ統一のため受け取る）。

    Returns:
        マッチした canonical key。マッチしない場合は ``None``。
    """
    ck = lookup_statement_exact(item.local_name)
    if ck is not None:
        return ck
    return lookup_statement_normalized(item.local_name)


def _default_statement_lookup(concept_name: str) -> str | None:
    """組み込み statement_mappings での2段 lookup。"""
    ck = lookup_statement_exact(concept_name)
    if ck is not None:
        return ck
    return lookup_statement_normalized(concept_name)


def definition_mapper(
    lookup: Callable[[str], str | None] | None = None,
) -> ConceptMapper:
    """Definition Linkbase の general-special で標準概念に遡上し CK を返すマッパーを生成する。

    提出者独自の科目名を Definition Linkbase の general-special arcrole を
    辿り、最も近い標準タクソノミの祖先概念を見つけて CK に変換する。

    事前に ``_build_parent_index()`` で構築した逆引きインデックスを使用するため、
    マッパー呼び出し時のコストは O(1) の辞書参照 + lookup のみ。

    Args:
        lookup: 祖先 concept 名 → canonical key の名寄せ関数。
            ``None`` の場合は組み込み statement_mappings を使用する。

    Returns:
        ``ConceptMapper`` として使える callable。
    """
    _lookup = lookup or _default_statement_lookup

    def _mapper(item: LineItem, ctx: MapperContext) -> str | None:
        if not ctx.definition_parent_index:
            return None
        ancestor = ctx.definition_parent_index.get(item.local_name)
        if ancestor is None:
            return None
        return _lookup(ancestor)

    _mapper.__name__ = "definition_mapper"
    _mapper.__qualname__ = "definition_mapper"
    return _mapper


def calc_mapper(
    lookup: Callable[[str], str | None] | None = None,
) -> ConceptMapper:
    """Calculation Linkbase の summation-item で親標準概念に遡上し CK を返すマッパーを生成する。

    提出者独自の科目名を Calculation Linkbase の親子関係（summation-item
    arcrole）を辿り、祖先に標準概念が見つかれば CK に変換する。

    全 role_uri を走査し、最初に CK が見つかった時点で返す。

    Args:
        lookup: 祖先 concept 名 → canonical key の名寄せ関数。
            ``None`` の場合は組み込み statement_mappings を使用する。

    Returns:
        ``ConceptMapper`` として使える callable。
    """
    _lookup = lookup or _default_statement_lookup

    def _mapper(item: LineItem, ctx: MapperContext) -> str | None:
        if ctx.calculation_linkbase is None:
            return None
        for role_uri in ctx.calculation_linkbase.role_uris:
            ancestors = ctx.calculation_linkbase.ancestors_of(
                item.local_name, role_uri=role_uri,
            )
            for ancestor in ancestors:
                ck = _lookup(ancestor)
                if ck is not None:
                    return ck
        return None

    _mapper.__name__ = "calc_mapper"
    _mapper.__qualname__ = "calc_mapper"
    return _mapper


def dict_mapper(
    mapping: dict[str, str],
    *,
    name: str | None = None,
) -> ConceptMapper:
    """辞書ベースのマッパーを生成する。

    Excel/CSV で管理しているマッピングテーブルをそのまま利用可能。

    Args:
        mapping: ``{concept_local_name: canonical_key}`` の辞書。
        name: マッパー名（``mapper_name`` に反映される）。
            未指定の場合は ``"dict_mapper(N entries)"``。

    Returns:
        ``ConceptMapper`` として使える callable。

    Example:
        >>> m = dict_mapper({"MyRevenue": "revenue"}, name="my_rules")
        >>> m.__name__
        'my_rules'
    """

    def _mapper(item: LineItem, ctx: MapperContext) -> str | None:
        return mapping.get(item.local_name)

    _mapper.__name__ = name or f"dict_mapper({len(mapping)} entries)"
    _mapper.__qualname__ = _mapper.__name__
    return _mapper
