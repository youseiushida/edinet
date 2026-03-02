"""G-9. ordinance_code → タクソノミモジュール完全マッピング生成スクリプト

実行方法: uv run docs/QAs/scripts/G-9.mapping_table.py
前提: edinet パッケージがインストール済みであること
出力: form_code.py の全エントリに対するタクソノミモジュールのマッピング表
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from edinet.models.form_code import all_form_codes, FormCodeEntry


# ordinance_code → タクソノミモジュールのマッピング定義
# ※ EDINET API仕様書 3章 府令コード一覧に準拠
ORDINANCE_TAXONOMY_MAP: dict[str, dict[str, Any]] = {
    "010": {
        "label": "開示府令",
        "default_taxonomy": "jpcrp",
        "financial_taxonomy": ["jppfs", "jpigp"],
        "dei": "jpdei",
        "special_cases": {
            "esr": "jpcrp-esr",   # 臨時報告書
            "sbr": "jpcrp-sbr",   # 自己株券買付状況報告書
        },
    },
    "015": {
        "label": "内部統制府令",
        "default_taxonomy": "jpctl",
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {},
    },
    "020": {
        "label": "外国債等府令",
        "default_taxonomy": "unknown",  # タクソノミ概要説明書に独立分割単位の記載なし
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {},
    },
    "030": {
        "label": "特定有価証券府令",
        "default_taxonomy": "jpsps",
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {
            "esr": "jpsps-esr",
            "sbr": "jpsps-sbr",
        },
    },
    "040": {
        "label": "他社株買付府令",
        "default_taxonomy": "jptoo-*",
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {},
    },
    "050": {
        "label": "自社株買付府令",
        "default_taxonomy": "jptoi",
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {},
    },
    "060": {
        "label": "大量保有府令",
        "default_taxonomy": "jplvh",
        "financial_taxonomy": [],
        "dei": "jpdei",
        "special_cases": {},
    },
}

# doc_type_name のキーワードから特殊タクソノミを判定
ESR_KEYWORDS = ["臨時報告書"]
SBR_KEYWORDS = ["自己株券買付状況報告書"]

# jptoo-* のサブモジュール特定用
JPTOO_FORM_MAP: dict[str, str] = {
    "第二号様式": "jptoo-ton",    # 公開買付届出書
    "第三号様式": "jptoo-ton",    # 公開買付届出書（訂正）
    "第四号様式": "jptoo-pst",    # 意見表明報告書
    "第五号様式": "jptoo-wto",    # 公開買付撤回届出書
    "第六号様式": "jptoo-tor",    # 公開買付報告書
    "第七号様式": "jptoo-tor",    # 公開買付報告書（訂正）
    "第八号様式": "jptoo-toa",    # 対質問回答報告書
}


def predict_taxonomy(entry: FormCodeEntry) -> list[str]:
    """FormCodeEntry からタクソノミモジュールを予測する。

    Args:
        entry: 様式コードエントリ。

    Returns:
        予測されるタクソノミモジュール名のリスト。
    """
    ord_info = ORDINANCE_TAXONOMY_MAP.get(entry.ordinance_code)
    if ord_info is None:
        return ["unknown"]

    result: list[str] = []

    # 特殊ケース判定（臨時報告書、自己株券買付状況報告書）
    is_esr = any(kw in entry.doc_type_name for kw in ESR_KEYWORDS)
    is_sbr = any(kw in entry.doc_type_name for kw in SBR_KEYWORDS)

    special = ord_info.get("special_cases", {})
    assert isinstance(special, dict)

    if is_esr and "esr" in special:
        result.append(special["esr"])
    elif is_sbr and "sbr" in special:
        result.append(special["sbr"])
    else:
        default = ord_info["default_taxonomy"]
        assert isinstance(default, str)

        # jptoo-* の場合、様式番号で詳細特定
        if default == "jptoo-*":
            form_num = entry.form_number
            matched = None
            for pattern, module in JPTOO_FORM_MAP.items():
                if pattern in form_num:
                    matched = module
                    break
            result.append(matched or "jptoo-?")
        else:
            result.append(default)

        # 財務諸表タクソノミ
        fin = ord_info.get("financial_taxonomy", [])
        if fin:
            assert isinstance(fin, list)
            result.append("/".join(fin))

    # DEI
    dei = ord_info.get("dei", "")
    if dei:
        assert isinstance(dei, str)
        result.append(dei)

    return result


def main() -> None:
    """メイン処理。"""
    print("G-9: ordinance_code → タクソノミモジュール マッピング生成")
    print("=" * 70)

    entries = all_form_codes()
    print(f"全様式コードエントリ数: {len(entries)}")

    # ── Step 1: ordinance_code ごとの統計 ──
    print(f"\n[Step 1] ordinance_code ごとの統計")
    print("-" * 70)

    ord_counter: Counter[str] = Counter()
    for e in entries:
        ord_counter[e.ordinance_code] += 1

    for ord_code, count in sorted(ord_counter.items()):
        info = ORDINANCE_TAXONOMY_MAP.get(ord_code, {})
        label = info.get("label", "不明") if info else "不明"
        print(f"  {ord_code} ({label}): {count} エントリ")

    # ── Step 2: 全エントリのマッピング ──
    print(f"\n[Step 2] 全エントリのタクソノミマッピング")
    print("-" * 70)

    # ordinance_code ごとにグループ化
    groups: dict[str, list[FormCodeEntry]] = defaultdict(list)
    for e in entries:
        groups[e.ordinance_code].append(e)

    for ord_code in sorted(groups.keys()):
        group = groups[ord_code]
        info = ORDINANCE_TAXONOMY_MAP.get(ord_code, {})
        label = info.get("label", "不明") if info else "不明"
        print(f"\n  === ordinance_code={ord_code} ({label}) ===")

        for e in group[:10]:  # 最初の10件を表示
            taxonomy = predict_taxonomy(e)
            print(
                f"    {e.form_code} {e.form_number:12s} "
                f"{e.doc_type_name:30s} → {', '.join(taxonomy)}"
            )
        if len(group) > 10:
            print(f"    ... (他 {len(group) - 10} エントリ)")

    # ── Step 3: タクソノミモジュール別の集計 ──
    print(f"\n\n[Step 3] タクソノミモジュール別の集計")
    print("-" * 70)

    taxonomy_counter: Counter[str] = Counter()
    for e in entries:
        taxonomy = predict_taxonomy(e)
        primary = taxonomy[0] if taxonomy else "unknown"
        taxonomy_counter[primary] += 1

    for tax, count in taxonomy_counter.most_common():
        print(f"  {tax:20s}: {count} エントリ")

    # ── Step 4: 特殊ケースの検証 ──
    print(f"\n\n[Step 4] 特殊ケースの検証")
    print("-" * 70)

    # 臨時報告書
    esr_entries = [e for e in entries if any(kw in e.doc_type_name for kw in ESR_KEYWORDS)]
    print(f"\n  臨時報告書: {len(esr_entries)} エントリ")
    for e in esr_entries:
        taxonomy = predict_taxonomy(e)
        print(f"    {e.ordinance_code}/{e.form_code} {e.doc_type_name} → {', '.join(taxonomy)}")

    # 自己株券買付状況報告書
    sbr_entries = [e for e in entries if any(kw in e.doc_type_name for kw in SBR_KEYWORDS)]
    print(f"\n  自己株券買付状況報告書: {len(sbr_entries)} エントリ")
    for e in sbr_entries:
        taxonomy = predict_taxonomy(e)
        print(f"    {e.ordinance_code}/{e.form_code} {e.doc_type_name} → {', '.join(taxonomy)}")

    # jptoo-* 詳細
    jptoo_entries = [e for e in entries if e.ordinance_code == "040"]
    print(f"\n  他社株買付 (ord=040): {len(jptoo_entries)} エントリ")
    for e in jptoo_entries:
        taxonomy = predict_taxonomy(e)
        print(
            f"    {e.form_code} {e.form_number:12s} "
            f"{e.doc_type_name:30s} → {', '.join(taxonomy)}"
        )

    # ── Step 5: unknown の検出 ──
    print(f"\n\n[Step 5] マッピング不明エントリの検出")
    print("-" * 70)

    unknowns = [
        e for e in entries
        if "unknown" in predict_taxonomy(e) or "jptoo-?" in predict_taxonomy(e)
    ]
    if unknowns:
        print(f"  マッピング不明: {len(unknowns)} エントリ")
        for e in unknowns:
            taxonomy = predict_taxonomy(e)
            print(
                f"    {e.ordinance_code}/{e.form_code} {e.form_number} "
                f"{e.doc_type_name} → {', '.join(taxonomy)}"
            )
    else:
        print("  全エントリのマッピングが成功しました。")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  全エントリ数: {len(entries)}")
    print(f"  ordinance_code 種別数: {len(ord_counter)}")
    print(f"  タクソノミモジュール種別数: {len(taxonomy_counter)}")
    print(f"  マッピング不明: {len(unknowns)}")


if __name__ == "__main__":
    main()
