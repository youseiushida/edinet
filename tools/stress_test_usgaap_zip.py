"""US-GAAP企業(野村HD)のZIP内ファイルを徹底調査。

file_type=1 (XBRL+監査) と file_type=5 (CSV) の両方を取得し、
US-GAAPの財務諸表データがどこかに構造化されていないか調べる。
"""

from __future__ import annotations

import os
import zipfile
from io import BytesIO

import edinet
from edinet import DocType, Company, configure, documents
from edinet.api.download import download_document

API_KEY = os.environ.get("EDINET_API_KEY", "cb5e960f897943299abf3edf8982e363")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)


def main():
    # 野村HDの有報を特定
    c = Company.search("野村ホールディングス", limit=1)[0]
    filings = c.get_filings(
        start="2025-06-01", end="2025-06-30",
        doc_type=DocType.ANNUAL_SECURITIES_REPORT,
    )
    filing = filings[0]
    doc_id = filing.doc_id
    print(f"対象: {filing.filer_name} (doc_id={doc_id})")

    # ========== 1. file_type=1 (XBRL ZIP) ==========
    print("\n" + "=" * 70)
    print("  file_type=1 (XBRL+監査報告書)")
    print("=" * 70)

    zip_bytes = download_document(doc_id, file_type="1")
    zf = zipfile.ZipFile(BytesIO(zip_bytes))

    print(f"\n  ZIP サイズ: {len(zip_bytes):,} bytes")
    print(f"  ファイル数: {len(zf.namelist())}")
    print(f"\n  全ファイル一覧:")
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        ext = name.rsplit(".", 1)[-1] if "." in name else ""
        print(f"    {name}  ({info.file_size:,} bytes) [{ext}]")

    # XBRLファイルの中身チェック
    xbrl_files = [n for n in zf.namelist() if n.endswith(".xbrl")]
    print(f"\n  .xbrl ファイル: {len(xbrl_files)}件")
    for xf in xbrl_files:
        data = zf.read(xf)
        print(f"\n  --- {xf} ({len(data):,} bytes) ---")
        # 先頭と末尾を表示
        text = data.decode("utf-8", errors="replace")
        lines = text.split("\n")
        print(f"    行数: {len(lines)}")
        # Fact数をカウント
        import re
        # テキストブロック(USGAAP TextBlock)を探す
        textblock_pattern = re.compile(r"<[^>]*USGAAP[^>]*TextBlock[^>]*>", re.IGNORECASE)
        textblocks = textblock_pattern.findall(text)
        print(f"    USGAAPTextBlock要素: {len(textblocks)}件")
        for tb in textblocks[:5]:
            tag_name = re.search(r"<([^ >]+)", tb)
            if tag_name:
                print(f"      {tag_name.group(1)}")

        # SummaryOfBusinessResults要素を探す
        sobr_pattern = re.compile(r"<[^>]*SummaryOfBusinessResults[^>]*>", re.IGNORECASE)
        sobr = sobr_pattern.findall(text)
        print(f"    SummaryOfBusinessResults要素: {len(sobr)}件")
        for s in sobr[:10]:
            tag_name = re.search(r"<([^ >]+)", s)
            if tag_name:
                print(f"      {tag_name.group(1)}")

        # jppfs_cor要素（日本基準の勘定科目）
        jppfs_pattern = re.compile(r"<jppfs_cor:(\w+)", re.IGNORECASE)
        jppfs = jppfs_pattern.findall(text)
        print(f"    jppfs_cor要素: {len(jppfs)}件")
        if jppfs:
            unique_jppfs = sorted(set(jppfs))
            print(f"    ユニーク: {len(unique_jppfs)}件")
            for j in unique_jppfs[:20]:
                print(f"      jppfs_cor:{j}")

        # jpigp(IFRS)要素
        jpigp_pattern = re.compile(r"<jpigp_cor:(\w+)", re.IGNORECASE)
        jpigp = jpigp_pattern.findall(text)
        print(f"    jpigp_cor要素: {len(jpigp)}件")

        # us-gaap名前空間
        usgaap_ns_pattern = re.compile(r"xmlns[^=]*=[\"'][^\"']*us-gaap[^\"']*[\"']", re.IGNORECASE)
        usgaap_ns = usgaap_ns_pattern.findall(text)
        print(f"    us-gaap名前空間宣言: {len(usgaap_ns)}件")
        for ns in usgaap_ns[:5]:
            print(f"      {ns}")

        # テキストブロックの中身サンプル
        # ConsolidatedStatementOfIncomeUSGAAPTextBlock の中身を見る
        income_tb = re.search(
            r"<jpcrp_cor:ConsolidatedStatementOfIncomeUSGAAPTextBlock[^>]*>(.*?)</jpcrp_cor:ConsolidatedStatementOfIncomeUSGAAPTextBlock>",
            text, re.DOTALL
        )
        if income_tb:
            content = income_tb.group(1)
            print(f"\n    --- ConsolidatedStatementOfIncomeUSGAAPTextBlock ---")
            print(f"    サイズ: {len(content):,} chars")
            # HTMLの中にtableがあるか
            tables = re.findall(r"<table[^>]*>", content, re.IGNORECASE)
            print(f"    <table>: {len(tables)}件")
            # td要素の数
            tds = re.findall(r"<td[^>]*>[^<]*</td>", content, re.IGNORECASE)
            print(f"    <td>: {len(tds)}件")
            # 最初の数行を表示
            clean = re.sub(r"<[^>]+>", " ", content)
            clean = re.sub(r"\s+", " ", clean).strip()
            print(f"    テキスト抜粋 (先頭500文字):")
            print(f"      {clean[:500]}")

    # iXBRLファイルの確認
    ixbrl_files = [n for n in zf.namelist() if "_ixbrl.htm" in n.lower() or n.endswith(".xhtml")]
    print(f"\n  iXBRL ファイル: {len(ixbrl_files)}件")
    for ix in ixbrl_files[:3]:
        data = zf.read(ix)
        print(f"    {ix} ({len(data):,} bytes)")

    # ========== 2. file_type=5 (CSV) ==========
    print("\n" + "=" * 70)
    print("  file_type=5 (CSV)")
    print("=" * 70)

    try:
        csv_bytes = download_document(doc_id, file_type="5")
        csv_zf = zipfile.ZipFile(BytesIO(csv_bytes))

        print(f"\n  ZIP サイズ: {len(csv_bytes):,} bytes")
        print(f"  ファイル数: {len(csv_zf.namelist())}")
        for name in sorted(csv_zf.namelist()):
            info = csv_zf.getinfo(name)
            print(f"    {name}  ({info.file_size:,} bytes)")

        # CSVの中身を全部見る
        for csv_name in csv_zf.namelist():
            if csv_name.endswith(".csv"):
                data = csv_zf.read(csv_name)
                # UTF-16 LE BOMの可能性
                try:
                    text = data.decode("utf-16-le")
                except Exception:
                    try:
                        text = data.decode("utf-8-sig")
                    except Exception:
                        text = data.decode("utf-8", errors="replace")

                lines = text.strip().split("\n")
                print(f"\n  --- {csv_name} ({len(lines)}行) ---")
                # ヘッダー
                if lines:
                    print(f"    ヘッダー: {lines[0][:200]}")
                # 全行表示（US-GAAPは行数少ないはず）
                for i, line in enumerate(lines[1:], 1):
                    print(f"    [{i:3d}] {line[:200]}")
                    if i > 50:
                        print(f"    ... 以降省略 (残り{len(lines)-51}行)")
                        break
    except Exception as e:
        print(f"  CSV取得エラー: {e}")

    print("\n完了")


if __name__ == "__main__":
    main()
