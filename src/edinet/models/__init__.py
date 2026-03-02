"""edinet.models — Pydantic データモデル。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.models.company import Company as Company
    from edinet.models.doc_types import DocType as DocType
    from edinet.models.filing import Filing as Filing
    from edinet.models.form_code import FormCodeEntry as FormCodeEntry
    from edinet.models.form_code import all_form_codes as all_form_codes
    from edinet.models.form_code import get_form_code as get_form_code
    from edinet.models.ordinance_code import OrdinanceCode as OrdinanceCode
    from edinet.models.revision import RevisionChain as RevisionChain
    from edinet.models.revision import (
        build_revision_chain as build_revision_chain,
    )

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "Company": ("edinet.models.company", "Company"),
    "DocType": ("edinet.models.doc_types", "DocType"),
    "Filing": ("edinet.models.filing", "Filing"),
    "OrdinanceCode": ("edinet.models.ordinance_code", "OrdinanceCode"),
    "FormCodeEntry": ("edinet.models.form_code", "FormCodeEntry"),
    "get_form_code": ("edinet.models.form_code", "get_form_code"),
    "all_form_codes": ("edinet.models.form_code", "all_form_codes"),
    # Wave 6: 訂正チェーン (L3)
    "RevisionChain": ("edinet.models.revision", "RevisionChain"),
    "build_revision_chain": ("edinet.models.revision", "build_revision_chain"),
}


def __getattr__(name: str):
    """公開シンボルを遅延ロードする。

    Args:
        name: 取得対象の属性名。

    Returns:
        遅延ロードされた属性。

    Raises:
        AttributeError: 公開対象外の属性名が指定された場合。
    """
    module_and_attr = _LAZY_EXPORTS.get(name)
    if module_and_attr is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = module_and_attr
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

__all__ = [
    "Company",
    "DocType",
    "Filing",
    "OrdinanceCode",
    "FormCodeEntry",
    "get_form_code",
    "all_form_codes",
    # Wave 6: 訂正チェーン (L3)
    "RevisionChain",
    "build_revision_chain",
]
