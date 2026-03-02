"""K-4. file_type 全パターンの ZIP 内容物調査スクリプト

実行方法: uv run docs/QAs/scripts/K-4.file_types.py
前提: EDINET_API_KEY 環境変数が必要
出力: 各 file_type (1-5) の ZIP/PDF 内容物一覧を表形式で出力
"""

from __future__ import annotations

import os
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
    (DownloadFileType.XBRL_AND_AUDIT, "XBRL + 監査報告書"),
    (DownloadFileType.PDF, "PDF"),
    (DownloadFileType.ATTACHMENT, "代替書面・添付"),
    (DownloadFileType.ENGLISH, "英文ファイル"),
    (DownloadFileType.CSV, "CSV"),
]


def find_full_flag_filing(lookback_days: int = 30) -> Filing | None:
    """全フラグが True の書類を探す。

    Args:
        lookback_days: 遡る最大日数。

    Returns:
        全フラグ True の Filing、見つからなければ最も多くのフラグが True のもの。
    """
    today = date.today()
    best = None
    best_count = 0

    for i in range(lookback_days):
        d = today - timedelta(days=i)
        filings = public_api.documents(date=d)
        for f in filings:
            flags = [f.has_xbrl, f.has_pdf, f.has_attachment, f.has_english, f.has_csv]
            count = sum(flags)
            if count == 5:
                return f
            if count > best_count:
                best = f
                best_count = count

    return best


def main() -> None:
    """メイン処理。"""
    print("K-4: file_type 全パターン ZIP 内容物調査")
    print("=" * 70)

    # Step 1: 全フラグ True の書類を探す
    print("\n[Step 1] 全フラグ True の書類を検索中...")
    filing = find_full_flag_filing()

    if filing is None:
        print("ERROR: 書類が見つかりませんでした")
        return

    flags = {
        "xbrl": filing.has_xbrl,
        "pdf": filing.has_pdf,
        "attachment": filing.has_attachment,
        "english": filing.has_english,
        "csv": filing.has_csv,
    }
    print(f"  書類ID: {filing.doc_id}")
    print(f"  提出者: {filing.filer_name}")
    print(f"  書類種別: {filing.doc_type_label_ja}")
    print(f"  提出日: {filing.filing_date}")
    print(f"  フラグ: {flags}")

    # Step 2: 各 file_type のダウンロードと分析
    print(f"\n[Step 2] 各 file_type のダウンロードと分析")
    print("=" * 70)

    results = []

    for ft, label in FILE_TYPES:
        flag_key = {
            DownloadFileType.XBRL_AND_AUDIT: "xbrl",
            DownloadFileType.PDF: "pdf",
            DownloadFileType.ATTACHMENT: "attachment",
            DownloadFileType.ENGLISH: "english",
            DownloadFileType.CSV: "csv",
        }[ft]

        print(f"\n--- file_type={ft.value} ({label}) ---")
        print(f"  has_{flag_key}: {flags[flag_key]}")

        if not flags[flag_key]:
            print(f"  スキップ: フラグが False")
            results.append({
                "file_type": ft.value,
                "label": label,
                "flag": False,
                "size": None,
                "is_zip": ft.is_zip,
                "members": [],
                "error": "フラグ False のためスキップ",
            })
            continue

        try:
            data = download_document(filing.doc_id, file_type=ft.value)
            print(f"  サイズ: {len(data):,} bytes")

            if ft.is_zip:
                members = list_zip_members(data)
                print(f"  ZIP メンバー数: {len(members)}")

                # カテゴリ別に分類
                by_ext: dict[str, list[str]] = {}
                for m in members:
                    ext = m.rsplit(".", 1)[-1].lower() if "." in m else "(拡張子なし)"
                    by_ext.setdefault(ext, []).append(m)

                print(f"  拡張子別:")
                for ext, files in sorted(by_ext.items()):
                    print(f"    .{ext}: {len(files)} ファイル")

                print(f"  全メンバー:")
                for m in members:
                    print(f"    {m}")

                # XBRL 関連ファイルの有無
                xbrl_related = [
                    m for m in members
                    if m.lower().endswith((".xbrl", ".xsd", ".xml", ".htm", ".html"))
                ]
                results.append({
                    "file_type": ft.value,
                    "label": label,
                    "flag": True,
                    "size": len(data),
                    "is_zip": True,
                    "members": members,
                    "xbrl_related": xbrl_related,
                    "by_ext": by_ext,
                    "error": None,
                })
            else:
                # PDF の場合
                print(f"  形式: PDF（非 ZIP）")
                results.append({
                    "file_type": ft.value,
                    "label": label,
                    "flag": True,
                    "size": len(data),
                    "is_zip": False,
                    "members": [],
                    "error": None,
                })

        except Exception as e:
            print(f"  エラー: {e}")
            results.append({
                "file_type": ft.value,
                "label": label,
                "flag": flags[flag_key],
                "size": None,
                "is_zip": ft.is_zip,
                "members": [],
                "error": str(e),
            })

    # Step 3: サマリー表
    print(f"\n\n{'=' * 70}")
    print("サマリー表")
    print(f"{'=' * 70}")
    print(f"{'file_type':>10} | {'ラベル':<20} | {'フラグ':>6} | {'ZIP?':>4} | {'サイズ':>12} | {'ファイル数':>8} | {'備考'}")
    print("-" * 100)
    for r in results:
        size_str = f"{r['size']:,}" if r["size"] else "N/A"
        member_count = len(r["members"])
        note = r["error"] or ""
        if r.get("xbrl_related"):
            note = f"XBRL関連: {len(r['xbrl_related'])}件"
        print(
            f"{r['file_type']:>10} | {r['label']:<20} | {str(r['flag']):>6} | "
            f"{'Yes' if r['is_zip'] else 'No':>4} | {size_str:>12} | "
            f"{member_count:>8} | {note}"
        )


if __name__ == "__main__":
    main()
