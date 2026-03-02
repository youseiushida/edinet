"""K-1. has_xbrl フラグ信頼性の追加検証スクリプト（サンプル増・多様化版）

実行方法: uv run docs/QAs/scripts/K-1.verify.py
前提: EDINET_API_KEY 環境変数が必要
出力: has_xbrl フラグの信頼性を拡大サンプルで再検証。
      元スクリプト K-1.xbrl_flag.py (N=5, lookback=7日) に対し、
      N=20, lookback=30日 に拡大。
      doc_type_code 別の件数内訳と code=140 (臨時報告書) の
      DEI のみ空提出チェックを追加。
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import date, timedelta

import edinet

edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api
from edinet.api.download import (
    download_document,
    extract_zip_member,
    list_zip_members,
)


SAMPLE_TRUE = 20
SAMPLE_FALSE_MAX = 30
LOOKBACK_DAYS = 30


def classify_htm_files(
    zip_bytes: bytes,
    members: tuple[str, ...],
) -> dict:
    """ZIP 内の HTM/XBRL ファイルを分類し、iXBRL タグの有無を検証する。

    Args:
        zip_bytes: ダウンロードした ZIP のバイト列。
        members: ZIP 内メンバー一覧。

    Returns:
        分類結果の辞書。
    """
    strict_xbrl = [
        m for m in members
        if "PublicDoc" in m
        and (
            m.lower().endswith(".xbrl")
            or "_ixbrl.htm" in m.lower()
            or m.startswith("XBRL/")
        )
    ]
    loose_htm = [
        m for m in members
        if m.lower().endswith((".htm", ".html"))
        and "PublicDoc" in m
        and m not in strict_xbrl
    ]

    ixbrl_confirmed = []
    plain_html_confirmed = []
    for htm_path in loose_htm:
        content = extract_zip_member(zip_bytes, htm_path)
        text = content.decode("utf-8", errors="replace")
        has_ix_ns = bool(re.search(r'xmlns:ix\b', text, re.IGNORECASE))
        has_ix_tag = bool(re.search(r'<ix:', text, re.IGNORECASE))
        has_xbrli = bool(re.search(r'xmlns:xbrli\b', text, re.IGNORECASE))
        if has_ix_ns or has_ix_tag or has_xbrli:
            ixbrl_confirmed.append(htm_path)
        else:
            plain_html_confirmed.append(htm_path)

    return {
        "strict_xbrl": strict_xbrl,
        "loose_htm": loose_htm,
        "ixbrl_confirmed": ixbrl_confirmed,
        "plain_html_confirmed": plain_html_confirmed,
    }


def check_dei_only(zip_bytes: bytes, members: tuple[str, ...]) -> dict:
    """XBRLファイルが DEI のみ（財務データなし）かどうかをチェックする。

    Args:
        zip_bytes: ダウンロードした ZIP のバイト列。
        members: ZIP 内メンバー一覧。

    Returns:
        DEI チェック結果の辞書。
    """
    xbrl_files = [
        m for m in members
        if m.lower().endswith(".xbrl") and "PublicDoc" in m
    ]
    ixbrl_files = [
        m for m in members
        if "_ixbrl.htm" in m.lower() and "PublicDoc" in m
    ]
    primary = (xbrl_files + ixbrl_files)[:1]

    if not primary:
        return {"has_primary": False}

    content = extract_zip_member(zip_bytes, primary[0])
    text = content.decode("utf-8", errors="replace")

    financial_ns = ["jppfs_cor", "jpcrp_cor", "ifrs-full", "us-gaap"]
    found_ns = [ns for ns in financial_ns if ns in text]

    fact_count = len(re.findall(
        r"<(?:ix:)?nonFraction|<(?:xbrli:)?context",
        text, re.IGNORECASE,
    ))

    return {
        "has_primary": True,
        "primary_path": primary[0],
        "primary_size": len(content),
        "financial_ns_found": found_ns,
        "fact_indicator_count": fact_count,
        "is_dei_only": len(found_ns) == 0,
    }


def main() -> None:
    """メイン処理。"""
    print("K-1 検証: has_xbrl フラグ信頼性（拡大サンプル版）")
    print("=" * 70)

    # Step 1: 30日分の書類を取得
    print(f"\n[Step 1] 直近 {LOOKBACK_DAYS} 日分の書類を取得中...")
    today = date.today()
    all_filings = []
    for i in range(LOOKBACK_DAYS):
        d = today - timedelta(days=i)
        filings = public_api.documents(date=d)
        all_filings.extend(filings)

    print(f"  合計: {len(all_filings)} 件")

    xbrl_true = [f for f in all_filings if f.has_xbrl]
    xbrl_false = [f for f in all_filings if not f.has_xbrl]
    print(f"  has_xbrl=True: {len(xbrl_true)} 件")
    print(f"  has_xbrl=False: {len(xbrl_false)} 件")

    # doc_type_code 別内訳
    print(f"\n[Step 1b] doc_type_code 別内訳")
    print("-" * 70)
    dtc_counter = Counter(f.doc_type_code for f in all_filings)
    dtc_true = Counter(f.doc_type_code for f in xbrl_true)
    dtc_false = Counter(f.doc_type_code for f in xbrl_false)

    print(f"  {'code':>6} | {'全体':>6} | {'xbrl=T':>6} | {'xbrl=F':>6} | 書類種別")
    print(f"  {'-'*6} | {'-'*6} | {'-'*6} | {'-'*6} | {'-'*20}")
    for code in sorted(dtc_counter.keys(), key=lambda x: x or ""):
        label = ""
        sample = next(
            (f for f in all_filings if f.doc_type_code == code), None
        )
        if sample:
            label = sample.doc_type_label_ja
        print(
            f"  {code or 'None':>6} | {dtc_counter[code]:>6} | "
            f"{dtc_true.get(code, 0):>6} | {dtc_false.get(code, 0):>6} | "
            f"{label}"
        )

    # Step 2: has_xbrl=True のサンプル検証 (N=20)
    print(f"\n\n[Step 2] has_xbrl=True のサンプル検証 (N={SAMPLE_TRUE})")
    print("-" * 70)
    # 多様な doc_type を含むようにシャッフル
    true_by_type: dict[str | None, list] = {}
    for f in xbrl_true:
        true_by_type.setdefault(f.doc_type_code, []).append(f)

    true_samples = []
    # 各 doc_type から最大3件ずつ取り、合計 SAMPLE_TRUE まで
    for code in sorted(true_by_type.keys(), key=lambda x: x or ""):
        for f in true_by_type[code][:3]:
            if len(true_samples) < SAMPLE_TRUE:
                true_samples.append(f)

    true_mismatches = 0
    for f in true_samples:
        try:
            zip_bytes = download_document(f.doc_id, file_type="1")
            members = list_zip_members(zip_bytes)
            cls = classify_htm_files(zip_bytes, members)
            real_xbrl = cls["strict_xbrl"] + cls["ixbrl_confirmed"]
            has_actual = len(real_xbrl) > 0

            if not has_actual:
                true_mismatches += 1
                print(
                    f"  MISMATCH: {f.doc_id} ({f.doc_type_label_ja}) "
                    f"- has_xbrl=True だが XBRL なし"
                )
        except Exception as e:
            print(f"  ERROR: {f.doc_id} ({f.doc_type_label_ja}) - {e}")

    print(f"\n  結果: {true_mismatches}/{len(true_samples)} ミスマッチ")

    # Step 3: has_xbrl=False のサンプル検証 (最大 SAMPLE_FALSE_MAX)
    n_false = min(len(xbrl_false), SAMPLE_FALSE_MAX)
    print(f"\n\n[Step 3] has_xbrl=False のサンプル検証 (N={n_false})")
    print("-" * 70)
    false_samples = xbrl_false[:n_false]
    false_mismatches = 0
    false_types = Counter()

    for f in false_samples:
        false_types[f.doc_type_code] += 1
        try:
            zip_bytes = download_document(f.doc_id, file_type="1")
            members = list_zip_members(zip_bytes)
            cls = classify_htm_files(zip_bytes, members)
            real_xbrl = cls["strict_xbrl"] + cls["ixbrl_confirmed"]

            if real_xbrl:
                false_mismatches += 1
                print(
                    f"  MISMATCH: {f.doc_id} ({f.doc_type_label_ja}) "
                    f"- has_xbrl=False だが XBRL あり: {real_xbrl[:3]}"
                )
        except Exception as e:
            # has_xbrl=False の書類は file_type=1 が取れない場合あり → OK
            pass

    print(f"\n  結果: {false_mismatches}/{n_false} ミスマッチ")
    print(f"  検証した書類種別:")
    for code, cnt in false_types.most_common():
        label = next(
            (f.doc_type_label_ja for f in false_samples
             if f.doc_type_code == code), ""
        )
        print(f"    {code}: {cnt}件 ({label})")

    # Step 4: 撤回書類
    print(f"\n\n[Step 4] 撤回書類 (withdrawal_status != '0')")
    print("-" * 70)
    withdrawn = [f for f in all_filings if f.withdrawal_status != "0"]
    print(f"  撤回書類数: {len(withdrawn)} 件")

    wd_download_ok = 0
    wd_download_fail = 0
    for f in withdrawn[:10]:
        try:
            zip_bytes = download_document(f.doc_id, file_type="1")
            wd_download_ok += 1
            print(
                f"  DL成功: {f.doc_id} (ws={f.withdrawal_status}) "
                f"- {len(zip_bytes):,} bytes"
            )
        except Exception:
            wd_download_fail += 1

    print(f"  DL 成功: {wd_download_ok}, 失敗: {wd_download_fail}")

    # Step 5: DEI のみ空提出チェック（doc_type_code 別）
    print(f"\n\n[Step 5] DEI のみ（空提出）チェック")
    print("-" * 70)

    # code=140 (臨時報告書) を明示的にカウント
    target_codes = {"140": "臨時報告書", "150": "半期報告書", "160": "半期報告書(投資信託)"}
    for code, label in target_codes.items():
        candidates = [f for f in xbrl_true if f.doc_type_code == code]
        print(f"\n  doc_type_code={code} ({label}): {len(candidates)} 件")

        for f in candidates[:5]:
            try:
                zip_bytes = download_document(f.doc_id, file_type="1")
                members = list_zip_members(zip_bytes)
                dei = check_dei_only(zip_bytes, members)

                status = "DEI_ONLY" if dei.get("is_dei_only") else "OK"
                print(
                    f"    {f.doc_id} ({f.filer_name}): {status} "
                    f"- NS={dei.get('financial_ns_found', [])}, "
                    f"Fact指標={dei.get('fact_indicator_count', 'N/A')}"
                )
            except Exception as e:
                print(f"    {f.doc_id}: ERROR - {e}")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  調査期間: 直近 {LOOKBACK_DAYS} 日（{today - timedelta(days=LOOKBACK_DAYS-1)} 〜 {today}）")
    print(f"  総書類数: {len(all_filings)}")
    print(f"  has_xbrl=True  のうち XBRL なし: {true_mismatches}/{len(true_samples)}")
    print(f"  has_xbrl=False のうち XBRL あり: {false_mismatches}/{n_false}")
    print(f"  撤回書類: {len(withdrawn)} 件 (DL成功={wd_download_ok}, 失敗={wd_download_fail})")

    # doc_type=140 の存在有無を明示
    n_140 = len([f for f in xbrl_true if f.doc_type_code == "140"])
    print(f"  doc_type_code=140 (臨時報告書, xbrl=True): {n_140} 件")


if __name__ == "__main__":
    main()
