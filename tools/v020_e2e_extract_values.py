"""v0.2.0 E2E 検証: extract_values() が全業種・全会計基準で動作するか確認。

各業種×会計基準の代表企業の有報を EDINET API から取得し、
SummaryOfBusinessResults の CK マッピングが正しく機能するか検証する。

使い方:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/v020_e2e_extract_values.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from edinet import configure  # noqa: E402
from edinet.models.filing import Filing  # noqa: E402
from edinet.financial.extract import extract_values  # noqa: E402
from edinet.financial.standards.canonical_keys import CK  # noqa: E402

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("EDINET_API_KEY", "")
TAXONOMY_ROOT = os.environ.get("EDINET_TAXONOMY_ROOT", "")

if not API_KEY:
    print("EDINET_API_KEY が未設定です")
    sys.exit(1)

configure(api_key=API_KEY, taxonomy_path=TAXONOMY_ROOT or None)

# 抽出する CK キー（全業種共通の主要指標）
TARGET_KEYS = [
    CK.REVENUE,
    CK.OPERATING_INCOME,
    CK.ORDINARY_INCOME,
    CK.NET_INCOME,
    CK.NET_INCOME_PARENT,
    CK.COMPREHENSIVE_INCOME,
    CK.TOTAL_ASSETS,
    CK.NET_ASSETS,
    CK.OPERATING_CF,
    CK.INVESTING_CF,
    CK.FINANCING_CF,
    CK.EPS,
    CK.EQUITY_RATIO,
    CK.ROE,
]

# ---------------------------------------------------------------------------
# テスト対象（doc_id 直接指定）
# ---------------------------------------------------------------------------


@dataclass
class Target:
    """テスト対象。"""

    name: str
    doc_id: str
    sector: str
    expected_standard: str


TARGETS: list[Target] = [
    # 一般事業会社
    Target("任天堂", "S100W7N4", "一般(JGAAP)", "jgaap"),
    Target("日立製作所", "S100W773", "一般(IFRS)", "ifrs"),
    Target("キヤノン", "S100VHZZ", "一般(USGAAP)", "usgaap"),
    Target("ソニーG", "S100W19Q", "一般(IFRS)", "ifrs"),
    # 銀行業
    Target("三菱UFJ FG", "S100W4FB", "銀行(JGAAP)", "jgaap"),
    # 建設業
    Target("鹿島建設", "S100W0FJ", "建設(JGAAP)", "jgaap"),
    # 鉄道業
    Target("JR東日本", "S100VZTK", "鉄道(JGAAP)", "jgaap"),
    # IFRS 大手
    Target("ソフトバンクG", "S100W4HN", "一般(IFRS)", "ifrs"),
]


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _fmt(v: Decimal | str | None) -> str:
    """値を表示用にフォーマット。"""
    if v is None:
        return "—"
    if isinstance(v, Decimal):
        if abs(v) >= 1_000_000_000:
            return f"{v / 1_000_000_000:,.1f}B"
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:,.0f}M"
        return f"{v:,.2f}"
    return str(v)


# ---------------------------------------------------------------------------
# 検証ロジック
# ---------------------------------------------------------------------------


@dataclass
class Result:
    """1企業の検証結果。"""

    target: Target
    success: bool
    detected_standard: str = "?"
    values: dict[str, Decimal | str | None] = field(default_factory=dict)
    error: str | None = None
    period_end: str | None = None


async def _test_one(target: Target, sem: asyncio.Semaphore) -> Result:
    """1企業を非同期で検証する。"""
    async with sem:
        try:
            # Filing を doc_id から構築してダウンロード
            filing = Filing.model_construct(
                seq_number=0,
                doc_id=target.doc_id,
                doc_type_code="120",
                ordinance_code=None,
                form_code=None,
                edinet_code=None,
                sec_code=None,
                jcn=None,
                filer_name=target.name,
                fund_code=None,
                submit_date_time=None,
                period_start=None,
                period_end=None,
                doc_description=None,
                issuer_edinet_code=None,
                subject_edinet_code=None,
                subsidiary_edinet_code=None,
                current_report_reason=None,
                parent_doc_id=None,
                ope_date_time=None,
                withdrawal_status="0",
                doc_info_edit_status="0",
                disclosure_status="0",
                has_xbrl=True,
                has_pdf=True,
                has_attachment=False,
                has_english=False,
                has_csv=False,
                legal_status="0",
            )

            # 非同期で XBRL パース
            stmts = await filing.axbrl()

            std_str = "?"
            if stmts.detected_standard is not None:
                std_str = str(stmts.detected_standard.standard)

            # extract_values で SummaryOfBusinessResults から抽出
            result = extract_values(stmts, TARGET_KEYS)

            values: dict[str, Decimal | str | None] = {}
            for k, ev in result.items():
                values[k] = ev.value if ev is not None else None

            period_end = None
            pc = stmts.period_classification
            if pc.current_instant is not None:
                period_end = str(pc.current_instant.instant)

            return Result(
                target=target,
                success=True,
                detected_standard=std_str,
                values=values,
                period_end=period_end,
            )

        except Exception as e:
            return Result(
                target=target,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )


async def main() -> None:
    """全企業を並列で検証。"""
    print("=" * 80)
    print("v0.2.0 E2E: extract_values() × 業種 × 会計基準")
    print("=" * 80)

    t0 = time.monotonic()
    sem = asyncio.Semaphore(3)  # 同時3接続

    tasks = [_test_one(t, sem) for t in TARGETS]
    results: list[Result] = await asyncio.gather(*tasks)

    elapsed = time.monotonic() - t0

    # 結果表示
    print()
    for r in results:
        mark = "✓" if r.success else "✗"
        print(f"{mark} {r.target.name:<14s} [{r.target.sector:<14s}]  "
              f"基準={r.detected_standard}")

        if r.error:
            print(f"    ERROR: {r.error}")
            continue

        hits = sum(1 for v in r.values.values() if v is not None)
        total = len(r.values)
        print(f"    期末={r.period_end}  抽出={hits}/{total}")

        for key in TARGET_KEYS:
            v = r.values.get(str(key))
            mark2 = "●" if v is not None else "○"
            print(f"      {mark2} {str(key):<28s}: {_fmt(v)}")
        print()

    # 集計
    print("-" * 80)
    ok = sum(1 for r in results if r.success)
    print(f"合計: {ok}/{len(results)} 成功  (所要時間: {elapsed:.1f}s)")

    # 全社で取れなかった CK
    missing_count: dict[str, int] = {}
    success_count = sum(1 for r in results if r.success)
    for r in results:
        if not r.success:
            continue
        for key in TARGET_KEYS:
            k = str(key)
            if r.values.get(k) is None:
                missing_count[k] = missing_count.get(k, 0) + 1

    if missing_count:
        print()
        print(f"取得できなかった CK（{success_count}社中）:")
        for k, c in sorted(missing_count.items(), key=lambda x: -x[1]):
            print(f"  {k}: {c}社で未取得")

    # ファイル保存
    out = os.path.join(os.path.dirname(__file__), "v020_e2e_results.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# v0.2.0 E2E extract_values() 検証結果\n\n")
        f.write(f"所要時間: {elapsed:.1f}s\n\n")
        f.write("| 企業 | セクター | 基準 | 抽出数 |\n")
        f.write("|------|---------|------|--------|\n")
        for r in results:
            h = sum(1 for v in r.values.values() if v is not None) if r.success else 0
            t = len(r.values) if r.success else 0
            st = r.detected_standard if r.success else r.error or "?"
            f.write(f"| {r.target.name} | {r.target.sector} | {st} | {h}/{t} |\n")
        f.write("\n## 詳細\n\n")
        for r in results:
            f.write(f"### {r.target.name} ({r.target.sector})\n\n")
            if r.error:
                f.write(f"**ERROR**: {r.error}\n\n")
                continue
            f.write("| CK | 値 |\n|---|---|\n")
            for key in TARGET_KEYS:
                v = r.values.get(str(key))
                f.write(f"| {key} | {_fmt(v)} |\n")
            f.write("\n")
    print(f"\n詳細: {out}")


if __name__ == "__main__":
    asyncio.run(main())
