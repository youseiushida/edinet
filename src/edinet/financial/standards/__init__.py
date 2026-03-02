"""会計基準の判別・正規化サブパッケージ。

会計基準の自動判別には :func:`detect_accounting_standard` を使用する。
判別後の基準固有モジュールは直接インポートする::

    from edinet.financial.standards import detect_accounting_standard, DetailLevel
    from edinet.financial.standards import jgaap, ifrs
    from edinet.financial.standards.usgaap import extract_usgaap_summary

    detected = detect_accounting_standard(facts, dei=dei)
    if detected.standard == "jgaap":
        mapping = jgaap.lookup("NetSales")
    elif detected.standard == "ifrs":
        mapping = ifrs.lookup("RevenueIFRS")
    elif detected.detail_level == DetailLevel.BLOCK_ONLY:
        summary = extract_usgaap_summary(facts, contexts)

Note:
    ``jgaap`` と ``ifrs`` は ``lookup``, ``canonical_key``,
    ``reverse_lookup`` 等の同名関数を持つため、
    ``__init__.py`` からの再エクスポートは行わない。
    利用者はサブモジュールから直接インポートすること。
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
from edinet.financial.standards.normalize import (
    cross_standard_lookup,
    get_canonical_key,
    get_concept_for_key,
    get_concept_order,
    get_known_concepts,
)

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
    # normalize
    "cross_standard_lookup",
    "get_canonical_key",
    "get_concept_for_key",
    "get_concept_order",
    "get_known_concepts",
]
