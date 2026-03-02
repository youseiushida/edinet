import functools
from dataclasses import dataclass
from edinet.models.financial import StatementType

__all__ = ['IFRSConceptMapping', 'IFRSProfile', 'NAMESPACE_MODULE_GROUP', 'lookup', 'canonical_key', 'reverse_lookup', 'mappings_for_statement', 'all_mappings', 'all_canonical_keys', 'ifrs_specific_concepts', 'load_ifrs_pl_concepts', 'load_ifrs_bs_concepts', 'load_ifrs_cf_concepts', 'get_ifrs_concept_set', 'ifrs_to_jgaap_map', 'jgaap_to_ifrs_map', 'is_ifrs_module', 'get_profile']

NAMESPACE_MODULE_GROUP: str

@dataclass(frozen=True, slots=True)
class IFRSConceptMapping:
    '''IFRS 科目の正規化マッピング。

    Lane 3 の ``ConceptMapping`` と対称的な構造を持つ。
    ``canonical_key`` を共通キーとして、Wave 3 の normalize が
    会計基準横断の統一アクセスを提供する。

    Attributes:
        concept: ``jpigp_cor`` の concept ローカル名（例: ``"RevenueIFRS"``）。
            バージョン非依存。
        canonical_key: 正規化キー（例: ``"revenue"``）。
            会計基準間で共通の文字列識別子。Lane 3 §5.2-5.5 で定義
            された J-GAAP の正規化キーと同一値を使用する。
            IFRS 固有科目には新規キーを定義。小文字 snake_case。
        statement_type: 所属する財務諸表。``INCOME_STATEMENT`` /
            ``BALANCE_SHEET`` / ``CASH_FLOW_STATEMENT``。
        is_ifrs_specific: IFRS 固有の概念か。
            ``True`` の場合、J-GAAP に直接対応する概念がない。
        jgaap_concept: J-GAAP 側の対応 concept ローカル名。
            IFRS 固有の科目の場合は ``None``。
        mapping_note: マッピングに関する補足説明。
    '''
    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_ifrs_specific: bool = ...
    jgaap_concept: str | None = ...
    mapping_note: str = ...

@dataclass(frozen=True, slots=True)
class IFRSProfile:
    '''IFRS 会計基準のプロファイル（概要情報）。

    ``standards/normalize`` (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。
    Lane 3 の ``JGAAPProfile`` と対称的な構造。

    Attributes:
        standard_id: 会計基準の識別子。``"ifrs"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に **固有の**（他の会計基準では使用されない）
            タクソノミモジュールグループの集合。
            IFRS 企業でも ``jpcrp_cor`` / ``jpdei_cor`` は共通して使用されるが、
            ``jpigp_cor`` は IFRS 企業のみが使用するため、
            ``{"jpigp"}`` のみを含む。
        canonical_key_count: 定義されている正規化キーの総数（PL + BS + CF）。
        has_ordinary_income: 経常利益の概念を持つか（``False``: IFRS にはない）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか（``False``）。
    '''
    standard_id: str
    display_name_ja: str
    display_name_en: str
    module_groups: frozenset[str]
    canonical_key_count: int
    has_ordinary_income: bool
    has_extraordinary_items: bool

def lookup(concept: str) -> IFRSConceptMapping | None:
    '''IFRS concept ローカル名からマッピング情報を取得する。

    Args:
        concept: ``jpigp_cor`` のローカル名（例: ``"RevenueIFRS"``）。

    Returns:
        ``IFRSConceptMapping``。登録されていない concept の場合は ``None``。
    '''
def canonical_key(concept: str) -> str | None:
    """IFRS concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: ``jpigp_cor`` のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    """
def reverse_lookup(key: str) -> IFRSConceptMapping | None:
    '''正規化キーから IFRS の ``IFRSConceptMapping`` を取得する（逆引き）。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        ``IFRSConceptMapping``。該当する IFRS concept がない場合は ``None``。
    '''
def mappings_for_statement(statement_type: StatementType) -> tuple[IFRSConceptMapping, ...]:
    """指定した財務諸表タイプの IFRS マッピングを返す。

    定義順（タクソノミの標準表示順序に準拠）。

    Args:
        statement_type: ``INCOME_STATEMENT`` / ``BALANCE_SHEET`` /
            ``CASH_FLOW_STATEMENT``。

    Returns:
        ``IFRSConceptMapping`` のタプル（定義順）。
    """
