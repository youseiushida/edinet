import enum
from dataclasses import dataclass
from edinet.models.financial import StatementType
from edinet.xbrl.linkbase.presentation import PresentationTree
from pathlib import Path

__all__ = ['ConceptEntry', 'ConceptSet', 'ConceptSetRegistry', 'StatementCategory', 'classify_role_uri', 'derive_concept_sets', 'derive_concept_sets_from_trees', 'get_concept_set']

class StatementCategory(enum.Enum):
    """財務諸表カテゴリ。

    ``StatementType`` (PL/BS/CF の 3 値) よりも広く、
    株主資本等変動計算書 (SS) や包括利益計算書 (CI) を含む。
    """
    BALANCE_SHEET = 'balance_sheet'
    INCOME_STATEMENT = 'income_statement'
    CASH_FLOW_STATEMENT = 'cash_flow_statement'
    STATEMENT_OF_CHANGES_IN_EQUITY = 'statement_of_changes_in_equity'
    COMPREHENSIVE_INCOME = 'comprehensive_income'
    def to_statement_type(self) -> StatementType | None:
        """対応する ``StatementType`` を返す。SS/CI は ``None``。"""
    @classmethod
    def from_statement_type(cls, st: StatementType) -> StatementCategory:
        """``StatementType`` から変換する。

        Args:
            st: 変換元の StatementType。

        Returns:
            対応する StatementCategory。
        """

@dataclass(frozen=True, slots=True)
class ConceptEntry:
    '''科目セット内の 1 エントリ。

    Attributes:
        concept: ローカル名 (例: ``"CashAndDeposits"``)。
        order: Presentation order。
        is_total: ``preferredLabel`` が totalLabel であるかどうか。
        is_abstract: Abstract 科目かどうか。
        depth: LineItems からの相対深さ (0-based)。
        href: 元 XSD href。
        preferred_label: ``presentationArc`` の ``preferredLabel`` 属性値。
            ``None`` は標準ラベル。``periodStartLabel`` / ``periodEndLabel``
            等の特殊ロールを保持し、CF 期首/期末残高の動的検出に使用する。
    '''
    concept: str
    order: float
    is_total: bool
    is_abstract: bool
    depth: int
    href: str
    preferred_label: str | None = ...

@dataclass(frozen=True, slots=True)
class ConceptSet:
    '''1 つの role URI に対応する科目セット。

    Attributes:
        role_uri: XBRL role URI。
        category: 財務諸表カテゴリ。
        is_consolidated: 連結かどうか。
        concepts: 科目エントリのタプル (表示順)。
        source_info: 導出元情報 (デバッグ用)。
        cf_method: CF の作成方法。``"direct"`` / ``"indirect"`` / ``None``。
            CF 以外は ``None``。
    '''
    role_uri: str
    category: StatementCategory
    is_consolidated: bool
    concepts: tuple[ConceptEntry, ...]
    source_info: str
    cf_method: str | None = ...
    def concept_names(self) -> frozenset[str]:
        """全科目名 (abstract 含む) の集合を返す。"""
    def non_abstract_concepts(self) -> frozenset[str]:
        """非 abstract 科目名の集合を返す。"""

def classify_role_uri(role_uri: str) -> tuple[StatementCategory, bool, str | None] | None:
    '''role URI から財務諸表カテゴリと連結/個別を判定する。

    Args:
        role_uri: XBRL role URI 文字列。

    Returns:
        ``(StatementCategory, is_consolidated, cf_method)`` のタプル。
        ``cf_method`` は CF の場合 ``"direct"`` / ``"indirect"`` / ``None``、
        CF 以外は ``None``。
        財務諸表に該当しない場合は ``None``。
    '''
def derive_concept_sets_from_trees(trees: dict[str, PresentationTree], *, source_info: str = '') -> list[ConceptSet]:
    """パース済み PresentationTree dict から ConceptSet を導出する。

    テストやアドホック解析向けの便利関数。
    ディレクトリ走査やキャッシュは行わない。

    Args:
        trees: ``{role_uri: PresentationTree}`` 辞書。
        source_info: 導出元情報 (デバッグ用)。

    Returns:
        導出された ConceptSet のリスト。
        非財務 role URI はスキップされる。
    """

@dataclass(frozen=True)
class ConceptSetRegistry:
    """業種別の ConceptSet レジストリ。

    Attributes:
        _sets: ``{industry_code: {role_uri: ConceptSet}}`` の辞書。
    """
    def get(self, statement_type: StatementType, *, consolidated: bool = True, industry_code: str = 'cai', cf_method: str | None = None) -> ConceptSet | None:
        '''指定条件に合致する ConceptSet を取得する。

        同一条件で複数の ConceptSet がある場合（例: CF の
        indirect/direct）、concepts 数が最大のものを返す。

        Args:
            statement_type: 財務諸表種別。
            consolidated: 連結かどうか。
            industry_code: 業種コード（デフォルト ``"cai"`` = 一般商工業）。
            cf_method: CF の作成方法でフィルタする。
                ``"indirect"`` / ``"direct"`` を指定するとその方法のみ返す。
                ``None``（デフォルト）は全候補から最大を返す。

        Returns:
            合致する ConceptSet。見つからない場合は ``None``。
        '''
    def all_for_industry(self, industry_code: str) -> dict[str, ConceptSet]:
        """指定業種の全 ConceptSet を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            ``{role_uri: ConceptSet}`` 辞書。存在しなければ空辞書。
        """
    def industries(self) -> frozenset[str]:
        """登録済み業種コードの集合を返す。"""
    def statement_categories(self, industry_code: str = 'cai') -> frozenset[StatementCategory]:
        """指定業種で利用可能な StatementCategory の集合を返す。

        Args:
            industry_code: 業種コード。

        Returns:
            利用可能な StatementCategory の frozenset。
        """

def derive_concept_sets(taxonomy_path: str | Path, *, use_cache: bool = True, module_group: str = 'jppfs') -> ConceptSetRegistry:
    '''タクソノミディレクトリから全業種の ConceptSet を導出する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        use_cache: キャッシュを使用するかどうか。
        module_group: スキャン対象のモジュールグループ。
            ``"jppfs"``（デフォルト）: J-GAAP、23 業種。
            ``"jpigp"``: IFRS、業種コード ``"ifrs"`` 固定。

    Returns:
        ConceptSetRegistry インスタンス。

    Raises:
        EdinetConfigError: パスが存在しない場合。
        EdinetConfigError: ``module_group="jppfs"`` で
            ``jppfs/*/r`` が見つからない場合。
    '''
def get_concept_set(taxonomy_path: str | Path, statement_type: StatementType, *, consolidated: bool = True, industry_code: str = 'cai', use_cache: bool = True, cf_method: str | None = None, module_group: str = 'jppfs') -> ConceptSet | None:
    '''ショートカット: 指定条件の ConceptSet を 1 つ取得する。

    Args:
        taxonomy_path: タクソノミのルートパス。
        statement_type: 財務諸表種別。
        consolidated: 連結かどうか。
        industry_code: 業種コード（デフォルト ``"cai"`` = 一般商工業）。
        use_cache: キャッシュを使用するかどうか。
        cf_method: CF の作成方法でフィルタする。
        module_group: スキャン対象のモジュールグループ。
            ``"jpigp"`` を指定する場合は ``industry_code="ifrs"`` を
            明示的に渡すこと（デフォルト ``"cai"`` では IFRS の概念セットに
            マッチしない）。

    Returns:
        合致する ConceptSet。見つからない場合は ``None``。
    '''
