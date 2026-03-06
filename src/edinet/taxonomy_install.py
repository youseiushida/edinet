"""EDINET タクソノミの自動ダウンロード・インストール。

金融庁公式サイトからタクソノミ ZIP をダウンロードし、
``platformdirs.user_data_dir("edinet")`` 以下に展開する。
一度インストールすれば以降のセッションで自動的に利用される。

Example:
    >>> import edinet
    >>> edinet.install_taxonomy()          # 最新版をインストール
    >>> edinet.install_taxonomy(year=2025) # 特定年度を指定
    >>> edinet.taxonomy_info()             # インストール済み情報を表示
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx
import platformdirs

from edinet._config import configure, get_config
from edinet.exceptions import EdinetConfigError, EdinetError

__all__ = [
    "TaxonomyInfo",
    "install_taxonomy",
    "list_taxonomy_versions",
    "taxonomy_info",
    "uninstall_taxonomy",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 金融庁公式サイトのタクソノミ公開ページ URL マッピング。
# key: 年度 (int), value: (FSA公開日文字列, タクソノミフォルダ名)
# フォルダ名は ZIP 内の日付ベース・EDINET ダウンロードページの選択肢に対応。
_KNOWN_VERSIONS: dict[int, tuple[str, str]] = {
    2026: ("20251111", "ALL_20251101"),
    2025: ("20241112", "ALL_20241101"),
    2024: ("20231211", "ALL_20231201"),
    2023: ("20221108", "ALL_20221101"),
    2022: ("20211109", "ALL_20211101"),
    2021: ("20201110", "ALL_20201101"),
    2020: ("20191101", "ALL_20191101"),
    2019: ("20190228", "ALL_20190228"),
    2018: ("20180228", "ALL_20180228"),
}

_FSA_BASE_URL = "https://www.fsa.go.jp/search"
_TAXONOMY_ZIP_NAME = "1c_Taxonomy.zip"

# ZIP 内のトップレベルフォルダ名（Shift-JIS エンコードの「タクソノミ」）。
# ZIP ファイルによって異なる可能性があるため、ヒューリスティックで判定する。
_EXPECTED_SUBDIRS = {"taxonomy", "samples"}


def _data_dir() -> Path:
    """タクソノミのインストール先ディレクトリを返す。

    Returns:
        ``platformdirs.user_data_dir("edinet")`` に基づくパス。
    """
    return Path(platformdirs.user_data_dir("edinet"))


def _download_url(year: int) -> str:
    """指定年度のタクソノミ ZIP の FSA ダウンロード URL を構築する。

    Args:
        year: タクソノミ年度（2018–2026）。

    Returns:
        ダウンロード URL 文字列。

    Raises:
        EdinetConfigError: 未知の年度が指定された場合。
    """
    if year not in _KNOWN_VERSIONS:
        available = ", ".join(str(y) for y in sorted(_KNOWN_VERSIONS))
        raise EdinetConfigError(
            f"タクソノミ年度 {year} は不明です。利用可能な年度: {available}"
        )
    fsa_date, _ = _KNOWN_VERSIONS[year]
    return f"{_FSA_BASE_URL}/{fsa_date}/{_TAXONOMY_ZIP_NAME}"


def _folder_name(year: int) -> str:
    """指定年度のタクソノミフォルダ名を返す。

    Args:
        year: タクソノミ年度。

    Returns:
        フォルダ名（例: ``"ALL_20251101"``）。
    """
    _, folder = _KNOWN_VERSIONS[year]
    return folder


def _latest_year() -> int:
    """利用可能な最新年度を返す。"""
    return max(_KNOWN_VERSIONS)


def _detect_zip_prefix(zf: zipfile.ZipFile) -> str:
    """ZIP 内のトップレベルプレフィックスを検出する。

    EDINET タクソノミ ZIP はトップレベルに「タクソノミ/」フォルダを持つ。
    このフォルダ名は Shift-JIS エンコードで格納されており環境依存のため、
    ``taxonomy/`` や ``samples/`` の親ディレクトリとして検出する。

    Args:
        zf: 開いた ZipFile オブジェクト。

    Returns:
        プレフィックス文字列（末尾スラッシュなし）。
        トップレベルが直接 taxonomy/samples の場合は空文字列。
    """
    for name in zf.namelist():
        parts = name.split("/")
        if len(parts) >= 2 and parts[1] in _EXPECTED_SUBDIRS:
            return parts[0]
        if len(parts) >= 1 and parts[0] in _EXPECTED_SUBDIRS:
            return ""
    return ""


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


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

    Example:
        >>> edinet.list_taxonomy_versions()
        [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]
    """
    return sorted(_KNOWN_VERSIONS, reverse=True)


def taxonomy_info() -> TaxonomyInfo | None:
    """インストール済みタクソノミの情報を返す。

    最新年度から順に探索し、最初に見つかったインストール済みタクソノミの
    情報を返す。見つからない場合は ``None`` を返す。

    Returns:
        インストール済みタクソノミの情報。未インストールなら ``None``。

    Example:
        >>> info = edinet.taxonomy_info()
        >>> if info:
        ...     print(f"{info.year}年版 ({info.folder_name}) @ {info.path}")
    """
    data_dir = _data_dir()
    cfg = get_config()
    current_path = cfg.taxonomy_path

    for year in sorted(_KNOWN_VERSIONS, reverse=True):
        folder = _folder_name(year)
        path = data_dir / folder
        if path.exists() and (path / "taxonomy").exists():
            configured = current_path is not None and Path(
                current_path
            ).resolve() == path.resolve()
            return TaxonomyInfo(
                year=year,
                folder_name=folder,
                path=path,
                configured=configured,
            )
    return None


