"""会計基準の判別・正規化サブパッケージ。

会計基準の自動判別には :func:`detect_accounting_standard` を使用する。
正規化キー（CK）による値抽出には ``summary_mappings`` を使用する::

    from edinet.financial.standards import detect_accounting_standard, CK
    from edinet.financial.standards.summary_mappings import lookup_summary

    detected = detect_accounting_standard(facts)
    ck = lookup_summary("NetSalesSummaryOfBusinessResults")
    # → "revenue"
"""

from edinet.financial.standards.detect import (
    DetectedStandard,
    DetectionMethod,
    DetailLevel,
    detect_accounting_standard,
    detect_from_dei,
    detect_from_namespaces,
)
from edinet.financial.standards.canonical_keys import CK

__all__ = [
    # canonical_keys
    "CK",
    # detect
    "DetectedStandard",
    "DetectionMethod",
    "DetailLevel",
    "detect_accounting_standard",
    "detect_from_dei",
    "detect_from_namespaces",
]
