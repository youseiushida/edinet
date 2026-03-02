import enum
from dataclasses import dataclass

NS_XBRLI: str
NS_XBRLDI: str
NS_LINK: str
NS_XLINK: str
NS_XSI: str
NS_XML: str
NS_ISO4217: str
NS_XBRLDT: str
NS_NUM: str
NS_NONNUM: str
NS_UTR: str
EDINET_BASE: str
EDINET_TAXONOMY_BASE: str

class NamespaceCategory(enum.Enum):
    """名前空間の分類カテゴリ。"""
    STANDARD_TAXONOMY = 'standard_taxonomy'
    FILER_TAXONOMY = 'filer_taxonomy'
    XBRL_INFRASTRUCTURE = 'xbrl_infrastructure'
    OTHER = 'other'

@dataclass(frozen=True, slots=True)
class NamespaceInfo:
    '''名前空間 URI の解析結果。

    Attributes:
        uri: 元の名前空間 URI。
        category: 分類カテゴリ。
        is_standard: EDINET 標準タクソノミであれば True。
            STANDARD_TAXONOMY の場合のみ True。XBRL_INFRASTRUCTURE は False。
        module_name: タクソノミモジュール名（例: "jppfs_cor"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        module_group: タクソノミモジュールグループ（例: "jppfs"）。
            STANDARD_TAXONOMY かつ正規表現マッチ時のみ値を持つ。
            後続レーン（standards/detect 等）での会計基準分岐に使用。
        taxonomy_version: タクソノミバージョン日付（例: "2025-11-01"）。
            STANDARD_TAXONOMY の場合のみ値を持つ。
        edinet_code: EDINET コード（例: "E02144"）。
            FILER_TAXONOMY の場合のみ値を持つ。
    '''
    uri: str
    category: NamespaceCategory
    is_standard: bool
    module_name: str | None = ...
    module_group: str | None = ...
    taxonomy_version: str | None = ...
    edinet_code: str | None = ...

def classify_namespace(uri: str) -> NamespaceInfo:
    """名前空間 URI を解析し、分類結果を返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        解析結果の NamespaceInfo。
    """
def is_standard_taxonomy(uri: str) -> bool:
    """名前空間 URI が EDINET 標準タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        標準タクソノミであれば True。
    """
def is_filer_namespace(uri: str) -> bool:
    """名前空間 URI が提出者別タクソノミかどうかを返す。

    Args:
        uri: 名前空間 URI。

    Returns:
        提出者別タクソノミであれば True。
    """
def extract_taxonomy_module(uri: str) -> str | None:
    '''名前空間 URI からタクソノミモジュール名を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        モジュール名（例: "jppfs_cor"）。標準タクソノミでない場合 None。
    '''
def extract_taxonomy_version(uri: str) -> str | None:
    '''名前空間 URI からタクソノミバージョン日付を抽出する。

    Args:
        uri: 名前空間 URI。

    Returns:
        バージョン日付（例: "2025-11-01"）。標準タクソノミでない場合 None。
    '''
