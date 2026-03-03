"""DataFrame エクスポートユーティリティ。

CSV / Parquet / Excel への薄いラッパー。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["to_csv", "to_parquet", "to_excel"]


def to_csv(
    df: pd.DataFrame,
    path: str | Path,
    *,
    encoding: str = "utf-8-sig",
    **kwargs: Any,
) -> None:
    """CSV 出力。

    デフォルトで ``utf-8-sig`` エンコーディングを使用し、
    Excel で開いた際の日本語文字化けを回避する。

    Args:
        df: 出力する DataFrame。
        path: 出力先ファイルパス。
        encoding: 文字エンコーディング。
        **kwargs: ``DataFrame.to_csv()`` に渡す追加引数。
    """
    df.to_csv(path, encoding=encoding, index=False, **kwargs)


def to_parquet(
    df: pd.DataFrame,
    path: str | Path,
    **kwargs: Any,
) -> None:
    """Parquet 出力。

    ``value`` 列に ``Decimal`` と ``str`` が混在する場合（Statements 全体の
    DataFrame 等）、pyarrow の型変換エラーを回避するため ``value`` 列を
    文字列に変換してから書き出す。

    Args:
        df: 出力する DataFrame。
        path: 出力先ファイルパス。
        **kwargs: ``DataFrame.to_parquet()`` に渡す追加引数。
    """
    out = df
    if "value" in df.columns and df["value"].apply(type).nunique() > 1:
        out = df.copy()
        out["value"] = out["value"].astype(str)
    out.to_parquet(path, index=False, **kwargs)


def to_excel(
    df: pd.DataFrame,
    path: str | Path,
    *,
    sheet_name: str = "Sheet1",
    **kwargs: Any,
) -> None:
    """Excel 出力。

    ``openpyxl`` が必要。インストールされていない場合は
    ``ImportError`` が発生する。

    Args:
        df: 出力する DataFrame。
        path: 出力先ファイルパス。
        sheet_name: シート名。
        **kwargs: ``DataFrame.to_excel()`` に渡す追加引数。
    """
    df.to_excel(path, sheet_name=sheet_name, index=False, **kwargs)
