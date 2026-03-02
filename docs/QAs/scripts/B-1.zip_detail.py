"""B-1. ZIP 内ディレクトリ構造 — 詳細分析スクリプト

実行方法: uv run docs/QAs/scripts/B-1.zip_detail.py
前提: EDINET_API_KEY 環境変数が必要
出力: ファイル命名規則の分解、リンクベース存在有無、_ref.xml 内容、
      IFRS vs J-GAAP 差異、エンコーディング確認、file_type=5 の取得可否等
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))

from _common import (  # noqa: E402
    extract_member,
    find_filings,
    find_members_by_ext,
    find_public_doc_members,
    get_zip,
    print_filing_info,
    print_zip_tree,
)

# ================================================================
# ターゲット定義（P-1 と同じ5社 + IFRS 企業）
# ================================================================
TARGETS = {
    "toyota": {
        "label": "トヨタ (E02144) — IFRS 適用、製造業",
        "edinet_code": "E02144",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-07-31",
    },
    "belluna": {
        "label": "ベルーナ (E03229) — J-GAAP、小売業",
        "edinet_code": "E03229",
        "doc_type": "120",
        "start": "2025-06-01",
        "end": "2025-06-30",
    },
    "taiyo": {
        "label": "太洋テクノレックス (E02097) — 四半期報告書",
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

# ファイル名の命名規則パターン
# 例: jpcrp030000-asr-001_E02144-000_2025-03-31_01_2025-06-18.xbrl
FILENAME_PATTERN = re.compile(
    r"^(?P<form_code>[a-z]+\d+)-"  # 府令略号+様式番号: jpcrp030000
    r"(?P<report_code>[a-z0-9]+)-"  # 報告書略号: asr
    r"(?P<seq>\d+)_"  # 連番: 001
    r"(?P<edinet_code>[A-Z]\d+)-"  # EDINETコード: E02144
    r"(?P<branch>\d+)_"  # 枝番: 000
    r"(?P<period_end>\d{4}-\d{2}-\d{2})_"  # 期末日: 2025-03-31
    r"(?P<submission_num>\d+)_"  # 提出回数: 01
    r"(?P<filing_date>\d{4}-\d{2}-\d{2})"  # 提出日: 2025-06-18
    r"(?P<suffix>_.*)?$"  # オプショナルサフィックス
)

REPORT_CODE_MAP = {
    "asr": "有価証券報告書(Annual Securities Report)",
    "ssr": "半期報告書(Semi-annual Securities Report)",
    "q1r": "第1四半期報告書",
    "q2r": "第2四半期報告書",
    "q3r": "第3四半期報告書",
    "q4r": "第4四半期報告書",
    "rvs": "訂正報告書(Revised)",
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


def analyze_naming_convention(zip_bytes: bytes) -> None:
    """B-1.1: ファイル命名規則の分解。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.1: ファイル命名規則の分解 ---")
    xbrl_files = find_members_by_ext(zip_bytes, ".xbrl")
    xsd_files = find_members_by_ext(zip_bytes, ".xsd")
    all_named = xbrl_files + xsd_files

    for member in all_named[:5]:
        basename = os.path.basename(member)
        name_no_ext = os.path.splitext(basename)[0]
        m = FILENAME_PATTERN.match(name_no_ext)
        if m:
            d = m.groupdict()
            print(f"\n  ファイル: {member}")
            print(f"    府令略号+様式番号 : {d['form_code']}")
            print(f"    報告書略号       : {d['report_code']}"
                  f" ({REPORT_CODE_MAP.get(d['report_code'], '不明')})")
            print(f"    連番            : {d['seq']}")
            print(f"    EDINETコード    : {d['edinet_code']}")
            print(f"    枝番            : {d['branch']}")
            print(f"    期末日          : {d['period_end']}")
            print(f"    提出回数        : {d['submission_num']}")
            print(f"    提出日          : {d['filing_date']}")
            if d.get("suffix"):
                print(f"    サフィックス    : {d['suffix']}")
        else:
            print(f"\n  ファイル: {member}")
            print(f"    パターン不一致（正規表現にマッチせず）")


