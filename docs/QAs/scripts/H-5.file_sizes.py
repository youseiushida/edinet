"""H-5. ファイルサイズの目安 — サンプル filing のサイズ統計スクリプト

実行方法: uv run docs/QAs/scripts/H-5.file_sizes.py
前提: EDINET_API_KEY 環境変数が必要
出力: 多様な filing の ZIP サイズ、.xbrl サイズ、.htm サイズの統計
"""

import io
import os
import zipfile
from collections import defaultdict

import httpx

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key")
BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"


def fetch_filing_list(date: str) -> list[dict]:
    """指定日の filing 一覧を取得する。

    Args:
        date: YYYY-MM-DD形式の日付

    Returns:
        filing情報の辞書リスト
    """
    url = f"{BASE_URL}/documents.json"
    params = {"date": date, "type": 2, "Subscription-Key": API_KEY}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def download_zip(doc_id: str) -> bytes | None:
    """filing の ZIP をダウンロードする。

    Args:
        doc_id: EDINET書類ID

    Returns:
        ZIPファイルのバイト列、失敗時はNone
    """
    url = f"{BASE_URL}/documents/{doc_id}"
    params = {"type": 1, "Subscription-Key": API_KEY}
    resp = httpx.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        return None
    if "application/octet-stream" not in resp.headers.get("content-type", ""):
        return None
    return resp.content


def analyze_zip(zip_bytes: bytes) -> dict:
    """ZIP の中身のサイズを分析する。

    Args:
        zip_bytes: ZIPファイルのバイト列

    Returns:
        分析結果の辞書
    """
    result: dict = {
        "zip_size_kb": len(zip_bytes) / 1024,
        "files": defaultdict(list),
    }
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            ext = info.filename.rsplit(".", 1)[-1].lower() if "." in info.filename else "other"
            result["files"][ext].append(
                {"name": info.filename.split("/")[-1], "size_kb": info.file_size / 1024}
            )
    return result


def main() -> None:
    """多様な filing をダウンロードしてサイズ統計を収集する。"""
    # 複数日付から多様なサンプルを取得
    dates = [
        "2025-06-20",  # 有報提出シーズン
        "2025-06-25",
        "2025-03-14",  # 四半期
        "2025-11-14",  # 中間期
    ]

    all_results = []
    # doc_type_code: 120=有報, 130=訂正有報, 140=四半期, 030=臨時報告書, 350=大量保有
    target_types = {"120", "130", "140", "030", "350", "160"}

    for date in dates:
        print(f"\n--- {date} の filing を取得中... ---")
        filings = fetch_filing_list(date)
        # 書類種別ごとに最大3件
        type_count: dict[str, int] = defaultdict(int)
        for f in filings:
            dtype = f.get("docTypeCode", "")
            if dtype not in target_types:
                continue
            if type_count[dtype] >= 3:
                continue

            doc_id = f.get("docID", "")
            filer = f.get("filerName", "不明")
            print(f"  DL: {doc_id} ({filer}, type={dtype})...", end=" ")

            zip_bytes = download_zip(doc_id)
            if zip_bytes is None:
                print("SKIP (DL failed)")
                continue

            analysis = analyze_zip(zip_bytes)
            analysis["doc_id"] = doc_id
            analysis["filer"] = filer
            analysis["doc_type"] = dtype
            all_results.append(analysis)
            type_count[dtype] += 1
            print(f"ZIP={analysis['zip_size_kb']:.0f}KB")

    # 統計表示
    print("\n" + "=" * 70)
    print("=== 全体統計 ===")
    print(f"サンプル数: {len(all_results)}")

    if not all_results:
        print("データが取得できませんでした")
        return

    zip_sizes = [r["zip_size_kb"] for r in all_results]
    print(f"ZIP サイズ: min={min(zip_sizes):.0f}KB, max={max(zip_sizes):.0f}KB, "
          f"avg={sum(zip_sizes) / len(zip_sizes):.0f}KB, "
          f"median={sorted(zip_sizes)[len(zip_sizes) // 2]:.0f}KB")

    # .xbrl ファイルサイズ
    xbrl_sizes = []
    for r in all_results:
        for info in r["files"].get("xbrl", []):
            xbrl_sizes.append(info["size_kb"])
    if xbrl_sizes:
        print(f".xbrl サイズ: min={min(xbrl_sizes):.0f}KB, max={max(xbrl_sizes):.0f}KB, "
              f"avg={sum(xbrl_sizes) / len(xbrl_sizes):.0f}KB, "
              f"median={sorted(xbrl_sizes)[len(xbrl_sizes) // 2]:.0f}KB")

    # .htm ファイルサイズ (iXBRL)
    htm_sizes = []
    for r in all_results:
        for info in r["files"].get("htm", []):
            htm_sizes.append(info["size_kb"])
    if htm_sizes:
        print(f".htm サイズ: min={min(htm_sizes):.0f}KB, max={max(htm_sizes):.0f}KB, "
              f"avg={sum(htm_sizes) / len(htm_sizes):.0f}KB, "
              f"median={sorted(htm_sizes)[len(htm_sizes) // 2]:.0f}KB")

    # 書類種別ごと
    print("\n=== 書類種別ごとの ZIP サイズ ===")
    type_labels = {"120": "有報", "130": "訂正有報", "140": "四半期", "030": "臨時報告書",
                   "350": "大量保有", "160": "半期報告書"}
    by_type: dict[str, list[float]] = defaultdict(list)
    for r in all_results:
        by_type[r["doc_type"]].append(r["zip_size_kb"])
    for dtype, sizes in sorted(by_type.items()):
        label = type_labels.get(dtype, dtype)
        print(f"  {label}(type={dtype}): n={len(sizes)}, "
              f"min={min(sizes):.0f}KB, max={max(sizes):.0f}KB, avg={sum(sizes) / len(sizes):.0f}KB")

    # 最大の filing の詳細
    largest = max(all_results, key=lambda r: r["zip_size_kb"])
    print(f"\n=== 最大 filing の詳細 ===")
    print(f"  {largest['doc_id']} ({largest['filer']}, type={largest['doc_type']})")
    print(f"  ZIP サイズ: {largest['zip_size_kb']:.0f}KB")
    for ext, files in sorted(largest["files"].items()):
        total = sum(f["size_kb"] for f in files)
        print(f"  .{ext}: {len(files)} ファイル, 合計 {total:.0f}KB")


if __name__ == "__main__":
    main()
