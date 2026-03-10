"""全年度の EDINET タクソノミ ZIP のディレクトリ構造を調査する。

ZIP をダウンロードせず HEAD + 部分 GET で構造だけ確認、
または小さい ZIP はフルダウンロードして namelist を表示する。
"""

from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx

# taxonomy_install.py からコピー
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


def check_year(year: int) -> None:
    fsa_date, folder_name = _KNOWN_VERSIONS[year]
    url = f"{_FSA_BASE_URL}/{fsa_date}/{_TAXONOMY_ZIP_NAME}"
    print(f"\n{'='*60}")
    print(f"Year {year}: {folder_name}")
    print(f"URL: {url}")

    try:
        with httpx.Client(follow_redirects=True, timeout=180.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    size_mb = len(resp.content) / 1024 / 1024
    print(f"  Size: {size_mb:.1f} MB")

    try:
        zf = zipfile.ZipFile(BytesIO(resp.content))
    except Exception as e:
        print(f"  BAD ZIP: {e}")
        return

    # taxonomy/ と samples/ を含むパスを探す
    taxonomy_paths = []
    samples_paths = []
    for name in zf.namelist():
        parts = name.split("/")
        for i, part in enumerate(parts):
            if part == "taxonomy" and i > 0:
                prefix = "/".join(parts[:i])
                taxonomy_paths.append((prefix, name))
                break
            elif part == "samples" and i > 0:
                prefix = "/".join(parts[:i])
                samples_paths.append((prefix, name))
                break

    # ユニークなプレフィックスを表示
    tax_prefixes = sorted(set(p for p, _ in taxonomy_paths))
    sam_prefixes = sorted(set(p for p, _ in samples_paths))
    print(f"  taxonomy/ prefixes: {tax_prefixes}")
    print(f"  samples/ prefixes:  {sam_prefixes}")

    # 最初の数エントリを表示
    print(f"  First 10 entries:")
    for name in zf.namelist()[:10]:
        print(f"    {name!r}")

    # プレフィックスの深さ
    if tax_prefixes:
        depth = tax_prefixes[0].count("/") + 1
        print(f"  Prefix depth: {depth} level(s)")
        print(f"  Detected prefix: {tax_prefixes[0]!r}")

    zf.close()


if __name__ == "__main__":
    # 引数で年度を指定可能、なければ全年度
    years = [int(a) for a in sys.argv[1:]] if sys.argv[1:] else sorted(_KNOWN_VERSIONS, reverse=True)
    for y in years:
        check_year(y)