def analyze_multiple_xbrl(zip_bytes: bytes) -> None:
    """B-1.2: 複数 .xbrl ファイルの分析。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.2: 複数 .xbrl ファイルの一覧 ---")
    xbrl_files = find_members_by_ext(zip_bytes, ".xbrl")
    public_xbrl = [f for f in xbrl_files if "/publicdoc/" in f"/{f.lower()}"]
    audit_xbrl = [f for f in xbrl_files if "/auditdoc/" in f"/{f.lower()}"]
    other_xbrl = [f for f in xbrl_files
                  if f not in public_xbrl and f not in audit_xbrl]

    print(f"  合計: {len(xbrl_files)}")
    print(f"  PublicDoc: {len(public_xbrl)}")
    for f in public_xbrl:
        print(f"    {f}")
    print(f"  AuditDoc: {len(audit_xbrl)}")
    for f in audit_xbrl:
        print(f"    {f}")
    if other_xbrl:
        print(f"  その他: {len(other_xbrl)}")
        for f in other_xbrl:
            print(f"    {f}")


def analyze_audit_doc(zip_bytes: bytes) -> None:
    """B-1.4: AuditDoc の詳細内容。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.4: AuditDoc の詳細 ---")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        audit_files = [
            i for i in zf.infolist()
            if not i.is_dir() and "/auditdoc/" in f"/{i.filename.lower()}"
        ]
        if not audit_files:
            print("  AuditDoc: なし")
            return

        print(f"  AuditDoc ファイル数: {len(audit_files)}")
        for info in sorted(audit_files, key=lambda x: x.filename):
            print(f"    {info.filename:<70s} {info.file_size:>10,} bytes")

        # jpaud 系名前空間の使用チェック
        for info in audit_files:
            if info.filename.lower().endswith((".xbrl", ".htm", ".xsd")):
                try:
                    raw = zf.read(info.filename)
                    text = decode_xml(raw)
                    if "jpaud" in text.lower():
                        print(f"\n  jpaud 名前空間の使用: YES ({info.filename})")
                        # 名前空間 URI を抽出
                        for line in text.splitlines():
                            if "jpaud" in line.lower():
                                print(f"    {line.strip()[:200]}")
                        break
                except Exception:
                    pass
        else:
            print("\n  jpaud 名前空間の使用: NO（AuditDoc 内に jpaud 参照なし）")


def analyze_linkbase_existence(zip_bytes: bytes) -> None:
    """B-1.5: リンクベースファイルの存在有無チェック。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.5: リンクベースファイルの存在有無 ---")
    suffixes = ["_lab.xml", "_lab-en.xml", "_pre.xml", "_cal.xml",
                "_def.xml", "_ref.xml"]

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        all_files = [i.filename for i in zf.infolist() if not i.is_dir()]

        for folder in ["PublicDoc", "AuditDoc"]:
            folder_files = [f for f in all_files
                           if f"/{folder.lower()}/" in f"/{f.lower()}"]
            if not folder_files:
                continue

            print(f"\n  {folder}/:")
            for suffix in suffixes:
                matching = [f for f in folder_files
                           if f.lower().endswith(suffix.lower())]
                status = "YES" if matching else "NO"
                print(f"    {suffix:<15s}: {status}"
                      + (f"  ({matching[0]})" if matching else ""))


def analyze_ref_xml(zip_bytes: bytes) -> None:
    """B-1.6: _ref.xml の内容サンプル。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.6: _ref.xml の内容 ---")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        ref_files = [
            i.filename for i in zf.infolist()
            if not i.is_dir() and i.filename.lower().endswith("_ref.xml")
        ]
        if not ref_files:
            print("  _ref.xml: 存在しない")
            return

        for ref_file in ref_files:
            raw = zf.read(ref_file)
            text = decode_xml(raw)
            lines = text.splitlines()
            print(f"\n  ファイル: {ref_file}")
            print(f"  サイズ: {len(raw):,} bytes, {len(lines)} 行")
            # 冒頭 30 行を表示
            display_lines = min(30, len(lines))
            print(f"  --- 冒頭 {display_lines} 行 ---")
            for i, line in enumerate(lines[:display_lines], 1):
                display = line if len(line) <= 150 else line[:150] + "..."
                print(f"    {i:4d}: {display}")
            if len(lines) > display_lines:
                print(f"    ... (残り {len(lines) - display_lines} 行)")


def analyze_encoding(zip_bytes: bytes) -> None:
    """B-1.9: ZIP 内パスのエンコーディング確認。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.9: ZIP 内パスのエンコーディング ---")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        all_ascii = True
        non_ascii_files = []
        for info in zf.infolist():
            try:
                info.filename.encode("ascii")
            except UnicodeEncodeError:
                all_ascii = False
                non_ascii_files.append(info.filename)

        if all_ascii:
            print("  全パスが ASCII のみ")
        else:
            print(f"  非ASCII パスあり: {len(non_ascii_files)} 件")
            for f in non_ascii_files[:10]:
                print(f"    {f}")

        # flag_bits チェック（UTF-8 フラグ）
        for info in zf.infolist():
            if info.flag_bits & 0x800:
                print("  ZIP エントリの UTF-8 フラグ (bit 11): SET")
                break
        else:
            print("  ZIP エントリの UTF-8 フラグ (bit 11): NOT SET")


def analyze_target_namespaces(zip_bytes: bytes) -> None:
    """B-1.11: 各 XSD の targetNamespace 数で複数エンティティの有無を確認。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.11: targetNamespace の確認 ---")
    xsd_files = find_members_by_ext(zip_bytes, ".xsd")
    namespaces = []

    for member in xsd_files:
        raw = extract_member(zip_bytes, member)
        text = decode_xml(raw)
        for m in re.finditer(r'targetNamespace="([^"]*)"', text):
            namespaces.append((member, m.group(1)))
            print(f"  {member}")
            print(f"    targetNamespace: {m.group(1)}")

    edinet_codes = set()
    for _, ns in namespaces:
        code_match = re.search(r"/([A-Z]\d{5})-\d{3}/", ns)
        if code_match:
            edinet_codes.add(code_match.group(1))

    print(f"\n  ユニークな EDINET コード数: {len(edinet_codes)}")
    if edinet_codes:
        print(f"  EDINET コード: {', '.join(sorted(edinet_codes))}")
    print(f"  複数報告エンティティ: {'YES' if len(edinet_codes) > 1 else 'NO'}")


