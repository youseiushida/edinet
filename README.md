# edinet — EDINET XBRL 財務データ Python ライブラリ

[![PyPI version](https://img.shields.io/pypi/v/edinet.svg)](https://pypi.org/project/edinet/)
[![Python](https://img.shields.io/pypi/pyversions/edinet.svg)](https://pypi.org/project/edinet/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

**edinet** は、[EDINET（金融庁 電子開示システム）](https://disclosure.edinet-fsa.go.jp/)の開示データを Python から扱うためのライブラリです。書類一覧の取得から XBRL パース、財務三表（PL/BS/CF）の組み立て、会計基準の自動判別、23 業種対応、タクソノミラベル解決、DataFrame 変換までをワンストップで提供します。全 42 書類タイプに対応し、J-GAAP / IFRS / US-GAAP の 3 会計基準を統一的に扱えます。内部の HTTP 通信には [httpx](https://github.com/encode/httpx) を使用しています。

[GitHub Repository](https://github.com/youseiushida/edinet)

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

## クイックスタート

```python
import edinet

edinet.configure(api_key="YOUR_API_KEY")

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
        print(f"  営業利益: {pl['営業利益'].value:,}")
        print(f"  総資産: {bs['資産合計'].value:,}")
        break
```

## 企業検索

11,000 社超の EDINET コードマスタを内蔵しています。企業名・銘柄コード・EDINET コードから検索できます。

```python
from edinet import Company

# 企業名で検索
results = Company.search("トヨタ")
toyota = results[0]
print(toyota.name_ja)      # "トヨタ自動車株式会社"
print(toyota.ticker)       # "7203"

# 銘柄コードから
sony = Company.from_sec_code("6758")

# EDINET コードから
company = Company.from_edinet_code("E02144")

# 最新の有報を取得
filing = toyota.latest(doc_type=edinet.DocType.ANNUAL_SECURITIES_REPORT)
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
result = extract_values(pl, [CK.OPERATING_INCOME])
print(result[CK.OPERATING_INCOME].value)  # 確実に取得
```

### 会計基準の自動判別

会計基準は DEI から自動判別されます。J-GAAP・IFRS・US-GAAP のいずれでも同じ API で操作できます。

```python
print(stmts.detected_standard)
# DetectedStandard(standard=<JAPAN_GAAP>, method=<DEI>, detail_level=<DETAILED>)

# IFRS 企業でも同じコードで動く
sony_stmts = sony_filing.xbrl()
sony_pl = sony_stmts.income_statement()
sony_pl["売上収益"].value  # IFRS の Revenue
```

### 2つのデータ取得方式

財務データの取得には 2 つの方式があります。用途に応じて使い分けてください。

| | `income_statement()` 等 | `extract_values()` |
|:---|:---|:---|
| **データソース** | Presentation Linkbase（タクソノミ定義） | 正規化キー辞書（手動マッピング） |
| **取得範囲** | PL/BS/CF の全詳細科目（数十行） | 主要指標のみ（売上高・営業利益等） |
| **表示順** | タクソノミの表示順序付き | なし（辞書） |
| **基準横断** | 基準ごとに科目名が異なる | 基準を問わず同じキーで取得 |
| **用途** | 財務諸表の表示・分析 | スクリーナー・複数企業の横並び比較 |

```python
# 方式1: 財務諸表として取得（全科目・表示順付き）
pl = stmts.income_statement()
for item in pl:
    print(f"{item.label_ja.text}: {item.value}")

# 方式2: 正規化キーで横断取得（主要指標・基準不問）
result = extract_values(pl, [CK.REVENUE, CK.OPERATING_INCOME])
```

### 正規化キーによる基準横断アクセス

canonical key を使うと、会計基準を意識せずに値を取得できます。スクリーナーの構築に最適です。

```python
from edinet import extract_values, extracted_to_dict, CK

# J-GAAP でも IFRS でも US-GAAP でも同じキーで取得
pl = stmts.income_statement()
result = extract_values(pl, [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME])

rev = result[CK.REVENUE]
print(rev.value)                 # Decimal('1234567000000')
print(rev.item.label_ja.text)    # "売上高"（J-GAAP）or "売上収益"（IFRS）
print(rev.item.source_line)      # XML の行番号（トレーサビリティ）

# pandas で複数企業を横並び
import pandas as pd

keys = [CK.REVENUE, CK.OPERATING_INCOME, CK.NET_INCOME, CK.TOTAL_ASSETS]
df = pd.DataFrame([
    {
        "ticker": f.ticker,
        "filer": f.filer_name,
        **extracted_to_dict(
            extract_values(f.xbrl().income_statement(), keys),
            extract_values(f.xbrl().balance_sheet(), keys),
        ),
    }
    for f in filings if f.has_xbrl
])
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
from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets, StatementCategory

registry = derive_concept_sets(taxonomy_path)
cs = registry.get(StatementCategory.INCOME_STATEMENT, consolidated=True, industry_code="cai")
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

# 非同期 HTTP クライアントの明示的な解放
await edinet.aclose()
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

## 設定

```python
import edinet

edinet.configure(
    api_key="YOUR_API_KEY",           # EDINET API キー（必須）
    taxonomy_path="/path/to/ALL_20251101",  # ローカルタクソノミ（任意）
    cache_dir="./cache",              # ZIP キャッシュディレクトリ（任意）
)
```

### API キーの取得

[EDINET](https://disclosure.edinet-fsa.go.jp/) にアカウント登録し、API キーを取得してください。

### タクソノミのセットアップ

タクソノミパスを指定すると、科目の階層表示やラベル解決の精度が向上します。指定しない場合は ZIP 内のタクソノミを使用します。

1. [金融庁の EDINET タクソノミページ](https://www.fsa.go.jp/search/20250808.html)から「EDINET タクソノミ」の ZIP をダウンロード（年度により URL が変わります）
2. ZIP を展開すると、中に `taxonomy/` と `samples/` を子に持つフォルダがあります:
   ```
   （ZIP を展開）
   └── ○○○/                ← フォルダ名は年度により異なる
       ├── taxonomy/        ← タクソノミ本体
       └── samples/         ← サンプルインスタンス
   ```
3. `taxonomy/` と `samples/` の**親フォルダ**のパスを指定します:
   ```python
   edinet.configure(
       api_key="YOUR_API_KEY",
       taxonomy_path="/path/to/○○○",  # ← taxonomy/ の親
   )
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
| テスト | 1,771+ |

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
