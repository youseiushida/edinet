"""C-3. EdinetcodeDlInfo.csv の業種分布調査スクリプト

実行方法: uv run docs/QAs/scripts/C-3.industry_csv.py
前提: data/source/EdinetcodeDlInfo.csv が存在すること
出力: 「提出者業種」列の値の集計、タクソノミ業種コードとの対応、企業例
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "source" / "EdinetcodeDlInfo.csv"

# 設定規約書 図表 1-4-6 に基づく業種略号と正式名称の対応
TAXONOMY_INDUSTRY_CODES: dict[str, str] = {
    "cai": "一般商工業",
    "cns": "建設業",
    "bk1": "銀行・信託業",
    "bk2": "銀行・信託業(特定取引勘定設置銀行)",
    "cna": "建設保証業",
    "sec": "第一種金融商品取引業",
    "in1": "生命保険業",
    "in2": "損害保険業",
    "rwy": "鉄道事業",
    "wat": "海運事業",
    "hwy": "高速道路事業",
    "elc": "電気通信事業",
    "ele": "電気事業",
    "gas": "ガス事業",
    "liq": "資産流動化業",
    "ivt": "投資運用業",
    "inv": "投資業",
    "spf": "特定金融業",
    "med": "社会医療法人",
    "edu": "学校法人",
    "cmd": "商品先物取引業",
    "lea": "リース事業",
    "fnd": "投資信託受益証券",
}


def read_csv() -> list[dict[str, str]]:
    """EdinetcodeDlInfo.csv を読み込む。

    Returns:
        CSV の全行をリストとして返す。
    """
    # Shift_JIS でエンコードされている
    rows: list[dict[str, str]] = []
    with open(CSV_PATH, encoding="cp932", newline="") as f:
        # 先頭行がヘッダーでない場合がある（1行目がメタ情報）
        lines = f.readlines()

    # 先頭の BOM やメタ行をスキップ
    header_idx = 0
    for i, line in enumerate(lines):
        if "ＥＤＩＮＥＴコード" in line or "EDINETコード" in line:
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        rows.append(row)

    return rows


def find_industry_column(rows: list[dict[str, str]]) -> str:
    """業種関連のカラム名を特定する。

    Args:
        rows: CSV の行リスト。

    Returns:
        業種カラム名。
    """
    if not rows:
        return ""

    sample = rows[0]
    for key in sample:
        if "業種" in key or "提出者業種" in key:
            return key
    return ""


def main() -> None:
    """メイン処理。"""
    print("=" * 80)
    print("C-3. 業種カテゴリコード調査 — EdinetcodeDlInfo.csv 分析")
    print("=" * 80)

    print(f"\nCSV パス: {CSV_PATH}")
    rows = read_csv()
    print(f"総行数: {len(rows)}")

    if not rows:
        print("ERROR: CSV データが読み込めませんでした")
        return

    # カラム名一覧
    print(f"\nカラム名一覧:")
    for i, key in enumerate(rows[0].keys()):
        print(f"  [{i}] {key}")

    # 業種カラムを特定
    industry_col = find_industry_column(rows)
    print(f"\n業種カラム: '{industry_col}'")

    if not industry_col:
        print("WARNING: 業種カラムが見つかりませんでした。全カラム名から推定を試みます。")
        return

    # 業種値の集計
    industry_counter = Counter(row[industry_col] for row in rows if row.get(industry_col))
    print(f"\n--- 提出者業種の値一覧 ({len(industry_counter)} 種類) ---")
    for industry, count in industry_counter.most_common():
        print(f"  {industry:<30s}: {count:>5d} 件")

    # タクソノミ業種コードとの対応関係調査
    print("\n" + "=" * 80)
    print("【タクソノミ業種コード vs CSV 提出者業種 対応表】")
    print("=" * 80)

    # CSV 業種名 → タクソノミコードのマッピングを推定
    csv_to_taxonomy: dict[str, str] = {}
    for code, tax_name in TAXONOMY_INDUSTRY_CODES.items():
        for csv_name in industry_counter:
            # 部分一致で対応を推定
            if tax_name in csv_name or csv_name in tax_name:
                csv_to_taxonomy[csv_name] = code
                break

    print(f"\n| タクソノミコード | タクソノミ名称 | CSV業種名 | CSV件数 |")
    print(f"|---|---|---|---|")
    matched_csv_names: set[str] = set()
    for code in sorted(TAXONOMY_INDUSTRY_CODES.keys()):
        tax_name = TAXONOMY_INDUSTRY_CODES[code]
        csv_match = ""
        csv_count = 0
        for csv_name, t_code in csv_to_taxonomy.items():
            if t_code == code:
                csv_match = csv_name
                csv_count = industry_counter.get(csv_name, 0)
                matched_csv_names.add(csv_name)
                break
        print(f"| {code} | {tax_name} | {csv_match} | {csv_count} |")

    # マッチしなかった CSV 業種
    unmatched = set(industry_counter.keys()) - matched_csv_names
    if unmatched:
        print(f"\n--- CSV にあるがタクソノミコードに対応しない業種 ---")
        for name in sorted(unmatched):
            print(f"  {name}: {industry_counter[name]} 件")

    # 各業種の企業例を抽出
    print("\n" + "=" * 80)
    print("【業種別 企業例（各業種から最大3社）】")
    print("=" * 80)

    # EDINET コードと提出者名のカラムを特定
    name_col = ""
    edinet_col = ""
    sec_code_col = ""
    for key in rows[0]:
        if "提出者名" in key or "会社名" in key:
            name_col = key
        if "ＥＤＩＮＥＴコード" in key or "EDINETコード" in key:
            edinet_col = key
        if "証券コード" in key:
            sec_code_col = key

    industry_examples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        ind = row.get(industry_col, "")
        name = row.get(name_col, "")
        sec_code = row.get(sec_code_col, "")
        edinet_code = row.get(edinet_col, "")
        if ind and name and len(industry_examples[ind]) < 3:
            # 上場企業（証券コードあり）を優先
            if sec_code and sec_code.strip():
                industry_examples[ind].insert(0, f"{name} ({edinet_code}, {sec_code})")
            elif len(industry_examples[ind]) < 3:
                industry_examples[ind].append(f"{name} ({edinet_code})")

    for ind in sorted(industry_examples.keys()):
        examples = industry_examples[ind][:3]
        print(f"\n  {ind}:")
        for ex in examples:
            print(f"    - {ex}")

    # 「一般商工業」(cai) = 一般事業会社の確認
    print("\n" + "=" * 80)
    print("【cai（一般商工業）vs cns（建設業）の確認】")
    print("=" * 80)
    for csv_name, count in industry_counter.most_common(5):
        tax_code = csv_to_taxonomy.get(csv_name, "不明")
        print(f"  {csv_name}: {count} 件 → タクソノミコード: {tax_code}")

    print("\n結論: cns = 建設業（construction）であり、一般事業会社コードではない")
    print("       cai = 一般商工業 が一般事業会社に対応するコード")


if __name__ == "__main__":
    main()
