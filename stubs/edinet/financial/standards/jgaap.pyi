from dataclasses import dataclass
from edinet.models.financial import StatementType

__all__ = ['ConceptMapping', 'JGAAPProfile', 'all_canonical_keys', 'all_mappings', 'canonical_key', 'get_profile', 'is_jgaap_module', 'jgaap_specific_concepts', 'lookup', 'mappings_for_statement', 'reverse_lookup']

@dataclass(frozen=True, slots=True)
class ConceptMapping:
    '''J-GAAP concept の正規化マッピング。

    1 つの jppfs_cor / jpcrp_cor concept について、正規化キーと
    メタデータを保持する。standards/normalize (Wave 3) が
    会計基準横断の統一アクセスを提供する際の入力データ。

    Attributes:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。
            バージョン非依存。
        canonical_key: 正規化キー（例: ``"revenue"``）。
            会計基準間で共通の文字列識別子。
            IFRS の Revenue も同じ ``"revenue"`` キーにマッピングされる。
            小文字 snake_case。
        statement_type: 所属する財務諸表。PL / BS / CF。
            複数に属する場合は主たる所属先。
            主要経営指標（EPS 等）は None。
        is_jgaap_specific: J-GAAP 固有の概念か。
            True の場合、IFRS / US-GAAP に直接対応する概念がない。
            例: 経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）。
    '''
    concept: str
    canonical_key: str
    statement_type: StatementType | None
    is_jgaap_specific: bool = ...

@dataclass(frozen=True, slots=True)
class JGAAPProfile:
    '''J-GAAP 会計基準のプロファイル（概要情報）。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に保持し、ディスパッチに使用する。

    Attributes:
        standard_id: 会計基準の識別子。``"japan_gaap"`` 固定。
        display_name_ja: 日本語表示名。
        display_name_en: 英語表示名。
        module_groups: この会計基準に関連する EDINET
            タクソノミモジュールグループの集合。
        canonical_key_count: 定義されている正規化キーの総数。
        has_ordinary_income: 経常利益の概念を持つか（J-GAAP 固有）。
        has_extraordinary_items: 特別利益/特別損失の概念を持つか。
    '''
    standard_id: str
    display_name_ja: str
    display_name_en: str
    module_groups: frozenset[str]
    canonical_key_count: int
    has_ordinary_income: bool
    has_extraordinary_items: bool

def lookup(concept: str) -> ConceptMapping | None:
    '''J-GAAP concept ローカル名からマッピング情報を取得する。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名
            （例: ``"NetSales"``）。

    Returns:
        ConceptMapping。登録されていない concept の場合は None。
    '''
def canonical_key(concept: str) -> str | None:
    """J-GAAP concept ローカル名を正規化キーにマッピングする。

    ``lookup()`` の簡易版。正規化キーのみを返す。

    Args:
        concept: jppfs_cor / jpcrp_cor のローカル名。

    Returns:
        正規化キー文字列。登録されていない concept の場合は None。
    """
def reverse_lookup(key: str) -> ConceptMapping | None:
    '''正規化キーから J-GAAP の ConceptMapping を取得する（逆引き）。

    一般事業会社の主要科目に限定した 1:1 マッピング。
    銀行業・保険業等の業種固有科目は Phase 4 で sector/ モジュールとして
    別途マッピングされるため、本関数の対象外。

    Args:
        key: 正規化キー（例: ``"revenue"``）。

    Returns:
        ConceptMapping。該当する J-GAAP concept がない場合は None。
    '''
def mappings_for_statement(statement_type: StatementType) -> tuple[ConceptMapping, ...]:
    """指定した財務諸表タイプの J-GAAP マッピングを返す。

    定義順（タクソノミの標準表示順序に準拠）。
    ``statement_type=None`` の ConceptMapping（主要経営指標）は
    本関数では取得できない。``all_mappings()`` を使用すること。

    Args:
        statement_type: PL / BS / CF。

    Returns:
        ConceptMapping のタプル（定義順）。
        未登録の StatementType の場合は空タプル。
    """
def all_mappings() -> tuple[ConceptMapping, ...]:
    """全ての J-GAAP マッピングを返す。

    PL → BS → CF → その他（statement_type=None）の順、
    各グループ内は定義順。

    Returns:
        全 ConceptMapping のタプル。
    """
def all_canonical_keys() -> frozenset[str]:
    """J-GAAP で定義されている全正規化キーの集合を返す。

    Returns:
        正規化キーのフローズンセット。
    """
def jgaap_specific_concepts() -> tuple[ConceptMapping, ...]:
    """J-GAAP 固有の概念（他会計基準に対応概念がないもの）を返す。

    対象科目: 営業外収益（NonOperatingIncome）、営業外費用（NonOperatingExpenses）、
    経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）、
    特別損失（ExtraordinaryLoss）。

    Returns:
        ``is_jgaap_specific=True`` の ConceptMapping のタプル。
    """
def is_jgaap_module(module_group: str) -> bool:
    '''module_group が J-GAAP に属するかどうかを判定する。

    J-GAAP に関連するモジュールグループ: ``"jppfs"``, ``"jpcrp"``, ``"jpdei"``。

    注意: IFRS 企業でも jppfs はディメンション要素等で併用される
    ため、この関数の結果だけで会計基準を断定してはならない。
    会計基準の判別は standards/detect を使用すること。

    Args:
        module_group: _namespaces.classify_namespace() で取得した
            NamespaceInfo.module_group の値。

    Returns:
        J-GAAP に関連するモジュールグループであれば True。
    '''
def get_profile() -> JGAAPProfile:
    """J-GAAP 会計基準のプロファイルを返す。

    standards/normalize (Wave 3) が全会計基準のプロファイルを
    並列に取得する際のエントリーポイント。

    Returns:
        JGAAPProfile。
    """
