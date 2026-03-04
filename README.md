# edinet — EDINET XBRL 財務データ Python ライブラリ

[![PyPI version](https://img.shields.io/pypi/v/edinet.svg)](https://pypi.org/project/edinet/)
[![Python](https://img.shields.io/pypi/pyversions/edinet.svg)](https://pypi.org/project/edinet/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Context7 Indexed](https://img.shields.io/badge/Context7-Indexed-047857)](https://context7.com/youseiushida/edinet)
[![Context7 llms.txt](https://img.shields.io/badge/Context7-llms.txt-047857)](https://context7.com/youseiushida/edinet/llms.txt)


**edinet** は、[EDINET（金融庁 電子開示システム）](https://disclosure.edinet-fsa.go.jp/)の開示データを Python から扱うためのライブラリです。書類一覧の取得から XBRL パース、財務三表（PL/BS/CF）の組み立て、会計基準の自動判別、23 業種対応、タクソノミラベル解決、DataFrame 変換までをワンストップで提供します。全 42 書類タイプに対応し、J-GAAP / IFRS / US-GAAP の 3 会計基準を統一的に扱えます。内部の HTTP 通信には [httpx](https://github.com/encode/httpx) を使用しています。

[GitHub Repository](https://github.com/youseiushida/edinet)

## 財務・非財務データ基盤 徹底比較マトリクス

「edinet」ライブラリは、既存のAPIや高額な商用ベンダーとは異なるアプローチ（XBRLのグラフ探索）で財務データを抽出します。それぞれの強みと、依然として商用ベンダーに分がある領域（弱み）を整理しました。

| 比較軸 | edinet (本ライブラリ) | 国内API (jquants等) | 国内商用プラットフォーム (SPEEDA, AstraManager等) | グローバルTier1ベンダー (Bloomberg, FactSet等) |
| :--- | :--- | :--- | :--- | :--- |
| **コスト** | **無料**（自社インフラ代のみ） | 月額数千〜数万円 | 年間約150万〜（法人契約・1アカウント、要問い合わせ） | 年間約450〜500万〜/1端末 |
| **名寄せの仕組み** | **辞書引き＋リンクベース推論の4段パイプライン（100%決定論的）** | 金融庁標準CSVベース（独自科目除外） | ベンダー側の人海戦術 ＋ 独自アルゴリズム | グローバル標準への強制マッピング（アナリスト手作業含む） |
| **データ反映ラグ** | **EDINET公開直後（パース約0.85秒/社）** | 数時間〜1日（サマリーは早い） | 数時間〜数日（深掘りデータほど遅い） | 同上（主要指標は早いが、注記やESGは遅延する） |
| **粒度（解像度）** | **独自科目・セグメントを完全保持** | 標準科目のみ（丸め込み） | 業界比較のために丸め込まれる | グローバル比較のために丸め込まれる（日本固有の文脈が消える） |
| **透明性（トレース）** | **完全（XBRL行番号、概念名まで追跡可能）** | 不可（ブラックボックス） | 不可（ベンダーの調整後数値） | 不可（「なぜこの値？」の検証にベンダーへの問い合わせが必要） |
| **ESG / 非財務** | **設定（CK追加）次第で無限に抽出可能** | ほぼ非対応 | 別途プレミアムオプション（高額） | 充実しているが、独自のESGスコア化ブラックボックスが強い |
| **[壁] 過去データの蓄積** | 直近数年〜次世代EDINET以降（調整は自前） | プラン依存：ライト5年〜プレミアム約15年（株式分割等は調整済み） | 20年以上の蓄積（コーポレートアクション調整済み） | Bloomberg 30年超、FactSet/LSEG等は20年程度（ベンダー差あり、コーポレートアクション調整済み） |
| **[壁] 市場データ連携** | なし（財務・非財務特化。株価等は別途取得）| あり（株価API等とIDで容易に結合可能） | あり（プラットフォーム上で完結） | 完璧（Tickデータ、コンセンサス、マクロ指標とシームレスに結合） |
| **[壁] 対象カバレッジ** | 日本国内のみ（EDINET提出企業） | 日本国内のみ | 国内中心〜一部アジア・グローバル | 全世界の主要取引所上場企業を網羅 |

### edinet の戦略的ポジショニング

edinet は「世界中の株価と業績を比較するツール」ではありません。日本の開示制度（EDINETタクソノミ）の仕様を極限までハックし、**「日本企業が市場に提出した生の構造化データから、商用ベンダーが切り捨てたアルファ（情報の非対称性）を最速で抽出する最上流エンジン」**です。市場データ連携や過去の株式分割調整などは、本ライブラリの出力結果を元に、利用者側（データサイエンティスト）のパイプラインで解決する設計思想です。

## インストール

```sh
pip install edinet
```

オプション依存:

```sh
# pandas + Parquet 連携
pip install 'edinet[analysis]'

# Rich ターミナル表示
pip install 'edinet[display]'

# 全部入り
pip install 'edinet[analysis,display]'
```

## 設定

### 必要なもの

| 項目 | 用途 | 必須？ |
|:---|:---|:---|
| **EDINET API キー** | 書類一覧・ZIP ダウンロード | 必須 |
| **EDINET タクソノミ** | XBRL 解析（三表・ラベル・CK 抽出すべて） | **XBRL 解析に必須** |
| キャッシュディレクトリ | ZIP の再ダウンロード防止 | 任意（推奨） |

> **注意**: タクソノミなしでも企業検索（`Company.search`）、書類一覧（`documents()`）、PDF 取得（`fetch_pdf()`）は動作しますが、`filing.xbrl()` 以降の全機能（三表取得・ラベルアクセス・DataFrame 変換・extract_values 等）にはタクソノミが必要です。

### タクソノミのセットアップ

1. [金融庁の EDINET タクソノミページ](https://www.fsa.go.jp/search/20250808.html)から「EDINET タクソノミ」の ZIP をダウンロード（年度により URL が変わります）
2. ZIP を展開すると、中に `taxonomy/` と `samples/` を子に持つフォルダがあります:
   ```
   （ZIP を展開）
   └── ○○○/                ← フォルダ名は年度により異なる
       ├── taxonomy/        ← タクソノミ本体
       └── samples/         ← サンプルインスタンス
   ```
3. `taxonomy/` と `samples/` の**親フォルダ**のパスを指定:

```python
import edinet

edinet.configure(
    api_key="YOUR_API_KEY",
    taxonomy_path="/path/to/○○○",  # ← taxonomy/ の親
    cache_dir="./cache",           # 任意（推奨）
)
```

### API キーの取得

[EDINET](https://disclosure.edinet-fsa.go.jp/) にアカウント登録し、API キーを取得してください。


## クイックスタート

```python
import edinet

edinet.configure(
    api_key="YOUR_API_KEY",
    taxonomy_path="/path/to/○○○"
)

# 有価証券報告書の一覧を取得
filings = edinet.documents("2025-06-26", doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)

# 最初の XBRL 付き Filing から財務諸表を取得
for filing in filings:
    if filing.has_xbrl:
        stmts = filing.xbrl()
        pl = stmts.income_statement()
        bs = stmts.balance_sheet()
        cf = stmts.cash_flow_statement()

        print(f"{filing.filer_name}（{filing.ticker}）")
        print(f"  売上高: {pl['売上高'].value:,}")

        # extract_values を使えば会計基準・ラベル表記を問わず取得可能
        from edinet import extract_values, CK
        result = extract_values(stmts, [CK.OPERATING_INCOME, CK.TOTAL_ASSETS])
        print(f"  営業利益: {result[CK.OPERATING_INCOME].value:,}")
        print(f"  総資産: {result[CK.TOTAL_ASSETS].value:,}")
        break
```

## 企業検索

11,000 社超の EDINET コードマスタを内蔵しています。企業名・銘柄コード・EDINET コードから検索できます。

```python
from edinet import Company

# 企業名で検索（部分一致、複数ヒット）
results = Company.search("トヨタ自動車")
toyota = results[0]
print(toyota.name_ja)      # "トヨタ自動車株式会社"
print(toyota.ticker)       # "7203"

# 銘柄コードから
sony = Company.from_sec_code("6758")

# EDINET コードから
company = Company.from_edinet_code("E02144")

# 最新の有報を取得（デフォルト: 過去90日間を検索）
filing = toyota.latest(doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
if filing is not None:
    stmts = filing.xbrl()
```

## 書類タイプ

全 42 書類タイプを `DocType` enum で定義しています。日本語名や訂正関係もプロパティで取得できます。

```python
from edinet import DocType

dt = DocType.ANNUAL_SECURITIES_REPORT
print(dt.name_ja)        # "有価証券報告書"
print(dt.is_correction)  # False

# 訂正報告書から元の書類を辿る
corrected = DocType.AMENDED_ANNUAL_SECURITIES_REPORT
print(corrected.original)  # DocType.ANNUAL_SECURITIES_REPORT

# 書類タイプでフィルタして取得
filings = edinet.documents("2025-06-26", doc_type=DocType.ANNUAL_SECURITIES_REPORT)
```

## 書類タイプ別のアクセス方法

書類タイプに応じて 3 つのアクセス層を使い分けます。

| 書類 | 例 | アクセス方法 |
|:---|:---|:---|
| **有報系**（7 タイプ） | 有報、四半期報告書、半期報告書 | `stmts.income_statement()` 等で三表取得 |
| **その他 XBRL 書類**（27 タイプ） | 大量保有報告書、公開買付届出書、臨時報告書 | `stmts["ラベル名"]` で全 Fact にアクセス |
| **PDF のみ**（8 タイプ） | 有価証券通知書、届出の取下げ | `filing.fetch_pdf()` でバイナリ取得 |

```python
# 有報系: 三表 + ラベルアクセス
stmts = filing.xbrl()
pl = stmts.income_statement()
pl["売上高"].value

# 大量保有報告書など: ラベルで直接アクセス（三表なし）
stmts = filing.xbrl()
ratio = stmts.get("保有割合の合計")
stmts.search("保有")  # キーワードで部分一致検索

# PDF のみの書類
pdf_bytes = filing.fetch_pdf()
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)
```

## 財務諸表

### 三表の取得

```python
stmts = filing.xbrl()

# 連結・当期（デフォルト）
pl = stmts.income_statement()
bs = stmts.balance_sheet()
cf = stmts.cash_flow_statement()

# 前期
pl_prior = stmts.income_statement(period="prior")

# 個別
pl_solo = stmts.income_statement(consolidated=False)
```

### 科目アクセス

日本語ラベル・英語ラベル・concept 名のいずれでも**完全一致**でアクセスできます。

```python
# 日本語ラベルで取得（完全一致）
item = pl["売上高"]
print(item.value)          # Decimal('1234567000000')
print(item.unit_ref)       # "JPY"

# 英語ラベル / concept 名でも OK
item = pl["Net sales"]
item = pl["NetSales"]

# 安全なアクセス（KeyError を避ける）
item = pl.get("売上高")  # LineItem | None
```

> **注意**: `get()` / `__getitem__` はタクソノミの**正式ラベルとの完全一致**です。
> 例えば `pl.get("営業利益")` は `None` を返します（正式ラベルは `"営業利益又は営業損失（△）"`）。
> 正式ラベルが分からない場合は `search()` で部分一致検索するか、
> `extract_values()` で canonical key を指定してください。

```python
# 部分一致検索: ラベルにキーワードを含む全科目を返す
hits = stmts.search("営業利益")
print(hits[0].label_ja.text)  # "営業利益又は営業損失（△）"

# canonical key: 会計基準・ラベル表記に依存しない安定的な取得方法
from edinet import extract_values, CK
result = extract_values(stmts, [CK.OPERATING_INCOME])
print(result[CK.OPERATING_INCOME].value)  # 確実に取得
```

### 会計基準の自動判別

会計基準は DEI から自動判別されます。J-GAAP・IFRS・US-GAAP のいずれでも同じ API で操作できます。

```python
print(stmts.detected_standard)       # "J-GAAP"
print(repr(stmts.detected_standard))  # DetectedStandard(standard=<...>, method=<DEI>, ...)

# IFRS 企業でも同じコードで動く
sony_stmts = sony_filing.xbrl()
sony_pl = sony_stmts.income_statement()
sony_pl["売上収益"].value  # IFRS の Revenue
```

### 2つのデータ取得方式

財務データの取得には 2 つの方式があります。用途に応じて使い分けてください。

| | `income_statement()` 等 | `extract_values()` |
|:---|:---|:---|
| **データソース** | Presentation Linkbase（タクソノミ定義） | パイプラインマッパー（Summary → Statement） |
| **取得範囲** | タクソノミ標準科目（提出者拡張は除外） | 主要指標（売上高・営業利益・のれん・有利子負債等） |
| **表示順** | タクソノミの表示順序付き | なし（辞書） |
| **基準横断** | 基準ごとに科目名が異なる | 基準を問わず同じキーで取得 |
| **用途** | 財務諸表の表示・分析 | スクリーナー・DB 永続化・複数企業の横並び比較 |

```python
# 方式1: 財務諸表として取得（タクソノミ標準科目・表示順付き）
pl = stmts.income_statement()
for item in pl:
    print(f"{item.label_ja.text}: {item.value}")

# 方式2: 正規化キーで横断取得（主要指標・基準不問）
result = extract_values(stmts, [CK.REVENUE, CK.TOTAL_ASSETS])
```

### 正規化キーによる基準横断アクセス

canonical key (CK) を使うと、会計基準を意識せずに値を取得できます。スクリーナーや DB 永続化に最適です。

```python
from edinet import extract_values, extracted_to_dict, CK

stmts = filing.xbrl()

# 当期・連結（デフォルト: period=None, consolidated=None で全期間・全区分から先頭マッチ）
result = extract_values(stmts, [CK.REVENUE, CK.OPERATING_INCOME, CK.GOODWILL])

# 当期・連結を明示指定
result = extract_values(stmts, [CK.REVENUE], period="current", consolidated=True)

# 前期
result = extract_values(stmts, [CK.REVENUE], period="prior")

# 個別（非連結）
result = extract_values(stmts, [CK.REVENUE], consolidated=False)

rev = result[CK.REVENUE]
print(rev.value)                 # Decimal('1234567000000')
print(rev.mapper_name)           # "summary_mapper" / "statement_mapper"
print(rev.item.label_ja.text)    # "売上高"（J-GAAP）or "売上収益"（IFRS）
print(rev.item.local_name)       # マッチした concept 名

# マッパー名でフィルタ（summary のみ信頼）
safe = {k: v for k, v in result.items() if v and v.mapper_name == "summary_mapper"}

# Summary のみ（PL/BS/CF 本体からの補完を無効化）
from edinet import summary_mapper
result = extract_values(stmts, [CK.REVENUE], mapper=[summary_mapper])

# pandas で複数企業を横並び
import pandas as pd

keys = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME, CK.TOTAL_ASSETS]
df = pd.DataFrame([
    {
        "ticker": f.ticker,
        "filer": f.filer_name,
        **extracted_to_dict(extract_values(f.xbrl(), keys, period="current", consolidated=True)),
    }
    for f in filings if f.has_xbrl
])
```

#### パラメータ

| パラメータ | デフォルト | 説明 |
|:---|:---|:---|
| `keys` | `None` | 抽出するキー。`None` で全マッピング可能科目 |
| `period` | `None` | `"current"` / `"prior"` / `None`（全期間から先頭マッチ） |
| `consolidated` | `None` | `True`（連結）/ `False`（個別）/ `None`（全区分） |
| `mapper` | `None` | マッパーまたはリスト。`None` で `[summary_mapper, statement_mapper, definition_mapper(), calc_mapper()]` |

#### パイプラインマッパー

`extract_values()` はマッパーのパイプライン（リスト）で名寄せを行います。パイプラインの先頭マッパーほど高優先です。

| デフォルトマッパー | `mapper_name` | データソース | 優先度 |
|:---|:---|:---|:---|
| `summary_mapper` | `"summary_mapper"` | SummaryOfBusinessResults（義務記載） | 最高 |
| `statement_mapper` | `"statement_mapper"` | PL/BS/CF 本体 + 注記（辞書 → 正規化） | 高 |
| `definition_mapper()` | `"definition_mapper"` | Definition Linkbase（general-special で標準概念に遡上） | 中 |
| `calc_mapper()` | `"calc_mapper"` | Calculation Linkbase（summation-item で親標準概念に遡上） | 低 |

カスタムマッパーを追加してパイプラインを拡張できます:

```python
from edinet import extract_values, summary_mapper, statement_mapper, dict_mapper

# Excel/CSV のマッピングテーブルをそのまま利用
my_mapper = dict_mapper({"MyCustomRevenue": "revenue"}, name="my_rules")

# カスタム → summary → statement の順で評価
result = extract_values(stmts, mapper=[my_mapper, summary_mapper, statement_mapper])
```

`definition_mapper()` / `calc_mapper()` はファクトリ関数です。デフォルト（`lookup=None`）では、リンクベースで遡上した標準概念名を `statement_mapper` と同じ組み込み辞書（statement_mappings）で CK に変換します。summary_mappings は使用しません（リンクベースの祖先にサマリー概念は出現しないため）。`lookup` 引数を指定すると、この辞書引きを任意の関数に差し替えられます:

```python
from edinet import definition_mapper, calc_mapper, dict_mapper, extract_values

# 独自の名寄せ辞書
my_map = {"NetSales": "売上高", "OperatingIncome": "営業利益"}

# リンクベース解決にも同じ辞書を適用
pipeline = [
    dict_mapper(my_map),
    definition_mapper(lookup=my_map.get),
    calc_mapper(lookup=my_map.get),
]
result = extract_values(stmts, mapper=pipeline)
```

## DataFrame 変換・エクスポート

```python
# FinancialStatement → DataFrame
df = pl.to_dataframe()
# → columns: label_ja, label_en, value, unit, concept

# 全カラム表示（トレーサビリティ情報込み）
df = pl.to_dataframe(full=True)
# → 18 columns: concept, namespace_uri, source_line, period_start, ...

# エクスポート
pl.to_csv("pl.csv")
pl.to_parquet("pl.parquet")
pl.to_excel("pl.xlsx")

# Statements 全体を DataFrame 化
df_all = stmts.to_dataframe()
```

## Rich ターミナル表示

```python
from rich.console import Console

# 財務諸表を階層表示
Console().print(pl)
```

## Jupyter 表示

```python
# セルに pl を置くだけで HTML テーブルが表示される
pl  # _repr_html_ 対応
```

## テキストブロック（LLM 連携）

有報のテキストセクション（事業等のリスク、MD&A 等）を構造的に抽出し、LLM に渡せます。

```python
from edinet.xbrl.text import extract_text_blocks, build_section_map, clean_html

blocks = extract_text_blocks(parsed.facts, context_map)
sections = build_section_map(blocks, resolver)

# セクション名でアクセス（tuple[TextBlock, ...] が返る）
risk_blocks = sections["事業等のリスク"]
clean_text = clean_html(risk_blocks[0].html)  # HTML → プレーンテキスト
```

## タクソノミ・リンクベース

### ラベル解決

```python
from edinet.xbrl.taxonomy import TaxonomyResolver

resolver = TaxonomyResolver(taxonomy_path)
label = resolver.resolve("jppfs_cor", "NetSales", lang="ja")
print(label.text)    # "売上高"
print(label.source)  # LabelSource.STANDARD
```

### Linkbase 解析

```python
from edinet.xbrl.linkbase import (
    parse_presentation_linkbase,
    parse_calculation_linkbase,
    parse_definition_linkbase,
    parse_footnote_links,
)

# Presentation: 表示順序の木構造
pres_trees = parse_presentation_linkbase(pres_xml_bytes)

# Calculation: 計算関係（親子の加減算）
calc_lb = parse_calculation_linkbase(calc_xml_bytes)

# Definition: Dimension 定義（軸・ドメイン・メンバー）
def_trees = parse_definition_linkbase(def_xml_bytes)

# Footnotes: 脚注リンク
footnote_map = parse_footnote_links(parsed.footnote_links)
```

### ConceptSet 自動導出

Presentation Linkbase をスキャンして 23 業種 × PL/BS/CF/SS/CI の科目セットを自動導出します。

```python
from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets, StatementType

registry = derive_concept_sets(taxonomy_path)
cs = registry.get(StatementType.INCOME_STATEMENT, consolidated=True, industry_code="cai")
for entry in cs.concepts[:5]:
    print(entry.concept, entry.depth, entry.is_total)
```

## 計算検証

Calculation Linkbase に基づき、親科目 = Σ(子科目 × weight) の整合性を検証します。

```python
from edinet import validate_calculations

result = validate_calculations(pl, calc_linkbase)
print(result.is_valid)       # True / False
print(result.checked_count)  # 検証した計算関係の数

for issue in result.issues:
    print(f"{issue.parent_concept}: 差額 {issue.difference}")
```

## 訂正チェーン

訂正報告書の連鎖を自動的に辿り、最新版や任意時点のスナップショットを取得できます。

```python
from edinet import build_revision_chain

chain = build_revision_chain(filing)
print(chain.is_corrected)    # True（訂正あり）
print(chain.count)           # チェーンの長さ

original = chain.original    # 原本
latest = chain.latest        # 最新（訂正済み）

# バックテスト用: 特定日時点のスナップショット
snapshot = chain.at_time(datetime(2025, 9, 1))
```

## 訂正差分・期間差分

```python
from edinet import diff_revisions, diff_periods

# 訂正前 vs 訂正後の Fact レベル差分
result = diff_revisions(original_stmts, corrected_stmts)
for item in result.modified:
    print(f"{item.label_ja.text}: {item.old_value} → {item.new_value}")

# 前期 vs 当期の科目増減
pl_prior = stmts.income_statement(period="prior")
pl_current = stmts.income_statement(period="current")
period_diff = diff_periods(pl_prior, pl_current)
print(period_diff.summary())  # "追加: 2, 削除: 1, 変更: 3, 変更なし: 50"
```

## セグメント分析

事業セグメント・地域セグメント等の多次元データを構造的に取得できます。

```python
from edinet import list_dimension_axes, extract_segments

# 利用可能な Dimension 軸を確認
axes = list_dimension_axes(stmts)
for axis in axes:
    print(f"{axis.label_ja}: {axis.member_count} メンバー")

# 事業セグメントのデータを抽出
segments = extract_segments(stmts, axis_local_name="OperatingSegmentsAxis")
for seg in segments:
    print(f"{seg.name}: {len(seg.items)} 科目")
```

## 非標準科目の判定

提出者が独自に追加した科目を識別し、標準タクソノミの祖先概念を推定します。

```python
from edinet import detect_custom_items

result = detect_custom_items(stmts)
print(f"標準科目: {len(result.standard_items)}")
print(f"独自科目: {len(result.custom_items)} ({result.custom_ratio:.1%})")

for ci in result.custom_items:
    print(f"  {ci.item.label_ja.text} → 標準祖先: {ci.parent_standard_concept}")
```

Calculation Linkbase から提出者拡張科目のみを抽出することもできます。

```python
from edinet import find_custom_concepts

custom_concepts = find_custom_concepts(calc_linkbase)
print(f"拡張科目数: {len(custom_concepts)}")
```

## 変則決算の判定

6ヶ月決算・15ヶ月決算等の変則決算を検出します。スクリーニング時の期間比較に必要です。

```python
from edinet import detect_fiscal_year

info = detect_fiscal_year(dei)
print(info.period_months)    # 12（通常）/ 6, 15 等（変則）
print(info.is_irregular)     # True なら変則決算
print(info.is_full_year)     # True なら通年
print(info.start_date)       # 会計期間の開始日
print(info.end_date)         # 会計期間の終了日
```

## 従業員情報

「従業員の状況」から人数・平均年齢・平均勤続年数・平均年間給与を抽出します。

```python
from edinet.financial.notes.employees import extract_employee_info

info = extract_employee_info(stmts)
if info is not None:
    print(info.count)                     # 従業員数
    print(info.average_age)               # 平均年齢
    print(info.average_service_years)     # 平均勤続年数
    print(info.average_annual_salary)     # 平均年間給与（円）
```

## Filing サマリー

```python
from edinet import build_summary

summary = build_summary(stmts)
print(summary.accounting_standard)  # "Japan GAAP"
print(summary.total_items)          # 3247
print(summary.standard_item_ratio)  # 0.89
print(summary.segment_count)        # 4
```

## 非同期クライアント

全 I/O 操作に async 版を提供しています。`a` プレフィクスを付けるだけです。

```python
import asyncio
import edinet

async def main():
    edinet.configure(api_key="YOUR_API_KEY")
    filings = await edinet.adocuments("2025-06-26")
    for filing in filings:
        if filing.has_xbrl:
            stmts = await filing.axbrl()
            pl = stmts.income_statement()
            print(pl["売上高"].value)
            break

asyncio.run(main())
```

### 複数企業の並列取得

`asyncio.gather` を使うと、複数企業の XBRL を並列ダウンロードして大幅に高速化できます。

```python
import asyncio
import edinet
from edinet import extract_values, extracted_to_dict, CK

async def screener():
    edinet.configure(api_key="YOUR_API_KEY", taxonomy_path="...")
    filings = await edinet.adocuments("2025-06-26", doc_type="120")
    targets = [f for f in filings if f.has_xbrl][:20]

    # 20社を並列ダウンロード+パース（直列60s → 並列5-10s）
    stmts_list = await asyncio.gather(*[f.axbrl() for f in targets])

    keys = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME, CK.TOTAL_ASSETS]
    rows = []
    for f, stmts in zip(targets, stmts_list):
        rows.append({
            "ticker": f.ticker,
            "filer": f.filer_name,
            **extracted_to_dict(extract_values(stmts, keys)),
        })

    import pandas as pd
    df = pd.DataFrame(rows)
    print(df)
    await edinet.aclose()

asyncio.run(screener())
```

## 期間分類

DEI から当期/前期の期間を自動分類します。`income_statement(period="prior")` の内部で使用されていますが、直接アクセスも可能です。

```python
from edinet.financial import classify_periods

pc = classify_periods(dei)
print(pc.current_duration)   # DurationPeriod(2024-04-01, 2025-03-31)
print(pc.prior_duration)     # DurationPeriod(2023-04-01, 2024-03-31)
print(pc.current_instant)    # InstantPeriod(2025-03-31)
```

## キャッシュ

ダウンロード済み ZIP のローカルキャッシュ。同一ドキュメントの再取得を防ぎます。

```python
import edinet

# キャッシュを有効化（ディレクトリ指定）
edinet.configure(api_key="...", cache_dir="./cache")

# キャッシュ情報
info = edinet.cache_info()
print(info.entry_count, info.total_bytes)

# キャッシュクリア
edinet.clear_cache()
```

## レートリミット

デフォルトではレートリミットは無効（`rate_limit=0`）です。EDINET API は指数バックオフ付きリトライを内蔵しているため、通常はレートリミット不要です。大量リクエスト時に接続遮断が心配な場合は手動で設定してください。

```python
edinet.configure(rate_limit=1.0)   # 1秒に1リクエスト
edinet.configure(rate_limit=0.5)   # 500msに1リクエスト
edinet.configure(rate_limit=0)     # 制限なし（デフォルト）
```

## エラーハンドリング

すべての例外は `edinet.EdinetError` を継承しています。

```python
import edinet

try:
    filings = edinet.documents("2025-06-26")
except edinet.EdinetConfigError:
    print("API キーが未設定")
except edinet.EdinetAPIError as e:
    print(f"API エラー: {e.status_code}")
except edinet.EdinetParseError:
    print("XBRL の解析に失敗")
```

| 例外クラス | 説明 |
|:---|:---|
| `EdinetError` | 基底例外 |
| `EdinetConfigError` | 設定エラー（API キー未設定等） |
| `EdinetAPIError` | API レスポンスエラー（HTTP ステータス付き） |
| `EdinetParseError` | JSON / ZIP / XBRL の解析失敗 |
| `EdinetWarning` | 非致命的な警告（`warnings` モジュール経由） |

## 低レベル API

高レベル API の裏側にある XBRL パーサーを直接使うこともできます。

```python
from edinet.xbrl import parse_xbrl_facts, extract_dei
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.units import structure_units

# XBRL インスタンスのパース
xbrl_path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

# DEI（企業属性）の抽出
dei = extract_dei(parsed.facts)
print(dei.filer_name_ja)          # 企業名
print(dei.accounting_standards)   # AccountingStandard.JAPAN_GAAP
print(dei.security_code)          # 証券コード

# Context / Unit の構造化
contexts = ContextCollection(structure_contexts(parsed.contexts))
units = structure_units(parsed.units)

# フィルタチェーン
consolidated = contexts.filter_consolidated().filter_no_extra_dimensions()
latest = consolidated.latest_duration_contexts()
```


## 対応範囲

| 項目 | 対応状況 |
|:---|:---|
| 書類タイプ | **全 42 タイプ** |
| 会計基準 | J-GAAP / IFRS / US-GAAP / JMIS |
| 業種 | 23 業種（ConceptSet 自動導出）+ 5 業種の専用科目マッピング |
| 財務諸表 | BS / PL / CF |
| Linkbase | Presentation / Calculation / Definition / Footnotes |
| エクスポート | DataFrame / CSV / Parquet / Excel |
| 表示 | Rich ターミナル / Jupyter HTML |
| I/O | sync / async 完全対応 |
| テスト | 1,398+ |

## 動作要件

- Python >= 3.12
- EDINET API キー（[EDINET](https://disclosure.edinet-fsa.go.jp/) で取得）

## ライセンス

[AGPL-3.0-or-later](https://www.gnu.org/licenses/agpl-3.0)

### AGPL v3 とは

GNU Affero General Public License v3 は、ソフトウェアの自由な利用・改変・再配布を保証するコピーレフトライセンスです。**ネットワーク経由でサービスを提供する場合にもソースコード公開義務が発生する**点が GPL v3 との主な違いです。

### 利用可否の早見表

| 利用形態 | 可否 | 説明 |
|:---|:---:|:---|
| 個人の学習・研究 | **OK** | 自由に利用可能 |
| 社内の財務分析・スクリーニング | **OK** | 社内利用はソースコード公開義務なし |
| クオンツ運用・自社トレーディング | **OK** | 社内利用に該当。成果物（投資判断）の公開義務なし |
| 学術研究・論文 | **OK** | 自由に利用可能 |
| このライブラリを組み込んだ **REST API / SaaS の公開** | **NG** | AGPL v3 によりサーバーサイドでもソースコード公開義務が発生。商用ライセンスが必要 |
| このライブラリを改変して社外に配布 | **条件付き** | AGPL v3 の条件に従いソースコードを公開する必要あり |

### 商用ライセンス

AGPL v3 の条件に該当する商用利用（REST API / SaaS 等）をご検討の場合は、商用ライセンスをご相談ください。

お問い合わせ: [https://x.com/_____uxoxu__](https://x.com/_____uxoxu__)

## 統一キー（CK）の日経225カバー率

`extract_values()` で使用する正規化キー（Canonical Key = CK）が、日経225構成銘柄の有価証券報告書からどの程度抽出できるかを実測した結果です。対象は 224 社（1 社はパースエラーで除外）、全 145 CK に対する抽出成功率を示します。

> **測定条件**: 2024年度有報（doc_type=120）、デフォルトマッパーパイプライン（summary → statement → definition → calc）、当期連結。

### 100% カバレッジ（28 CK）

全社で抽出に成功する主要指標です。

| CK | 説明 | 社数 |
|:---|:---|---:|
| `revenue` | 売上高 | 224/224 |
| `operating_income` (\*) | 営業利益 | 222/224 |
| `ordinary_income` | 経常利益 | 224/224 |
| `income_before_tax` | 税引前利益 | 224/224 |
| `income_taxes` | 法人税等 | 224/224 |
| `net_income` | 当期純利益 | 224/224 |
| `total_assets` | 総資産 | 224/224 |
| `total_liabilities` | 負債合計 | 224/224 |
| `net_assets` | 純資産合計 | 224/224 |
| `liabilities_and_net_assets` | 負債純資産合計 | 224/224 |
| `shareholders_equity` | 株主資本 | 224/224 |
| `capital_stock` | 資本金 | 224/224 |
| `capital_surplus` | 資本剰余金 | 224/224 |
| `retained_earnings` | 利益剰余金 | 224/224 |
| `treasury_stock` | 自己株式 | 224/224 |
| `operating_cf` | 営業CF | 224/224 |
| `investing_cf` | 投資CF | 224/224 |
| `financing_cf` | 財務CF | 224/224 |
| `cash_end` | 現金期末残高 | 224/224 |
| `eps` | 1株当たり当期純利益 | 224/224 |
| `bps` | 1株当たり純資産 | 224/224 |
| `dps` | 1株当たり配当額 | 224/224 |
| `per` | 株価収益率 | 224/224 |
| `roe` | 自己資本利益率 | 224/224 |
| `equity_ratio` | 自己資本比率 | 224/224 |
| `payout_ratio` | 配当性向 | 224/224 |
| `total_shares_issued` | 発行済株式総数 | 224/224 |
| `employees` | 従業員数 | 224/224 |
| `female_directors_ratio` | 女性役員比率 | 224/224 |

> (\*) `operating_income` は 222/224 社（99.1%）ですが、IFRS 企業の一部で「営業利益」を任意記載としているため。

### 99%以上（11 CK）

| CK | 社数 | 率 |
|:---|---:|---:|
| `audit_fees` | 223/224 | 99.6% |
| `deferred_tax_assets` | 223/224 | 99.6% |
| `net_income_parent` | 223/224 | 99.6% |
| `current_assets` | 222/224 | 99.1% |
| `current_liabilities` | 222/224 | 99.1% |
| `income_taxes_deferred` | 222/224 | 99.1% |
| `investments_and_other` | 222/224 | 99.1% |
| `noncurrent_assets` | 222/224 | 99.1% |
| `noncurrent_liabilities` | 222/224 | 99.1% |
| `oci_accumulated` | 222/224 | 99.1% |
| `operating_income` | 222/224 | 99.1% |

### 96%〜99%未満（10 CK）

| CK | 社数 | 率 |
|:---|---:|---:|
| `cash_and_deposits` | 221/224 | 98.7% |
| `comprehensive_income_parent` | 221/224 | 98.7% |
| `eps_diluted` | 221/224 | 98.7% |
| `intangible_assets` | 221/224 | 98.7% |
| `interim_dps` | 221/224 | 98.7% |
| `non_operating_expenses` | 221/224 | 98.7% |
| `non_operating_income` | 221/224 | 98.7% |
| `ppe` | 221/224 | 98.7% |
| `comprehensive_income` | 220/224 | 98.2% |
| `cash_and_equivalents` | 218/224 | 97.3% |

### 90%〜96%未満（13 CK）

| CK | 社数 | 率 |
|:---|---:|---:|
| `sga_expenses` | 215/224 | 96.0% |
| `dividends_paid_cf` | 211/224 | 94.2% |
| `fx_effect_on_cash` | 211/224 | 94.2% |
| `cross_shareholdings_amount` | 209/224 | 93.3% |
| `cross_shareholdings_count` | 209/224 | 93.3% |
| `interest_expense_pl` | 209/224 | 93.3% |
| `extraordinary_income` | 208/224 | 92.9% |
| `extraordinary_loss` | 208/224 | 92.9% |
| `purchase_ppe_cf` | 207/224 | 92.4% |
| `comprehensive_income_minority` | 206/224 | 92.0% |
| `minority_interests` | 203/224 | 90.6% |
| `net_income_minority` | 203/224 | 90.6% |
| `retirement_benefit_liability` | 203/224 | 90.6% |

### 80%〜90%未満（18 CK）

| CK | 社数 | 率 |
|:---|---:|---:|
| `deferred_tax_liabilities` | 200/224 | 89.3% |
| `subtotal_operating_cf` | 200/224 | 89.3% |
| `interest_expense_cf` | 199/224 | 88.8% |
| `depreciation_cf` | 198/224 | 88.4% |
| `interest_dividend_income_cf` | 198/224 | 88.4% |
| `net_change_in_cash` | 197/224 | 87.9% |
| `gender_pay_gap` | 192/224 | 85.7% |
| `trade_payables_change_cf` | 192/224 | 85.7% |
| `trade_receivables` | 192/224 | 85.7% |
| `trade_payables` | 191/224 | 85.3% |
| `trade_receivables_change_cf` | 191/224 | 85.3% |
| `female_managers_ratio` | 190/224 | 84.8% |
| `long_term_loans` | 188/224 | 83.9% |
| `interest_income_pl` | 186/224 | 83.0% |
| `gross_profit` | 185/224 | 82.6% |
| `short_term_loans` | 184/224 | 82.1% |
| `cost_of_sales` | 181/224 | 80.8% |
| `inventories_change_cf` | 180/224 | 80.4% |

### 50%〜80%未満（16 CK）

| CK | 社数 | 率 |
|:---|---:|---:|
| `male_childcare_leave_rate` | 179/224 | 79.9% |
| `proceeds_ppe_sale_cf` | 178/224 | 79.5% |
| `rd_expenses` | 174/224 | 77.7% |
| `bonds_payable` | 172/224 | 76.8% |
| `equity_method_cf` | 172/224 | 76.8% |
| `goodwill` | 171/224 | 76.3% |
| `impairment_loss_cf` | 168/224 | 75.0% |
| `repayment_long_term_loans_cf` | 154/224 | 68.8% |
| `purchase_treasury_stock_cf` | 150/224 | 67.0% |
| `proceeds_long_term_loans_cf` | 142/224 | 63.4% |
| `other_operating_cf` | 124/224 | 55.4% |
| `income_taxes_paid_cf` | 122/224 | 54.5% |
| `ppe_sale_loss_gain_cf` | 119/224 | 53.1% |
| `inventories` | 118/224 | 52.7% |
| `other_investing_cf` | 113/224 | 50.4% |
| `purchase_investment_securities_cf` | 112/224 | 50.0% |

### 30%〜50%未満（14 CK）

IFRS 固有科目や業種特有の CF 明細が中心です。該当しない企業では元の報告書にも記載がないため、カバー率の上限が構造的に制約されます。

| CK | 社数 | 率 |
|:---|---:|---:|
| `redemption_bonds_cf` | 111/224 | 49.6% |
| `proceeds_investment_securities_cf` | 104/224 | 46.4% |
| `other_financing_cf` | 99/224 | 44.2% |
| `stock_options` | 99/224 | 44.2% |
| `equity_method_income` | 97/224 | 43.3% |
| `capex` | 96/224 | 42.9% |
| `equity_parent` | 94/224 | 42.0% |
| `equity_method_income_ifrs` | 85/224 | 37.9% |
| `equity_method_investments` | 85/224 | 37.9% |
| `finance_costs` | 85/224 | 37.9% |
| `proceeds_bonds_cf` | 85/224 | 37.9% |
| `finance_income` | 83/224 | 37.1% |
| `loans_paid_cf` | 73/224 | 32.6% |
| `allowance_doubtful_change_cf` | 71/224 | 31.7% |

### 30%未満（35 CK）

業種限定の科目（銀行業・保険業・証券業）や、IFRS 専用科目、特殊な CF 明細項目です。日経225 の業種構成上、該当企業が限定的であるため低いカバー率は想定通りです。

| CK | 社数 | 率 | 備考 |
|:---|---:|---:|:---|
| `other_income_ifrs` | 67/224 | 29.9% | IFRS |
| `short_term_borrowings_net_cf` | 66/224 | 29.5% | |
| `other_expenses_ifrs` | 65/224 | 29.0% | IFRS |
| `fx_loss_gain_cf` | 62/224 | 27.7% | |
| `dividends_paid_nci_cf` | 59/224 | 26.3% | |
| `goodwill_amortization_cf` | 59/224 | 26.3% | J-GAAP のみ |
| `loans_collected_cf` | 56/224 | 25.0% | |
| `interest_bearing_debt_ncl` | 52/224 | 23.2% | |
| `inventory_writedowns` | 52/224 | 23.2% | |
| `interest_bearing_debt_cl` | 49/224 | 21.9% | |
| `dividends_received_cf` | 46/224 | 20.5% | |
| `consolidation_scope_change_cash` | 40/224 | 17.9% | |
| `lease_liabilities_cl` | 38/224 | 17.0% | IFRS |
| `lease_liabilities_ncl` | 38/224 | 17.0% | IFRS |
| `dividend_income` | 28/224 | 12.5% | |
| `nci_capital_contribution_cf` | 23/224 | 10.3% | |
| `deferred_assets` | 22/224 | 9.8% | |
| `investment_property` | 21/224 | 9.4% | |
| `deposits` | 10/224 | 4.5% | 銀行業 |
| `continuing_operations_income` | 5/224 | 2.2% | US-GAAP |
| `net_premiums_written` | 3/224 | 1.3% | 保険業 |
| `interest_bearing_debt` | 2/224 | 0.9% | |
| `loans_and_bills_discounted` | 2/224 | 0.9% | 銀行業 |
| `sbc_cf` | 2/224 | 0.9% | |
| `securities_banking` | 2/224 | 0.9% | 銀行業 |
| `capital_adequacy_ratio_bis` | 0/224 | 0.0% | 銀行業（BIS） |
| `capital_adequacy_ratio_domestic` | 0/224 | 0.0% | 銀行業（国内） |
| `capital_adequacy_ratio_domestic_2` | 0/224 | 0.0% | 銀行業（国内2） |
| `capital_adequacy_ratio_international` | 0/224 | 0.0% | 銀行業（国際） |
| `interest_dividend_income_ins` | 0/224 | 0.0% | 保険業 |
| `investment_yield_income` | 0/224 | 0.0% | 保険業 |
| `investment_yield_realized` | 0/224 | 0.0% | 保険業 |
| `lease_liabilities` | 0/224 | 0.0% | IFRS |
| `net_loss_ratio` | 0/224 | 0.0% | 保険業 |
| `net_operating_expense_ratio` | 0/224 | 0.0% | 保険業 |

### サマリー

| 帯域 | CK数 | 累計CK | 備考 |
|:---|---:|---:|:---|
| **100%** | 28 | 28 | PL/BS/CF主要科目 + 指標 + ESG |
| **99%以上** | 11 | 39 | BS詳細 + 包括利益 |
| **96%〜99%** | 10 | 49 | EPS希薄化 + CF関連 |
| **90%〜96%** | 13 | 62 | 特別損益 + 少数株主 |
| **80%〜90%** | 18 | 80 | CF明細 + ESG + 借入金 |
| **50%〜80%** | 16 | 96 | のれん + 投資CF明細 |
| **30%〜50%** | 14 | 110 | IFRS科目 + 持分法 |
| **30%未満** | 35 | 145 | 業種限定（銀行・保険） |
