from collections.abc import Callable
from dataclasses import dataclass
from edinet.financial.standards.detect import DetectedStandard
from edinet.models.financial import LineItem
from edinet.xbrl.dei import DEI
from edinet.xbrl.linkbase.calculation import CalculationLinkbase

__all__ = ['ConceptMapper', 'MapperContext', 'calc_mapper', 'definition_mapper', 'dict_mapper', 'statement_mapper', 'summary_mapper']

ConceptMapper = Callable[['LineItem', 'MapperContext'], str | None]

@dataclass(frozen=True, slots=True)
class MapperContext:
    '''マッパーに渡されるコンテキスト情報。

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
        calculation_linkbase: 提出者の Calculation Linkbase。
    '''
    dei: DEI | None
    detected_standard: DetectedStandard | None
    industry_code: str | None
    definition_parent_index: dict[str, str]
    calculation_linkbase: CalculationLinkbase | None

def summary_mapper(item: LineItem, ctx: MapperContext) -> str | None:
    """SummaryOfBusinessResults（経営成績の概況）から名寄せするマッパー。

    Args:
        item: 走査中の LineItem。
        ctx: マッパーコンテキスト（未使用だがシグネチャ統一のため受け取る）。

    Returns:
        マッチした canonical key。マッチしない場合は ``None``。
    """
def statement_mapper(item: LineItem, ctx: MapperContext) -> str | None:
    """財務諸表本体（PL/BS/CF）から名寄せするマッパー。

    Args:
        item: 走査中の LineItem。
        ctx: マッパーコンテキスト（未使用だがシグネチャ統一のため受け取る）。

    Returns:
        マッチした canonical key。マッチしない場合は ``None``。
    """
def definition_mapper(
    lookup: Callable[[str], str | None] | None = None,
) -> ConceptMapper:
    """Definition Linkbase の general-special で標準概念に遡上し CK を返すマッパーを生成する。

    Args:
        lookup: 祖先 concept 名 → canonical key の名寄せ関数。
            ``None`` の場合は組み込み statement_mappings を使用する。

    Returns:
        ``ConceptMapper`` として使える callable。
    """
def calc_mapper(
    lookup: Callable[[str], str | None] | None = None,
) -> ConceptMapper:
    """Calculation Linkbase の summation-item で親標準概念に遡上し CK を返すマッパーを生成する。

    Args:
        lookup: 祖先 concept 名 → canonical key の名寄せ関数。
            ``None`` の場合は組み込み statement_mappings を使用する。

    Returns:
        ``ConceptMapper`` として使える callable。
    """
def dict_mapper(mapping: dict[str, str], *, name: str | None = None) -> ConceptMapper:
    '''辞書ベースのマッパーを生成する。

    Args:
        mapping: ``{concept_local_name: canonical_key}`` の辞書。
        name: マッパー名（``mapper_name`` に反映される）。
            未指定の場合は ``"dict_mapper(N entries)"``。

    Returns:
        ``ConceptMapper`` として使える callable。

    Example:
        >>> m = dict_mapper({"MyRevenue": "revenue"}, name="my_rules")
        >>> m.__name__
        \'my_rules\'
    '''
