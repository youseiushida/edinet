"""C-12. Formula/Assertion Linkbase の有無調査

実行方法: uv run docs/QAs/scripts/C-12.formula_search.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: formula/assertion 関連の namespace・arcrole・ファイル名の検索結果
"""

import os
from pathlib import Path

TAXONOMY_ROOT = Path(
    os.environ.get("EDINET_TAXONOMY_ROOT", r"C:\Users\nezow\Downloads\ALL_20251101")
)

FORMULA_PATTERNS = [
    "formula",
    "assertion",
    "variable",
    "xbrl.org/2008/formula",
    "xbrl.org/2008/assertion",
    "xbrl.org/2008/variable",
    "xbrl.org/2008/consistency-assertion",
    "xbrl.org/2008/existence-assertion",
    "xbrl.org/2008/value-assertion",
]


def search_file_names():
    """ファイル名に formula/assertion/variable を含むファイルを検索する。

    Returns:
        list[str]: マッチしたファイルパスのリスト。
    """
    print("=" * 60)
    print("1. ファイル名検索（formula/assertion/variable）")
    print("=" * 60)
    found = []
    for root, dirs, files in os.walk(TAXONOMY_ROOT):
        for f in files:
            fl = f.lower()
            if any(p in fl for p in ["formula", "assertion", "variable"]):
                found.append(os.path.join(root, f))
    if found:
        for f in found:
            print(f"  {f}")
    else:
        print("  該当ファイルなし")
    return found


def search_file_contents():
    """XMLファイル内に formula/assertion 関連の namespace を検索する。

    Returns:
        dict[str, list[str]]: ファイルパスをキー、マッチしたパターンのリストを値とする辞書。
    """
    print("\n" + "=" * 60)
    print("2. ファイル内容検索（formula/assertion 関連 namespace）")
    print("=" * 60)
    found = {}
    count = 0
    for root, dirs, files in os.walk(TAXONOMY_ROOT):
        for f in files:
            if not f.endswith((".xml", ".xsd")):
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    content = fh.read()
                    for pattern in FORMULA_PATTERNS:
                        if pattern.lower() in content.lower():
                            if filepath not in found:
                                found[filepath] = []
                            found[filepath].append(pattern)
            except Exception:
                pass
            count += 1

    print(f"  検索対象ファイル数: {count}")
    if found:
        for fp, patterns in found.items():
            print(f"  {fp}")
            for p in set(patterns):
                print(f"    マッチ: {p}")
    else:
        print("  該当なし — formula/assertion 関連の namespace は存在しない")
    return found


def main():
    """メインエントリポイント。タクソノミ内の Formula/Assertion 関連ファイルを検索する。"""
    print(f"タクソノミルート: {TAXONOMY_ROOT}")
    if not TAXONOMY_ROOT.exists():
        print(f"エラー: {TAXONOMY_ROOT} が存在しません")
        return

    name_results = search_file_names()
    content_results = search_file_contents()

    print("\n" + "=" * 60)
    print("結論")
    print("=" * 60)
    if not name_results and not content_results:
        print(
            "  EDINET タクソノミには Formula/Assertion Linkbase は含まれていない。"
        )
        print("  計算リンクベース（summation-item）のみが計算検証に使用される。")
    else:
        print(f"  ファイル名マッチ: {len(name_results)} 件")
        print(f"  内容マッチ: {len(content_results)} 件")


if __name__ == "__main__":
    main()
