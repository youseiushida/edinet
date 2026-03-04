"""
TDnet 調査結果の検証スクリプト
各エンドポイントとデータ構造の動作確認用

使用方法:
  uv run python reports/verify_tdnet.py
"""

import httpx
import zipfile
import io
from datetime import datetime, timedelta


BASE_URL = "https://www.release.tdnet.info/inbs"
SEARCH_URL = "https://www.release.tdnet.info/onsf/TDJFSearch/TDJFSearch"
YANOSHIN_URL = "https://webapi.yanoshin.jp/webapi/tdnet/list"
TAXONOMY_BASE = "http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet"


def test_daily_list():
    """1. 日付別一覧ページの取得テスト"""
    print("=" * 60)
    print("[1] 日付別一覧ページのテスト")

    today = datetime.now().strftime("%Y%m%d")
    url = f"{BASE_URL}/I_list_001_{today}.html"
    print(f"  URL: {url}")

    resp = httpx.get(url, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Length: {len(resp.content)} bytes")
    print(f"  Content-Type: {resp.headers.get('content-type')}")

    # テーブルの存在確認
    has_table = 'id="main-list-table"' in resp.text
    print(f"  main-list-table found: {has_table}")

    # PDF/ZIPリンクの数をカウント
    import re
    pdf_links = re.findall(r'href="(\d+\.pdf)"', resp.text)
    zip_links = re.findall(r'href="(\d+\.zip)"', resp.text)
    print(f"  PDF links: {len(pdf_links)}")
    print(f"  ZIP links: {len(zip_links)}")

    if pdf_links:
        print(f"  Sample PDF: {pdf_links[0]}")
    if zip_links:
        print(f"  Sample ZIP: {zip_links[0]}")

    return pdf_links, zip_links


def test_search_api():
    """2. 検索APIのテスト"""
    print("\n" + "=" * 60)
    print("[2] 検索APIのテスト")

    today = datetime.now().strftime("%Y%m%d")
    data = {"t0": today, "t1": today, "q": "決算", "m": "0"}
    print(f"  POST {SEARCH_URL}")
    print(f"  Data: {data}")

    resp = httpx.post(SEARCH_URL, data=data, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Length: {len(resp.content)} bytes")

    import re
    result_match = re.search(r'(\d+)件.*の結果が見つかりました', resp.text)
    if result_match:
        print(f"  Results found: {result_match.group(1)}件")
    elif "該当する適時開示情報が見つかりませんでした" in resp.text:
        print("  Results found: 0件")


def test_pdf_download(pdf_links: list):
    """3. PDFダウンロードテスト"""
    print("\n" + "=" * 60)
    print("[3] PDFダウンロードテスト")

    if not pdf_links:
        print("  No PDF links available. Skipping.")
        return

    filename = pdf_links[0]
    url = f"{BASE_URL}/{filename}"
    print(f"  URL: {url}")

    resp = httpx.head(url, timeout=30)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('content-type')}")
    print(f"  Content-Length: {resp.headers.get('content-length')} bytes")


def test_xbrl_download(zip_links: list):
    """4. XBRL ZIPダウンロード・構造テスト"""
    print("\n" + "=" * 60)
    print("[4] XBRL ZIPダウンロード・構造テスト")

    if not zip_links:
        print("  No ZIP links available. Skipping.")
        return

    filename = zip_links[0]
    url = f"{BASE_URL}/{filename}"
    prefix = filename[:4]
    print(f"  URL: {url}")
    print(f"  Prefix: {prefix} ({'フル決算' if prefix == '0812' else '簡易修正情報' if prefix == '0912' else '不明'})")

    resp = httpx.get(url, timeout=60)
    print(f"  Status: {resp.status_code}")
    print(f"  Size: {len(resp.content)} bytes")

    # ZIP内容を確認
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        print(f"  Files in ZIP ({len(names)}):")
        for name in sorted(names):
            info = zf.getinfo(name)
            print(f"    {name} ({info.file_size} bytes)")


def test_taxonomy():
    """5. タクソノミスキーマの取得テスト"""
    print("\n" + "=" * 60)
    print("[5] タクソノミスキーマの取得テスト")

    urls = {
        "Main Schema": f"{TAXONOMY_BASE}/ed/t/2014-01-12/tse-ed-t-2014-01-12.xsd",
        "Role Types": f"{TAXONOMY_BASE}/ed/o/rt/2014-01-12/tse-ed-rt-2014-01-12.xsd",
        "Labels (JA)": f"{TAXONOMY_BASE}/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab.xml",
        "Labels (EN)": f"{TAXONOMY_BASE}/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab-en.xml",
    }

    for name, url in urls.items():
        resp = httpx.head(url, timeout=30)
        size = resp.headers.get("content-length", "?")
        print(f"  {name}: {resp.status_code} ({size} bytes)")
        print(f"    {url}")


def test_yanoshin_api():
    """6. やのしんWEB-APIのテスト"""
    print("\n" + "=" * 60)
    print("[6] やのしんWEB-APIテスト")

    today = datetime.now().strftime("%Y%m%d")
    url = f"{YANOSHIN_URL}/{today}.json2"
    print(f"  URL: {url}")

    resp = httpx.get(url, params={"limit": 3}, timeout=30)
    print(f"  Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total count: {data.get('total_count')}")
        items = data.get("items", [])
        for item in items[:3]:
            print(f"  [{item['pubdate']}] {item['company_code']} {item['company_name']}")
            print(f"    {item['title']}")
            if item.get("url_xbrl"):
                print(f"    XBRL: {item['url_xbrl']}")

    # XBRL付きのみ
    url2 = f"{YANOSHIN_URL}/{today}.json2"
    resp2 = httpx.get(url2, params={"hasXBRL": 1, "limit": 3}, timeout=30)
    if resp2.status_code == 200:
        data2 = resp2.json()
        print(f"\n  XBRL only: {data2.get('total_count')} items")


def test_response_headers():
    """7. レスポンスヘッダの詳細確認"""
    print("\n" + "=" * 60)
    print("[7] レスポンスヘッダ詳細")

    today = datetime.now().strftime("%Y%m%d")
    url = f"{BASE_URL}/I_list_001_{today}.html"
    resp = httpx.head(url, timeout=30)

    important_headers = [
        "server", "x-frame-options", "x-content-type-options",
        "cache-control", "pragma", "content-type", "set-cookie"
    ]
    for h in important_headers:
        val = resp.headers.get(h)
        if val:
            print(f"  {h}: {val}")


def test_data_retention():
    """8. 過去30日分のデータ保持状況確認"""
    import re
    import time

    print("\n" + "=" * 60)
    print("[8] 過去30日分のデータ保持状況")
    print(f"  {'日付':12} {'日前':>5} {'リスト':6} {'PDF':>6} {'XBRL':>6} {'PDF実体':>8} {'XBRL実体':>8}")
    print("  " + "-" * 65)

    for i in range(30):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"{BASE_URL}/I_list_001_{date}.html"
        resp = httpx.get(url, timeout=15)
        has_table = 'id="main-list-table"' in resp.text

        if not has_table:
            print(f"  {date:12} {i:>5} {'空':6} {'---':>6} {'---':>6} {'---':>8} {'---':>8}")
            time.sleep(0.5)
            continue

        pdf_links = re.findall(r'href="(\d+\.pdf)"', resp.text)
        zip_links = re.findall(r'href="(\d+\.zip)"', resp.text)

        pdf_status = "---"
        zip_status = "---"

        if pdf_links:
            r = httpx.head(f"{BASE_URL}/{pdf_links[0]}", timeout=15)
            pdf_status = str(r.status_code)
            time.sleep(0.5)

        if zip_links:
            r = httpx.head(f"{BASE_URL}/{zip_links[0]}", timeout=15)
            zip_status = str(r.status_code)
            time.sleep(0.5)

        print(
            f"  {date:12} {i:>5} {'あり':6} "
            f"{len(pdf_links):>6} {len(zip_links):>6} "
            f"{pdf_status:>8} {zip_status:>8}"
        )
        time.sleep(0.5)


if __name__ == "__main__":
    print("TDnet 調査結果 検証スクリプト")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    pdf_links, zip_links = test_daily_list()
    test_search_api()
    test_pdf_download(pdf_links)
    test_xbrl_download(zip_links)
    test_taxonomy()
    test_yanoshin_api()
    test_response_headers()
    test_data_retention()

    print("\n" + "=" * 60)
    print("検証完了")
