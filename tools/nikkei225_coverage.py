"""日経225全銘柄のCKカバレッジ調査。

非同期I/Oで並列化し、各銘柄の有報から extract_values() を実行。
カバーできているCKとできていないCKを銘柄ごとにリストアップする。

Usage:
    EDINET_API_KEY=... EDINET_TAXONOMY_ROOT=... uv run python tools/nikkei225_coverage.py

結果は reports/nikkei225_coverage.json に保存。
中断した場合は再実行で前回の結果から再開する。
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import warnings
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

import edinet
from edinet.financial.standards.canonical_keys import CK

RESULTS_FILE = Path("reports/nikkei225_coverage.json")
MAX_CONCURRENT_XBRL = 8
MAX_CONCURRENT_SEARCH = 10

# fmt: off
NIKKEI225: dict[str, str] = {
    # 医薬品
    "4151": "協和キリン", "4502": "武田薬品工業", "4503": "アステラス製薬",
    "4506": "住友ファーマ", "4507": "塩野義製薬", "4519": "中外製薬",
    "4523": "エーザイ", "4568": "第一三共", "4578": "大塚ホールディングス",
    # 電気機器
    "4062": "イビデン", "6479": "ミネベアミツミ", "6501": "日立製作所",
    "6503": "三菱電機", "6504": "富士電機", "6506": "安川電機",
    "6526": "ソシオネクスト", "6645": "オムロン", "6674": "ジーエス・ユアサ",
    "6701": "日本電気", "6702": "富士通", "6723": "ルネサスエレクトロニクス",
    "6724": "セイコーエプソン", "6752": "パナソニックHD", "6753": "シャープ",
    "6758": "ソニーグループ", "6762": "TDK", "6770": "アルプスアルパイン",
    "6841": "横河電機", "6857": "アドバンテスト", "6861": "キーエンス",
    "6902": "デンソー", "6920": "レーザーテック", "6952": "カシオ計算機",
    "6954": "ファナック", "6963": "ローム", "6971": "京セラ",
    "6976": "太陽誘電", "6981": "村田製作所", "7735": "SCREENホールディングス",
    "7751": "キヤノン", "7752": "リコー", "8035": "東京エレクトロン",
    # 自動車
    "7201": "日産自動車", "7202": "いすゞ自動車", "7203": "トヨタ自動車",
    "7205": "日野自動車", "7211": "三菱自動車工業", "7261": "マツダ",
    "7267": "本田技研工業", "7269": "スズキ", "7270": "SUBARU",
    "7272": "ヤマハ発動機",
    # 精密機器
    "4543": "テルモ", "4902": "コニカミノルタ", "6146": "ディスコ",
    "7731": "ニコン", "7733": "オリンパス", "7741": "HOYA",
    # 通信
    "9432": "NTT", "9433": "KDDI", "9434": "ソフトバンク",
    "9984": "ソフトバンクグループ",
    # 銀行
    "5831": "しずおかFG", "7186": "横浜FG", "8304": "あおぞら銀行",
    "8306": "三菱UFJ", "8308": "りそなHD", "8309": "三井住友トラスト",
    "8316": "三井住友FG", "8331": "千葉銀行", "8354": "ふくおかFG",
    "8411": "みずほFG",
    # その他金融
    "8253": "クレディセゾン", "8591": "オリックス", "8697": "日本取引所G",
    # 証券
    "8601": "大和証券G", "8604": "野村HD",
    # 保険
    "8630": "SOMPO", "8725": "MS&AD", "8750": "第一生命HD",
    "8766": "東京海上HD", "8795": "T&D HD",
    # 水産
    "1332": "ニッスイ",
    # 食品
    "2002": "日清製粉G", "2269": "明治HD", "2282": "日本ハム",
    "2501": "サッポロHD", "2502": "アサヒグループHD", "2503": "キリンHD",
    "2801": "キッコーマン", "2802": "味の素", "2871": "ニチレイ",
    "2914": "日本たばこ産業",
    # 小売業
    "3086": "Jフロントリテイリング", "3092": "ZOZO",
    "3099": "三越伊勢丹HD", "3382": "セブン&アイHD", "7453": "良品計画",
    "8233": "高島屋", "8252": "丸井グループ", "8267": "イオン",
    "9843": "ニトリHD", "9983": "ファーストリテイリング",
    # サービス
    "2413": "エムスリー", "2432": "ディー・エヌ・エー", "3659": "ネクソン",
    "3697": "SHIFT", "4307": "野村総合研究所", "4324": "電通グループ",
    "4385": "メルカリ", "4661": "オリエンタルランド", "4689": "LINEヤフー",
    "4704": "トレンドマイクロ", "4751": "サイバーエージェント",
    "4755": "楽天グループ", "6098": "リクルートHD", "6178": "日本郵政",
    "6532": "ベイカレント", "7974": "任天堂", "9602": "東宝",
    "9735": "セコム", "9766": "コナミグループ",
    # 鉱業
    "1605": "INPEX",
    # 繊維
    "3401": "帝人", "3402": "東レ",
    # パルプ・紙
    "3861": "王子HD",
    # 化学
    "3405": "クラレ", "3407": "旭化成", "4004": "レゾナックHD",
    "4005": "住友化学", "4021": "日産化学", "4042": "東ソー",
    "4043": "トクヤマ", "4061": "デンカ", "4063": "信越化学工業",
    "4183": "三井化学", "4188": "三菱ケミカルG", "4208": "UBE",
    "4452": "花王", "4901": "富士フイルムHD", "4911": "資生堂",
    "6988": "日東電工",
    # 石油
    "5019": "出光興産", "5020": "ENEOSHD",
    # ゴム
    "5101": "横浜ゴム", "5108": "ブリヂストン",
    # 窯業
    "5201": "AGC", "5214": "日本電気硝子", "5233": "太平洋セメント",
    "5301": "東海カーボン", "5332": "TOTO", "5333": "日本碍子",
    # 鉄鋼
    "5401": "日本製鉄", "5406": "神戸製鋼所", "5411": "JFE HD",
    # 非鉄・金属
    "3436": "SUMCO", "5706": "三井金属", "5711": "三菱マテリアル",
    "5713": "住友金属鉱山", "5714": "DOWA HD", "5801": "古河電気工業",
    "5802": "住友電気工業", "5803": "フジクラ",
    # 商社
    "2768": "双日", "8001": "伊藤忠商事", "8002": "丸紅",
    "8015": "豊田通商", "8031": "三井物産", "8053": "住友商事",
    "8058": "三菱商事",
    # 建設
    "1721": "コムシスHD", "1801": "大成建設", "1802": "大林組",
    "1803": "清水建設", "1808": "長谷工コーポレーション", "1812": "鹿島建設",
    "1925": "大和ハウス工業", "1928": "積水ハウス", "1963": "日揮HD",
    # 機械
    "5631": "日本製鋼所", "6103": "オークマ", "6113": "アマダ",
    "6273": "SMC", "6301": "小松製作所", "6302": "住友重機械工業",
    "6305": "日立建機", "6326": "クボタ", "6361": "荏原製作所",
    "6367": "ダイキン工業", "6471": "日本精工", "6472": "NTN",
    "6473": "ジェイテクト", "7004": "カナデビア", "7011": "三菱重工業",
    "7013": "IHI",
    # 造船
    "7012": "川崎重工業",
    # その他製造
    "7832": "バンダイナムコHD", "7911": "TOPPAN HD", "7912": "大日本印刷",
    "7951": "ヤマハ",
    # 不動産
    "3289": "東急不動産HD", "8801": "三井不動産", "8802": "三菱地所",
    "8804": "東京建物", "8830": "住友不動産",
    # 鉄道・バス
    "9001": "東武鉄道", "9005": "東急", "9007": "小田急電鉄",
    "9008": "京王電鉄", "9009": "京成電鉄", "9020": "JR東日本",
    "9021": "JR西日本", "9022": "JR東海",
    # 陸運
    "9064": "ヤマトHD", "9147": "NIPPON EXPRESS HD",
    # 海運
    "9101": "日本郵船", "9104": "商船三井", "9107": "川崎汽船",
    # 空運
    "9201": "日本航空", "9202": "ANAHD",
    # 電力
    "9501": "東京電力HD", "9502": "中部電力", "9503": "関西電力",
    # ガス
    "9531": "東京瓦斯", "9532": "大阪瓦斯",
}
# fmt: on

ALL_CK_VALUES = sorted(str(ck) for ck in CK)


def _generate_search_dates() -> list[date]:
    """有報が提出される可能性のある日付を生成（全営業日）。"""
    dates: list[date] = []
    d = date(2024, 4, 1)
    end = date(2025, 3, 31)
    while d <= end:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return dates


async def search_filings(remaining: set[str]) -> dict[str, edinet.Filing]:
    """非同期で全日付を検索し、各銘柄の最新有報を見つける。"""
    ticker_to_filing: dict[str, edinet.Filing] = {}
    dates = _generate_search_dates()
    sem = asyncio.Semaphore(MAX_CONCURRENT_SEARCH)
    lock = asyncio.Lock()
    searched = [0]

    async def search_one(dt: date) -> None:
        async with sem:
            try:
                docs = await edinet.adocuments(dt, doc_type="120")
                async with lock:
                    for doc in docs:
                        sc = doc.sec_code
                        if sc and len(sc) >= 4:
                            ticker = sc[:4]
                            if ticker in remaining and ticker not in ticker_to_filing:
                                if doc.has_xbrl:
                                    ticker_to_filing[ticker] = doc
                    searched[0] += 1
                    if searched[0] % 50 == 0:
                        found = len(ticker_to_filing)
                        print(
                            f"  検索進捗: {searched[0]}/{len(dates)} 日, "
                            f"{found}/{len(remaining)} 銘柄発見",
                            flush=True,
                        )
            except Exception:
                pass
            # 全銘柄発見したら早期終了
            if not remaining - set(ticker_to_filing.keys()):
                return

    tasks = [search_one(dt) for dt in dates]
    await asyncio.gather(*tasks)
    return ticker_to_filing


def process_one_filing(ticker: str, filing: edinet.Filing) -> dict:
    """1つの Filing を処理してカバレッジ情報を返す。"""
    try:
        stmts = filing.xbrl()
        extracted = edinet.extract_values(stmts)  # dict[str, ExtractedValue | None]
        covered = sorted(k for k, v in extracted.items() if v is not None)
        missing = sorted(set(ALL_CK_VALUES) - set(covered))
        return {
            "ticker": ticker,
            "company": filing.filer_name,
            "doc_id": filing.doc_id,
            "doc_description": filing.doc_description,
            "covered_count": len(covered),
            "missing_count": len(missing),
            "total_ck": len(ALL_CK_VALUES),
            "coverage_pct": round(len(covered) / len(ALL_CK_VALUES) * 100, 1),
            "covered": covered,
            "missing": missing,
            "status": "ok",
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "company": filing.filer_name,
            "doc_id": filing.doc_id,
            "status": "error",
            "error": str(e),
        }


async def process_filings(
    ticker_to_filing: dict[str, edinet.Filing],
    existing: dict[str, dict],
) -> dict[str, dict]:
    """全 Filing を並列処理。"""
    results = dict(existing)
    sem = asyncio.Semaphore(MAX_CONCURRENT_XBRL)
    processed = [0]

    to_process = {t: f for t, f in ticker_to_filing.items() if t not in existing}
    total = len(to_process) + len(existing)

    if not to_process:
        print("  全銘柄処理済み")
        return results

    print(
        f"  {len(to_process)} 銘柄を処理中 (並列数={MAX_CONCURRENT_XBRL})...",
        flush=True,
    )

    async def process_one(ticker: str, filing: edinet.Filing) -> None:
        async with sem:
            result = await asyncio.to_thread(process_one_filing, ticker, filing)
            results[ticker] = result
            processed[0] += 1
            status = "ok" if result.get("status") == "ok" else "ERROR"
            cov = result.get("covered_count", "?")
            tot = result.get("total_ck", "?")
            pct = result.get("coverage_pct", "?")
            print(
                f"  [{processed[0]+len(existing)}/{total}] "
                f"{ticker} {result.get('company', '?')} → "
                f"{cov}/{tot} CK ({pct}%) [{status}]",
                flush=True,
            )
            # 逐次保存
            RESULTS_FILE.write_text(
                json.dumps(results, ensure_ascii=False, indent=2)
            )

    tasks = [process_one(t, f) for t, f in to_process.items()]
    await asyncio.gather(*tasks)
    return results


async def main() -> None:
    api_key = os.environ.get("EDINET_API_KEY")
    tax_root = os.environ.get("EDINET_TAXONOMY_ROOT")
    if not api_key or not tax_root:
        print("EDINET_API_KEY / EDINET_TAXONOMY_ROOT が未設定", file=sys.stderr)
        sys.exit(1)

    edinet.configure(api_key=api_key, taxonomy_path=Path(tax_root))
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 既存結果を読み込み
    existing: dict[str, dict] = {}
    if RESULTS_FILE.exists():
        try:
            existing = json.loads(RESULTS_FILE.read_text())
            print(f"既存結果: {len(existing)} 銘柄")
        except Exception:
            pass

    remaining = set(NIKKEI225.keys()) - set(existing.keys())
    if not remaining:
        print("全銘柄処理済み。結果を表示します。")
    else:
        print(f"残り {len(remaining)}/{len(NIKKEI225)} 銘柄")

        # Phase 1: 有報検索
        t0 = time.perf_counter()
        ticker_to_filing = await search_filings(remaining)
        t1 = time.perf_counter()
        print(
            f"Phase 1 完了: {len(ticker_to_filing)}/{len(remaining)} "
            f"銘柄の有報を発見 ({t1 - t0:.1f}秒)"
        )

        not_found = remaining - set(ticker_to_filing.keys())
        if not_found:
            print(f"  未発見: {sorted(not_found)}")
            for t in not_found:
                existing[t] = {
                    "ticker": t,
                    "company": NIKKEI225[t],
                    "status": "not_found",
                }

        # Phase 2: XBRL 処理
        t2 = time.perf_counter()
        existing = await process_filings(ticker_to_filing, existing)
        t3 = time.perf_counter()
        print(f"Phase 2 完了 ({t3 - t2:.1f}秒)")

    # 最終保存
    RESULTS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    # === サマリー ===
    print("\n" + "=" * 70)
    print("サマリー")
    print("=" * 70)

    ok_results = [r for r in existing.values() if r.get("status") == "ok"]
    errors = [r for r in existing.values() if r.get("status") == "error"]
    not_found_list = [r for r in existing.values() if r.get("status") == "not_found"]

    print(f"成功: {len(ok_results)} / エラー: {len(errors)} / 未発見: {len(not_found_list)}")

    if ok_results:
        avg_cov = sum(r["covered_count"] for r in ok_results) / len(ok_results)
        avg_miss = sum(r["missing_count"] for r in ok_results) / len(ok_results)
        total_ck = ok_results[0]["total_ck"]
        print(
            f"平均カバー率: {avg_cov:.1f}/{total_ck} CK "
            f"({avg_cov / total_ck * 100:.1f}%)"
        )

        # CK ごとのカバー率
        ck_coverage: dict[str, int] = {ck: 0 for ck in ALL_CK_VALUES}
        for r in ok_results:
            for ck in r["covered"]:
                ck_coverage[ck] += 1

        print(f"\n--- CK 別カバー率（{len(ok_results)} 社中）---")
        for ck in ALL_CK_VALUES:
            count = ck_coverage[ck]
            pct = count / len(ok_results) * 100
            bar = "█" * int(pct / 5)
            print(f"  {ck:45s} {count:3d}/{len(ok_results)} ({pct:5.1f}%) {bar}")

    print(f"\n結果ファイル: {RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
