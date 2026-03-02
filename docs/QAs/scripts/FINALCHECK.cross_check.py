"""FINALCHECK. クロスチェック検証スクリプト

実行方法: uv run docs/QAs/scripts/FINALCHECK.cross_check.py
前提: docs/QAs/*.a.md と docs/仕様書/2026 配下の実ファイルが存在すること
出力: FINALCHECK.q.md の 9 項目に対する OK / NEEDS_FIX 判定と根拠
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


QA_ROOT = Path("docs/QAs")
SCRIPTS_ROOT = QA_ROOT / "scripts"
SAMPLE_ROOT = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ"
)
TAXONOMY_ROOT = Path("docs/仕様書/2026/タクソノミ")

EDINET_TAXONOMY_PREFIX = "http://disclosure.edinet-fsa.go.jp/taxonomy/"


@dataclass
class CheckResult:
    """単一チェックの判定結果。"""

    name: str
    status: str  # OK | NEEDS_FIX | WARN
    detail: str
    evidence: list[str]


def read_text(path: Path) -> str:
    """UTF-8 でテキストファイルを読み込む。"""
    return path.read_text(encoding="utf-8")


def find_sample_dir(prefix: str) -> Path:
    """サンプルディレクトリ番号から対象ディレクトリを返す。"""
    matches = sorted(SAMPLE_ROOT.glob(f"{prefix}_*"))
    if not matches:
        raise FileNotFoundError(f"sample dir not found: {prefix}_*")
    return matches[0]


def first_public_file(sample_dir: Path, suffix: str) -> Path:
    """PublicDoc 配下の最初の指定拡張子ファイルを返す。"""
    matches = sorted(sample_dir.rglob(f"PublicDoc/*{suffix}"))
    if not matches:
        raise FileNotFoundError(f"PublicDoc/*{suffix} not found in {sample_dir}")
    return matches[0]


def classify(ok: bool, detail_ok: str, detail_ng: str, evidence: list[str]) -> CheckResult:
    """真偽から CheckResult を生成する。"""
    return CheckResult(
        name="",
        status="OK" if ok else "NEEDS_FIX",
        detail=detail_ok if ok else detail_ng,
        evidence=evidence,
    )


def check_1_namespace() -> CheckResult:
    """P-2 名前空間宣言 ↔ A-1 一致判定。"""
    p2 = read_text(QA_ROOT / "P-2.a.md")
    a1 = read_text(QA_ROOT / "A-1.a.md")

    sample03 = find_sample_dir("03")
    header03 = sample03 / (
        "S003XXXX/XBRL/PublicDoc/"
        "0000000_header_jpcrp030000-asr-001_X99002-000_2026-03-31_01_2026-06-12_ixbrl.htm"
    )
    htxt = read_text(header03)

    # 名前空間宣言としての列挙有無を確認する（単なる本文言及は除外）
    required_decl = {
        "iso4217": "xmlns:iso4217=",
        "jpigp_cor": "xmlns:jpigp_cor=",
    }
    missing_in_p2 = [k for k, marker in required_decl.items() if marker not in p2]
    targets = tuple(required_decl.keys())
    present_in_a1 = all(t in a1 for t in targets)
    present_in_header = all(f"xmlns:{t}" in htxt for t in targets)

    ok = not missing_in_p2 and present_in_a1 and present_in_header
    res = classify(
        ok,
        "P-2 と A-1 の名前空間は一致。",
        "P-2 の名前空間列挙に不足があり、A-1/実ファイルと不一致。",
        [
            f"P-2 missing: {missing_in_p2}" if missing_in_p2 else "P-2 missing: none",
            f"A-1 has targets: {present_in_a1}",
            f"sample03 header has targets: {present_in_header}",
            str(header03),
        ],
    )
    res.name = "1) P-2 名前空間 ↔ A-1 名前空間"
    return res


def check_2_context_structure() -> CheckResult:
    """P-2 Context 構造 ↔ A-2 一致判定。"""
    p2 = read_text(QA_ROOT / "P-2.a.md")
    a2 = read_text(QA_ROOT / "A-2.a.md")

    sample03 = find_sample_dir("03")
    xbrl03 = first_public_file(sample03, ".xbrl")
    xtxt = read_text(xbrl03)

    scenario_count = len(re.findall(r"<xbrli:scenario>", xtxt))
    segment_count = len(re.findall(r"<xbrli:segment>", xtxt))
    explicit_count = len(re.findall(r"xbrldi:explicitMember", xtxt))

    doc_claims_ok = (
        "scenario" in a2
        and "segment は使用しない" in a2
        and "xbrldi:explicitMember" in a2
        and "Context 定義数: 278" in p2
        and "278" in a2
    )
    data_ok = scenario_count > 0 and segment_count == 0 and explicit_count > 0
    ok = doc_claims_ok and data_ok

    res = classify(
        ok,
        "Context 構造は一致（scenario 使用、segment 不使用、explicitMember 使用）。",
        "Context 構造に不一致（doc記述または実ファイルが整合しない）。",
        [
            f"scenario_count={scenario_count}",
            f"segment_count={segment_count}",
            f"explicitMember_count={explicit_count}",
            f"doc_claims_ok={doc_claims_ok}",
            str(xbrl03),
        ],
    )
    res.name = "2) P-2 Context ↔ A-2 Context"
    return res


def check_3_schemaref() -> CheckResult:
    """P-2 schemaRef ↔ H-1 一致判定。"""
    p2 = read_text(QA_ROOT / "P-2.a.md")
    h1 = read_text(QA_ROOT / "H-1.a.md")

    sample03 = find_sample_dir("03")
    xbrl03 = first_public_file(sample03, ".xbrl")
    xtxt = read_text(xbrl03)
    m = re.search(r"<link:schemaRef[^>]*xlink:href=\"([^\"]+)\"", xtxt)
    href = m.group(1) if m else ""
    is_relative = bool(href and not re.match(r"^(?:https?://|/)", href))

    docs_ok = "相対パス" in p2 and "相対パス" in h1
    ok = docs_ok and is_relative

    res = classify(
        ok,
        "schemaRef は P-2/H-1/実ファイルで相対パス一致。",
        "schemaRef の相対/絶対判定が不一致。",
        [
            f"schemaRef href={href}",
            f"is_relative={is_relative}",
            f"docs_ok={docs_ok}",
            str(xbrl03),
        ],
    )
    res.name = "3) P-2 schemaRef ↔ H-1 schemaRef"
    return res


def check_4_import_mapping() -> CheckResult:
    """P-3 import URL ↔ H-1b URL→ローカル変換整合判定。"""
    p3 = read_text(QA_ROOT / "P-3.a.md")
    h1b = read_text(QA_ROOT / "H-1b.a.md")

    sample03 = find_sample_dir("03")
    xsd03 = first_public_file(sample03, ".xsd")
    xtxt = read_text(xsd03)
    urls = re.findall(r"schemaLocation=\"([^\"]+)\"", xtxt)
    edinet_urls = [u for u in urls if u.startswith(EDINET_TAXONOMY_PREFIX)]

    missing_local: list[str] = []
    for url in edinet_urls:
        rel = url[len(EDINET_TAXONOMY_PREFIX) :]
        local = TAXONOMY_ROOT / "taxonomy" / rel
        if not local.exists():
            missing_local.append(str(local))

    # 文言一致ではなく、双方が「taxonomy URL をローカルへ変換可能」と述べているかを緩めに判定
    docs_ok = (
        "/taxonomy/" in p3
        and "URL→ローカルパス" in h1b
        and "http://disclosure.edinet-fsa.go.jp/taxonomy/" in h1b
    )
    ok = docs_ok and not missing_local and len(edinet_urls) > 0

    res = classify(
        ok,
        "import URL と URL→ローカル変換ルールは整合。",
        "import URL と URL→ローカル変換ルールに不整合。",
        [
            f"edinet_urls={len(edinet_urls)}",
            f"missing_local={len(missing_local)}",
            f"docs_ok={docs_ok}",
            str(xsd03),
        ],
    )
    res.name = "4) P-3 import URL ↔ H-1b 変換ルール"
    return res


def check_5_ixbrl_adoption() -> CheckResult:
    """P-1 拡張子 ↔ K-2 iXBRL 採用状況判定。"""
    p1 = read_text(QA_ROOT / "P-1.a.md")
    k2 = read_text(QA_ROOT / "K-2.a.md")

    sample02 = find_sample_dir("02")
    files = list(sample02.rglob("*"))
    xbrl_count = sum(1 for p in files if p.is_file() and p.suffix.lower() == ".xbrl")
    htm_count = sum(1 for p in files if p.is_file() and p.suffix.lower() == ".htm")

    docs_ok = (
        ".xbrl" in p1
        and ".htm" in p1
        and "iXBRL" in k2
        and ".xbrl" in k2
        and ".htm" in k2
    )
    data_ok = xbrl_count > 0 and htm_count > 0
    ok = docs_ok and data_ok

    res = classify(
        ok,
        "P-1 と K-2 は iXBRL + 自動生成 .xbrl の同梱で一致。",
        "P-1 と K-2 の拡張子/採用状況に不一致。",
        [
            f"xbrl_count={xbrl_count}",
            f"htm_count={htm_count}",
            f"docs_ok={docs_ok}",
            str(sample02),
        ],
    )
    res.name = "5) P-1 拡張子 ↔ K-2 iXBRL 採用"
    return res


def check_6_concept_attrs() -> CheckResult:
    """P-6 concept 定義 ↔ C-9 属性リスト判定。"""
    p6 = read_text(QA_ROOT / "P-6.a.md")
    c9 = read_text(QA_ROOT / "C-9.a.md")

    xsd = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd"
    xtxt = read_text(xsd)
    groups = sorted(set(re.findall(r"substitutionGroup=\"([^\"]+)\"", xtxt)))

    p6_claims_single = "全要素共通" in p6 and "substitutionGroup" in p6
    c9_claims_multi = all(
        token in c9
        for token in ("xbrli:item", "iod:identifierItem", "xbrldt:hypercubeItem", "xbrldt:dimensionItem")
    )

    # 実データで substitutionGroup が複数あるのに P-6 が「全要素共通」と書いていたら不一致。
    has_data_multi = len(groups) > 1
    ok = c9_claims_multi and (not (has_data_multi and p6_claims_single))

    res = classify(
        ok,
        "P-6 と C-9 の concept 属性記述は整合。",
        "P-6 の substitutionGroup 記述が実データ/C-9 と不一致。",
        [
            f"substitution_groups={groups}",
            f"has_data_multi={has_data_multi}",
            f"p6_claims_single={p6_claims_single}",
            f"c9_claims_multi={c9_claims_multi}",
            str(xsd),
        ],
    )
    res.name = "6) P-6 concept 定義 ↔ C-9 属性"
    return res


def check_7_label_structure() -> CheckResult:
    """P-6 ラベルリンクベース ↔ C-5/C-10 構造判定。"""
    p6 = read_text(QA_ROOT / "P-6.a.md")
    c5 = read_text(QA_ROOT / "C-5.a.md")
    c10 = read_text(QA_ROOT / "C-10.a.md")

    lab = TAXONOMY_ROOT / "taxonomy/jppfs/2025-11-01/label/jppfs_2025-11-01_lab.xml"
    ltxt = read_text(lab)
    data_ok = all(token in ltxt for token in ("<link:labelLink", "<link:loc", "<link:labelArc", "concept-label"))
    p6_has_chain = ("loc -> labelArc" in p6) or ("loc → labelArc" in p6)
    docs_ok = (
        p6_has_chain
        and "labelLink" in c5
        and "concept-label" in c5
        and "link:labelArc" in c10
        and "concept-label" in c10
    )
    ok = docs_ok and data_ok

    res = classify(
        ok,
        "P-6 と C-5/C-10 のラベルリンクベース構造は一致。",
        "ラベルリンクベース構造の記述に不一致。",
        [
            f"data_ok={data_ok}",
            f"docs_ok={docs_ok}",
            str(lab),
        ],
    )
    res.name = "7) P-6 ラベル構造 ↔ C-5/C-10"
    return res


def check_8_bank_zip_vs_e5() -> CheckResult:
    """P-1d 銀行 ZIP ↔ E-5 業種差異判定。"""
    p1 = read_text(QA_ROOT / "P-1.a.md")
    e5 = read_text(QA_ROOT / "E-5.a.md")

    sample04 = find_sample_dir("04")  # 銀行業サンプル
    has_public = any(p.is_dir() and p.name == "PublicDoc" for p in sample04.rglob("*"))
    has_audit = any(p.is_dir() and p.name == "AuditDoc" for p in sample04.rglob("*"))

    docs_ok = (
        "銀行業" in p1
        and "同一パターン" in p1
        and "OrdinaryIncomeBNK" in e5
        and "DepositsLiabilitiesBNK" in e5
        and "業種差異" in e5
    )
    data_ok = has_public and has_audit
    ok = docs_ok and data_ok

    res = classify(
        ok,
        "銀行業 ZIP 構造共通（P-1d）と業種 concept 差異（E-5）は整合。",
        "銀行業 ZIP と業種差異説明に不整合。",
        [
            f"has_public={has_public}",
            f"has_audit={has_audit}",
            f"docs_ok={docs_ok}",
            str(sample04),
        ],
    )
    res.name = "8) P-1d 銀行 ZIP ↔ E-5 業種差異"
    return res


def check_9_amendment_zip_vs_g7() -> CheckResult:
    """P-1e 訂正 ZIP ↔ G-7 訂正構造判定。"""
    p1 = read_text(QA_ROOT / "P-1.a.md")
    g7 = read_text(QA_ROOT / "G-7.a.md")

    sample20 = find_sample_dir("20")
    sample02 = find_sample_dir("02")
    c20_xbrl = len(list(sample20.rglob("*.xbrl")))
    c20_xsd = len(list(sample20.rglob("*.xsd")))
    c02_xbrl = len(list(sample02.rglob("*.xbrl")))
    c02_xsd = len(list(sample02.rglob("*.xsd")))

    header20 = sample20 / (
        "S021XXXX/XBRL/PublicDoc/"
        "0000000_header_jpcrp030000-asr-001_X99001-000_2026-03-31_02_2026-07-02_ixbrl.htm"
    )
    h20 = read_text(header20)
    amendment_flag = re.search(
        r"jpdei_cor:AmendmentFlagDEI\"[^>]*>(true|false)<", h20
    )
    id_target = re.search(
        r"jpdei_cor:IdentificationOfDocumentSubjectToAmendmentDEI\"[^>]*>([^<]+)<",
        h20,
    )
    amendment_ok = amendment_flag and amendment_flag.group(1) == "true"
    target_ok = id_target and id_target.group(1).strip() == "S002XXXX"

    docs_ok = (
        "完全再提出" in p1
        and "全体を再提出" in g7
        and "差分" in g7
    )
    data_ok = c20_xbrl == c02_xbrl and c20_xsd == c02_xsd and amendment_ok and target_ok
    ok = docs_ok and data_ok

    res = classify(
        ok,
        "訂正報告書は全体再提出で P-1e と G-7 が一致。",
        "訂正報告書構造の記述に不一致。",
        [
            f"counts20: xbrl={c20_xbrl}, xsd={c20_xsd}",
            f"counts02: xbrl={c02_xbrl}, xsd={c02_xsd}",
            f"amendment_ok={bool(amendment_ok)}",
            f"target_ok={bool(target_ok)}",
            f"docs_ok={docs_ok}",
            str(header20),
        ],
    )
    res.name = "9) P-1e 訂正 ZIP ↔ G-7 訂正構造"
    return res


def run_checks() -> list[CheckResult]:
    """全 9 項目のチェックを実行する。"""
    return [
        check_1_namespace(),
        check_2_context_structure(),
        check_3_schemaref(),
        check_4_import_mapping(),
        check_5_ixbrl_adoption(),
        check_6_concept_attrs(),
        check_7_label_structure(),
        check_8_bank_zip_vs_e5(),
        check_9_amendment_zip_vs_g7(),
    ]


def main() -> None:
    """メイン処理。"""
    print("FINALCHECK クロスチェック検証")
    print("=" * 70)

    checks = run_checks()

    ok_count = sum(1 for c in checks if c.status == "OK")
    fix_count = sum(1 for c in checks if c.status == "NEEDS_FIX")
    warn_count = sum(1 for c in checks if c.status == "WARN")

    for c in checks:
        print(f"\n[{c.status}] {c.name}")
        print(f"  {c.detail}")
        for ev in c.evidence:
            print(f"  - {ev}")

    print(f"\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"OK       : {ok_count}")
    print(f"NEEDS_FIX: {fix_count}")
    print(f"WARN     : {warn_count}")

    if fix_count == 0:
        print("\n→ 全 9 項目で整合。")
    else:
        print("\n→ 要修正項目あり。FINALCHECK.a.md の指摘と合わせて更新してください。")


if __name__ == "__main__":
    main()
