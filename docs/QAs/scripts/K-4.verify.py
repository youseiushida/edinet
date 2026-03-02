"""K-4. file_type 全パターン ZIP 内容物の追加検証スクリプト（書類種別多様化版）

実行方法: uv run docs/QAs/scripts/K-4.verify.py
前提: EDINET_API_KEY 環境変数が必要
出力: 複数の書類種別（一般事業会社有報、投資信託有報、has_english=True）で
      各 file_type の ZIP 内容物を比較検証。
      元スクリプト K-4.file_types.py が投資信託有報1件のみだったのに対し、
      書類種別を多様化して構造の一般性を確認する。
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import date, timedelta

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api
from edinet.api.download import (
    DownloadFileType,
    download_document,
    list_zip_members,
)
from edinet.models.filing import Filing


FILE_TYPES = [
    (DownloadFileType.XBRL_AND_AUDIT, "XBRL + 監査報告書", "xbrl"),
    (DownloadFileType.PDF, "PDF", "pdf"),
    (DownloadFileType.ATTACHMENT, "代替書面・添付", "attachment"),
    (DownloadFileType.ENGLISH, "英文ファイル", "english"),
    (DownloadFileType.CSV, "CSV", "csv"),
]


def find_diverse_samples(lookback_days: int = 60) -> list[dict]:
    """多様な書類種別のサンプルを探す。

    以下の3カテゴリを探索する:
    1. 一般事業会社の有報 (sec_code != None, doc_type_code=120)
    2. has_english=True の書類
    3. 四半期報告書 (doc_type_code=130 or 143)

    Args:
        lookback_days: 遡る最大日数。

    Returns:
        カテゴリごとの Filing を含む辞書のリスト。
    """
    targets = {
        "general_yuho": {
            "label": "一般事業会社 有価証券報告書",
            "filing": None,
            "match": lambda f: (
                f.has_xbrl
                and f.sec_code is not None
                and f.doc_type_code == "120"
            ),
        },
        "english": {
            "label": "英文ファイルあり書類",
            "filing": None,
            "match": lambda f: (
                f.has_xbrl and f.has_english
            ),
        },
        "quarterly": {
            "label": "四半期報告書",
            "filing": None,
            "match": lambda f: (
                f.has_xbrl
                and f.doc_type_code in ("130", "133", "143", "150")
            ),
        },
    }

    today = date.today()
    for i in range(lookback_days):
        d = today - timedelta(days=i)
        filings = public_api.documents(date=d)
        for f in filings:
            for key, t in targets.items():
                if t["filing"] is None and t["match"](f):
                    t["filing"] = f

        if all(t["filing"] is not None for t in targets.values()):
            break

    return [
        {"key": key, "label": t["label"], "filing": t["filing"]}
        for key, t in targets.items()
    ]


def analyze_filing_file_types(filing: Filing, label: str) -> dict:
    """1つの書類について全 file_type をダウンロード・分析する。

    Args:
        filing: 分析対象の Filing。
        label: 書類カテゴリの表示ラベル。

    Returns:
        分析結果の辞書。
    """
    print(f"\n{'=' * 70}")
    print(f"【{label}】")
    print(f"  書類ID: {filing.doc_id}")
    print(f"  提出者: {filing.filer_name}")
    print(f"  書類種別: {filing.doc_type_label_ja} (code={filing.doc_type_code})")
    print(f"  提出日: {filing.filing_date}")

    flags = {
        "xbrl": filing.has_xbrl,
        "pdf": filing.has_pdf,
        "attachment": filing.has_attachment,
        "english": filing.has_english,
        "csv": filing.has_csv,
    }
    print(f"  フラグ: {flags}")

    results = {}
    for ft, ft_label, flag_key in FILE_TYPES:
        print(f"\n  --- file_type={ft.value} ({ft_label}) ---")

        if not flags[flag_key]:
            print(f"    スキップ: has_{flag_key}=False")
            results[ft.value] = {
                "label": ft_label,
                "skipped": True,
                "reason": f"has_{flag_key}=False",
            }
            continue

        try:
            data = download_document(filing.doc_id, file_type=ft.value)
            print(f"    サイズ: {len(data):,} bytes")

            if ft.is_zip:
                members = list_zip_members(data)
                print(f"    ファイル数: {len(members)}")

                by_ext: Counter = Counter()
                for m in members:
                    ext = m.rsplit(".", 1)[-1].lower() if "." in m else "none"
                    by_ext[ext] += 1

                print(f"    拡張子別: ", end="")
                print(", ".join(f".{e}={n}" for e, n in by_ext.most_common()))

                # ディレクトリ構造
                dirs = sorted(set(
                    m.split("/")[0] for m in members if "/" in m
                ))
                print(f"    トップディレクトリ: {dirs}")

                results[ft.value] = {
                    "label": ft_label,
                    "skipped": False,
                    "size": len(data),
                    "file_count": len(members),
                    "by_ext": dict(by_ext),
                    "top_dirs": dirs,
                    "members": list(members),
                }
            else:
                print(f"    形式: PDF（非 ZIP）")
                results[ft.value] = {
                    "label": ft_label,
                    "skipped": False,
                    "size": len(data),
                    "is_pdf": True,
                }
        except Exception as e:
            print(f"    エラー: {e}")
            results[ft.value] = {
                "label": ft_label,
                "skipped": False,
                "error": str(e),
            }

    return results


def main() -> None:
    """メイン処理。"""
    print("K-4 検証: file_type 全パターン（書類種別多様化版）")
    print("=" * 70)

    # Step 1: 多様なサンプルを探す
    print("\n[Step 1] 多様な書類種別のサンプルを検索中...")
    samples = find_diverse_samples()

    for s in samples:
        if s["filing"] is None:
            print(f"  WARNING: {s['label']} が見つかりませんでした")
        else:
            f = s["filing"]
            print(f"  {s['label']}: {f.doc_id} ({f.filer_name})")

    # Step 2: 各サンプルで全 file_type を分析
    print(f"\n[Step 2] 各サンプルの file_type 分析")
    all_results = {}
    for s in samples:
        if s["filing"] is not None:
            r = analyze_filing_file_types(s["filing"], s["label"])
            all_results[s["key"]] = r

    # Step 3: 比較サマリー
    print(f"\n\n{'=' * 70}")
    print("比較サマリー")
    print(f"{'=' * 70}")

    # file_type=1 のディレクトリ構造比較
    print("\n--- file_type=1 (XBRL) のディレクトリ構造比較 ---")
    for s in samples:
        if s["filing"] is None:
            continue
        r = all_results.get(s["key"], {}).get("1", {})
        if r.get("skipped") or r.get("error"):
            continue
        top_dirs = r.get("top_dirs", [])
        by_ext = r.get("by_ext", {})
        print(f"\n  {s['label']}:")
        print(f"    トップディレクトリ: {top_dirs}")
        print(f"    拡張子内訳: {dict(by_ext)}")
        print(f"    ファイル数: {r.get('file_count', 'N/A')}")

    # file_type=4 (英文) の結果
    print("\n--- file_type=4 (英文ファイル) の検証 ---")
    for s in samples:
        if s["filing"] is None:
            continue
        r = all_results.get(s["key"], {}).get("4", {})
        if r.get("skipped"):
            print(f"  {s['label']}: スキップ ({r.get('reason', '')})")
        elif r.get("error"):
            print(f"  {s['label']}: エラー ({r['error']})")
        else:
            print(f"  {s['label']}: {r.get('file_count', 'N/A')} ファイル")
            print(f"    拡張子: {r.get('by_ext', {})}")
            print(f"    ディレクトリ: {r.get('top_dirs', [])}")
            if r.get("members"):
                for m in r["members"][:20]:
                    print(f"      {m}")

    # 全体の構造一貫性チェック
    print("\n--- 構造一貫性チェック ---")
    for ft_val, ft_label, _ in FILE_TYPES:
        print(f"\n  file_type={ft_val} ({ft_label}):")
        for s in samples:
            if s["filing"] is None:
                continue
            r = all_results.get(s["key"], {}).get(ft_val, {})
            if r.get("skipped"):
                status = f"スキップ"
            elif r.get("error"):
                status = f"エラー"
            elif r.get("is_pdf"):
                status = f"PDF {r['size']:,}B"
            else:
                status = (
                    f"ZIP {r.get('size', 0):,}B, "
                    f"{r.get('file_count', 0)}ファイル"
                )
            print(f"    {s['label']}: {status}")


if __name__ == "__main__":
    main()
