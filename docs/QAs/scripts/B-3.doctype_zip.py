"""B-3. 書類種別ごとの ZIP の違い — 各 doc_type の ZIP 取得・分析スクリプト

実行方法: uv run docs/QAs/scripts/B-3.doctype_zip.py
前提: EDINET_API_KEY 環境変数が必要
出力: 各 doc_type_code の ZIP 内容（.xbrl 有無、.htm 有無、構造）
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_members_by_ext,
    get_zip,
    print_filing_info,
)

# 調査対象の doc_type 一覧
DOC_TYPES = [
    ("120", "有価証券報告書"),
    ("130", "有価証券報告書（訂正）"),
    ("140", "四半期報告書"),
    ("150", "四半期報告書（訂正）"),
    ("160", "半期報告書"),
    ("170", "半期報告書（訂正）"),
    ("030", "有価証券届出書"),
    ("180", "臨時報告書"),
    ("235", "内部統制報告書"),
    ("240", "公開買付届出書"),
    ("290", "意見表明報告書"),
    ("350", "大量保有報告書"),
]

# 各 doc_type の検索期間
# API は 1日 = 1コールのため、期間を最小限に絞る（3〜7日）
# 有報は 6 月下旬に集中、四半期は 2024-08 に集中
SEARCH_PERIODS = {
    "120": ("2025-06-25", "2025-06-30"),   # 有報: 6月下旬に大量提出
    "130": ("2025-07-01", "2025-07-07"),   # 訂正: 有報提出直後
    "140": ("2024-08-12", "2024-08-16"),   # 四半期: Q1 提出集中期
    "150": ("2024-09-01", "2024-09-07"),   # 訂正四半期
    "160": ("2025-09-25", "2025-09-30"),   # 半期: 9月下旬
    "170": ("2025-10-01", "2025-10-07"),   # 訂正半期
    "030": ("2025-06-01", "2025-06-07"),   # 届出書
    "180": ("2025-06-25", "2025-06-30"),   # 臨時報告書: 随時
    "235": ("2025-06-25", "2025-06-30"),   # 内部統制: 有報と同時提出
    "240": ("2025-06-01", "2025-06-07"),   # 公開買付
    "290": ("2025-06-01", "2025-06-07"),   # 意見表明
    "350": ("2025-06-25", "2025-06-30"),   # 大量保有: 随時
}


def decode_xml(raw: bytes) -> str:
    """XML バイト列をテキストにデコードする。

    Args:
        raw: デコード対象のバイト列。

    Returns:
        デコードされたテキスト。
    """
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode("utf-8", errors="replace")


def check_dei_accounting_standard(zip_bytes: bytes) -> str | None:
    """XBRL から AccountingStandardsDEI を簡易抽出する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        会計基準文字列、取得できない場合は None。
    """
    xbrl_files = find_members_by_ext(zip_bytes, ".xbrl")
    for member in xbrl_files:
        if "/publicdoc/" in f"/{member.lower()}":
            try:
                raw = extract_member(zip_bytes, member)
                text = decode_xml(raw)
                m = re.search(
                    r"<[^>]*AccountingStandardsDEI[^>]*>"
                    r"([^<]*)</[^>]*AccountingStandardsDEI>",
                    text,
                )
                if m:
                    return m.group(1).strip()
            except Exception:
                pass
    return None


def check_financial_statements(zip_bytes: bytes) -> dict[str, bool]:
    """XBRL 内の財務諸表関連 concept の有無を簡易チェックする。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        財務諸表種別 -> 存在有無の辞書。
    """
    result = {
        "BS": False,
        "PL": False,
        "CF": False,
    }
    xbrl_files = find_members_by_ext(zip_bytes, ".xbrl")
    for member in xbrl_files:
        if "/publicdoc/" in f"/{member.lower()}":
            try:
                raw = extract_member(zip_bytes, member)
                text = decode_xml(raw)
                if "Assets" in text or "TotalAssets" in text:
                    result["BS"] = True
                if "NetSales" in text or "Revenue" in text or "OperatingIncome" in text:
                    result["PL"] = True
                if "CashFlow" in text or "NetCashProvided" in text:
                    result["CF"] = True
            except Exception:
                pass
    return result


def analyze_zip_structure(zip_bytes: bytes) -> dict:
    """ZIP の構造を分析する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        分析結果の辞書。
    """
    result: dict = {
        "total_files": 0,
        "zip_size": len(zip_bytes),
        "has_xbrl": False,
        "has_htm": False,
        "has_xsd": False,
        "has_public_doc": False,
        "has_audit_doc": False,
        "xbrl_files": [],
        "htm_files": [],
        "folders": set(),
    }

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        result["total_files"] = len(infos)

        for info in infos:
            name = info.filename
            ext = os.path.splitext(name)[1].lower()

            # フォルダの記録
            parts = name.split("/")
            if len(parts) > 1:
                result["folders"].add(parts[0])
                if len(parts) > 2:
                    result["folders"].add(f"{parts[0]}/{parts[1]}")

            if ext == ".xbrl":
                result["has_xbrl"] = True
                result["xbrl_files"].append(name)
            if ext in (".htm", ".html"):
                result["has_htm"] = True
                result["htm_files"].append(name)
            if ext == ".xsd":
                result["has_xsd"] = True
            if "/publicdoc/" in f"/{name.lower()}":
                result["has_public_doc"] = True
            if "/auditdoc/" in f"/{name.lower()}":
                result["has_audit_doc"] = True

    return result


def process_doc_type(doc_type_code: str, doc_type_name: str) -> dict | None:
    """1 つの doc_type を処理する。

    Args:
        doc_type_code: 書類種別コード。
        doc_type_name: 書類種別名。

    Returns:
        分析結果の辞書。見つからなければ None。
    """
    print(f"\n{'=' * 70}")
    print(f"doc_type={doc_type_code}: {doc_type_name}")
    print(f"{'=' * 70}")

    start, end = SEARCH_PERIODS.get(
        doc_type_code, ("2025-01-01", "2025-12-31"),
    )

    # has_xbrl=True で検索（API コール数を抑えるため XBRL ありのみ）
    filings_xbrl = find_filings(
        doc_type=doc_type_code,
        start=start,
        end=end,
        has_xbrl=True,
        max_results=1,
    )

    print(f"  検索結果: XBRL有={len(filings_xbrl)}")

    if not filings_xbrl:
        print(f"  結果: 期間内に XBRL 付き提出なし")
        return None

    filing = filings_xbrl[0]
    print_filing_info(filing, label=f"doc_type={doc_type_code} サンプル")

    # ZIP ダウンロード
    try:
        zip_bytes = get_zip(filing.doc_id)
    except Exception as exc:
        print(f"  ZIP ダウンロード失敗: {type(exc).__name__}: {exc}")
        return None

    # 構造分析
    structure = analyze_zip_structure(zip_bytes)
    print(f"\n  ZIP サイズ: {structure['zip_size']:,} bytes")
    print(f"  ファイル数: {structure['total_files']}")
    print(f"  フォルダ: {sorted(structure['folders'])}")
    print(f"  .xbrl: {'YES' if structure['has_xbrl'] else 'NO'}"
          f" ({len(structure['xbrl_files'])} ファイル)")
    print(f"  .htm: {'YES' if structure['has_htm'] else 'NO'}"
          f" ({len(structure['htm_files'])} ファイル)")
    print(f"  .xsd: {'YES' if structure['has_xsd'] else 'NO'}")
    print(f"  PublicDoc: {'YES' if structure['has_public_doc'] else 'NO'}")
    print(f"  AuditDoc: {'YES' if structure['has_audit_doc'] else 'NO'}")

    # XBRL ファイル一覧
    if structure["xbrl_files"]:
        print(f"\n  .xbrl ファイル一覧:")
        for f in structure["xbrl_files"]:
            print(f"    {f}")

        # DEI チェック
        acct_std = check_dei_accounting_standard(zip_bytes)
        if acct_std:
            print(f"\n  AccountingStandardsDEI: {acct_std}")

        # 財務諸表チェック
        fs_check = check_financial_statements(zip_bytes)
        print(f"  財務諸表: BS={fs_check['BS']}, PL={fs_check['PL']}, "
              f"CF={fs_check['CF']}")

    return {
        "doc_type_code": doc_type_code,
        "doc_type_name": doc_type_name,
        "doc_id": filing.doc_id,
        "filer_name": filing.filer_name,
        "has_xbrl_flag": filing.has_xbrl,
        "structure": structure,
    }


def main() -> None:
    """メイン処理。"""
    print("B-3: 書類種別ごとの ZIP の違い")
    print("=" * 70)

    results: list[dict] = []

    for doc_type_code, doc_type_name in DOC_TYPES:
        try:
            result = process_doc_type(doc_type_code, doc_type_name)
            if result:
                results.append(result)
        except Exception as exc:
            print(f"\n  ERROR (doc_type={doc_type_code}): "
                  f"{type(exc).__name__}: {exc}")

    # サマリテーブル
    print(f"\n{'#' * 70}")
    print("=== サマリテーブル ===")
    print(f"{'#' * 70}")
    print(f"\n{'doc_type':<10s} {'書類名':<25s} {'XBRL':>5s} {'HTM':>5s} "
          f"{'XSD':>5s} {'Pub':>5s} {'Aud':>5s} {'Files':>6s}")
    print("-" * 75)

    for r in results:
        s = r["structure"]
        print(f"{r['doc_type_code']:<10s} {r['doc_type_name']:<25s} "
              f"{'Y' if s['has_xbrl'] else 'N':>5s} "
              f"{'Y' if s['has_htm'] else 'N':>5s} "
              f"{'Y' if s['has_xsd'] else 'N':>5s} "
              f"{'Y' if s['has_public_doc'] else 'N':>5s} "
              f"{'Y' if s['has_audit_doc'] else 'N':>5s} "
              f"{s['total_files']:>6d}")

    print(f"\n{'=' * 70}")
    print("B-3 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
