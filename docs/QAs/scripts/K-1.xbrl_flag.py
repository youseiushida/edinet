"""K-1. has_xbrl フラグ信頼性調査スクリプト

実行方法: uv run docs/QAs/scripts/K-1.xbrl_flag.py
前提: EDINET_API_KEY 環境変数が必要
出力: has_xbrl フラグと実際の ZIP 内容の一致検証結果
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import edinet
edinet.configure(api_key=os.environ["EDINET_API_KEY"])

import edinet.public_api as public_api
from edinet.api.download import (
    download_document,
    extract_zip_member,
    list_zip_members,
)


SAMPLE_COUNT = 5
LOOKBACK_DAYS = 7


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
    import re

    # パスパターンで分類
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

    # loose_htm に対して iXBRL タグの内容検証を行う
    ixbrl_confirmed = []
    plain_html_confirmed = []
    for htm_path in loose_htm:
        content = extract_zip_member(zip_bytes, htm_path)
        text = content.decode("utf-8", errors="replace")
        # iXBRL の判定: ix: 名前空間宣言 or ix: タグの存在
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


def check_xbrl_presence(doc_id: str) -> dict:
    """XBRL ZIP をダウンロードし、XBRL ファイルの存在を確認する。

    Args:
        doc_id: 書類管理番号。

    Returns:
        確認結果の辞書。
    """
    import re

    result: dict = {"doc_id": doc_id, "error": None}
    try:
        zip_bytes = download_document(doc_id, file_type="1")
        members = list_zip_members(zip_bytes)
        result["members"] = members
        result["zip_size"] = len(zip_bytes)

        classification = classify_htm_files(zip_bytes, members)
        result["classification"] = classification

        # 厳密判定: strict_xbrl または ixbrl_confirmed があれば XBRL あり
        all_xbrl = (
            classification["strict_xbrl"]
            + classification["ixbrl_confirmed"]
        )
        result["xbrl_files"] = all_xbrl
        result["has_xbrl_actual"] = len(all_xbrl) > 0
        result["plain_html_files"] = classification["plain_html_confirmed"]

        # DEI のみチェック
        if all_xbrl:
            primary = all_xbrl[0]
            content = extract_zip_member(zip_bytes, primary)
            result["primary_size"] = len(content)
            text = content.decode("utf-8", errors="replace")

            non_fraction_count = len(re.findall(
                r"<(?:ix:)?nonFraction|<(?:xbrli:)?context",
                text, re.IGNORECASE,
            ))
            result["fact_indicator_count"] = non_fraction_count

            has_financial_ns = any(
                ns in text for ns in [
                    "jppfs_cor", "jpcrp_cor",
                    "ifrs-full", "us-gaap",
                ]
            )
            result["has_financial_ns"] = has_financial_ns

    except Exception as e:
        result["error"] = str(e)

    return result


def main() -> None:
    """メイン処理。"""
    print("K-1: has_xbrl フラグ信頼性調査")
    print("=" * 70)

    # Step 1: 直近数日分の書類一覧を取得
    print(f"\n[Step 1] 直近 {LOOKBACK_DAYS} 日分の書類を取得中...")
    today = date.today()
    all_filings = []
    for i in range(LOOKBACK_DAYS):
        d = today - timedelta(days=i)
        filings = public_api.documents(date=d)
        all_filings.extend(filings)
        print(f"  {d}: {len(filings)} 件")

    print(f"  合計: {len(all_filings)} 件")

    xbrl_true = [f for f in all_filings if f.has_xbrl]
    xbrl_false = [f for f in all_filings if not f.has_xbrl]
    print(f"  has_xbrl=True: {len(xbrl_true)} 件")
    print(f"  has_xbrl=False: {len(xbrl_false)} 件")

    # Step 2: has_xbrl=True のサンプルを検証
    print(f"\n[Step 2] has_xbrl=True のサンプル検証 ({SAMPLE_COUNT} 件)")
    print("-" * 70)
    true_samples = xbrl_true[:SAMPLE_COUNT]
    true_mismatches = 0

    for f in true_samples:
        result = check_xbrl_presence(f.doc_id)
        match = "OK" if result.get("has_xbrl_actual") else "MISMATCH"
        if not result.get("has_xbrl_actual"):
            true_mismatches += 1

        print(f"\n  doc_id: {f.doc_id}")
        print(f"  提出者: {f.filer_name}")
        print(f"  書類: {f.doc_type_label_ja}")
        if result["error"]:
            print(f"  エラー: {result['error']}")
        else:
            print(f"  ZIP サイズ: {result['zip_size']:,} bytes")
            cls = result.get("classification", {})
            print(f"  strict XBRL (パス判定): {cls.get('strict_xbrl', [])}")
            print(f"  iXBRL 確認済 (タグ検証): {cls.get('ixbrl_confirmed', [])}")
            print(f"  plain HTML (タグなし):   {cls.get('plain_html_confirmed', [])}")
            print(f"  結果: {match}")
            if result.get("primary_size") is not None:
                print(f"  Primary サイズ: {result['primary_size']:,} bytes")
                print(f"  Fact 指標数: {result.get('fact_indicator_count', 'N/A')}")
                print(f"  財務NS有無: {result.get('has_financial_ns', 'N/A')}")

    # Step 3: has_xbrl=False のサンプルを検証
    print(f"\n\n[Step 3] has_xbrl=False のサンプル検証 ({SAMPLE_COUNT} 件)")
    print("-" * 70)
    false_samples = xbrl_false[:SAMPLE_COUNT]
    false_mismatches = 0

    for f in false_samples:
        print(f"\n  doc_id: {f.doc_id}")
        print(f"  提出者: {f.filer_name}")
        print(f"  書類: {f.doc_type_label_ja}")

        try:
            zip_bytes = download_document(f.doc_id, file_type="1")
            members = list_zip_members(zip_bytes)
            classification = classify_htm_files(zip_bytes, members)

            # 厳密判定
            real_xbrl = (
                classification["strict_xbrl"]
                + classification["ixbrl_confirmed"]
            )
            plain_html = classification["plain_html_confirmed"]

            if real_xbrl:
                false_mismatches += 1
                print(f"  MISMATCH: has_xbrl=False だが XBRL が存在")
                print(f"  XBRL ファイル: {real_xbrl}")
            else:
                print(f"  OK: XBRL なし（フラグと一致）")

            if plain_html:
                print(f"  plain HTML (iXBRL タグなし): {plain_html}")
            if classification["loose_htm"]:
                print(f"  ※ .htm ファイルは存在するが iXBRL タグなし")

            print(f"  ZIP メンバー: {members[:10]}{'...' if len(members) > 10 else ''}")
        except Exception as e:
            print(f"  ダウンロード不可: {e}")
            print(f"  （has_xbrl=False の書類は file_type=1 取得不可の場合がある）")

    # Step 4: 撤回書類のチェック
    print(f"\n\n[Step 4] 撤回書類 (withdrawal_status != '0') の検証")
    print("-" * 70)
    withdrawn = [f for f in all_filings if f.withdrawal_status != "0"]
    print(f"  撤回書類数: {len(withdrawn)} 件")

    for f in withdrawn[:3]:
        print(f"\n  doc_id: {f.doc_id}")
        print(f"  提出者: {f.filer_name}")
        print(f"  withdrawal_status: {f.withdrawal_status}")
        print(f"  has_xbrl: {f.has_xbrl}")
        try:
            zip_bytes = download_document(f.doc_id, file_type="1")
            members = list_zip_members(zip_bytes)
            print(f"  ダウンロード: 成功 ({len(zip_bytes):,} bytes)")
            print(f"  ファイル数: {len(members)}")
        except Exception as e:
            print(f"  ダウンロード: 失敗 ({e})")

    # Step 5: DEI のみ（空提出）の可能性があるケース
    print(f"\n\n[Step 5] DEI のみ（空提出）の可能性チェック")
    print("-" * 70)
    # 臨時報告書（doc_type_code="140"）やその他の小規模な提出を探す
    small_filings = [
        f for f in xbrl_true
        if f.doc_type_code in ("140", "150", "160")  # 臨時報告書等
    ]
    print(f"  臨時報告書等 (has_xbrl=True): {len(small_filings)} 件")

    for f in small_filings[:3]:
        result = check_xbrl_presence(f.doc_id)
        print(f"\n  doc_id: {f.doc_id}")
        print(f"  提出者: {f.filer_name}")
        print(f"  書類: {f.doc_type_label_ja} (code={f.doc_type_code})")
        if result["error"]:
            print(f"  エラー: {result['error']}")
        else:
            print(f"  Primary サイズ: {result.get('primary_size', 'N/A')} bytes")
            print(f"  Fact 指標数: {result.get('fact_indicator_count', 'N/A')}")
            print(f"  財務NS有無: {result.get('has_financial_ns', 'N/A')}")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  has_xbrl=True  のうち実際に XBRL なし: {true_mismatches}/{len(true_samples)}")
    print(f"  has_xbrl=False のうち実際に XBRL あり: {false_mismatches}/{len(false_samples)}")
    print(f"  撤回書類数: {len(withdrawn)}")
    print(f"  臨時報告書等 (has_xbrl=True): {len(small_filings)}")


if __name__ == "__main__":
    main()