def install_taxonomy(
    year: int | None = None,
    *,
    force: bool = False,
    timeout: float = 120.0,
) -> TaxonomyInfo:
    """EDINET タクソノミをダウンロードしてインストールする。

    金融庁公式サイトからタクソノミ ZIP をダウンロードし、
    ``platformdirs.user_data_dir("edinet")`` 以下に展開する。
    展開後、自動的に ``edinet.configure(taxonomy_path=...)`` を呼び出し、
    以降のセッションでも利用可能にする。

    Args:
        year: タクソノミ年度。``None`` の場合は最新版。
        force: ``True`` の場合、既存のインストールを上書きする。
        timeout: ダウンロードのタイムアウト（秒）。

    Returns:
        インストールされたタクソノミの情報。

    Raises:
        EdinetConfigError: 不明な年度が指定された場合。
        EdinetError: ダウンロードまたは展開に失敗した場合。

    Example:
        >>> info = edinet.install_taxonomy()
        >>> print(info.path)
        /home/user/.local/share/edinet/ALL_20251101
    """
    if year is None:
        year = _latest_year()
    if year not in _KNOWN_VERSIONS:
        available = ", ".join(str(y) for y in sorted(_KNOWN_VERSIONS))
        raise EdinetConfigError(
            f"タクソノミ年度 {year} は不明です。利用可能な年度: {available}"
        )

    folder = _folder_name(year)
    data_dir = _data_dir()
    dest = data_dir / folder

    # 既にインストール済みか確認
    if dest.exists() and (dest / "taxonomy").exists() and not force:
        logger.info("タクソノミは既にインストール済みです: %s", dest)
        configure(taxonomy_path=str(dest))
        return TaxonomyInfo(
            year=year,
            folder_name=folder,
            path=dest,
            configured=True,
        )

    # ダウンロード
    url = _download_url(year)
    logger.info("タクソノミをダウンロード中: %s", url)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout, connect=30.0),
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EdinetError(
            f"タクソノミのダウンロードに失敗しました: {exc}"
        ) from exc

    zip_bytes = response.content
    logger.info(
        "ダウンロード完了 (%.1f MB)", len(zip_bytes) / 1024 / 1024
    )

    # ZIP を検証
    try:
        zf = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise EdinetError(
            "ダウンロードしたファイルが正しい ZIP ではありません"
        ) from exc

    # 展開
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    prefix = _detect_zip_prefix(zf)
    logger.info("ZIP プレフィックス: %r → 展開先: %s", prefix, dest)

    extracted_count = 0
    with zf:
        for member in zf.namelist():
            # プレフィックスを除去してフラットに展開
            if prefix:
                if not member.startswith(prefix + "/"):
                    continue
                relative = member[len(prefix) + 1 :]
            else:
                relative = member

            if not relative:
                continue

            target = dest / relative

            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_count += 1

    logger.info("展開完了: %d ファイル", extracted_count)

    # taxonomy/ ディレクトリの存在を確認
    if not (dest / "taxonomy").exists():
        raise EdinetError(
            f"展開後に taxonomy ディレクトリが見つかりません: {dest}"
        )

    # グローバル設定に反映
    configure(taxonomy_path=str(dest))

    info = TaxonomyInfo(
        year=year,
        folder_name=folder,
        path=dest,
        configured=True,
    )
    logger.info(
        "タクソノミ %d年版 をインストールしました: %s", year, dest
    )
    return info


def uninstall_taxonomy(year: int | None = None) -> bool:
    """インストール済みタクソノミを削除する。

    Args:
        year: 削除するタクソノミ年度。``None`` の場合はインストール済みの
            最新版を削除する。

    Returns:
        削除に成功した場合 ``True``、対象が存在しなかった場合 ``False``。

    Raises:
        EdinetConfigError: 不明な年度が指定された場合。
    """
    if year is None:
        info = taxonomy_info()
        if info is None:
            return False
        year = info.year

    if year not in _KNOWN_VERSIONS:
        available = ", ".join(str(y) for y in sorted(_KNOWN_VERSIONS))
        raise EdinetConfigError(
            f"タクソノミ年度 {year} は不明です。利用可能な年度: {available}"
        )

    folder = _folder_name(year)
    dest = _data_dir() / folder

    if not dest.exists():
        return False

    # 現在の設定が削除対象を指している場合はクリア
    cfg = get_config()
    if cfg.taxonomy_path and Path(cfg.taxonomy_path).resolve() == dest.resolve():
        configure(taxonomy_path=None)

    shutil.rmtree(dest)
    logger.info("タクソノミを削除しました: %s", dest)
    return True


def detect_installed_taxonomy() -> str | None:
    """インストール済みタクソノミのパスを自動検出する。

    ``edinet.configure(taxonomy_path=...)`` が未設定の場合に、
    ``platformdirs.user_data_dir("edinet")`` 以下の最新タクソノミを探す。

    Returns:
        見つかったタクソノミパスの文字列。見つからなければ ``None``。
    """
    info = taxonomy_info()
    if info is not None:
        return str(info.path)
    return None
