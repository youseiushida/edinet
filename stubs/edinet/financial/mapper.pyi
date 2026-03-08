from _typeshed import Incomplete
from collections.abc import Callable
from dataclasses import dataclass, field
from edinet.financial.standards.detect import DetectedStandard
from edinet.models.financial import LineItem
from edinet.xbrl.dei import DEI
from edinet.xbrl.linkbase.calculation import CalculationLinkbase

__all__ = ['ConceptMapper', 'MapperContext', 'calc_mapper', 'definition_mapper', 'dict_mapper', 'standard_concept_mapper', 'statement_mapper', 'summary_mapper']

ConceptMapper: Incomplete

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
            ``definition_mapper`` が使用する。``None`` の場合は
            ``definition_mapper`` は常に ``None`` を返す。
        calculation_linkbase: 提出者の Calculation Linkbase。
            ``calc_mapper`` が ``ancestors_of()`` で祖先を辿る。
            ``None`` の場合は ``calc_mapper`` は常に ``None`` を返す。
    '''
    dei: DEI | None
    detected_standard: DetectedStandard | None
    industry_code: str | None
    definition_parent_index: dict[str, str] = field(default_factory=dict)
    calculation_linkbase: CalculationLinkbase | None = ...

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
def standard_concept_mapper(item: LineItem, ctx: MapperContext) -> str | None:
    """標準タクソノミの科目は local_name をそのまま返すマッパー。

    名前空間 URI で標準タクソノミか企業固有かを判定し、
    標準タクソノミに属する科目は ``item.local_name`` をそのまま返す。
    企業固有科目は ``None`` を返し、後続マッパー（``definition_mapper`` /
    ``calc_mapper``）に委譲する。

    CK（canonical key）を使わず、XBRL の concept ID で直接名寄せしたい
    場合に使用する。

    Args:
        item: 走査中の LineItem。
        ctx: マッパーコンテキスト（未使用だがシグネチャ統一のため受け取る）。

    Returns:
        標準タクソノミの場合は ``item.local_name``。企業固有の場合は ``None``。

    Example:
        CK を使わず concept ID で名寄せするパイプライン::

            pipeline = [
                standard_concept_mapper,
                definition_mapper(lookup=lambda name: name),
                calc_mapper(lookup=lambda name: name),
            ]
            result = extract_values(stmts, ["NetSales", "OperatingIncome"],
                                    mapper=pipeline)
    """
def definition_mapper(lookup: Callable[[str], str | None] | None = None) -> ConceptMapper:
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
def calc_mapper(lookup: Callable[[str], str | None] | None = None) -> ConceptMapper:
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
def dict_mapper(mapping: dict[str, str], *, name: str | None = None) -> ConceptMapper:
    '''辞書ベースのマッパーを生成する。

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
        \'my_rules\'
    '''
