# TDnet サイト構造分析レポート

調査日: 2026-03-04
対象: https://www.release.tdnet.info/

---

## 1. サイト全体構造

TDnetには2つの主要エントリーポイントが存在する。

### 1.1 適時開示情報閲覧サービス（日付ベース一覧）
- **URL**: `https://www.release.tdnet.info/inbs/I_main_00.html`
- **構造**: メインページがiframeで日付別リストを埋め込む
- **サーバ**: Apache
- **キャッシュ**: `Cache-Control: max-age=2`（2秒）、`Pragma: no-cache`
- **Cookie**: `te-w1-pri` セッションCookie が設定される

### 1.2 適時開示情報検索サービス
- **URL**: `https://www.release.tdnet.info/index.html`
- **構造**: iframe で `/onsf/TDJFSearch/I_head` を全画面表示
- **検索フォーム**: POST `/onsf/TDJFSearch/TDJFSearch`
- **英語切替**: パラメータ `m=1` で英語モード

---

## 2. URL体系の詳細

### 2.1 日付別開示一覧ページ

```
https://www.release.tdnet.info/inbs/I_list_{PAGE}_{YYYYMMDD}.html
```

| パラメータ | 説明 | 例 |
|-----------|------|-----|
| `{PAGE}` | ページ番号（3桁ゼロ埋め） | `001`, `002` |
| `{YYYYMMDD}` | 日付 | `20260304` |

- 1ページあたり最大100件表示
- ページネーション例: `I_list_001_20260303.html`（1ページ目）→ `I_list_002_20260303.html`（2ページ目）
- **一覧ページの保持期間**: 約30営業日（200 OK）→ ~39日で404
  - 休日・祝日は空ページ（1779 bytes、テーブルなし）が返る
- **⚠️ ファイルの実アクセス可能期間**: 約2-3営業日のみ
  - 一覧ページにリンクが表示されていても、PDF/XBRLファイル自体は公開後2-3営業日で403 Forbiddenになる
  - 一覧ページの保持期間（~30日）とファイルの保持期間は異なるので注意

**検証コマンド:**
```bash
curl -s 'https://www.release.tdnet.info/inbs/I_list_001_20260304.html' \
  -H 'User-Agent: Mozilla/5.0' | head -60
```

### 2.2 開示資料PDF

```
https://www.release.tdnet.info/inbs/{PREFIX}{YYYYMMDD}{DOCID}.pdf
```

| プレフィックス | 意味 |
|--------------|------|
| `1401` | PDF開示資料（最も一般的） |

**例:**
- `140120260304575196.pdf` → 2026/03/04付 文書ID 575196 のPDF

### 2.3 XBRL ZIPファイル

```
https://www.release.tdnet.info/inbs/{PREFIX}{YYYYMMDD}{DOCID}.zip
```

| プレフィックス | 意味 | ZIP内部構造 |
|--------------|------|------------|
| `0912` | 業績予想修正・配当予想修正等のXBRL | フラットファイル（3ファイル） |
| `0812` | 決算短信（フル決算）のXBRL | `XBRLData/Summary/` + `XBRLData/Attachment/` |

**例:**
- `091220260304575196.zip` → 修正情報のXBRL（フラット構造）
- `081220260303574359.zip` → 決算短信のXBRL（階層構造）

### 2.4 ドキュメントID体系

ファイル名: `{PREFIX}{YYYYMMDD}{DOCID}.{ext}`

- `PREFIX`: 4桁（文書種別を示す）
- `YYYYMMDD`: 8桁（日付）
- `DOCID`: 6桁（開示文書ID、一意識別子）

同一の `YYYYMMDD + DOCID` が PDF と ZIP で共有される:
- `140120260304575196.pdf` ← PDF版
- `091220260304575196.zip` ← XBRL版（同じ 575196）

---

## 3. 検索API

### 3.1 エンドポイント

