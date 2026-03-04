# TDnet 安定的なファイル取得方法レポート

調査日: 2026-03-04

---

## 1. 取得方法の比較

| 方法 | 安定性 | コスト | 遅延 | XBRL | 備考 |
|------|--------|--------|------|------|------|
| JPX公式 TDnet API | 最高 | 月7万円~ | リアルタイム | あり | 5年分保持 |
| J-Quants API | 高 | 無料~有料 | 無料:12週遅延 | - | 決算情報中心 |
| やのしんWEB-API | 中~高 | 無料 | リアルタイム | あり | 非公式、認証不要 |
| release.tdnet.info 直接 | 中 | 無料 | リアルタイム | あり | robots.txt違反、**ファイル保持2-3営業日** |

---

## 2. JPX公式 TDnet APIサービス（有料）

### 概要
- **サービスページ**: https://www.jpx.co.jp/markets/paid-info-listing/tdnet/02.html
- **Swagger仕様**: https://apidoc-tdnet.jpx-dataservice.com/
- **問い合わせ**: api-service@jpx.co.jp

### 料金体系（税別）
| 項目 | 料金 |
|------|------|
| 基本料金 | 70,000円/月 |
| 取得件数 300件以下 | 0円 |
| 301 - 2,000件 | 50,000円 |
| 2,001 - 15,000件 | 170,000円 |

### 主な特徴
- 過去5年分のデータ取得可能
- Index API（一覧取得）と Document API（書類取得）の2種類
- PDF、XBRL形式で取得可能
- テストサーバーあり

---

## 3. やのしんWEB-API（非公式・無料）

### 概要
- **公式**: https://webapi.yanoshin.jp/tdnet/
- 個人開発だが長期間安定稼働
- 認証不要、6形式対応（xml, rss, atom, json, html, json2）

### エンドポイント

```
https://webapi.yanoshin.jp/webapi/tdnet/list/{条件}.{形式}[?パラメータ]
```

### 条件指定

| 条件 | 例 | 説明 |
|------|-----|------|
| `recent` | `recent.json2` | 最新 |
| `today` | `today.json2` | 本日分 |
| `YYYYMMDD` | `20260304.json2` | 特定日 |
| `YYYYMMDD-YYYYMMDD` | `20260301-20260304.json2` | 期間指定 |
| `{証券コード}` | `7203.json2` | 企業指定 |

### パラメータ
| パラメータ | 説明 |
|-----------|------|
| `limit` | 最大取得件数（デフォルト300） |
| `hasXBRL` | `1`でXBRL付きのみ |

### 検証コマンド

```bash
# 最新の開示情報
curl -s 'https://webapi.yanoshin.jp/webapi/tdnet/list/recent.json2?limit=5' | python3 -m json.tool

# 特定日のXBRL付き開示のみ
curl -s 'https://webapi.yanoshin.jp/webapi/tdnet/list/20260304.json2?hasXBRL=1'

# RSS形式
curl -s 'https://webapi.yanoshin.jp/webapi/tdnet/list/recent.rss?limit=20'
```

### レスポンス例（json2）

```json
{
    "total_count": 1,
    "condition_desc": "2026-03-04に報告された適時開示情報一覧(XBRL)",
    "items": [
        {
            "id": "1230153",
            "pubdate": "2026-03-04 15:00:00",
            "company_code": "18670",
            "company_name": "植木組",
            "title": "業績予想の修正並びに配当予想の修正に関するお知らせ",
            "document_url": "https://www.release.tdnet.info/inbs/140120260304575196.pdf",
            "url_xbrl": "https://www.release.tdnet.info/inbs/091220260304575196.zip",
            "markets_string": "東",
            "update_history": null
        }
    ]
}
```

---

## 4. release.tdnet.info 直接取得

### 4.1 日付別一覧のスクレイピング

```bash
# 日付別ページを取得
curl -s 'https://www.release.tdnet.info/inbs/I_list_001_20260304.html'

# ページ2（100件超の場合）
curl -s 'https://www.release.tdnet.info/inbs/I_list_002_20260304.html'
```

パース対象テーブル: `id="main-list-table"`

### 4.2 検索API

```bash
curl -s -X POST 'https://www.release.tdnet.info/onsf/TDJFSearch/TDJFSearch' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 't0=20260301&t1=20260304&q=決算&m=0'
```

### 4.3 ファイルダウンロード

```bash
# PDF
curl -o document.pdf 'https://www.release.tdnet.info/inbs/140120260304575196.pdf'

# XBRL ZIP
curl -o xbrl.zip 'https://www.release.tdnet.info/inbs/091220260304575196.zip'
```

### 4.4 注意事項

- **robots.txt**: `Disallow: /` （全ページクロール拒否）
- **一覧ページの保持期間**: 約30営業日（~39日で404）
- **⚠️ ファイルの保持期間**: **約2-3営業日のみ**（その後403 Forbidden）
  - 一覧ページにリンクが残っていても、実ファイルは2-3営業日で削除される
  - リアルタイムまたは毎日のバッチでダウンロードする設計が必須
- **利用規約**: 無断転用・複製・販売禁止
- **レート制限**: 明文化なし、1-3秒間隔推奨

---

## 5. 既存のPythonライブラリ

| ライブラリ | GitHub | 特徴 |
|-----------|--------|------|
| tdnet-disclosure-mcp | https://github.com/ajtgjmdjp/tdnet-disclosure-mcp | やのしんAPI利用、MCP対応 |
| tdnet_tool | https://github.com/kurama8103/tdnet_tool | BS4スクレイピング、SQLite保存 |
| jquants-api-client-python | https://github.com/J-Quants/jquants-api-client-python | JPX公式、決算情報 |

---

## 6. 推奨アプローチ

### このプロジェクトでの推奨構成

本プロジェクト（`pyproject.toml`に`httpx`依存あり）では以下の2層アプローチを推奨:

1. **メタデータ取得**: やのしんWEB-API（json2形式）
   - 開示一覧の取得、企業別検索に最適
   - 認証不要、レスポンスが構造化されている

2. **ファイルダウンロード**: release.tdnet.info 直接
   - やのしんAPIが返すURLがrelease.tdnet.infoを指すため自然にこの形になる
   - PDF/XBRLの実ファイルはrelease.tdnet.infoからしか取得できない

### サンプルコード

```python
import httpx
from pathlib import Path

YANOSHIN_BASE = "https://webapi.yanoshin.jp/webapi/tdnet/list"

async def get_xbrl_disclosures(date: str) -> list[dict]:
    """XBRL付き開示情報を取得"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{YANOSHIN_BASE}/{date}.json2",
            params={"hasXBRL": 1, "limit": 300},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

async def download_xbrl(url: str, dest: Path) -> Path:
    """XBRL ZIPをダウンロード"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
```
