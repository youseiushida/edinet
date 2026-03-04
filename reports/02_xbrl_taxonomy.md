# TDnet XBRL / タクソノミ構造レポート

調査日: 2026-03-04

---

## 1. XBRLバージョンとフォーマット

- **XBRL仕様**: XBRL 2.1 (Recommendation 2003-12-31, Errata 2013-02-20適用)
- **iXBRL**: Inline XBRL Part 1: Specification 1.1 (2014年導入)
- **iXBRL名前空間**: `http://www.xbrl.org/2008/inlineXBRL`
- **生成ツール**: `Fujitsu Interstage XWand B0250` / `PRONEXUS WORKS`
- **XBRL開始年**: 2003年（世界初の実用化）、2008年にデータ本格提供
- **XBRL対象書類**: 決算短信（通期・四半期）、業績予想修正、配当予想修正、CG報告書、REIT決算短信

---

## 2. タクソノミサーバ

**ベースURL**: `http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/`

ディレクトリリスティングは403 Forbiddenだが、個別ファイルはアクセス可能。

### 2.1 メインタクソノミスキーマ（要素定義）

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12.xsd
```
- 名前空間: `http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12`
- プレフィックス: `tse-ed-t`
- サイズ: 825行、約200KB
- 最終更新: 2024-06-24

### 2.2 ロールタイプスキーマ

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/o/rt/2014-01-12/tse-ed-rt-2014-01-12.xsd
```
- 名前空間: `http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/o/rt/2014-01-12`
- プレフィックス: `tse-ed-rt`

### 2.3 カスタム型定義

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/o/types/2014-01-12/tse-ed-types-2014-01-12.xsd
```

### 2.4 ラベルファイル（日本語）

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab.xml
```
- 4845行、要素名と日本語ラベルの対応

### 2.5 ラベルファイル（英語）

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab-en.xml
```

### 2.6 公式ドキュメント

- **JPX公式XBRL仕様**: https://www.jpx.co.jp/equities/listing/disclosure/xbrl/03.html
- **タクソノミ説明書PDF**: http://www.xbrl.tdnet.info/doc/taxo_exp_2011-06-30-01.pdf

---

## 3. タクソノミのディレクトリ構造

```
http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/
├── ed/                          # Earnings Disclosure (決算短信)
│   ├── t/                       # Taxonomy elements
│   │   └── 2014-01-12/
│   │       ├── tse-ed-t-2014-01-12.xsd        # メインスキーマ
│   │       ├── tse-ed-t-2014-01-12-lab.xml     # 日本語ラベル
│   │       └── tse-ed-t-2014-01-12-lab-en.xml  # 英語ラベル
│   └── o/                       # Other schemas
│       ├── rt/                  # Role Types
│       │   └── 2014-01-12/
│       │       └── tse-ed-rt-2014-01-12.xsd
│       └── types/               # Custom types
│           └── 2014-01-12/
│               └── tse-ed-types-2014-01-12.xsd
└── (re/?)                       # REIT等他の報告書タイプ
```

---

## 4. XBRL ZIPファイルの2つの構造

### 4.1 タイプA: 簡易XBRL（プレフィックス `0912`）

修正情報（業績予想修正、配当予想修正等）用。フラットなファイル構成。

```
091220260304575196.zip
├── tse-rvfc-18670-20260304575196.xsd         # インスタンススキーマ
├── tse-rvfc-18670-20260304575196-ixbrl.htm   # iXBRLインスタンス
└── tse-rvfc-18670-20260304575196-def.xml     # 定義リンクベース
```

**ファイル命名規則:**
```
tse-{報告書種別}-{証券コード}-{日付}{文書ID}{サフィックス}.{拡張子}
```

- `rvfc` = Revised Forecast（業績予想修正）

### 4.2 タイプB: フル決算XBRL（プレフィックス `0812`）

決算短信用。階層的なフォルダ構成。

```
081220260303574359.zip
└── XBRLData/
    ├── Summary/                                    # サマリー（決算短信1面）
    │   ├── tse-qcedjpsm-47500-20260303347500.xsd
    │   ├── tse-qcedjpsm-47500-20260303347500-ixbrl.htm
    │   └── tse-qcedjpsm-47500-20260303347500-def.xml
    └── Attachment/                                  # 添付資料（財務諸表）
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03.xsd
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03-def.xml
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03-cal.xml
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03-pre.xml
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03-lab.xml
        ├── tse-qcedjpfr-47500-2026-01-20-01-2026-03-03-lab-en.xml
        ├── 0101010-qcbs01-...-ixbrl.htm              # 貸借対照表
        ├── 0102010-qcpl11-...-ixbrl.htm             # 損益計算書
        ├── 0102020-qcci11-...-ixbrl.htm             # 包括利益計算書
        ├── 0103010-qcsg01-...-ixbrl.htm             # 株主資本等変動計算書
        ├── qualitative.htm                           # 定性情報
        ├── manifest.xml                              # ファイル一覧
        └── index.txt                                 # インデックス
