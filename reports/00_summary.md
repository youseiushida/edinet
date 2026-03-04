# TDnet 調査サマリー

調査日: 2026-03-04
目的: tdnet用Pythonライブラリ構築のための事前調査

---

## 調査結果ファイル一覧

| ファイル | 内容 |
|---------|------|
| `reports/01_site_structure.md` | TDnetサイト構造分析（URL体系、API、HTML構造） |
| `reports/02_xbrl_taxonomy.md` | XBRL/タクソノミ構造（ZIP構造、スキーマ、要素定義） |
| `reports/03_stable_retrieval.md` | 安定的な取得方法（API比較、コード例） |
| `reports/verify_tdnet.py` | 検証用スクリプト |

---

## 重要な発見事項

### 1. TDnetのURL体系は予測可能で安定している

- **日付別一覧**: `https://www.release.tdnet.info/inbs/I_list_{PAGE}_{YYYYMMDD}.html`
- **PDF**: `https://www.release.tdnet.info/inbs/1401{YYYYMMDD}{DOCID}.pdf`
- **XBRL**: `https://www.release.tdnet.info/inbs/{0812|0912}{YYYYMMDD}{DOCID}.zip`
- **検索API**: `POST https://www.release.tdnet.info/onsf/TDJFSearch/TDJFSearch`
  - パラメータ: `t0`, `t1`, `q`, `m`

### 2. XBRLには2種類のZIP構造がある

| プレフィックス | 用途 | 構造 |
|--------------|------|------|
| `0812` | 決算短信 | `XBRLData/Summary/` + `XBRLData/Attachment/`（階層型） |
| `0912` | 修正情報 | フラット（3ファイル: .xsd, -ixbrl.htm, -def.xml） |

### 3. タクソノミは公開アクセス可能

- **ベースURL**: `http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/`
- **メインスキーマ**: `ed/t/2014-01-12/tse-ed-t-2014-01-12.xsd`
- **名前空間**: `http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12`
- **プレフィックス**: `tse-ed-t`
- 日本語/英語ラベルファイルあり

### 4. 4つの取得方法が利用可能

| 方法 | コスト | おすすめ度 |
|------|--------|-----------|
| **やのしんWEB-API** | 無料 | ライブラリ構築に最適 |
| JPX公式 TDnet API | 月7万円~ | 商用利用向け |
| J-Quants API | 無料~ | 決算データのみ |
| 直接スクレイピング | 無料 | robots.txt違反に注意 |

### 5. ⚠️ ファイル保持期間は約2-3営業日（重要）

- 一覧ページ（`I_list_*`）は約30営業日保持されるが、**PDF/XBRLファイル自体は公開後2-3営業日で403 Forbiddenになる**
- 一覧ページにリンクが残っていてもファイルにはアクセスできない
- リアルタイムまたは毎日バッチでダウンロードする設計が必須
- やのしんAPIのメタデータは365日以上保持されるが、URLが指すファイルは同様に403になる

### 6. robots.txtは全拒否だが技術的にはアクセス可能

- `User-agent: * / Disallow: /` だが、HTTP直接アクセスにブロック機能なし
- 常識的なレート制限（1-3秒間隔）を守る必要あり
- 商用利用には公式APIを推奨

---

## ライブラリ設計への示唆

### 推奨アーキテクチャ

```
tdnet/
├── client.py          # HTTPクライアント（httpx）
├── models.py          # データモデル（Disclosure, Company等）
├── parsers/
│   ├── html.py        # HTML一覧ページのパーサー
│   ├── xbrl.py        # XBRLパーサー
│   └── search.py      # 検索結果パーサー
├── sources/
│   ├── yanoshin.py    # やのしんWEB-API
│   ├── tdnet.py       # release.tdnet.info直接
│   └── base.py        # 共通インターフェース
└── taxonomy/
    └── loader.py      # タクソノミスキーマのローダー
```

### 優先実装順序

1. やのしんWEB-API経由のメタデータ取得（JSON、パース不要）
2. PDF/XBRLファイルのダウンロード
3. XBRL ZIPの解凍・構造解析
4. iXBRLパース（BeautifulSoup/lxml）
5. タクソノミスキーマの活用
6. release.tdnet.info直接スクレイピング（フォールバック用）

---

## 一次情報URL一覧

### TDnet本体
- 閲覧サービス: https://www.release.tdnet.info/inbs/I_main_00.html
- 検索サービス: https://www.release.tdnet.info/index.html

### 公式ドキュメント
- JPX XBRL仕様ページ: https://www.jpx.co.jp/equities/listing/disclosure/xbrl/03.html
- JPX XBRL仕様ページ(英語): https://www.jpx.co.jp/english/equities/listing/disclosure/xbrl/03.html
- タクソノミ説明書: http://www.xbrl.tdnet.info/doc/taxo_exp_2011-06-30-01.pdf
- TDnet API仕様(Swagger): https://apidoc-tdnet.jpx-dataservice.com/

### タクソノミ
- メインスキーマ: http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12.xsd
- ロールタイプ: http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/o/rt/2014-01-12/tse-ed-rt-2014-01-12.xsd
- 日本語ラベル: http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab.xml
- 英語ラベル: http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab-en.xml

### 非公式API
- やのしんWEB-API: https://webapi.yanoshin.jp/tdnet/

### 参考記事
- TDnetのXBRLデータで比較: https://qiita.com/XBRLJapan/items/31fb4e89031c1b267cf8
- 決算短信XBRLファイルの読み込み: https://qiita.com/Fortinbras/items/0c0f9154a9cd543653a8
- TDnet XBRL解析: https://qiita.com/maskot1977/items/d741d980df2f8b7ac41a
- Python EDINET/TDNET XBRL DL: https://qiita.com/9uant/items/14e5686103f48d4d14c3

### 既存ツール
- tdnet-disclosure-mcp: https://github.com/ajtgjmdjp/tdnet-disclosure-mcp
- tdnet_tool: https://github.com/kurama8103/tdnet_tool
- jquants-api-client-python: https://github.com/J-Quants/jquants-api-client-python
