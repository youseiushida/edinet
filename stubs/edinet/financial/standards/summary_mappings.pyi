from dataclasses import dataclass

__all__ = ['SummaryMapping', 'all_summary_mappings', 'lookup_summary', 'summary_concepts_for_standard']

@dataclass(frozen=True, slots=True)
class SummaryMapping:
    '''SummaryOfBusinessResults concept の CK マッピング。

    Attributes:
        concept: jpcrp_cor のローカル名（例: ``"NetSalesSummaryOfBusinessResults"``）。
        canonical_key: 正規化キー（例: ``"revenue"``）。
        standard: 会計基準識別子。
            ``"jgaap"`` / ``"ifrs"`` / ``"usgaap"`` / ``"jmis"``。
    '''
    concept: str
    canonical_key: str
    standard: str

def lookup_summary(concept: str) -> str | None:
    '''SummaryOfBusinessResults concept から CK を返す。

    Args:
        concept: jpcrp_cor のローカル名
            （例: ``"NetSalesSummaryOfBusinessResults"``）。

    Returns:
        正規化キー文字列。登録されていない concept の場合は ``None``。
    '''
def all_summary_mappings() -> tuple[SummaryMapping, ...]:
    """全 SummaryMapping を返す。

    Returns:
        全マッピングのタプル（J-GAAP → IFRS → US-GAAP → JMIS 順）。
    """
def summary_concepts_for_standard(standard: str) -> tuple[SummaryMapping, ...]:
    '''指定基準の SummaryMapping を返す。

    Args:
        standard: ``"jgaap"`` / ``"ifrs"`` / ``"usgaap"`` / ``"jmis"``。

    Returns:
        該当基準のマッピングタプル。未知の基準は空タプル。
    '''