```

**Summaryファイル命名:**
```
tse-{報告書}-{証券コード}-{日付}{文書ID}.{拡張子}
```
- `qcedjpsm` = Quarterly Consolidated Earnings Digest JP Summary

**Attachmentファイル命名:**
```
tse-{報告書}-{証券コード}-{期末日}-{提出回数}-{提出日}.{拡張子}
```
- `qcedjpfr` = Quarterly Consolidated Earnings Digest JP Financial Report

**Attachment iXBRLファイルのプレフィックス:**

| プレフィックス | 内容 |
|--------------|------|
| `0101010-qcbs01` | 四半期連結貸借対照表 |
| `0102010-qcpl11` | 四半期連結損益計算書 |
| `0102020-qcci11` | 四半期連結包括利益計算書 |
| `0103010-qcsg01` | 四半期連結株主資本等変動計算書 |

---

## 5. 主要なXBRL要素（タクソノミ要素）

### 5.1 文書・エンティティ情報

| 要素名 | 型 | 説明 |
|--------|-----|------|
| `tse-ed-t:DocumentName` | string | 文書名 |
| `tse-ed-t:FilingDate` | date | 提出日 |
| `tse-ed-t:CompanyName` | string | 会社名 |
| `tse-ed-t:SecuritiesCode` | string | 証券コード |
| `tse-ed-t:URL` | anyURI | 企業URL |
| `tse-ed-t:FASFMemberMark` | boolean | FASF会員マーク |

### 5.2 上場市場

| 要素名 | 説明 |
|--------|------|
| `tse-ed-t:TokyoStockExchangePrime` | 東証プライム |
| `tse-ed-t:TokyoStockExchangeStandard` | 東証スタンダード |
| `tse-ed-t:TokyoStockExchangeGrowth` | 東証グロース |
| `tse-ed-t:NagoyaStockExchange` | 名証 |

### 5.3 財務データ

| 要素名 | 型 | 説明 |
|--------|-----|------|
| `tse-ed-t:ProfitAttributableToOwnersOfParent` | monetary | 親会社に帰属する当期純利益 |
| `tse-ed-t:AmountChangeProfitAttributableToOwnersOfParent` | monetary | 増減額 |
| `tse-ed-t:ChangeInProfitAttributableToOwnersOfParent` | percentage | 増減率 |

### 5.4 iXBRLタグ

```html
<!-- 非数値データ -->
<ix:nonnumeric name="tse-ed-t:SecuritiesCode" contextRef="Context">18670</ix:nonnumeric>

<!-- 数値データ -->
<ix:nonfraction name="tse-ed-t:NetSales" contextRef="Current"
                unitRef="JPY" decimals="-6" scale="6" format="ixt:numdotdecimal">
  12,345
</ix:nonfraction>
```

---

## 6. ロールタイプ（セクション定義）

主要なロール定義（`tse-ed-rt-2014-01-12.xsd`より）:

| ロールID | 説明 |
|---------|------|
| `Role_std_DocumentEntityInformation` | 文書・エンティティ情報 |
| `Role_std_BusinessResultsOperatingResults` | 経営成績 |
| `Role_std_BusinessResultsFinancialPositions` | 財政状態 |
| `Role_std_BusinessResultsCashFlows` | キャッシュ・フロー |
| `Role_std_Dividends` | 配当 |
| `Role_std_Forecasts` | 業績予想 |
| `Role_std_QuarterlyForecasts` | 四半期業績予想 |
| `RoleConsolidatedInformationAnnual` | 連結情報（通期） |
| `RoleConsolidatedInformationQ2YTD` | 連結情報（四半期累計） |
| `RoleNonConsolidatedInformationAnnual` | 個別情報（通期） |
| `RoleNoteFinancialForecastCorrection` | 業績予想修正 |
| `RoleNoteRevisedDividendForecast` | 配当予想修正 |

---

## 7. 検証スクリプト

### タクソノミスキーマの取得

```bash
# メインスキーマ
curl -o taxonomy_main.xsd \
  'http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12.xsd'

# ロールタイプ
curl -o taxonomy_roles.xsd \
  'http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/o/rt/2014-01-12/tse-ed-rt-2014-01-12.xsd'

# ラベル（日本語）
curl -o taxonomy_labels_ja.xml \
  'http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab.xml'

# ラベル（英語）
curl -o taxonomy_labels_en.xml \
  'http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12/tse-ed-t-2014-01-12-lab-en.xml'