def all_mappings() -> tuple[IFRSConceptMapping, ...]:
    """全 ``IFRSConceptMapping`` を返す（PL → BS → CF 順）。

    Returns:
        全 ``IFRSConceptMapping`` のタプル。
    """
def all_canonical_keys() -> frozenset[str]:
    """定義されている全 ``canonical_key`` の集合を返す。

    「この key は IFRS で定義されているか」の高速判定に使用。
    モジュールレベルで事前構築済みの ``frozenset`` を返す。

    Returns:
        正規化キーのフローズンセット。
    """
def ifrs_specific_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 固有の概念（J-GAAP に対応概念がないもの）を返す。

    対象科目: 金融収益（``FinanceIncomeIFRS``）、
    金融費用（``FinanceCostsIFRS``）等。
    モジュールレベルで事前構築済みのタプルを返す。

    Returns:
        ``is_ifrs_specific=True`` の ``IFRSConceptMapping`` のタプル。
    """
def load_ifrs_pl_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 損益計算書の科目定義を返す。"""
def load_ifrs_bs_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS 貸借対照表の科目定義を返す。"""
def load_ifrs_cf_concepts() -> tuple[IFRSConceptMapping, ...]:
    """IFRS キャッシュフロー計算書の科目定義を返す。"""
def get_ifrs_concept_set(statement_type: StatementType) -> frozenset[str]:
    """指定された財務諸表タイプの IFRS concept 名の集合を返す。

    ``LineItem`` の concept 名がこの集合に含まれるかを
    高速に判定するために使用する。
    モジュールレベルで事前構築済みの ``frozenset`` を返す。

    Args:
        statement_type: 財務諸表タイプ。

    Returns:
        concept ローカル名の ``frozenset``。
    """
@functools.cache
def ifrs_to_jgaap_map() -> dict[str, str | None]:
    '''IFRS concept 名 → J-GAAP concept 名の辞書を返す（補助）。

    ``_ALL_MAPPINGS`` の ``jgaap_concept`` フィールドから自動生成。
    IFRS 固有の科目（J-GAAP に対応なし）は ``None`` にマッピングされる。
    結果はキャッシュされる。

    Returns:
        IFRS concept 名をキー、J-GAAP concept 名（または ``None``）を値とする辞書。

    Example:
        >>> m = ifrs_to_jgaap_map()
        >>> m["RevenueIFRS"]
        \'NetSales\'
        >>> m["FinanceIncomeIFRS"] is None
        True
    '''
@functools.cache
def jgaap_to_ifrs_map() -> dict[str, str | None]:
    '''J-GAAP concept 名 → IFRS concept 名の辞書を返す（補助）。

    キーには以下が含まれる:

    - ``_ALL_MAPPINGS`` で ``jgaap_concept`` が定義されている J-GAAP concept
      （値は IFRS concept 名）
    - ``_JGAAP_ONLY_CONCEPTS`` に含まれる J-GAAP 固有科目
      （値は ``None``）

    Lane 3 の KPI 概念（EPS / BPS 等）は含まない。
    結果はキャッシュされる。

    Returns:
        J-GAAP concept 名をキー、IFRS concept 名（または ``None``）を値とする辞書。

    Example:
        >>> m = jgaap_to_ifrs_map()
        >>> m["NetSales"]
        \'RevenueIFRS\'
        >>> m["OrdinaryIncome"] is None
        True
    '''
def is_ifrs_module(module_group: str) -> bool:
    """``module_group`` が IFRS 固有のモジュールに属するかを判定する。

    注意: IFRS 企業でも ``jppfs_cor`` はディメンション要素等で
    併用されるため（D-1）、この関数の結果だけで会計基準を
    断定してはならない。会計基準の判別は ``standards/detect`` を使用すること。

    NOTE: ``jpdei`` / ``jpcrp`` は J-GAAP / IFRS 両方で使用される共通モジュール。
    Lane 3 の ``is_jgaap_module()`` は ``jpdei``/``jpcrp`` を ``True`` と判定するが、
    本関数は ``jpigp`` のみを ``True`` と判定する。この非対称性は Wave 3 の
    normalize で会計基準判別ロジックが吸収する。

    Args:
        module_group: ``_namespaces.classify_namespace()`` で取得した
            ``NamespaceInfo.module_group`` の値。

    Returns:
        IFRS 固有のモジュールグループであれば ``True``。
    """
def get_profile() -> IFRSProfile:
    """IFRS 会計基準のプロファイルを返す。

    ``standards/normalize`` (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。Lane 3 の ``get_profile()`` と対称。

    Returns:
        ``IFRSProfile``。
    """
