from dataclasses import dataclass
from pathlib import Path

__all__ = ['TaxonomyInfo', 'install_taxonomy', 'list_taxonomy_versions', 'taxonomy_info', 'uninstall_taxonomy']

_KNOWN_VERSIONS: dict[int, tuple[str, str]]

@dataclass(frozen=True)
class TaxonomyInfo:
    """インストール済みタクソノミの情報。

    Attributes:
        year: タクソノミ年度（例: ``2026``）。
        folder_name: フォルダ名（例: ``"ALL_20251101"``）。
        path: インストール先の絶対パス。
        configured: 現在のセッションで ``taxonomy_path`` として設定済みか。
    """
    year: int
    folder_name: str
    path: Path
    configured: bool

def list_taxonomy_versions() -> list[int]:
    """ダウンロード可能なタクソノミ年度の一覧を返す。

    Returns:
        利用可能な年度の降順リスト（例: ``[2026, 2025, ...]``）。
    """

def taxonomy_info() -> TaxonomyInfo | None:
    """インストール済みタクソノミの情報を返す。

    Returns:
        インストール済みタクソノミの情報。未インストールなら ``None``。
    """

def install_taxonomy(year: int | None = None, *, force: bool = False, timeout: float = 120.0) -> TaxonomyInfo:
    """EDINET タクソノミをダウンロードしてインストールする。

    Args:
        year: タクソノミ年度。``None`` の場合は最新版。
        force: ``True`` の場合、既存のインストールを上書きする。
        timeout: ダウンロードのタイムアウト（秒）。

    Returns:
        インストールされたタクソノミの情報。

    Raises:
        EdinetConfigError: 不明な年度が指定された場合。
        EdinetError: ダウンロードまたは展開に失敗した場合。
    """

def uninstall_taxonomy(year: int | None = None) -> bool:
    """インストール済みタクソノミを削除する。

    Args:
        year: 削除するタクソノミ年度。``None`` の場合は最新版。

    Returns:
        削除に成功した場合 ``True``、対象が存在しなかった場合 ``False``。
    """

def detect_installed_taxonomy() -> str | None:
    """インストール済みタクソノミのパスを自動検出する。

    Returns:
        見つかったタクソノミパスの文字列。見つからなければ ``None``。
    """
