"""test_xbrl パッケージ共通のテストヘルパー。"""

from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "xbrl_fragments"
TAXONOMY_MINI_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "taxonomy_mini"


def load_xbrl_bytes(name: str) -> bytes:
    """フィクスチャファイルを bytes として読み込む。

    Args:
        name: フィクスチャファイル名（例: ``"simple_pl.xbrl"``）。

    Returns:
        ファイル内容の bytes。
    """
    return (FIXTURE_DIR / name).read_bytes()
