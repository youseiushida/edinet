from dataclasses import dataclass
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod
from edinet.xbrl.dei import DEI

__all__ = ['PeriodClassification', 'classify_periods']

@dataclass(frozen=True, slots=True)
class PeriodClassification:
    """DEI ベースの期間分類結果。

    Attributes:
        current_duration: 当期の duration 期間。
        prior_duration: 前期の duration 期間。
        current_instant: 当期末の instant 時点。
        prior_instant: 前期末の instant 時点。
    """
    current_duration: DurationPeriod | None
    prior_duration: DurationPeriod | None
    current_instant: InstantPeriod | None
    prior_instant: InstantPeriod | None

def classify_periods(dei: DEI) -> PeriodClassification:
    """DEI の日付情報から当期/前期を分類する。

    Args:
        dei: ``extract_dei()`` で取得した DEI。

    Returns:
        PeriodClassification。日付情報が不足している場合は
        該当フィールドが None になる。
    """
