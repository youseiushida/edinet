"""E-6. 提出者独自の拡張科目 — 複数企業の拡張要素分析スクリプト

実行方法: uv run docs/QAs/scripts/E-6.ext_elements.py
前提: EDINET_API_KEY 環境変数が必要
出力: 各社の拡張要素数、ラベル、role URI、wider-narrower arcrole の有無
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_public_doc_members,
    get_zip,
    print_filing_info,
)

# P-1 の5ターゲット
TARGETS = {
    "toyota": {
        "label": "トヨタ (E02144) — IFRS",
        "edinet_code": "E02144",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
    "belluna": {
        "label": "ベルーナ (E03229) — J-GAAP",
        "edinet_code": "E03229",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-06-30",
    },
    "taiyo": {
        "label": "太洋テクノレックス (E02097) — 四半期",
        "edinet_code": "E02097",
        "doc_type": "140",
        "start": "2024-08-01",
        "end": "2024-11-30",
    },
    "mufg": {
        "label": "三菱UFJ (E03606) — 銀行業",
        "edinet_code": "E03606",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
    "shikigaku": {
        "label": "識学 (E34634) — 訂正報告書",
        "edinet_code": "E34634",
        "doc_type": "130",
        "start": "2025-06-01",
        "end": "2025-09-30",
    },
}

# XML 名前空間
NS = {
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "label": "http://www.xbrl.org/2003/linkbase",
    "gen": "http://xbrl.org/2008/generic",
}


def decode_xml(raw: bytes) -> str:
    """XML バイト列をテキストにデコードする。

    Args:
        raw: デコード対象のバイト列。

    Returns:
        デコードされたテキスト。
    """
    for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode("utf-8", errors="replace")


def extract_extension_elements(zip_bytes: bytes) -> list[dict]:
    """XSD から拡張要素定義を抽出する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        拡張要素のリスト（name, type, periodType, balance, abstract, nillable）。
    """
    xsd_members = find_public_doc_members(zip_bytes, ".xsd")
    elements = []

    for member in xsd_members:
        raw = extract_member(zip_bytes, member)
        text = decode_xml(raw)

        # targetNamespace を取得
        tns_match = re.search(r'targetNamespace="([^"]*)"', text)
        tns = tns_match.group(1) if tns_match else ""

        # element 定義を抽出（正規表現で柔軟に対応）
        for m in re.finditer(
            r'<(?:xs:|xsd:)?element\b([^>]*?)(?:/>|>)',
            text,
            re.IGNORECASE,
        ):
            attrs_str = m.group(1)
            attrs = {}
            for attr_m in re.finditer(
                r'(\w+(?::\w+)?)\s*=\s*"([^"]*)"',
                attrs_str,
            ):
                attrs[attr_m.group(1)] = attr_m.group(2)

            if "name" in attrs:
                elements.append({
                    "name": attrs.get("name", ""),
                    "type": attrs.get("type", ""),
                    "periodType": attrs.get("xbrli:periodType", ""),
                    "balance": attrs.get("xbrli:balance", ""),
                    "abstract": attrs.get("abstract", "false"),
                    "nillable": attrs.get("nillable", ""),
                    "substitutionGroup": attrs.get("substitutionGroup", ""),
                    "namespace": tns,
                    "source_file": member,
                })

    return elements


def extract_labels(zip_bytes: bytes) -> dict[str, dict[str, str]]:
    """_lab.xml から拡張要素のラベルを取得する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        要素名 -> {role: label_text} の辞書。
    """
    labels: dict[str, dict[str, str]] = {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        lab_files = [
            i.filename for i in zf.infolist()
            if not i.is_dir()
            and "/publicdoc/" in f"/{i.filename.lower()}"
            and i.filename.lower().endswith("_lab.xml")
        ]

        for lab_file in lab_files:
            raw = zf.read(lab_file)
            text = decode_xml(raw)

            # loc 要素の xlink:label → concept名 のマッピング
            loc_map: dict[str, str] = {}
            for m in re.finditer(
                r'<link:loc\b[^>]*xlink:label="([^"]*)"[^>]*'
                r'xlink:href="[^"]*#([^"]*)"',
                text,
            ):
                loc_map[m.group(1)] = m.group(2)
            # 属性の順序が逆のケースも対応
            for m in re.finditer(
                r'<link:loc\b[^>]*xlink:href="[^"]*#([^"]*)"[^>]*'
                r'xlink:label="([^"]*)"',
                text,
            ):
                loc_map[m.group(2)] = m.group(1)

            # labelArc の from → to マッピング
            arc_map: dict[str, str] = {}
            for m in re.finditer(
                r'<link:labelArc\b[^>]*xlink:from="([^"]*)"[^>]*'
                r'xlink:to="([^"]*)"',
                text,
            ):
                arc_map[m.group(1)] = m.group(2)
            for m in re.finditer(
                r'<link:labelArc\b[^>]*xlink:to="([^"]*)"[^>]*'
                r'xlink:from="([^"]*)"',
                text,
            ):
                arc_map[m.group(2)] = m.group(1)

            # label 要素の xlink:label → テキスト
            label_texts: dict[str, str] = {}
            for m in re.finditer(
                r'<link:label\b[^>]*xlink:label="([^"]*)"[^>]*'
                r'xlink:role="([^"]*)"[^>]*>([^<]*)</link:label>',
                text,
            ):
                label_texts[m.group(1)] = m.group(3).strip()

            # マッピングを統合
            for loc_label, concept in loc_map.items():
                if loc_label in arc_map:
                    to_label = arc_map[loc_label]
                    if to_label in label_texts:
                        if concept not in labels:
                            labels[concept] = {}
                        labels[concept]["standard"] = label_texts[to_label]

    return labels


def extract_presentation_roles(zip_bytes: bytes) -> dict[str, list[str]]:
    """_pre.xml から拡張要素の role URI を取得する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        要素名 -> role URI リストの辞書。
    """
    roles: dict[str, list[str]] = {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        pre_files = [
            i.filename for i in zf.infolist()
            if not i.is_dir()
            and "/publicdoc/" in f"/{i.filename.lower()}"
            and i.filename.lower().endswith("_pre.xml")
        ]

        for pre_file in pre_files:
            raw = zf.read(pre_file)
            text = decode_xml(raw)

            # presentationLink の role
            # roleごとのブロックを分割してパース
            blocks = re.split(
                r'<link:presentationLink\b',
                text,
            )
            for block in blocks[1:]:
                role_m = re.search(r'xlink:role="([^"]*)"', block)
                if not role_m:
                    continue
                role = role_m.group(1)

                # loc 参照から concept 名を取得
                for loc_m in re.finditer(
                    r'xlink:href="[^"]*#([^"]*)"',
                    block,
                ):
                    concept = loc_m.group(1)
                    if concept not in roles:
                        roles[concept] = []
                    if role not in roles[concept]:
                        roles[concept].append(role)

    return roles


def check_wider_narrower(zip_bytes: bytes) -> list[dict]:
    """_def.xml から wider-narrower arcrole の有無を確認する。

    Args:
        zip_bytes: ZIP バイト列。

    Returns:
        wider-narrower 関係のリスト。
    """
    results = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        def_files = [
            i.filename for i in zf.infolist()
            if not i.is_dir()
            and "/publicdoc/" in f"/{i.filename.lower()}"
            and i.filename.lower().endswith("_def.xml")
        ]

        for def_file in def_files:
            raw = zf.read(def_file)
            text = decode_xml(raw)

            # wider-narrower arcrole の検索
            if "wider-narrower" in text.lower():
                for m in re.finditer(
                    r'arcrole="([^"]*wider-narrower[^"]*)"',
                    text,
                    re.IGNORECASE,
                ):
                    results.append({
                        "file": def_file,
                        "arcrole": m.group(1),
                    })

            # arcrole 一覧を収集
            arcroles = set()
            for m in re.finditer(
                r'xlink:arcrole="([^"]*)"',
                text,
            ):
                arcroles.add(m.group(1))

            if arcroles:
                print(f"    _def.xml arcroles ({def_file}):")
                for ar in sorted(arcroles):
                    print(f"      {ar}")

    return results


def analyze_target(
    target_id: str, config: dict,
) -> dict | None:
    """1 つのターゲットを分析する。

    Args:
        target_id: ターゲット ID。
        config: ターゲット設定辞書。

    Returns:
        分析結果の辞書。
    """
    print(f"\n{'#' * 70}")
    print(f"=== {target_id}: {config['label']} ===")
    print(f"{'#' * 70}")

    filings = find_filings(
        edinet_code=config["edinet_code"],
        doc_type=config["doc_type"],
        start=config["start"],
        end=config["end"],
        has_xbrl=True,
        max_results=1,
    )

    if not filings:
        print(f"  ERROR: Filing が見つかりません")
        return None

    filing = filings[0]
    print_filing_info(filing, label=f"{target_id} 選定結果")

    zip_bytes = get_zip(filing.doc_id)

    # E-6.1/E-6.2: 拡張要素の抽出
    print(f"\n--- E-6.1: 拡張要素定義 ---")
    elements = extract_extension_elements(zip_bytes)
    non_abstract = [e for e in elements if e["abstract"] != "true"]
    abstract_els = [e for e in elements if e["abstract"] == "true"]

    print(f"  拡張要素数: {len(elements)} (うち abstract {len(abstract_els)})")

    # 型別分類
    type_counts: dict[str, int] = {}
    for e in elements:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"\n  型別分類:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:<50s}: {c}")

    # 要素一覧（先頭20件）
    print(f"\n  拡張要素一覧 (先頭20件):")
    for e in elements[:20]:
        balance = f" balance={e['balance']}" if e["balance"] else ""
        abstract = " [abstract]" if e["abstract"] == "true" else ""
        print(f"    {e['name']:<60s} {e['type']:<40s} "
              f"period={e['periodType']}{balance}{abstract}")
    if len(elements) > 20:
        print(f"    ... (残り {len(elements) - 20} 要素)")

    # E-6.2: ラベル取得
    print(f"\n--- E-6.2: 拡張要素のラベル ---")
    labels = extract_labels(zip_bytes)
    ext_names = {e["name"] for e in elements}
    labeled_ext = {n: labels[n] for n in ext_names if n in labels}
    print(f"  ラベル取得済み: {len(labeled_ext)} / {len(ext_names)}")

    for name, lbl in list(labeled_ext.items())[:10]:
        label_text = lbl.get("standard", "（ラベルなし）")
        print(f"    {name}: {label_text}")
    if len(labeled_ext) > 10:
        print(f"    ... (残り {len(labeled_ext) - 10} 要素)")

    # E-6.3: role URI 分析
    print(f"\n--- E-6.3: 拡張要素の role URI ---")
    pre_roles = extract_presentation_roles(zip_bytes)
    ext_roles = {n: pre_roles[n] for n in ext_names if n in pre_roles}

    # role の分類
    role_summary: dict[str, int] = {}
    for _, rlist in ext_roles.items():
        for r in rlist:
            # role URI の末尾部分で分類
            short = r.rsplit("/", 1)[-1] if "/" in r else r
            role_summary[short] = role_summary.get(short, 0) + 1

    print(f"  role URI に出現する拡張要素数: {len(ext_roles)}")
    if role_summary:
        print(f"  role 別カウント:")
        for role, count in sorted(
            role_summary.items(), key=lambda x: -x[1],
        )[:15]:
            print(f"    {role}: {count}")

    # E-6.6: wider-narrower arcrole
    print(f"\n--- E-6.6: wider-narrower arcrole ---")
    wn_results = check_wider_narrower(zip_bytes)
    if wn_results:
        print(f"  wider-narrower: YES ({len(wn_results)} 件)")
        for wn in wn_results:
            print(f"    {wn['file']}: {wn['arcrole']}")
    else:
        print(f"  wider-narrower: NO")

    return {
        "target_id": target_id,
        "filer_name": filing.filer_name,
        "total_elements": len(elements),
        "non_abstract": len(non_abstract),
        "abstract": len(abstract_els),
        "type_counts": type_counts,
        "labeled_count": len(labeled_ext),
        "has_wider_narrower": len(wn_results) > 0,
    }


def main() -> None:
    """メイン処理。"""
    print("E-6: 提出者独自の拡張科目 — 拡張要素分析")
    print("=" * 70)

    results: list[dict] = []

    for target_id, config in TARGETS.items():
        try:
            result = analyze_target(target_id, config)
            if result:
                results.append(result)
        except Exception as exc:
            print(f"\n  ERROR ({target_id}): {type(exc).__name__}: {exc}")

    # サマリテーブル
    print(f"\n{'#' * 70}")
    print("=== サマリテーブル ===")
    print(f"{'#' * 70}")
    print(f"\n{'企業':<20s} {'要素数':>6s} {'非abs':>6s} {'abs':>6s} "
          f"{'ラベル':>6s} {'W-N':>5s}")
    print("-" * 55)

    for r in results:
        print(f"{r['filer_name'][:18]:<20s} {r['total_elements']:>6d} "
              f"{r['non_abstract']:>6d} {r['abstract']:>6d} "
              f"{r['labeled_count']:>6d} "
              f"{'Y' if r['has_wider_narrower'] else 'N':>5s}")

    print(f"\n{'=' * 70}")
    print("E-6 調査完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