def analyze_file_type_5(doc_id: str) -> None:
    """B-1.12: file_type=5 の取得可否チェック。

    Args:
        doc_id: 書類管理番号。
    """
    print("\n--- B-1.12: file_type=5 の取得可否 ---")
    try:
        zip5 = get_zip(doc_id, file_type="5")
        with zipfile.ZipFile(io.BytesIO(zip5)) as zf:
            files = [i.filename for i in zf.infolist() if not i.is_dir()]
            print(f"  file_type=5: 取得成功 ({len(zip5):,} bytes, "
                  f"{len(files)} ファイル)")
            for f in files[:10]:
                print(f"    {f}")
            if len(files) > 10:
                print(f"    ... (他 {len(files) - 10} ファイル)")
    except Exception as exc:
        print(f"  file_type=5: 取得失敗 ({type(exc).__name__}: {exc})")


def analyze_meta_inf(zip_bytes: bytes) -> None:
    """B-1.13: META-INF ディレクトリの存在確認。

    Args:
        zip_bytes: ZIP バイト列。
    """
    print("\n--- B-1.13: META-INF / 非 XBRL ファイル ---")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        all_names = [i.filename for i in zf.infolist()]

        meta_inf = [f for f in all_names if "meta-inf" in f.lower()]
        if meta_inf:
            print(f"  META-INF: YES ({len(meta_inf)} ファイル)")
            for f in meta_inf:
                print(f"    {f}")
        else:
            print("  META-INF: NO — XBRL Report Package 非準拠")

        # 拡張子サマリ
        ext_counts: dict[str, int] = defaultdict(int)
        for info in zf.infolist():
            if not info.is_dir():
                ext = os.path.splitext(info.filename)[1].lower()
                ext_counts[ext] += 1

        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"}
        image_count = sum(v for k, v in ext_counts.items() if k in image_exts)
        if image_count:
            print(f"\n  画像ファイル: {image_count} ファイル")
            for ext in sorted(image_exts):
                if ext in ext_counts:
                    print(f"    {ext}: {ext_counts[ext]}")


def process_target(target_id: str, config: dict) -> tuple[str, bytes] | None:
    """1 つのターゲットを処理する。

    Args:
        target_id: ターゲット ID。
        config: ターゲット設定辞書。

    Returns:
        (doc_id, zip_bytes) のタプル。見つからなければ None。
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

    # 各分析を実行
    print_zip_tree(zip_bytes, title=f"{target_id} ZIP ツリー")
    analyze_naming_convention(zip_bytes)
    analyze_multiple_xbrl(zip_bytes)
    analyze_audit_doc(zip_bytes)
    analyze_linkbase_existence(zip_bytes)
    analyze_ref_xml(zip_bytes)
    analyze_encoding(zip_bytes)
    analyze_target_namespaces(zip_bytes)
    analyze_meta_inf(zip_bytes)

    return filing.doc_id, zip_bytes


def main() -> None:
    """メイン処理。"""
    print("B-1: ZIP 内ディレクトリ構造 — 詳細分析")
    print("=" * 70)

    results: dict[str, tuple[str, bytes]] = {}

    for target_id, config in TARGETS.items():
        try:
            result = process_target(target_id, config)
            if result:
                results[target_id] = result
        except Exception as exc:
            print(f"\n  ERROR ({target_id}): {type(exc).__name__}: {exc}")

    # B-1.7: IFRS vs J-GAAP 比較
    print(f"\n{'#' * 70}")
    print("=== B-1.7: IFRS (トヨタ) vs J-GAAP (ベルーナ) 比較 ===")
    print(f"{'#' * 70}")

    for key in ("toyota", "belluna"):
        if key not in results:
            print(f"  {key}: データなし")
            continue
        _, zb = results[key]
        xsd_members = find_public_doc_members(zb, ".xsd")
        for xsd in xsd_members:
            raw = extract_member(zb, xsd)
            text = decode_xml(raw)
            imports = re.findall(r'schemaLocation="([^"]*)"', text)
            print(f"\n  {key} ({xsd}):")
            print(f"    import 数: {len(imports)}")
            for imp in imports:
                basename = os.path.basename(imp)
                print(f"      {basename}")

    # B-1.12: file_type=5 テスト（トヨタのみ）
    if "toyota" in results:
        print(f"\n{'#' * 70}")
        print("=== B-1.12: file_type=5 テスト ===")
        print(f"{'#' * 70}")
        analyze_file_type_5(results["toyota"][0])

    print(f"\n{'=' * 70}")
    print("B-1 詳細分析完了")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
