import enum
from dataclasses import dataclass
from edinet.xbrl._linkbase_utils import ROLE_LABEL as ROLE_LABEL, ROLE_TOTAL_LABEL, ROLE_VERBOSE_LABEL
from edinet.xbrl.taxonomy.concept_sets import ConceptEntry as ConceptEntry, ConceptSet as ConceptSet, ConceptSetRegistry as ConceptSetRegistry, StatementCategory as StatementCategory, classify_role_uri as classify_role_uri, derive_concept_sets as derive_concept_sets, derive_concept_sets_from_trees as derive_concept_sets_from_trees, get_concept_set as get_concept_set
from pathlib import Path

__all__ = ['LabelInfo', 'LabelSource', 'TaxonomyResolver', 'ROLE_LABEL', 'ROLE_VERBOSE', 'ROLE_TOTAL', 'ConceptEntry', 'ConceptSet', 'ConceptSetRegistry', 'StatementCategory', 'classify_role_uri', 'derive_concept_sets', 'derive_concept_sets_from_trees', 'get_concept_set', 'get_and_fork_resolver']

type _LabelKey = tuple[str, str, str, str]
class LabelSource(enum.Enum):
    """ラベルの情報源。

    Attributes:
        STANDARD: EDINET 標準タクソノミ由来。
        FILER: 提出者別タクソノミ由来。
        FALLBACK: ラベルが見つからず local name を使用。
    """
    STANDARD = 'standard'
    FILER = 'filer'
    FALLBACK = 'fallback'

@dataclass(frozen=True, slots=True)
class LabelInfo:
    '''解決されたラベル情報。

    Attributes:
        text: ラベルテキスト（例: ``"売上高"``）。
        role: ラベルロール URI。
        lang: 言語コード（``"ja"`` / ``"en"``）。
        source: ラベルの情報源。
    '''
    text: str
    role: str
    lang: str
    source: LabelSource
ROLE_VERBOSE = ROLE_VERBOSE_LABEL
ROLE_TOTAL = ROLE_TOTAL_LABEL

def get_and_fork_resolver(taxonomy_path: str | Path, *, use_cache: bool = True) -> TaxonomyResolver:
    """スレッドセーフに TaxonomyResolver の独立コピーを取得する。

    共有キャッシュからの取得と fork をロック内でアトミックに行い、
    返された子インスタンスに対して安全に load_filer_labels() できる。

    Args:
        taxonomy_path: タクソノミのルートディレクトリパス。
        use_cache: pickle キャッシュを使用するか。

    Returns:
        独立した TaxonomyResolver インスタンス（filer_labels は空）。
    """

class TaxonomyResolver:
    '''EDINET タクソノミのラベル解決を行うクラス。

    標準タクソノミの ``_lab.xml`` / ``_lab-en.xml`` をパースし、
    concept → ラベルの辞書を構築する。初回パース結果は pickle で
    キャッシュされ、2 回目以降は高速に読み込まれる。

    Attributes:
        taxonomy_version: タクソノミバージョン（例: ``"ALL_20251101"``）。
        taxonomy_path: タクソノミのルートパス。

    Example:
        >>> resolver = TaxonomyResolver("/path/to/ALL_20251101")
        >>> label = resolver.resolve("jppfs_cor", "NetSales")
        >>> print(label.text)
        売上高
    '''
    def __init__(self, taxonomy_path: str | Path, *, use_cache: bool = True) -> None:
        """TaxonomyResolver を初期化する。

        Args:
            taxonomy_path: タクソノミのルートディレクトリパス。
                ``ALL_20251101`` 等の最上位ディレクトリを指定する。
            use_cache: pickle キャッシュを使用するか。
                ``False`` の場合は毎回パースする（テスト用）。

        Raises:
            EdinetConfigError: taxonomy_path が存在しない場合。
        """
    @property
    def taxonomy_version(self) -> str:
        '''タクソノミバージョン文字列（例: ``"ALL_20251101"``）。'''
    @property
    def taxonomy_path(self) -> Path:
        """タクソノミのルートパス。"""
    def resolve(self, prefix: str, local_name: str, *, role: str = ..., lang: str = 'ja') -> LabelInfo:
        '''concept のラベルを解決する。

        Args:
            prefix: 名前空間プレフィックス（例: ``"jppfs_cor"``）。
            local_name: ローカル名（例: ``"NetSales"``）。
            role: ラベルロール URI。デフォルトは標準ラベル。
            lang: 言語コード。``"ja"`` または ``"en"``。

        Returns:
            解決された LabelInfo。ラベルが見つからない場合は
            指定 role → 標準ラベル → local name の順でフォールバック。

        Note:
            フォールバック時の LabelInfo は ``source=LabelSource.FALLBACK``、
            ``text=local_name`` となる。
        '''
    def resolve_clark(self, concept_qname: str, *, role: str = ..., lang: str = 'ja') -> LabelInfo:
        '''Clark notation の concept QName からラベルを解決する。

        Args:
            concept_qname: Clark notation の QName
                （例: ``"{http://...jppfs_cor}NetSales"``）。
            role: ラベルロール URI。
            lang: 言語コード。

        Returns:
            解決された LabelInfo。
        '''
    def load_filer_labels(self, lab_xml_bytes: bytes | None = None, lab_en_xml_bytes: bytes | None = None, *, xsd_bytes: bytes | None = None) -> int:
        """提出者別タクソノミのラベルを追加読み込みする。

        Args:
            lab_xml_bytes: 提出者の ``_lab.xml``（日本語）の bytes。
            lab_en_xml_bytes: 提出者の ``_lab-en.xml``（英語）の bytes。
            xsd_bytes: 提出者の ``.xsd`` の bytes。渡された場合、
                ``targetNamespace`` を抽出して ``_ns_to_prefix`` に
                追加する。

        Returns:
            追加されたラベル数。

        Warns:
            EdinetWarning: ``_filer_labels`` が空でない状態で呼ばれた場合。
        """
    def clear_filer_labels(self) -> None:
        """提出者別ラベルをクリアし、提出者由来の ``_ns_to_prefix`` エントリも除去する。

        次の filing を処理する前に呼び出す。
        """
    def fork(self) -> TaxonomyResolver:
        """不変データを共有し可変データを独立コピーした新インスタンスを返す。

        大量の Filing を並列処理する際、``get_taxonomy_resolver()`` で
        取得した共有インスタンスに ``load_filer_labels()`` した後、
        ``fork()`` で Filing ごとの独立コピーを作成する。
        これにより次の filing の ``clear_filer_labels()`` が
        ``Statements._resolver`` のラベルを破壊しなくなる。

        Returns:
            ``_standard_labels`` を参照共有し、
            ``_filer_labels`` / ``_ns_to_prefix`` 等を独立コピーした
            新しい TaxonomyResolver。
        """
