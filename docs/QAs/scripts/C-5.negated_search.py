"""C-5. negatedLabel 使用頻度調査

実行方法: uv run docs/QAs/scripts/C-5.negated_search.py
前提: EDINET_TAXONOMY_ROOT 環境変数（デフォルト: C:\\Users\\nezow\\Downloads\\ALL_20251101）
出力: プレゼンテーションリンクベースでの negatedLabel 使用件数、negativeLabel ロール分析
"""

import os
import re
from pathlib import Path
from collections import Counter


_default = r"C:\Users\nezow\Downloads\ALL_20251101"
_wsl = "/mnt/c/Users/nezow/Downloads/ALL_20251101"
_env = os.environ.get("EDINET_TAXONOMY_ROOT", "")
if _env:
    TAXONOMY_ROOT = Path(_env)
elif Path(_wsl).exists():
    TAXONOMY_ROOT = Path(_wsl)
else:
    TAXONOMY_ROOT = Path(_default)


def main():
    """メイン処理。negatedLabel と negativeLabel の使用状況を調査する。"""
    taxonomy_dir = TAXONOMY_ROOT / "taxonomy"

    print("=" * 80)
    print("1. negatedLabel / negativeLabel の preferredLabel 使用頻度調査")
    print("=" * 80)

    total_arcs = 0
    negated_count = 0
    negated_files = []
    negated_concepts = []
    preferred_labels = Counter()

    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if "_pre_" in f and f.endswith(".xml"):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()

                    arcs = re.findall(r"<link:presentationArc[^>]*>", content)
                    total_arcs += len(arcs)

                    for arc in arcs:
                        pref = re.search(r'preferredLabel="([^"]+)"', arc)
                        if pref:
                            preferred_labels[pref.group(1)] += 1
                            if "negat" in pref.group(1).lower():
                                negated_count += 1
                                to_match = re.search(r'xlink:to="([^"]+)"', arc)
                                if to_match:
                                    negated_concepts.append(to_match.group(1))
                                rel = os.path.relpath(filepath, taxonomy_dir)
                                negated_files.append(rel)
                except Exception:
                    pass

    # pre ファイル名パターンに一致しないファイルも含めて再検索
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if f.endswith("_pre.xml") and "_pre_" not in f:
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()

                    arcs = re.findall(r"<link:presentationArc[^>]*>", content)
                    total_arcs += len(arcs)

                    for arc in arcs:
                        pref = re.search(r'preferredLabel="([^"]+)"', arc)
                        if pref:
                            preferred_labels[pref.group(1)] += 1
                            if "negat" in pref.group(1).lower():
                                negated_count += 1
                                to_match = re.search(r'xlink:to="([^"]+)"', arc)
                                if to_match:
                                    negated_concepts.append(to_match.group(1))
                                rel = os.path.relpath(filepath, taxonomy_dir)
                                negated_files.append(rel)
                except Exception:
                    pass

    print(f"\n  総 presentationArc 数: {total_arcs}")
    print(f"  preferredLabel 設定あり: {sum(preferred_labels.values())}")
    print(f"  negatedLabel/negativeLabel 使用: {negated_count}")

    print(f"\n  preferredLabel 値の分布:")
    for label, count in preferred_labels.most_common():
        print(f"    {label}: {count}")

    if negated_count > 0:
        print(f"\n  negatedLabel/negativeLabel が使用されているファイル:")
        for f in sorted(set(negated_files)):
            print(f"    {f}")
        print(f"\n  negatedLabel/negativeLabel の対象 concept (先頭20件):")
        for c in sorted(set(negated_concepts))[:20]:
            print(f"    {c}")
        if len(set(negated_concepts)) > 20:
            print(f"    ... 他 {len(set(negated_concepts)) - 20} 件")
    else:
        print(
            "\n  → EDINET タクソノミの標準プレゼンテーションリンクベースでは"
            " negatedLabel/negativeLabel は使用されていない"
        )

    # negativeLabel ロールのラベル存在確認
    print("\n" + "=" * 80)
    print("2. negativeLabel ロールのラベル存在確認（_lab.xml）")
    print("=" * 80)

    neg_label_count = 0
    neg_label_files = []
    for root, dirs, files in os.walk(taxonomy_dir):
        for f in files:
            if f.endswith("_lab.xml"):
                filepath = os.path.join(root, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    count = content.count("negativeLabel")
                    if count > 0:
                        rel = os.path.relpath(filepath, taxonomy_dir)
                        print(f"  {rel}: negativeLabel 出現 {count} 回")
                        neg_label_count += count
                        neg_label_files.append(rel)
                except Exception:
                    pass

    if neg_label_count == 0:
        # negatedLabel も検索
        for root, dirs, files in os.walk(taxonomy_dir):
            for f in files:
                if f.endswith("_lab.xml"):
                    filepath = os.path.join(root, f)
                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            content = fh.read()
                        count = content.count("negatedLabel")
                        if count > 0:
                            rel = os.path.relpath(filepath, taxonomy_dir)
                            print(f"  {rel}: negatedLabel 出現 {count} 回")
                            neg_label_count += count
                    except Exception:
                        pass

    print(f"\n  negativeLabel/negatedLabel 合計出現回数: {neg_label_count}")

    # negativeLabel ロールの具体的なラベル内容をサンプル抽出
    print("\n" + "=" * 80)
    print("3. negativeLabel ロールのラベル内容サンプル")
    print("=" * 80)

    if neg_label_files:
        filepath = os.path.join(
            taxonomy_dir,
            neg_label_files[0].replace("\\", os.sep).replace("/", os.sep),
        )
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                content = fh.read()
            # negativeLabel を含むラベル要素を抽出
            labels = re.findall(
                r'<link:label[^>]*negativeLabel[^>]*>([^<]*)</link:label>', content
            )
            print(f"  ファイル: {neg_label_files[0]}")
            print(f"  negativeLabel ロールのラベル例（先頭10件）:")
            for lbl in labels[:10]:
                print(f"    「{lbl.strip()}」")
            print(f"  合計: {len(labels)} 件")
        except Exception as e:
            print(f"  エラー: {e}")


if __name__ == "__main__":
    main()