```

### サンプルXBRL ZIPの取得・解凍

```bash
# 簡易XBRL（修正情報）
curl -o sample_simple.zip \
  'https://www.release.tdnet.info/inbs/091220260304575196.zip'
unzip sample_simple.zip -d sample_simple/

# フル決算XBRL
curl -o sample_full.zip \
  'https://www.release.tdnet.info/inbs/081220260303574359.zip'
unzip sample_full.zip -d sample_full/
```

---

## 8. JPX公式仕様書・ダウンロード一覧

### 仕様書PDF（直リンク）

| ドキュメント | URL |
|------------|-----|
| 提出書類ファイル仕様書 | https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/File_Specification_for_TDnet_Filing.pdf |
| タクソノミ解説文書（2025-01-31版） | https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/Kaiji_taxonomy_kaisetsu_kessan_2025-01-31.pdf |
| 提出者別タクソノミ作成要領（2025-01-31版） | https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/TeisyutusyaTaxonomy_2025-01-31.pdf |
| 四半期財務諸表タクソノミ管理方針（2025-03） | https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/management_policy_for_quarterly_financial_statement_taxonomy_2025-03.pdf |
| TDnet API仕様書 | https://www.jpx.co.jp/markets/paid-info-listing/tdnet/co3pgt0000005o97-att/tdnetapi_specifications.pdf |
| TDnet APIサービスガイド | https://www.jpx.co.jp/markets/paid-info-listing/tdnet/co3pgt0000005o97-att/TDnetAPI_ServiceGuide.pdf |
| TDnet API利用約款 | https://www.jpx.co.jp/markets/paid-info-listing/tdnet/co3pgt0000005o97-att/TermsTDAPIJ.pdf |

### Swagger仕様書
- 日本語: https://apidoc-tdnet.jpx-dataservice.com/
- 英語: https://apidoc-tdneten.jpx-dataservice.com/

### JPXダウンロードページ
- https://www.jpx.co.jp/equities/listing/disclosure/xbrl/03.html
  - 決算短信タクソノミ（ZIP）
  - CG報告書タクソノミ（ZIP）
  - 四半期財務諸表タクソノミ（ZIP）
  - サンプルインスタンス（ZIP）
  - 項目リスト（ZIP/Excel）

---

## 9. タクソノミプレフィックス命名規則（詳細）

| プレフィックス | 分解 | 意味 |
|--------------|------|------|
| `tse-acedjpsm` | ac + ed + jp + sm | 通期連結・日本基準・サマリー |
| `tse-qcedjpsm` | qc + ed + jp + sm | 四半期連結・日本基準・サマリー |
| `tse-qcedifsm` | qc + ed + if + sm | 四半期連結・IFRS・サマリー |
| `tse-anedjpsm` | an + ed + jp + sm | 通期個別・日本基準・サマリー |
| `tse-qcedjpfr` | qc + ed + jp + fr | 四半期連結・日本基準・財務諸表 |
| `tse-qcediffr` | qc + ed + if + fr | 四半期連結・IFRS・財務諸表 |
| `tse-rvfc` | rvfc | 業績予想修正（Revised Forecast） |

**略語一覧:**
- `ac` = Annual Consolidated（通期連結）
- `qc` = Quarterly Consolidated（四半期連結）
- `an` = Annual Non-consolidated（通期個別）
- `ed` = Earnings Digest（決算短信）
- `jp` = Japanese GAAP（日本基準）
- `if` = IFRS（国際財務報告基準）
- `us` = US GAAP（米国基準）
- `sm` = Summary（サマリー）
- `fr` = Financial Report（財務諸表）

---

## 10. TDnet API詳細（有料）

### エンドポイント
- **書類API**: `https://api.arrowfront.jp/tdfile`
- **認証**: `x-api-key` ヘッダ

### ファイル種別（fileTypeFlag）
| 値 | 意味 |
|-----|------|
| `g` | 全文情報PDF |
| `s` | サマリー情報PDF |
| `x` | XBRLファイル（Base64エンコードZIP） |

---

## 11. 2026年7月1日適用予定の新仕様

JPXは2026年7月1日適用予定の新仕様を公開済み。2026年4月1日以降に開始する四半期会計期間から適用。ライブラリ設計時には新旧両仕様への対応を考慮すべき。

---

## 12. ZIPファイルの制約

- 圧縮後サイズ: **10MB以下**
- 複数フォルダ・サブフォルダの存在は不可（Summary/Attachment除く）
- EDINETタクソノミも併用（特に財務諸表部分: `jppfs_cor` 名前空間等）

---

## 13. iXBRLのみ提供（伝統的XBRLインスタンスなし）

