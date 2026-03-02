"""E-1d. 直接法キャッシュフロー計算書の採用企業スキャンスクリプト（非同期版）

実行方法: uv run docs/QAs/scripts/E-1d.cf_direct_scan.py
前提: EDINET_API_KEY 環境変数が必要
出力: 有価証券報告書の XBRL インスタンスをスキャンし、
      直接法 CF（role URI に -direct を含む）を採用している企業を検出する。
      300社以上をスキャンして直接法の実態を確認する。
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import zipfile
from dataclasses import dataclass, field

import edinet
from edinet.api.download import adownload_document
from edinet.models.filing import Filing
import edinet.public_api as public_api

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

MAX_CONCURRENT = 5


@dataclass
class CFScanResult:
    """1社分の CF 方式スキャン結果。"""

    filer_name: str
    doc_id: str
    sec_code: str
    direct_roles: list[str] = field(default_factory=list)
    indirect_roles: list[str] = field(default_factory=list)
    has_direct: bool = False
    has_indirect: bool = False


def scan_cf_roles(xbrl_bytes: bytes) -> tuple[list[str], list[str]]:
    """XBRL インスタンスから CF 関連の roleRef を抽出し、直接法/間接法を判定する。

    Args:
        xbrl_bytes: XBRL ファイルのバイト列。

    Returns:
        (direct_roles, indirect_roles) のタプル。
    """
    try:
        content = xbrl_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = xbrl_bytes.decode("cp932", errors="replace")

    direct_roles: list[str] = []
    indirect_roles: list[str] = []

    # roleRef の roleURI 属性を検索
    for m in re.finditer(r'roleURI="([^"]*)"', content):
        uri = m.group(1)
        uri_lower = uri.lower()
        if "cashflow" in uri_lower or "cf" in uri_lower.split("/")[-1]:
            if "-direct" in uri_lower:
                direct_roles.append(uri)
            elif "-indirect" in uri_lower:
                indirect_roles.append(uri)

    # roleRef がない場合、context の scenario/segment や
    # Fact の concept 名でも補助判定
    if not direct_roles and not indirect_roles:
        # concept ベース判定: 間接法特有の IncomeBeforeIncomeTaxes
        if "IncomeBeforeIncomeTaxes" in content and "OpeCF" in content:
            indirect_roles.append("(concept-based: indirect)")
        elif "OperatingIncomeOpeCF" in content:
            direct_roles.append("(concept-based: direct)")

    return direct_roles, indirect_roles


async def scan_filing(
    filing: Filing, sem: asyncio.Semaphore
) -> CFScanResult | None:
    """1件の Filing をスキャンする。

    Args:
        filing: 対象 Filing。
        sem: 同時接続制限用セマフォ。

    Returns:
        スキャン結果。失敗時は None。
    """
    async with sem:
        try:
            zip_bytes = await adownload_document(filing.doc_id, file_type="1")
        except Exception:
            return None

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xbrl_members = [
            m
            for m in zf.namelist()
            if m.lower().endswith(".xbrl") and "publicdoc" in m.lower()
        ]
        if not xbrl_members:
            return None
        xbrl_bytes = zf.read(xbrl_members[0])

    direct_roles, indirect_roles = scan_cf_roles(xbrl_bytes)

    result = CFScanResult(
        filer_name=filing.filer_name or filing.doc_id,
        doc_id=filing.doc_id,
        sec_code=filing.sec_code or "----",
        direct_roles=direct_roles,
        indirect_roles=indirect_roles,
        has_direct=len(direct_roles) > 0,
        has_indirect=len(indirect_roles) > 0,
    )

    # 直接法が見つかったら即座に報告
    if result.has_direct:
        print(f"  *** 直接法検出! {filing.filer_name} ({filing.sec_code}) ***")
        for r in direct_roles:
            print(f"      role: {r}")

    return result


async def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1d. 直接法 CF 採用企業スキャン（非同期版）")
    print("=" * 80)

    # 有報を広範囲に検索（2025年4月〜9月: 決算集中期間）
    print("\n有価証券報告書 (doc_type=120) を検索中...")
    filings = await public_api.adocuments(
        doc_type="120", start="2025-04-01", end="2025-09-30"
    )
    filings = [
        f
        for f in filings
        if f.has_xbrl and f.edinet_code and f.sec_code and f.filer_name
    ]
    print(f"  XBRL 付き有報: {len(filings)} 件")

    if not filings:
        print("ERROR: 該当 Filing なし")
        return

    # 全件スキャン（上限 300 社）
    target = filings[:300]
    print(f"  スキャン対象: {len(target)} 社\n")

    print("スキャン中...")
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [scan_filing(f, sem) for f in target]

    # 進捗表示付き
    done = 0
    results: list[CFScanResult] = []
    for coro in asyncio.as_completed(tasks):
        result = await coro
        done += 1
        if result is not None:
            results.append(result)
        if done % 50 == 0 or done == len(tasks):
            print(f"  ... {done}/{len(tasks)} 完了 ({len(results)} 成功)")

    # 集計
    print(f"\n{'=' * 80}")
    print(f"【集計結果】 スキャン成功: {len(results)} 社")
    print("=" * 80)

    direct_companies = [r for r in results if r.has_direct]
    indirect_companies = [r for r in results if r.has_indirect]
    neither = [r for r in results if not r.has_direct and not r.has_indirect]

    print(f"\n  間接法: {len(indirect_companies)} 社 "
          f"({len(indirect_companies) / len(results) * 100:.1f}%)")
    print(f"  直接法: {len(direct_companies)} 社 "
          f"({len(direct_companies) / len(results) * 100:.1f}%)")
    print(f"  判定不能: {len(neither)} 社")

    if direct_companies:
        print(f"\n--- 直接法採用企業一覧 ---")
        for r in direct_companies:
            print(f"  {r.filer_name} ({r.sec_code}) doc_id={r.doc_id}")
            for role in r.direct_roles:
                print(f"    role: {role}")
    else:
        print(f"\n  直接法採用企業は {len(results)} 社中 0 社でした。")
        print("  → 日本の上場企業はほぼ全社が間接法を採用していると結論できます。")

    # 両方持つ企業がいたら報告
    both = [r for r in results if r.has_direct and r.has_indirect]
    if both:
        print(f"\n--- 直接法・間接法の両方を持つ企業 ---")
        for r in both:
            print(f"  {r.filer_name} ({r.sec_code})")


if __name__ == "__main__":
    asyncio.run(main())
