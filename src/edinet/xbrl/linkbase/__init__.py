"""XBRL リンクベース解析サブパッケージ。"""

from edinet.xbrl._linkbase_utils import (
    ROLE_LABEL,
    ROLE_NEGATED_LABEL,
    ROLE_PERIOD_END_LABEL,
    ROLE_PERIOD_START_LABEL,
    ROLE_TERSE_LABEL,
    ROLE_TOTAL_LABEL,
    ROLE_VERBOSE_LABEL,
)
from edinet.xbrl.linkbase.calculation import (
    CalculationArc,
    CalculationLinkbase,
    CalculationTree,
    parse_calculation_linkbase,
)
from edinet.xbrl.linkbase.definition import (
    AxisInfo,
    DefinitionArc,
    DefinitionTree,
    HypercubeInfo,
    MemberNode,
    parse_definition_linkbase,
)
from edinet.xbrl.linkbase.footnotes import (
    Footnote,
    FootnoteMap,
    parse_footnote_links,
)
from edinet.xbrl.linkbase.presentation import (
    PresentationNode,
    PresentationTree,
    merge_presentation_trees,
    parse_presentation_linkbase,
)

__all__ = [
    # Presentation
    "PresentationNode",
    "PresentationTree",
    "parse_presentation_linkbase",
    "merge_presentation_trees",
    # Calculation
    "CalculationArc",
    "CalculationTree",
    "CalculationLinkbase",
    "parse_calculation_linkbase",
    # Definition
    "DefinitionArc",
    "MemberNode",
    "AxisInfo",
    "HypercubeInfo",
    "DefinitionTree",
    "parse_definition_linkbase",
    # Footnotes (Wave 7: L3)
    "Footnote",
    "FootnoteMap",
    "parse_footnote_links",
    # ラベルロール定数
    "ROLE_LABEL",
    "ROLE_TOTAL_LABEL",
    "ROLE_VERBOSE_LABEL",
    "ROLE_TERSE_LABEL",
    "ROLE_PERIOD_START_LABEL",
    "ROLE_PERIOD_END_LABEL",
    "ROLE_NEGATED_LABEL",
]