```
POST https://www.release.tdnet.info/onsf/TDJFSearch/TDJFSearch
Content-Type: application/x-www-form-urlencoded
```

### 3.2 パラメータ

| パラメータ | 型 | 説明 | 例 |
|-----------|------|------|-----|
| `t0` | string | 検索開始日（YYYYMMDD） | `20260301` |
| `t1` | string | 検索終了日（YYYYMMDD） | `20260304` |
| `q` | string | キーワード（コード/会社名/表題） | `決算` |
| `m` | int | 言語モード（0=日本語, 1=英語） | `0` |

### 3.3 検証コマンド

```bash
curl -s -X POST 'https://www.release.tdnet.info/onsf/TDJFSearch/TDJFSearch' \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 't0=20260302&t1=20260304&q=決算&m=0'
```

### 3.4 レスポンス形式

HTML形式で返却される。テーブル構造は一覧ページと類似。
- 日付+時刻が `2026/03/04 14:00` 形式で表示（一覧ページでは時刻のみ）
- PDFリンクは `/inbs/140120260304575442.pdf` のように絶対パス

---

## 4. HTMLテーブル構造（パース対象）

### 4.1 一覧ページ（`I_list_*.html`）

テーブルID: `main-list-table`

| CSSクラス | カラム | 内容 |
|----------|--------|------|
| `kjTime` | 時刻 | `15:00` |
| `kjCode` | コード | `18670` |
| `kjName` | 会社名 | `植木組` |
| `kjTitle` | 表題 | `<a href="140120260304575196.pdf">タイトル</a>` |
| `kjXbrl` | XBRL | `<a href="091220260304575196.zip">XBRL</a>` or 空 |
| `kjPlace` | 上場取引所 | `東`, `東名` 等 |
| `kjHistroy` | 更新履歴 | 空 or 更新情報 |

行のCSSクラス:
- `oddnew-*` / `evennew-*`: 新規表示（通常）
- `odd-*` / `even-*`: （更新表示の可能性）

### 4.2 検索結果ページ

テーブルID: `maintable`

| CSSクラス | カラム |
|----------|--------|
| `time` | 日時（`2026/03/04 14:00`） |
| `code` | コード |
| `companyname` | 会社名 |
| `title` | 表題 |
| `xbrl` | XBRL |
| `exchange` | 上場取引所 |
| `update` | 更新履歴 |

---

## 5. JavaScriptファイル

### 5.1 `/inbs/js/I_JAVASCRIPT.js`
- ページ遷移関数（`pageChange`, `pager`, `pagerLink`）
- 検索ウィンドウオープン（`openSearch`）
- ページ更新（`renewalPage`）
- キーボード/マウス制御（BackSpace, F5, Ctrl+R 等を無効化）

### 5.2 `/onsf/js/I_JAVASCRIPT.js`
- 検索ページ版のJS（同様のキー制御 + 英語切替機能）

### 5.3 `/inbs/js/TDJEModal.js`
- モーダルダイアログ表示用

---

## 6. レスポンスヘッダ分析

```
Server: Apache
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Cache-Control: max-age=2  (一覧ページ)
Cache-Control: private, max-age=3136  (ZIPファイル: ~52分)
Content-Type: text/html  (HTML)
Content-Type: application/zip  (ZIP)
```

- **認証不要**: 一覧ページは公開アクセス可能だが、PDF/XBRLファイルは公開後2-3営業日で403になる
- **CORS**: 未設定（ブラウザからのクロスオリジンリクエストは不可）
- **レート制限**: 明示的なヘッダなし（ただし過度なアクセスは避けるべき）

---

## 7. 免責事項（利用規約）

`/inbs/js/I_MENSEKI.js` より:

> 適時開示情報閲覧サービスに記載されている内容は、著作物として著作権法により保護されており、
> 株式会社東京証券取引所に無断で転用、複製又は販売等を行うことは固く禁じます。

**注意**: 個人利用での閲覧・分析は一般的に許容されるが、再配布や商用利用には制約がある。
