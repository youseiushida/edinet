"""表示・整形ユーティリティを提供するサブパッケージ。"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edinet.display.html import to_html as to_html
    from edinet.display.rich import render_statement as render_statement
    from edinet.display.statements import (
        DisplayRow as DisplayRow,
        build_display_rows as build_display_rows,
        render_hierarchical_statement as render_hierarchical_statement,
    )

__all__ = [
    "render_statement",
    "DisplayRow",
    "build_display_rows",
    "render_hierarchical_statement",
    # Wave 7: Jupyter HTML 表示 (L7)
    "to_html",
]


def __getattr__(name: str):  # noqa: ANN202
    """遅延 import。Rich がインストールされていなくても import edinet.display は成功する。"""
    if name == "render_statement":
        from edinet.display.rich import render_statement

        return render_statement
    if name in ("DisplayRow", "build_display_rows", "render_hierarchical_statement"):
        import edinet.display.statements as _stmts

        return getattr(_stmts, name)
    if name == "to_html":
        from edinet.display.html import to_html

        return to_html
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """IDE 補完のために公開名を列挙する。"""
    return __all__
