"""ファンド系 XBRL のパース失敗の根本原因を特定する。

axbrl() の完全な例外チェーンを表示する。

使い方:
    EDINET_API_KEY=your_api_key_here uv run python tools/_inspect_fund_parse.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import edinet
from edinet.taxonomy_install import install_taxonomy

# りそなAM 1件 + 野村AM 1件
TEST_DOC_IDS = ["S100VMJV", "S100VP7L"]

REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "fund_parse_error.txt"


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY", "your_api_key_here")
    edinet.configure(api_key=api_key)

    tax_info = install_taxonomy(year=2025)
    print(f"タクソノミ: {tax_info.path}")

    results: list[str] = []

    for doc_id in TEST_DOC_IDS:
        print(f"\n{'='*70}")
        print(f"doc_id: {doc_id}")

        # Filing 取得（複数日を検索）
        filing = None
        for d in ["2025-06-25", "2025-06-26", "2025-06-27"]:
            filings = await edinet.adocuments(date=d)
            for f in filings:
                if f.doc_id == doc_id:
                    filing = f
                    break
            if filing:
                break

        if filing is None:
            msg = f"{doc_id}: Filing が見つかりません"
            print(msg)
            results.append(msg)
            continue

        print(f"  提出者: {filing.filer_name}")
        print(f"  書類種別: {filing.doc_type_code}")
        print(f"  has_xbrl: {filing.has_xbrl}")

        # axbrl() でフルトレースバック取得
        try:
            stmts = await filing.axbrl(taxonomy_path=str(tax_info.path))
            msg = f"{doc_id}: 成功！ items={len(stmts._items)}"
            print(f"  {msg}")
            results.append(msg)
        except Exception as e:
            tb = traceback.format_exc()
            # __cause__ チェーンも表示
            cause_chain = []
            exc = e
            while exc is not None:
                cause_chain.append(f"  {type(exc).__name__}: {exc}")
                exc = exc.__cause__

            print(f"  失敗!")
            for c in cause_chain:
                print(c)
            print(f"\n  フルトレースバック:")
            print(tb)

            results.append(
                f"{doc_id}: 失敗\n"
                f"例外チェーン:\n" + "\n".join(cause_chain) + "\n\n"
                f"トレースバック:\n{tb}"
            )

    await edinet.aclose()

    # レポート保存
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("ファンド系 XBRL パースエラー詳細\n")
        f.write("=" * 70 + "\n\n")
        for r in results:
            f.write(r + "\n\n")
    print(f"\nレポート保存: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
