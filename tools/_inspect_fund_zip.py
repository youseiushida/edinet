"""ファンド系 ZIP の構造を調査する。

失敗した doc_id の ZIP をダウンロードし、メンバー数・サイズ・
PublicDoc 内の .xbrl / .htm ファイルの有無を調べる。

使い方:
    uv run python tools/_inspect_fund_zip.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.api.download import (
    MAX_MEMBER_COUNT,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    MAX_ZIP_BYTES,
    DownloadFileType,
)

# ストレステストで失敗した doc_id（りそなAM 3件 + 野村AM 3件）
FAILED_DOC_IDS = [
    "S100VMJV",  # りそなAM
    "S100VMJU",  # りそなAM
    "S100VMJX",  # りそなAM
    "S100VP7L",  # 野村AM
    "S100VP7I",  # 野村AM
    "S100VSHC",  # 野村AM
]

REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "fund_zip_report.txt"


async def inspect_zip(doc_id: str) -> dict:
    """ZIP をダウンロードして構造を調査する。"""
    result: dict = {"doc_id": doc_id}

    try:
        # 直接 API でダウンロード（ライブラリの制限チェック前に生 bytes を取得）
        from edinet import _http

        response = await _http.aget(
            f"/documents/{doc_id}",
            params={"type": DownloadFileType.XBRL_AND_AUDIT.value},
        )
        zip_bytes = response.content
        result["zip_size_mb"] = len(zip_bytes) / (1024 * 1024)
        result["zip_size_exceeds"] = len(zip_bytes) > MAX_ZIP_BYTES

        try:
            zf = ZipFile(BytesIO(zip_bytes))
        except BadZipFile as e:
            result["error"] = f"BadZipFile: {e}"
            return result

        all_infos = [info for info in zf.infolist() if not info.is_dir()]
        result["member_count"] = len(all_infos)
        result["member_count_exceeds"] = len(all_infos) > MAX_MEMBER_COUNT

        total_uncompressed = sum(info.file_size for info in all_infos)
        result["total_uncompressed_mb"] = total_uncompressed / (1024 * 1024)
        result["total_uncompressed_exceeds"] = (
            total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES
        )

        # PublicDoc 配下のファイル分析
        public_doc_files = [
            info
            for info in all_infos
            if "/publicdoc/" in f"/{info.filename.lower()}"
        ]
        result["public_doc_count"] = len(public_doc_files)

        xbrl_files = [
            info.filename
            for info in public_doc_files
            if info.filename.lower().endswith(".xbrl")
        ]
        result["xbrl_count"] = len(xbrl_files)
        result["xbrl_files"] = xbrl_files[:10]  # 最大10件表示

        ixbrl_files = [
            info.filename
            for info in public_doc_files
            if info.filename.lower().endswith("_ixbrl.htm")
        ]
        result["ixbrl_count"] = len(ixbrl_files)
        result["ixbrl_files"] = ixbrl_files[:10]

        htm_files = [
            info.filename
            for info in public_doc_files
            if info.filename.lower().endswith(".htm")
            or info.filename.lower().endswith(".html")
        ]
        result["htm_count"] = len(htm_files)

        # トップレベルディレクトリ構造
        top_dirs = Counter()
        for info in all_infos:
            parts = info.filename.split("/")
            if len(parts) >= 2:
                top_dirs[parts[0] + "/" + parts[1]] += 1
            else:
                top_dirs[parts[0]] += 1
        result["top_dirs"] = dict(top_dirs.most_common(20))

        # 拡張子の分布
        ext_counter = Counter()
        for info in public_doc_files:
            ext = Path(info.filename).suffix.lower()
            ext_counter[ext] += 1
        result["public_doc_extensions"] = dict(ext_counter.most_common(15))

        zf.close()

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    return result


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    print(f"ファンド系 ZIP 構造調査: {len(FAILED_DOC_IDS)} 件")
    print("=" * 70)

    results = []
    for doc_id in FAILED_DOC_IDS:
        print(f"\n--- {doc_id} ---")
        r = await inspect_zip(doc_id)
        results.append(r)

        if "error" in r:
            print(f"  エラー: {r['error']}")
            continue

        print(f"  ZIP サイズ: {r['zip_size_mb']:.1f} MB (超過: {r['zip_size_exceeds']})")
        print(
            f"  メンバー数: {r['member_count']} (超過: {r['member_count_exceeds']})"
        )
        print(
            f"  展開サイズ: {r['total_uncompressed_mb']:.1f} MB"
            f" (超過: {r['total_uncompressed_exceeds']})"
        )
        print(f"  PublicDoc ファイル数: {r['public_doc_count']}")
        print(f"  .xbrl ファイル数: {r['xbrl_count']}")
        print(f"  iXBRL (.htm) ファイル数: {r['ixbrl_count']}")
        print(f"  全 .htm/.html 数: {r['htm_count']}")

        if r["xbrl_files"]:
            print(f"  XBRL ファイル:")
            for f in r["xbrl_files"]:
                print(f"    {f}")

        if r["ixbrl_files"]:
            print(f"  iXBRL ファイル:")
            for f in r["ixbrl_files"]:
                print(f"    {f}")

        print(f"  PublicDoc 拡張子分布: {r['public_doc_extensions']}")
        print(f"  トップディレクトリ:")
        for d, count in list(r["top_dirs"].items())[:10]:
            print(f"    {d}: {count} files")

    await edinet.aclose()

    # レポート保存
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("ファンド系 ZIP 構造調査レポート\n")
        f.write("=" * 70 + "\n\n")
        for r in results:
            f.write(f"--- {r['doc_id']} ---\n")
            if "error" in r:
                f.write(f"  エラー: {r['error']}\n\n")
                continue
            f.write(f"  ZIP: {r['zip_size_mb']:.1f} MB\n")
            f.write(f"  メンバー数: {r['member_count']} (上限: {MAX_MEMBER_COUNT})\n")
            f.write(f"  展開サイズ: {r['total_uncompressed_mb']:.1f} MB\n")
            f.write(f"  PublicDoc: {r['public_doc_count']} files\n")
            f.write(f"  .xbrl: {r['xbrl_count']}\n")
            f.write(f"  iXBRL: {r['ixbrl_count']}\n")
            f.write(f"  .htm/.html: {r['htm_count']}\n")
            f.write(f"  拡張子: {r['public_doc_extensions']}\n")
            if r["xbrl_files"]:
                f.write(f"  XBRL files: {r['xbrl_files']}\n")
            if r["ixbrl_files"]:
                f.write(f"  iXBRL files: {r['ixbrl_files']}\n")
            f.write(f"  ディレクトリ: {r['top_dirs']}\n\n")

    print(f"\nレポート保存: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
