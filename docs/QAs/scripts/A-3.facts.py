"""A-3 調査スクリプト: サンプル .xbrl の Fact を網羅的に解析する。

decimals 分布、nil Fact、データ型、空文字、負の値、重複チェック（A-7 流用）等を
分析する。A-8 の id/xml:lang 属性も併せてチェックする。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from lxml import etree

SAMPLE_BASE = Path(__file__).resolve().parents[2] / "仕様書" / "2026" / "サンプルインスタンス" / "サンプルインスタンス" / "ダウンロードデータ"

JGAAP_XBRL = SAMPLE_BASE / "02_開示府令-有価証券報告書" / "S002XXXX" / "XBRL" / "PublicDoc" / "jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xbrl"

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_LINK = "http://www.xbrl.org/2003/linkbase"

# 非 Fact 要素のローカル名（除外対象）
NON_FACT_TAGS = {
    "xbrl", "context", "entity", "identifier", "segment", "period",
    "instant", "startDate", "endDate", "forever", "scenario",
    "unit", "measure", "divide", "unitNumerator", "unitDenominator",
    "schemaRef", "linkbaseRef", "roleRef", "arcroleRef",
    "footnoteLink", "footnote", "loc", "footnoteArc",
}


def is_fact_element(elem: etree._Element) -> bool:
    """要素がFact要素かどうかを判定する。

    Args:
        elem: XML要素。

    Returns:
        Fact要素であればTrue。
    """
    tag = elem.tag
    if not isinstance(tag, str) or "}" not in tag:
        return False

    ns, local = tag.rsplit("}", 1)
    ns = ns.lstrip("{")

    # XBRL Infrastructure 名前空間の要素はFactではない
    if ns in (NS_XBRLI, NS_LINK):
        return False
    if local in NON_FACT_TAGS:
        return False

    # contextRef があればFact
    return elem.get("contextRef") is not None


def analyze_facts(path: Path) -> None:
    """XBRLファイルのFact構造を分析・表示する。

    Args:
        path: XBRLファイルのパス。
    """
    tree = etree.parse(str(path))
    root = tree.getroot()

    facts = [elem for elem in root if is_fact_element(elem)]
    print(f"Fact 総数: {len(facts)}")

    # 分類
    numeric_facts = []
    text_facts = []
    nil_facts = []
    negative_facts = []
    empty_facts = []
    facts_with_id = []
    facts_with_lang = []
    decimals_counter: Counter = Counter()
    unit_counter: Counter = Counter()
    namespace_counter: Counter = Counter()
    duplicate_check: defaultdict = defaultdict(list)

    for fact in facts:
        tag = fact.tag
        ns, local = tag.rsplit("}", 1)
        ns = ns.lstrip("{")
        namespace_counter[ns] += 1

        context_ref = fact.get("contextRef", "")
        unit_ref = fact.get("unitRef")
        decimals = fact.get("decimals")
        is_nil = fact.get(f"{{{NS_XSI}}}nil") == "true"
        fact_id = fact.get("id")
        xml_lang = fact.get("{http://www.w3.org/XML/1998/namespace}lang")
        value = fact.text or ""

        # nil チェック
        if is_nil:
            nil_facts.append((local, context_ref, unit_ref))

        # id チェック
        if fact_id:
            facts_with_id.append((local, fact_id))

        # xml:lang チェック
        if xml_lang:
            facts_with_lang.append((local, xml_lang))

        # 数値 vs テキスト
        if unit_ref is not None:
            numeric_facts.append(fact)
            if decimals:
                decimals_counter[decimals] += 1
            if unit_ref:
                unit_counter[unit_ref] += 1
            if not is_nil and value.startswith("-"):
                negative_facts.append((local, value, context_ref))
        else:
            text_facts.append(fact)

        # 空文字チェック
        if not is_nil and value == "" and len(fact) == 0:
            empty_facts.append((local, context_ref))

        # 重複チェック（A-7）
        dup_key = (tag, context_ref, unit_ref or "")
        duplicate_check[dup_key].append(value if not is_nil else "<nil>")

    # 結果表示
    print("\n--- Fact 分類 ---")
    print(f"  数値 Fact: {len(numeric_facts)}")
    print(f"  テキスト Fact: {len(text_facts)}")
    print(f"  nil Fact: {len(nil_facts)}")

    print("\n--- decimals 分布 ---")
    for dec, count in decimals_counter.most_common():
        print(f"  decimals={dec:5s}: {count} 件")

    print("\n--- unitRef 分布 ---")
    for unit, count in unit_counter.most_common():
        print(f"  unitRef={unit:15s}: {count} 件")

    print("\n--- 名前空間分布 ---")
    for ns, count in namespace_counter.most_common():
        # 短縮表示
        short = ns.split("/")[-1] if "/" in ns else ns
        print(f"  {short:40s}: {count} 件")

    print("\n--- 負の値 ---")
    print(f"  負の値を持つ Fact: {len(negative_facts)} 件")
    for local, val, ctx in negative_facts[:5]:
        print(f"    {local}: {val} (context={ctx})")
    if len(negative_facts) > 5:
        print(f"    ... 他 {len(negative_facts) - 5} 件")

    print("\n--- 空文字 Fact ---")
    print(f"  空文字 Fact: {len(empty_facts)} 件")
    for local, ctx in empty_facts[:5]:
        print(f"    {local} (context={ctx})")

    print("\n--- id 属性 ---")
    print(f"  id 属性付き Fact: {len(facts_with_id)} 件")
    for local, fid in facts_with_id[:5]:
        print(f"    {local}: id={fid}")
    if len(facts_with_id) > 5:
        print(f"    ... 他 {len(facts_with_id) - 5} 件")

    print("\n--- xml:lang 属性 ---")
    print(f"  xml:lang 属性付き Fact: {len(facts_with_lang)} 件")
    for local, lang in facts_with_lang[:5]:
        print(f"    {local}: xml:lang={lang}")

    print("\n--- nil Fact の例 (先頭 5 件) ---")
    for local, ctx, unit in nil_facts[:5]:
        print(f"  {local}: context={ctx}, unit={unit}")

    # 重複チェック（A-7）
    print("\n--- 重複 Fact チェック (A-7) ---")
    consistent_dups = 0
    inconsistent_dups = 0
    for key, values in duplicate_check.items():
        if len(values) > 1:
            unique_values = set(values)
            if len(unique_values) == 1:
                consistent_dups += 1
            else:
                inconsistent_dups += 1
                _, local_name = key[0].rsplit("}", 1)
                print(f"  [INCONSISTENT] {local_name} context={key[1]} unit={key[2]}: {values}")

    print(f"  consistent duplicate: {consistent_dups} 件")
    print(f"  inconsistent duplicate: {inconsistent_dups} 件")

    # precision 属性の検索
    precision_count = sum(1 for f in facts if f.get("precision") is not None)
    print("\n--- precision 属性 ---")
    print(f"  precision 属性付き Fact: {precision_count} 件")


def main() -> None:
    """メイン処理。"""
    print(f"ファイル: {JGAAP_XBRL.name}")
    if not JGAAP_XBRL.exists():
        print(f"[ERROR] ファイルが存在しません: {JGAAP_XBRL}")
        return
    analyze_facts(JGAAP_XBRL)


if __name__ == "__main__":
    main()
