"""H-8. 実データの品質 — xsi:nil / 該当なし / 計算検証の調査スクリプト

実行方法: uv run docs/QAs/scripts/H-8.quality.py
前提: EDINET_API_KEY 環境変数が必要
出力: 実データにおける nil 使用頻度、該当なし要素、計算不整合の統計
"""

import io
import os
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

import httpx

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key")
BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"

# XBRL 名前空間
XBRLI_NS = "http://www.xbrl.org/2003/instance"
LINK_NS = "http://www.xbrl.org/2003/linkbase"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# メタ要素の名前空間（Fact ではないもの）
META_NS = {XBRLI_NS, LINK_NS}


def fetch_xbrl_from_filing(doc_id: str) -> tuple[str, bytes] | None:
    """filing から primary .xbrl ファイルを取得する。

    Args:
        doc_id: EDINET書類ID

    Returns:
        (ファイル名, バイト列) のタプル、失敗時はNone
    """
    url = f"{BASE_URL}/documents/{doc_id}"
    params = {"type": 1, "Subscription-Key": API_KEY}
    resp = httpx.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        return None
    content_type = resp.headers.get("content-type", "")
    if "application/octet-stream" not in content_type:
        return None

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xbrl_files = [
            n for n in zf.namelist()
            if n.startswith("XBRL/PublicDoc/") and n.endswith(".xbrl")
        ]
        if not xbrl_files:
            return None
        # 最大サイズのファイルを選択（primary）
        primary = max(xbrl_files, key=lambda n: zf.getinfo(n).file_size)
        return (primary, zf.read(primary))


def analyze_xbrl(xbrl_bytes: bytes) -> dict:
    """XBRL インスタンスの品質指標を分析する。

    Args:
        xbrl_bytes: .xbrl ファイルのバイト列

    Returns:
        分析結果の辞書
    """
    root = ET.fromstring(xbrl_bytes)
    result: dict = {
        "total_facts": 0,
        "nil_facts": 0,
        "empty_facts": 0,
        "not_applicable_concepts": 0,
        "negative_zero": 0,
        "decimals_dist": Counter(),
        "nil_concepts": [],
        "not_applicable_examples": [],
    }

    for child in root:
        tag = child.tag
        ns = tag.split("}")[0].lstrip("{") if "}" in tag else ""
        if ns in META_NS:
            continue

        result["total_facts"] += 1
        local_name = tag.split("}")[-1] if "}" in tag else tag

        # xsi:nil チェック
        nil_val = child.get(f"{{{XSI_NS}}}nil")
        if nil_val == "true":
            result["nil_facts"] += 1
            if len(result["nil_concepts"]) < 10:
                result["nil_concepts"].append(local_name)

        # 空要素チェック
        text = (child.text or "").strip()
        if not text and nil_val != "true":
            result["empty_facts"] += 1

        # 該当なし concept チェック
        if "NotApplicable" in local_name or "該当なし" in text:
            result["not_applicable_concepts"] += 1
            if len(result["not_applicable_examples"]) < 5:
                result["not_applicable_examples"].append(
                    (local_name, text[:100] if text else "(empty)")
                )

        # マイナスゼロチェック
        if text == "-0":
            result["negative_zero"] += 1

        # decimals 分布
        decimals = child.get("decimals")
        if decimals:
            result["decimals_dist"][decimals] += 1

    return result


def main() -> None:
    """複数の filing の品質指標を調査する。"""
    # 有報シーズンからサンプリング
    dates = ["2025-06-20", "2025-06-25", "2025-11-14"]
    target_types = {"120", "130"}  # 有報と訂正有報のみ

    all_results = []

    for date in dates:
        print(f"\n--- {date} ---")
        url = f"{BASE_URL}/documents.json"
        params = {"date": date, "type": 2, "Subscription-Key": API_KEY}
        resp = httpx.get(url, params=params, timeout=30)
        resp.raise_for_status()
        filings = resp.json().get("results", [])

        count = 0
        for f in filings:
            if f.get("docTypeCode") not in target_types:
                continue
            if count >= 5:
                break

            doc_id = f.get("docID", "")
            filer = f.get("filerName", "不明")
            print(f"  {doc_id} ({filer})...", end=" ")

            xbrl_data = fetch_xbrl_from_filing(doc_id)
            if xbrl_data is None:
                print("SKIP")
                continue

            _, xbrl_bytes = xbrl_data
            analysis = analyze_xbrl(xbrl_bytes)
            analysis["doc_id"] = doc_id
            analysis["filer"] = filer
            all_results.append(analysis)
            count += 1

            print(
                f"Facts={analysis['total_facts']}, "
                f"nil={analysis['nil_facts']}, "
                f"N/A={analysis['not_applicable_concepts']}"
            )

    if not all_results:
        print("データが取得できませんでした")
        return

    # 統計サマリ
    print("\n" + "=" * 70)
    print(f"=== 品質統計（{len(all_results)} filing）===")

    total_facts = sum(r["total_facts"] for r in all_results)
    total_nil = sum(r["nil_facts"] for r in all_results)
    total_empty = sum(r["empty_facts"] for r in all_results)
    total_na = sum(r["not_applicable_concepts"] for r in all_results)
    total_neg_zero = sum(r["negative_zero"] for r in all_results)

    print(f"  総 Fact 数: {total_facts:,}")
    print(f"  xsi:nil=\"true\": {total_nil:,} ({total_nil / total_facts * 100:.1f}%)")
    print(f"  空要素（nil でない）: {total_empty:,} ({total_empty / total_facts * 100:.1f}%)")
    print(f"  NotApplicable 系: {total_na:,}")
    print(f"  マイナスゼロ: {total_neg_zero:,}")

    # decimals 分布（全体）
    print("\n=== decimals 分布 ===")
    all_decimals: Counter = Counter()
    for r in all_results:
        all_decimals.update(r["decimals_dist"])
    for dec, cnt in all_decimals.most_common(10):
        print(f"  decimals={dec}: {cnt:,}")

    # nil の concept 例
    print("\n=== xsi:nil の concept 例 ===")
    nil_all: Counter = Counter()
    for r in all_results:
        nil_all.update(r["nil_concepts"])
    for concept, cnt in nil_all.most_common(15):
        print(f"  {concept}: {cnt}")

    # NotApplicable の例
    print("\n=== NotApplicable の例 ===")
    seen = set()
    for r in all_results:
        for concept, text in r["not_applicable_examples"]:
            if concept not in seen:
                print(f"  {concept}: {text}")
                seen.add(concept)
            if len(seen) >= 10:
                break


if __name__ == "__main__":
    main()
