"""P-1. 実際の ZIP の中身 — ZIP 構造調査スクリプト

実行方法: uv run docs/QAs/scripts/P-1.tree.py
前提: EDINET_API_KEY 環境変数が必要
出力: 各ターゲットの ZIP ツリー（ファイル名・拡張子・サイズ）、拡張子サマリ、
      iXBRL/XBRL 存在フラグ
"""

from __future__ import annotations

import sys
import os

# スクリプトのディレクトリを sys.path に追加
sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    find_amendment_filing,
    find_filings,
    find_quarterly_filing,
    find_small_company_filing,
    get_zip,
    print_filing_info,
    print_zip_tree,
)

# ================================================================
# v0.1.0 対象のターゲット定義
# ================================================================
TARGETS_V010 = {
    "P-1a": {
        "label": "トヨタ (E02144) — J-GAAP、製造業、巨大企業",
        "edinet_code": "E02144",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
    "P-1b": {
        "label": "小規模企業 — ファイル数が少ないケース",
        "edinet_code": None,  # 自動選定
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-06-30",
    },
    "P-1c": {
        "label": "四半期報告書 — 通期との構造差異の確認",
        "edinet_code": None,  # 自動選定
        "doc_type": "140",
        "start": "2024-08-01",
        "end": "2024-11-30",
    },
    "P-1d": {
        "label": "三菱UFJ (E03606) — 銀行業、業種別差異の確認",
        "edinet_code": "E03606",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
    "P-1e": {
        "label": "訂正報告書 (130) — 訂正報告書の構造確認",
        "edinet_code": None,  # 自動選定
        "doc_type": "130",
        "start": "2025-06-01",
        "end": "2025-09-30",
    },
}


def process_target(target_id: str, config: dict) -> None:
    """1 つのターゲットを処理する。

    Args:
        target_id: ターゲット ID（例: "P-1a"）。
        config: ターゲット設定辞書。
    """
    print(f"\n{'#' * 70}")
    print(f"=== {target_id}: {config['label']} ===")
    print(f"{'#' * 70}")

    # Filing を検索
    filing = None

    if target_id == "P-1b":
        print("\n[検索] 小規模企業を自動選定中...")
        filing = find_small_company_filing(
            doc_type=config["doc_type"],
            start=config["start"],
            end=config["end"],
        )
    elif target_id == "P-1c":
        print("\n[検索] 四半期報告書を検索中...")
        filing = find_quarterly_filing(
            start=config["start"],
            end=config["end"],
        )
    elif target_id == "P-1e":
        print("\n[検索] 訂正報告書を検索中...")
        filing = find_amendment_filing(
            start=config["start"],
            end=config["end"],
        )
    else:
        print(f"\n[検索] edinet_code={config['edinet_code']}, "
              f"doc_type={config['doc_type']} ...")
        filings = find_filings(
            edinet_code=config["edinet_code"],
            doc_type=config["doc_type"],
            start=config["start"],
            end=config["end"],
            has_xbrl=True,
            max_results=1,
        )
        filing = filings[0] if filings else None

    if filing is None:
        print(f"  ERROR: {target_id} に合致する Filing が見つかりません")
        return

    print_filing_info(filing, label=f"{target_id} 選定結果")

    # ZIP ダウンロードとツリー表示
    zip_bytes = get_zip(filing.doc_id)
    print_zip_tree(zip_bytes, title=f"{target_id} ZIP ツリー")


def main() -> None:
    """メイン処理。"""
    print("P-1: 実際の ZIP の中身 — ZIP 構造調査")
    print("=" * 70)

    for target_id, config in TARGETS_V010.items():
        try:
            process_target(target_id, config)
        except Exception as exc:
            print(f"\n  ERROR ({target_id}): {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 70}")
    print("P-1 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