- TDnetのZIPにはInline XBRL（`-ixbrl.htm`）のみ含まれる
- 伝統的なXBRLインスタンス文書（`<xbrli:xbrl>` ルートの `.xbrl` / `.xml`）は提供されない
- `.xml` ファイルはすべてリンクベース（`-def.xml`, `-cal.xml`, `-pre.xml`, `-lab.xml`）
- パーサーは `ix:nonFraction`（数値）と `ix:nonNumeric`（テキスト）の抽出のみで対応可能

---

## 14. Consolidated/NonConsolidated Axis（連結/非連結の区別）

日本XBRLにおける「連結/非連結」の区別はAxis-Memberパターンで表現される共通慣習。
ただしTDnetとEDINETで命名が異なる。

| 項目 | TDnet | EDINET |
|------|-------|--------|
| Axis | `tse-ed-t:ConsolidatedNonconsolidatedAxis` | `ConsolidatedOrNonConsolidatedAxis` |
| 連結 | `tse-ed-t:ConsolidatedMember` | `jppfs_cor:ConsolidatedMember` |
| 非連結 | `tse-ed-t:NonConsolidatedMember` | — |

TDnetタクソノミでは4つのAxisが定義されている:

| Axis | 用途 |
|------|------|
| `ConsolidatedNonconsolidatedAxis` | 連結/非連結の区別 |
| `PreviousCurrentAxis` | 前期/当期の区別 |
| `ResultForecastAxis` | 実績/予想の区別 (Result/Forecast/Upper/Lower) |
| `AnnualDividendPaymentScheduleAxis` | 配当回次 (Q1/Q2/Q3/YearEnd/Annual) |

0812決算短信のAttachment部分ではEDINETタクソノミ（`jppfs_cor`）の`ConsolidatedMember`も併用される。

---

## 15. 過去30日間のXBRL開示種別（実測 2026-03-04）

全2,070件のXBRL付き開示を分類:

| カテゴリ | 件数 | 比率 | ZIPプレフィックス |
|---------|------|------|-----------------|
| 決算短信 | 1,846 | 89.2% | `0812` |
| 業績予想修正 | 170 | 8.2% | `0912` |
| 配当予想修正 | 39 | 1.9% | `0912` |
| その他（業績予想の開示等） | 10 | 0.5% | `0812`, `0912` |
| 配当関連（修正でない） | 3 | 0.1% | `0912` |
| その他修正（REIT分配金等） | 2 | 0.1% | `0912` |

XBRLが添付されるのは決算短信と修正系のみ。自己株式取得、代表者変更、MBO等にはXBRLなし。

---

## 16. サンプルファイル（`samples/` 配下）

取得日: 2026-03-04。iXBRL（`-ixbrl.htm`）と企業拡張スキーマ（`.xsd`）を抽出保存。各ディレクトリにオリジナルZIPも同梱。

### 16.1 決算短信 — 3社（業種違い）

| ディレクトリ | 企業 | 種別 | iXBRL数 | .xsd数 |
|------------|------|------|---------|--------|
| `0812_kessan_daisan` | 47500 ダイサン（建設足場） | Q3決算短信・連結 `qcedjp` | Summary 1 + Attachment 4 | 2 |
| `0812_kessan_eiken` | 72650 エイケン工業（自動車部品） | Q1決算短信・非連結 `qnedjp` | Summary 1 + Attachment 3 | 2 |
| `0812_kessan_people` | 78650 ピープル（玩具） | 通期決算短信・非連結 `anedjp` | Summary 1 + Attachment 5 | 2 |

Attachment iXBRLの内容コード:

| コード | 意味 | 連結(`qc`) | 非連結Q1(`qn`) | 非連結通期(`an`) |
|-------|------|-----------|--------------|----------------|
| `bs` | 貸借対照表 | `0101010-qcbs01` | `1100000-qnbs02` | `0500000-anbs02` |
| `pl` | 損益計算書 | `0102010-qcpl11` | `1200000-qnpl12` | `0501000-anpl02` |
| `ci` | 包括利益計算書 | `0102020-qcci11` | — | — |
| `ss` | 株主資本等変動計算書 | — | — | `0503000-anss02` |
| `cf` | キャッシュフロー計算書 | — | — | `0504000-ancf02` |
| `sg` | セグメント情報 | `0103010-qcsg01` | `1400000-qnsg02` | `0600000-ansg02` |

### 16.2 修正系 — 1社

| ディレクトリ | 企業 | 種別 | iXBRL | .xsd |
|------------|------|------|-------|------|
| `0912_shusei_uekigumi` | 18670 植木組（建設） | 業績予想修正 `rvfc` | 1 | 1 |
