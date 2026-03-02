"""E-1c. SS 定義リンクベースの arcrole 検証スクリプト

実行方法: uv run docs/QAs/scripts/E-1c.ss_arcroles.py
前提: EDINET_TAXONOMY_ROOT 環境変数（ALL_20251101 のパス）が必要
出力: _cm_ (科目一覧ツリー) と _ac_ 等 (詳細ツリー) の SS 定義リンクベースにおける
      arcrole の違いを確認する。E-1c.a.md [F10] の検証用。
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

TAXONOMY_ROOT = Path(os.environ["EDINET_TAXONOMY_ROOT"])

NS = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
}

BASE_DIR = TAXONOMY_ROOT / "taxonomy" / "jppfs" / "2025-11-01"


def extract_arcroles(file_path: Path) -> Counter[str]:
    """定義リンクベースファイルから全 definitionArc の arcrole を集計する。

    Args:
        file_path: 定義リンクベースファイルのパス。

    Returns:
        arcrole 値ごとの出現回数。
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    counter: Counter[str] = Counter()
    for arc in root.iter(f"{{{NS['link']}}}definitionArc"):
        arcrole = arc.get(f"{{{NS['xlink']}}}arcrole", "")
        counter[arcrole] += 1

    return counter


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("E-1c. SS 定義リンクベース arcrole 検証")
    print("=" * 80)

    # 業種ごとの _def_ss ファイルを検索
    for industry in ["cns", "cai"]:
        r_dir = BASE_DIR / "r" / industry
        if not r_dir.exists():
            continue

        def_ss_files = sorted(r_dir.glob("*_def_ss*"))
        print(f"\n{'=' * 70}")
        print(f"【{industry} 業種 — SS 定義リンクベース一覧】")
        print(f"{'=' * 70}")

        if not def_ss_files:
            print("  SS 定義リンクベースなし")
            continue

        for f in def_ss_files:
            print(f"\n  ファイル: {f.name}")

            # _cm_ か _ac_/_an_ 等かを判別
            if "_cm_" in f.name:
                file_type = "科目一覧ツリー (cm)"
            elif "_ac_" in f.name:
                file_type = "詳細ツリー (ac: 連結通期)"
            elif "_an_" in f.name:
                file_type = "詳細ツリー (an: 個別通期)"
            elif "_sc" in f.name:
                file_type = "詳細ツリー (sc: 中間連結)"
            elif "_sn" in f.name:
                file_type = "詳細ツリー (sn: 中間個別)"
            else:
                file_type = "不明"

            print(f"  種別: {file_type}")

            arcroles = extract_arcroles(f)
            print(f"  definitionArc 総数: {sum(arcroles.values())}")
            print("  arcrole 値:")
            for arcrole, count in arcroles.most_common():
                # URL の末尾部分だけ表示
                short = arcrole.rsplit("/", 1)[-1] if "/" in arcrole else arcrole
                print(f"    {short:<25s}: {count:>4d} 件  ({arcrole})")

    print(f"\n{'=' * 70}")
    print("【結論】")
    print("=" * 70)
    print("""
  _cm_ (科目一覧ツリー):
    → arcrole は general-special のみ
    → 概念間の汎化-特化関係を定義（ハイパーキューブ構造ではない）

  _ac_/_an_/_sc-t2_/_sn-t2_ (詳細ツリー):
    → XBRL Dimensions の arcrole 5種を使用:
      all, hypercube-dimension, dimension-domain, dimension-default, domain-member
    → ハイパーキューブ・ディメンション・メンバーの正式な次元構造を定義

  cns 業種には _cm_ の SS 定義のみ存在し、詳細ツリーの SS 定義は存在しない。
  cai 業種には _cm_ + 詳細ツリー 4 件の SS 定義が存在する。
""")


if __name__ == "__main__":
    main()
