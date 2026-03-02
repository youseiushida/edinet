"""過去データから role URI パターンを抽出し、_STATEMENT_KEYWORDS の堅牢性を検証する。

2019〜2025年の有価証券報告書 XBRL から:
1. XBRL instance 内の roleRef の roleURI を抽出
2. ZIP 内の _pre*.xml ファイル名パターンを確認
3. concept_sets.py の _STATEMENT_KEYWORDS (9キーワード) が全年で分類可能か検証
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from collections import defaultdict

# プロジェクトルートを path に追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from edinet import configure, documents  # noqa: E402
from edinet.api.download import (  # noqa: E402
    DownloadFileType,
    download_document,
)

# _STATEMENT_KEYWORDS と同じ9キーワード (concept_sets.py からコピー)
_STATEMENT_KEYWORDS: dict[str, str] = {
    "BalanceSheet": "BS",
    "StatementOfFinancialPosition": "BS",
    "StatementOfIncome": "PL",
    "StatementOfComprehensiveIncome": "CI",
    "StatementsOfCashFlows": "CF",
    "StatementOfCashFlows": "CF",
    "StatementOfChangesInEquity": "SS",
    "StatementsOfChangesInNetAssets": "SS",
    "StatementOfChangesInNetAssets": "SS",
}

# ファイル名パターン (_pre_(bs|pl|cf|ss|ci))
_STMT_RE = re.compile(r"_pre_(bs|pl|cf|ss|ci)", re.IGNORECASE)


def classify_role(role_uri: str) -> str | None:
    """role URI を _STATEMENT_KEYWORDS で分類する。"""
    for keyword, cat in _STATEMENT_KEYWORDS.items():
        if keyword in role_uri:
            return cat
    return None


def extract_role_uris_from_xbrl(xbrl_bytes: bytes) -> list[str]:
    """XBRL instance バイト列から roleRef の roleURI を抽出する。"""
    text = xbrl_bytes.decode("utf-8", errors="replace")
    pattern = re.compile(r'roleURI="([^"]+)"')
    return pattern.findall(text)


def extract_pre_filenames_from_zip(zip_bytes: bytes) -> list[str]:
    """ZIP 内から _pre を含む XML ファイル名を抽出する。"""
    results = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if "_pre" in name.lower() and name.lower().endswith(".xml"):
                    results.append(name)
    except zipfile.BadZipFile:
        pass
    return results


# 各年度の一般商工業企業の有報 docID (前回の E2E テストで使用したもの)
YEARLY_DOCS = {
    2019: "S100FP8E",  # NECキャピタルソリューション
    2020: "S100IU1L",  # モスフードサービス
    2021: "S100LNRH",  # Oakキャピタル
    2022: "S100OOJK",  # 日本空調サービス
    2023: "S100RYHO",  # リックス
    2024: "S100UOPU",  # メディカルシステムネットワーク
    2025: "S100W4MW",  # 日本甜菜製糖
}


def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY")
    if not api_key:
        print("ERROR: EDINET_API_KEY が未設定")
        sys.exit(1)

    configure(api_key=api_key)

    all_results: dict[int, dict[str, list[str]]] = {}
    all_pre_files: dict[int, list[str]] = {}

    for year, doc_id in sorted(YEARLY_DOCS.items()):
        print(f"\n{'='*70}")
        print(f"Year {year}: {doc_id}")
        print(f"{'='*70}")

        try:
            # ZIP をダウンロード
            zip_bytes = download_document(
                doc_id, file_type=DownloadFileType.XBRL_AND_AUDIT
            )

            # ZIP 内の _pre ファイル名を抽出
            pre_files = extract_pre_filenames_from_zip(zip_bytes)
            all_pre_files[year] = pre_files

            # primary XBRL を探して roleURI を抽出
            from edinet.api.download import extract_primary_xbrl
            result = extract_primary_xbrl(zip_bytes)
            if result is None:
                print("  ERROR: primary XBRL が見つからない")
                continue
            xbrl_path, xbrl_bytes = result
            print(f"  primary XBRL: {xbrl_path}")

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # roleURI を抽出
        role_uris = extract_role_uris_from_xbrl(xbrl_bytes)
        print(f"\n  roleURI 総数: {len(role_uris)}")

        # 分類
        classified: dict[str, list[str]] = defaultdict(list)
        unclassified: list[str] = []

        for uri in sorted(set(role_uris)):
            cat = classify_role(uri)
            if cat:
                classified[cat].append(uri)
            else:
                unclassified.append(uri)

        print(f"\n  分類結果:")
        for cat in ("BS", "PL", "CI", "CF", "SS"):
            uris = classified.get(cat, [])
            print(f"    {cat}: {len(uris)} 件")
            for u in uris:
                print(f"      {u}")

        print(f"\n  未分類 (非財務諸表): {len(unclassified)} 件")
        for u in unclassified[:5]:
            print(f"    {u}")
        if len(unclassified) > 5:
            print(f"    ... 他 {len(unclassified) - 5} 件")

        # _pre ファイル名パターン
        print(f"\n  ZIP 内 _pre ファイル: {len(pre_files)} 件")
        stmt_pre_files = []
        other_pre_files = []
        for f in pre_files:
            m = _STMT_RE.search(f)
            if m:
                stmt_pre_files.append((f, m.group(1).upper()))
            else:
                other_pre_files.append(f)

        print(f"    財務諸表 _pre: {len(stmt_pre_files)} 件")
        for f, cat in sorted(stmt_pre_files, key=lambda x: x[1]):
            fname = f.rsplit("/", 1)[-1] if "/" in f else f
            print(f"      [{cat}] {fname}")
        print(f"    その他 _pre: {len(other_pre_files)} 件")
        for f in other_pre_files[:3]:
            fname = f.rsplit("/", 1)[-1] if "/" in f else f
            print(f"      {fname}")

        all_results[year] = dict(classified)

    # サマリー
    print(f"\n\n{'='*70}")
    print("サマリー: 年度別の role URI 分類数 (ユニーク)")
    print(f"{'='*70}")
    print(f"{'Year':>6} | {'BS':>4} | {'PL':>4} | {'CI':>4} | {'CF':>4} | {'SS':>4} | 分類OK?")
    print("-" * 60)
    all_ok = True
    for year in sorted(all_results.keys()):
        r = all_results[year]
        bs = len(r.get("BS", []))
        pl = len(r.get("PL", []))
        ci = len(r.get("CI", []))
        cf = len(r.get("CF", []))
        ss = len(r.get("SS", []))
        ok = bs > 0 and pl > 0 and cf > 0 and ss > 0
        if not ok:
            all_ok = False
        status = "OK" if ok else "NG"
        print(
            f"{year:>6} | {bs:>4} | {pl:>4} | {ci:>4} | {cf:>4} | {ss:>4} | {status}"
        )

    print(f"\n{'='*70}")
    if all_ok:
        print("結論: _STATEMENT_KEYWORDS は 2019-2025 の全年度で正しく分類可能")
    else:
        print("警告: 一部年度で分類できない roleURI が存在")

    # _pre ファイル名パターンのサマリー
    print(f"\n{'='*70}")
    print("サマリー: 年度別 _pre ファイルパターン")
    print(f"{'='*70}")
    for year in sorted(all_pre_files.keys()):
        files = all_pre_files[year]
        cats = set()
        for f in files:
            m = _STMT_RE.search(f)
            if m:
                cats.add(m.group(1).upper())
        print(f"  {year}: {sorted(cats)} ({len(files)} files total)")


if __name__ == "__main__":
    main()
