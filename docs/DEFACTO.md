# DEFACTO: ディファクトスタンダードへの道

edinet ライブラリが EDINET エコシステムにおけるディファクトスタンダードになれるかの分析。
edgartools (SEC EDGAR) との比較、競合分析、アーキテクチャ評価、フォルダ構造の再設計方針を含む。

---

## 1. edgartools が「ディファクト」である理由

### 1-1. 定量指標

| 指標 | edgartools |
|---|---|
| GitHub Stars | ~1,800 |
| 累計 DL 数 | 2,010,000 |
| デイリー DL | 1,300–2,100 |
| リリース数 | 200+ (2022/12〜) |
| テスト数 | 1,000+ |
| 対応 Filing タイプ | 24+ |
| Python | 3.10–3.14 |
| ライセンス | MIT |

### 1-2. 技術的特徴

**API 設計: オブジェクト指向・ワンライナー**

```python
from edgar import Company, set_identity
set_identity("your.name@example.com")

company = Company("AAPL")
financials = company.get_financials()
balance_sheet = financials.balance_sheet
revenue = financials.get_revenue()
```

**XBRL 正規化**: ~2,000 の XBRL タグを ~95 の標準概念にマッピング。
`financials.get_revenue()` は会計基準に依存せず動作。

**Multi-Period Stitching**: `MultiFinancials.extract(filings)` で複数期間の財務諸表を自動接合。

**Rich 表示**: Terminal + Jupyter。全オブジェクトが `rich` でフォーマット表示。

**AI/MCP 統合**: 内蔵 MCP サーバー (3,450+ 行の API ドキュメント)。

**ゼロフリクション**: API キー不要（SEC EDGAR は公開データ）、スマートキャッシュ、レート制限対応。

### 1-3. ディファクトの本質

edgartools がディファクトである理由は技術力だけではない:

1. **出している**: PyPI に 200+ リリース。`pip install edgartools` で即座に使える
2. **見せている**: ReadTheDocs の包括的ドキュメント、Quick Start、Filing タイプ別ガイド
3. **磨いている**: v5.x で HTML パーサーを大幅書き換え。継続的な品質改善
4. **広げている**: 24+ Filing タイプ対応。XBRL 以外のデータ（Form 4 XML、13F TXT）もパース

---

## 2. EDINET 競合環境: 真空地帯

### 2-1. 既存ライブラリ

| ライブラリ | DL 数 | 最終更新 | 状態 | 特徴 |
|---|---|---|---|---|
| edinet-python | 53K | 2019/10 | 死亡 | 薄い API ラッパー。XBRL 正規化なし |
| edinet-xbrl | 41K | 2018/01 | 死亡 | Python 3.3–3.6。基本パーサー |
| edinet-tools | 5K | 2026/02 | 活動中 | 27 stars。型付きオブジェクト、J-GAAP+IFRS |
| edinet-mcp | N/A | 2026/02 | 新生 | 1 star。MCP 特化。161 科目マッピング |
| edinet2dataset | 32 stars | — | ニッチ | SakanaAI。LLM ベンチマーク用データセット構築 CLI |

### 2-2. 比較表

| 機能 | edgartools | edinet-tools | edinet-mcp | **本ライブラリ** |
|---|---|---|---|---|
| XBRL パース深度 | SEC API 経由 | 型付きオブジェクト | 正規化 161 項目 | **生 XBRL + Linkbase 木構造** |
| 会計基準対応 | US-GAAP 中心 | J-GAAP + IFRS | 3 基準 | **J-GAAP + IFRS + US-GAAP** |
| 業種対応 | N/A (SEC) | なし | なし | **23 業種 ConceptSet** |
| Linkbase 解析 | なし (API 依存) | なし | なし | **Calc + Pres + Def** |
| 階層表示 | あり | なし | なし | **あり (ConceptSet depth)** |
| DataFrame 出力 | pandas | 限定的 | Polars + pandas | **pandas + CSV/Parquet/Excel** |
| テスト数 | 1,000+ | 330 | 不明 | **1,267** |
| 型安全性 | Full | 部分的 | 部分的 | **Pydantic + frozen DC + .pyi** |

**結論: 技術的に最も深い実装を持つが、未リリース。**

---

## 3. 本ライブラリのソースコード実態

### 3-1. コード規模

| カテゴリ | 行数 | ファイル数 |
|---|---|---|
| XBRL パース・構造化 | ~6,500 | 18 |
| モデル層 (Filing, Financial, Company, DocType) | ~1,600 | 7 |
| API・HTTP 層 | ~1,100 | 4 |
| DataFrame・エクスポート | ~240 | 2 |
| 表示 (Rich, 階層表示) | ~340 | 3 |
| 設定・例外・バリデーション | ~320 | 5 |
| **合計（実ロジック）** | **~10,100** | **39** |
| テスト | 19,422 | 1,267 テスト関数 |

テスト/コード比 ≈ 2:1。非常に健全。

### 3-2. 実装済み機能の実態

以下は FEATURES.md のステータスではなく、ソースコードを直接読んで確認した実態:

| 機能 | 実態 | 品質評価 |
|---|---|---|
| API クライアント (sync/async) | 完成 | 堅実。レート制限対応、エラー体系 |
| XBRL パーサー | 完成 | **非常に高品質。** 1,187 行。strict/lenient、重複 Fact 検出、ネスト Fact 警告、source_line 保持 |
| Context 構造化 | 完成 | 691 行。dimension、entity、period を完全構造化 |
| Unit 解析 | 完成 | SimpleMeasure / DivideMeasure の Union 型 |
| 名前空間解決 | 完成 | 標準/提出者別の判別 |
| DEI 抽出 | 完成 | 461 行。会計基準・業種コード判定 |
| Calculation Linkbase | 完成 | 木構造解析 |
| Presentation Linkbase | 完成 | 686 行。マージ対応 |
| Definition Linkbase | 完成 | dimension-domain 解析 |
| ConceptSet 自動導出 | 完成 | **862 行。23 業種全カバー。Presentation Linkbase から自動導出** |
| **BS / PL / CF 三表** | **動作する** | 概念セットベースで分類。連結/個別、当期/前期対応 |
| J-GAAP 正規化 | 完成 | 445 行。canonical_key マッピング |
| IFRS 正規化 | 完成 | 605 行。J-GAAP との相互マッピング |
| US-GAAP サマリー | 完成 | 736 行。BLOCK_ONLY 専用パス (`_build_usgaap_statement`) |
| 業種別 (5 業種) | WIP | `_base.py` で統一フレームワーク。各業種モジュール実装中 |
| 連結/個別切替 | 完成 | フォールバック付き。strict モード |
| 当期/前期 | 完成 | DEI ベースの自動分類 (`classify_periods`) |
| Company ナビゲーション | 部分的 | EDINET コード起点は動く。名前引きはまだ |
| Filing → Statements パイプライン | 完成 | `filing.xbrl()` / `filing.axbrl()` でワンライン |
| DataFrame 出力 | 完成 | 5 列 / 全カラム、CSV / Parquet / Excel |
| 階層表示 | 完成 | ConceptSet の depth で自動インデント |
| Rich 表示 | 完成 | `__rich_console__` Protocol |
| 型安全性 | 高 | Pydantic + frozen dataclass + .pyi スタブ |
| 例外体系 | 完成 | `EdinetError` 階層 |
| ラベル解決 | 完成 | 標準/提出者別。日英。フォールバックチェーン |

### 3-3. ワンライナーパイプラインの実態

```python
import edinet

edinet.configure(api_key="...", taxonomy_path="/path/to/ALL_20251101")

# 書類一覧 → Filing → Statements → 財務諸表
filings = edinet.documents(date="2026-03-01", doc_type="有価証券報告書")
stmts = filings[0].xbrl()

pl = stmts.income_statement()                    # 損益計算書
bs = stmts.balance_sheet()                        # 貸借対照表
cf = stmts.cash_flow_statement()                  # キャッシュフロー計算書

pl_prior = stmts.income_statement(period="prior") # 前期
bs_non   = stmts.balance_sheet(consolidated=False) # 個別

# 科目アクセス
item = pl["売上高"]       # KeyError if not found
item = pl.get("売上高")   # None if not found
"売上高" in pl            # True/False

# DataFrame
df = pl.to_dataframe()
pl.to_csv("pl.csv")
pl.to_parquet("pl.parquet")
```

### 3-4. 有報以外の書類での動作

`parse_xbrl_facts()` は `contextRef` を持つ全ての XBRL Fact を抽出する汎用パーサーであり、
書類タイプには依存しない。以下の全 docType で Fact 抽出は動作する:

- 有価証券報告書 (120)
- 四半期報告書 (140) / 半期報告書 (160)
- 有価証券届出書 (030)
- 大量保有報告書 (350)
- 公開買付届出書 (240)
- 発行登録書 (080)
- その他 XBRL を含む全書類

`build_statements()` も概念セットベースの分類であり、概念セットに含まれる Fact があれば
どの docType でも財務諸表を組み立てる。

---

## 4. edgartools の書類タイプ別対応アーキテクチャ

### 4-1. 2 層構造

```
Layer 1: 汎用 Filing (全書類に共通)
  ├── メタデータ、添付ファイル、生の XBRL/HTML
  └── .xbrl() → 汎用 XBRL 層（6 段階の statement 解決、概念標準化）

Layer 2: .obj() → 書類タイプ別の型付きオブジェクト (24 種)
  ├── CompanyReport (10-K, 10-Q, 8-K, 20-F, 40-F)
  │     → 共通 XBRL 財務諸表 + 書類別セクション構造
  ├── Ownership (Form 3/4/5) → XML 直接パース
  ├── ThirteenF → XML/TXT パース、保有比較
  ├── Form144 → 異常検知つき
  ├── ProxyStatement → 役員報酬 XBRL
  ├── Schedule13D/G → 大量保有
  └── Fund 系 (NPORT-P, N-MFP2 等) → ファンド固有

  ★ 24 種以外 → Layer 1 の汎用 XBRL にフォールバック
```

### 4-2. `.obj()` ディスパッチメカニズム

```python
def obj(sec_filing: Filing) -> Optional[object]:
    if matches_form(sec_filing, "10-K"):
        return TenK(sec_filing)
    elif matches_form(sec_filing, "10-Q"):
        return TenQ(sec_filing)
    elif matches_form(sec_filing, "8-K"):
        return EightK(sec_filing)
    # ... 20+ more ...

    # フォールバック: 汎用 XBRL
    filing_xbrl = sec_filing.xbrl()
    if filing_xbrl:
        return filing_xbrl
```

24 種以外の書類タイプ (S-1, S-3, 424B 等) は自動的に汎用 XBRL にフォールバック。

### 4-3. 書類タイプ別の実装内容

| Filing Type | クラス | 何をしているか |
|---|---|---|
| **10-K / 10-Q** | `TenK` / `TenQ` extends `CompanyReport` | 共通 XBRL 財務諸表 + セクション構造 (Item 1, 1A, 7 等の HTML 内位置解決) |
| **8-K** | `EightK` extends `CompanyReport` | 33 種の SEC 8-K Item の検出 + EX-99 プレスリリースからの決算テーブル抽出 |
| **13F-HR** | `ThirteenF` | XML/TXT から保有テーブルをパース。四半期比較。**XBRL 不使用** |
| **Form 3/4/5** | `Form3/4/5` extends `Ownership` | SEC 独自 XML スキーマから取引情報を直接パース。**XBRL 不使用** |
| **Form 144** | `Form144` | 制限株式売却通知。異常検知 (大量売却、短期保有) |
| **DEF 14A** | `ProxyStatement` | 役員報酬を ECD タクソノミ (専用 XBRL スキーマ) から構造化 |
| **Schedule 13D/G** | `Schedule13D/G` | 大量保有。保有者名・保有割合 |
| **Fund 系** | `FundReport` 等 | ファンド固有のドメインモデル |
| **S-1 等** | なし (フォールバック) | 汎用 XBRL のみ |

### 4-4. 核心的なインサイト

**財務諸表の抽出は「汎用 XBRL 層」で共有されている。**

10-K も 10-Q も 8-K も同じ `Financials.extract()` → `XBRL.from_filing()` パスを通る。
書類タイプ別クラスが追加しているのは:

1. **セクション構造** — HTML 内のセクション見出し位置解決
2. **非 XBRL 構造データ** — Form 4 の XML、13F の TXT、8-K のプレスリリース HTML テーブル
3. **ドメイン固有の分析** — 13F の四半期比較、Form 144 の異常検知

### 4-5. EDINET での対応関係

| EDINET 書類 | 汎用 XBRL (実装済み) | 追加で必要なもの |
|---|---|---|
| 有価証券報告書 (120) | BS/PL/CF 抽出 | セクション構造 (事業等のリスク等) |
| 四半期報告書 (140) | BS/PL/CF 抽出 | ほぼ同上 |
| 半期報告書 (160) | BS/PL/CF 抽出 | ほぼ同上 |
| 有価証券届出書 (030) | Fact 抽出 | 募集条件・資金使途の構造化 |
| 大量保有報告書 (350) | Fact 抽出 | 保有者名・保有割合の構造化 |
| 公開買付書 (240) | Fact 抽出 | 買付条件の構造化 |
| 発行登録書 (080) | Fact 抽出 | 発行条件の構造化 |

**本ライブラリは edgartools の Layer 1 (汎用 XBRL 層) と同等のものを既に持っている。**

---

## 5. フォルダ構造の再設計

### 5-1. 現状の問題

`xbrl/` に **2 つの異なる関心事** が混在している:

```
xbrl/
├── 【汎用 XBRL パース】全 docType で使う
│   parser.py, facts.py, contexts.py, units.py, dei.py
│   _namespaces.py, _linkbase_utils.py
│   linkbase/ (calc / pres / def)
│   taxonomy/ (ラベル解決, ConceptSet 導出)
│
├── 【有報の財務諸表組み立て】有報系 docType 専用
│   statements.py (Statements, build_statements)
│   standards/ (jgaap / ifrs / usgaap / normalize)
│   sector/ (banking / insurance / ...)
│   dimensions/ (consolidated / period_variants)
```

有報専用の財務諸表ロジック（会計基準の名寄せ、業種別科目、三表分類）と
全書類タイプで動く汎用 XBRL パースの責任境界が不明確。

### 5-2. 採用する構造

```
edinet/
├── xbrl/                  ← 汎用 XBRL パース（全 docType で使う）
│   ├── parser.py
│   ├── facts.py
│   ├── contexts.py
│   ├── units.py
│   ├── dei.py
│   ├── _namespaces.py
│   ├── _linkbase_utils.py
│   ├── linkbase/
│   ├── taxonomy/
│   └── text/              ← テキストブロック（XBRL Fact の一種）
│       ├── blocks.py
│       ├── sections.py
│       └── clean.py
├── financial/             ← 有報系の財務諸表組み立て
│   ├── statements.py
│   ├── standards/
│   ├── sector/
│   └── dimensions/
├── api/                   ← 変更なし
├── models/                ← 変更なし
├── dataframe/             ← 変更なし
└── display/               ← 変更なし
```

**import パス:**
```python
from edinet.xbrl import parse_xbrl_facts        # 汎用 XBRL パース
from edinet.xbrl.text import extract_sections    # テキストブロック
from edinet.financial import Statements          # 財務諸表
```

`doctypes/` は設けない。書類タイプ固有の型付きオブジェクト（`LargeHolding` 等）は
保守コスト（doctype ごとの名寄せテーブル）に見合わないため作らない。
全 27 書類タイプは汎用パイプライン（`stmts["ラベル名"]` / `stmts.search("キーワード")`）でアクセスする。
ラベルはタクソノミから自動解決されるため、タクソノミ更新に自動追従し保守不要。
将来ユーザー要望があり、かつ保守が容易になった場合に再検討する。

### 5-3. 採用する理由

1. **汎用 XBRL とテキストブロックは同じ層**: テキストブロックは textBlockItemType の Fact を抽出するだけ。`xbrl/` の中にあるのが自然

2. **有報専用ロジックを分離**: `statements.py`, `standards/`, `sector/`, `dimensions/` は会計基準・業種の名寄せという有報固有の関心事。`xbrl/` から出すことで責任が明確になる

3. **import パスが自然**: `from edinet.financial import Statements` は「財務諸表モジュール」、`from edinet.xbrl.text import extract_sections` は「XBRL テキスト抽出」であることが明白

### 5-4. 実施方針

v0.0.1 → v0.1.0 のリリース前に一括実行:

1. `edinet/financial/` を作成、`xbrl/statements.py`, `xbrl/standards/`, `xbrl/sector/`, `xbrl/dimensions/` を移動
2. `edinet/xbrl/text/` を作成（text_blocks 実装時）
3. import パスの全更新（`xbrl.statements` → `financial.statements` 等）
4. テスト・スタブの更新
5. `Filing.xbrl()` の内部 import パス更新
6. public API (`__init__.py` の re-export) は変更なし — ユーザー向け破壊なし

**移動対象（4 ディレクトリのみ）:**
```
xbrl/statements.py      → financial/statements.py
xbrl/standards/          → financial/standards/
xbrl/sector/             → financial/sector/
xbrl/dimensions/         → financial/dimensions/
```

---

## 6. 書類タイプ別対応の戦略: 汎用パイプライン + ラベルアクセス

### 6-1. 背景: 「構造化」の本質は名寄せテーブル

有報の財務諸表では型付きオブジェクト（`FinancialStatement`）が価値を持つ:

1. **基準間の名寄せ**: `NetSales` (J-GAAP) と `Revenue` (IFRS) を同じキーで引ける
2. **業種間の名寄せ**: 一般事業会社と銀行業で異なる concept を統一
3. **三表の分類**: PL/BS/CF の concept セットで自動分類
4. **並び順**: Presentation Linkbase の表示順序

しかし大量保有報告書・公開買付書等にはこの問題がない
（会計基準差異なし、業種差異なし、表の分類不要）。
型付きオブジェクトを作ると doctype ごとに手動保守のマッピングテーブルが増えるだけ。

### 6-2. 決定: 汎用パイプライン + dict-like アクセス

書類タイプ固有の型付きオブジェクトは作らない。
`Statements` に dict-like プロトコルを追加し、タクソノミ解決済みラベルで全 Fact にアクセスする。

> **Note**: 以下は v0.1.0 で追加予定（現時点の `Statements` は `_items` が private）。

```python
# 3 つのキーで完全一致アクセス（FinancialStatement と同じプロトコル）
stmts["保有割合の合計"]          # 1. label_ja  — タクソノミ日本語ラベル
stmts["Total holding ratio"]    # 2. label_en  — タクソノミ英語ラベル
stmts["TotalHoldingRatio"]      # 3. local_name — XBRL concept タグ名

# None 安全
stmts.get("保有割合の合計")      # LineItem | None

# 存在確認
"保有割合の合計" in stmts        # True/False

# 部分一致検索（探索用）
stmts.search("保有")            # list[LineItem] — ラベルに「保有」を含む全件

# Sequence プロトコル
stmts.items                     # tuple[LineItem, ...]
len(stmts)                      # int
for item in stmts: ...          # Iterator[LineItem]
```

**使い分け:**
- **有報**: `stmts.income_statement()["売上高"]` — 期間/連結フィルタ済みで一意
- **有報以外**: `stmts["保有割合の合計"]` — 期間/連結の区分がないため直接アクセスで一意

ラベルはタクソノミから自動解決されるため、書類タイプ固有のマッピング保守が不要。
タクソノミ更新にも自動追従する。

> **Note**: サンプルコード中のラベル名（「保有割合の合計」「買付け等の価格」等）は
> 実データ未確認の仮名称。実装時にタクソノミを確認して正確な名称に修正する。

### 6-3. 将来の型付きオブジェクト追加方針

型付きオブジェクト（`LargeHolding` 等）は **ユーザー要望が来てから** 追加する。
追加する場合のコスト: 各 doctype で 100-300 行のマッピング定義 + 年1回のタクソノミ突合。
汎用パイプラインの上に乗る薄いラッパーなので追加自体は容易。

---

## 7. ディファクトになるために必要なこと

### 7-1. 致命的に足りないもの

| 項目 | 理由 |
|---|---|
| **PyPI リリース** | `pip install edinet` できないライブラリは使えない |
| **README / Quick Start** | 初見ユーザーが 30 秒で価値を理解し、5 行で動かせる必要がある |
| **Company 名前引き** | `edinet.Company("トヨタ")` の体験。168K 行の EDINET コードデータは既にある |

### 7-2. 重要だが致命的ではないもの

| 項目 | 理由 |
|---|---|
| Jupyter `_repr_html_` | 分析者の主要環境 |
| テキストブロック抽出 | LLM 時代の核心データ |
| CLI | スクリプト連携 |
| cache 機構 | 繰り返し利用時の体験 |
| ドキュメントサイト | ReadTheDocs 等 |

### 7-3. 結論

**技術的な深さでは EDINET エコシステムで最も進んでいる。**
XBRL パース層は edgartools が SEC の API に依存しているのに対し、本ライブラリは
生の XBRL インスタンスを lxml で直接パースし Linkbase の木構造まで解析している。

**競合が事実上いない。** 最大の競合 edinet-tools は 27 stars / 5K DL。

**ディファクトになれない理由は技術ではなく「出してない」こと。**
PyPI リリース + README + Company 名前引きの 3 つが揃えば、
EDINET エコシステムにおいて最も有力なディファクト候補になる。
出せば勝てるポジションにいる。問題は「出すこと」。

---

## 8. v0.1.0 の完成形

Tier A + Tier B + diff + フォルダ構造リファクタを完了した v0.1.0 の姿。

### 8-1. 全 35 書類タイプの対応レベル

| Tier | 対応レベル | 書類数 | 書類タイプ |
|---|---|---|---|
| **Tier 1** | 三表 (BS/PL/CF) + テキストブロック + セグメント + 汎用ラベルアクセス | **7** | 有報(120), 訂正有報(130), 四半期(140), 訂正四半期(150), 半期(160), 訂正半期(170), 有価証券届出書(030) |
| **Tier 2** | 汎用ラベルアクセス（`stmts["ラベル名"]` / `stmts.search("キーワード")`） | **18** | 大量保有(350/360), 公開買付(240/250/270/280), 意見表明(290/300), 対質問回答(310/320), 別途買付け禁止(330/340), 内部統制(235/236), 確認書(135/136), 親会社等(200/210), 自己株券(220/230), 発行登録(080/090/100), 訂正届出書(040) |
| **Tier 3** | PDF ダウンロード (`fetch_pdf`) | **8** | 有価証券通知書(010/020), 届出取下げ(050), 発行登録通知(060/070), 発行登録取下(110), 公開買付撤回(260), 基準日届出(370), 変更届出(380) |
| **Tier 4** | DEI + テキスト Fact（汎用ラベルアクセス経由） | **2** | 臨時報告書(180/190) |

> **Note**: Tier 1 の有報系も汎用ラベルアクセス（`stmts["売上高"]`）で直接取得可能。
> 三表（`income_statement()` 等）は期間/連結フィルタが必要な場合の推奨パス。
> Tier 2 の汎用ラベルアクセス（`Statements.__getitem__` / `search()`）は v0.1.0 で追加予定（§6-2 参照）。

**XBRL を含む全 27 書類タイプ** で構造化データを取得可能。
残り 8 書類は XBRL がそもそも存在しないため PDF 対応。

### 8-2. ユーザーストーリー別の体験

> **Note**: 以下のサンプルコード中のラベル名（「保有割合の合計」「買付け等の価格」等）は
> 実データ未確認の仮名称。実装時にタクソノミを確認して正確な名称に修正する。

#### A. 有報の財務分析（最も一般的な用途）

```python
import edinet

edinet.configure(api_key="...", taxonomy_path="/path/to/ALL_20251101")

# 企業名で検索して最新の有報を取得
company = edinet.Company("トヨタ")
filing = company.latest("有価証券報告書")

# ワンラインで三表
stmts = filing.xbrl()
pl = stmts.income_statement()                      # 損益計算書
bs = stmts.balance_sheet()                          # 貸借対照表
cf = stmts.cash_flow_statement()                    # キャッシュフロー計算書

# 科目アクセス（日本語ラベル/英語ラベル/concept 名）
pl["売上高"].value                                   # Decimal
pl["営業利益"].value
bs["総資産"].value

# 前期比較
pl_prior = stmts.income_statement(period="prior")

# 個別財務諸表
pl_solo = stmts.income_statement(consolidated=False)

# Rich で見慣れた階層表示
from rich.console import Console
Console().print(pl)                                  # インデント付きの財務諸表

# Jupyter でも
display(pl)                                          # _repr_html_ で表示

# DataFrame 変換 → 保存
df = pl.to_dataframe()
pl.to_parquet("toyota_pl_2025.parquet")

# 計算リンクの検証
from edinet.xbrl.validation import validate_calculations
results = validate_calculations(stmts)








for err in results:
    print(f"{err.parent}: 計算不一致 (差分={err.difference})")
```

#### B. 会計基準を意識しないクロス分析

```python
# J-GAAP 企業
sony = edinet.Company("ソニー")           # IFRS
toyota = edinet.Company("トヨタ")         # J-GAAP

sony_pl = sony.latest("有報").xbrl().income_statement()
toyota_pl = toyota.latest("有報").xbrl().income_statement()

# 会計基準に関係なく同じキーでアクセス
sony_pl["売上高"].value      # IFRS: Revenue
toyota_pl["売上高"].value    # J-GAAP: NetSales
```

#### C. 大量保有報告書の探索（有報以外）

```python
# 日付範囲で大量保有報告書を検索
filings = edinet.documents(
    start="2026-02-01", end="2026-03-01",
    doc_type="大量保有報告書",
)

for filing in filings:
    stmts = filing.xbrl()

    # タクソノミ解決済み日本語ラベルで完全一致取得（concept 名の知識不要）
    ratio = stmts.get("保有割合の合計")
    purpose = stmts.get("保有目的")
    print(f"{filing.filer_name}: {ratio.value}% ({purpose.value})")

    # 何があるか分からない時は search で部分一致探索
    stmts.search("保有")  # → ラベルに「保有」を含む全 LineItem

    # パイプラインに組み込む（get は None 安全）
    results = [
        {"filer": f.filer_name, "ratio": r.value if (r := f.xbrl().get("保有割合の合計")) else None}
        for f in filings
    ]
```

#### D. 公開買付の追跡

```python
filings = edinet.documents(
    start="2026-01-01", end="2026-03-01",
    doc_type="公開買付届出書",
)

for filing in filings:
    stmts = filing.xbrl()
    # タクソノミ解決済みラベルで直接取得
    price = stmts.get("買付け等の価格")
    target = stmts.get("対象者の名称")
    if price and target:
        print(f"{filing.filer_name} → {target.value} @ {price.value}")
```

#### E. テキストブロックの LLM 活用

```python
filing = edinet.Company("トヨタ").latest("有報")
stmts = filing.xbrl()

# テキストブロックをセクション名でアクセス
risk = stmts.sections["事業等のリスク"]         # クリーンテキスト
mdna = stmts.sections["経営者による財政状態…"]

# LLM に渡す
prompt = f"以下の有報のリスク情報を要約してください:\n{risk.clean_text}"
```

#### F. Filing Diff（訂正箇所の特定）

```python
# 訂正チェーンを辿る
original = filing.revision_chain().original
corrected = filing.revision_chain().latest

# Fact レベルの差分
from edinet.diff import diff_filings
changes = diff_filings(original, corrected)
for change in changes.modified:
    print(f"{change.label_ja}: {change.old_value} → {change.new_value}")
```

#### G. EDA（探索的データ分析）

```python
filing = edinet.Company("三菱UFJ").latest("有報")
stmts = filing.xbrl()

# Filing の概観
summary = stmts.summary()
print(summary)
# → 会計基準: J-GAAP (銀行業)
#   Fact 数: 3,247
#   標準科目: 89%, 非標準科目: 11%
#   連結: あり, 個別: あり
#   セグメント: 4 (リテール, ホールセール, 国際, 市場)
```

#### H. キャッシュ効率

```python
# 2回目以降はローカルキャッシュからロード（API コール不要）
filing = edinet.Company("トヨタ").latest("有報")
stmts = filing.xbrl()   # 1回目: API → ZIP → パース → キャッシュ保存
stmts = filing.xbrl()   # 2回目: キャッシュからロード（高速）
```

### 8-3. v0.1.0 の技術仕様

| 指標 | 値 |
|---|---|
| 対応書類タイプ | **35 全タイプ**（XBRL 27 + PDF 8） |
| 会計基準 | J-GAAP / IFRS / US-GAAP |
| 業種対応 | 23 業種（ConceptSet 自動導出） |
| 財務諸表 | BS / PL / CF（三表） |
| テスト数 | 1,267+ |
| Python | >= 3.12 |
| 依存 | httpx, lxml, pydantic, platformdirs（最小構成） |
| オプション依存 | pandas, pyarrow（analysis）, rich（display） |
| ライセンス | MIT |

### 8-4. v0.1.0 に含まれる全機能

各項目に FEATURES.md の機能名、NEXT.temp.md の Tier を付記。

**Data Access**
- `edinet.documents()` / `edinet.adocuments()` — 書類一覧（sync/async） `[list]` `{DONE}`
- `Filing.fetch()` / `Filing.afetch()` — ZIP ダウンロード（sync/async） `[fetch]` `{DONE}`
- `Filing.fetch_pdf()` — PDF ダウンロード `[fetch_pdf]` `{Tier B}`
- ローカル ZIP キャッシュ（`configure(cache_dir=...)` で設定） `[cache]` `{Tier A}`
- 訂正チェーン解決（`filing.revision_chain().latest`） `[revision_chain]` `{Tier A}`

**Company API**
- `edinet.Company("トヨタ")` — 名前/銘柄コード/EDINET コードで検索 `[company/lookup]` `{Tier A}`
- `company.get_filings()` — 企業単位の書類一覧 `[company/filings]` `{DONE}`
- `company.latest("有報")` — 最新書類ショートカット `[company/latest]` `{DONE}`

**XBRL Core**
- XBRL パーサー（strict/lenient、重複 Fact 検出） `[facts]` `{DONE}`
- Context 構造化（period, entity, dimension） `[contexts]` `{DONE}`
- Unit 解析（通貨、株数、複合単位） `[units]` `{DONE}`
- DEI 抽出（会計基準判別、業種コード判定） `[dei]` `{DONE}`
- 名前空間解決（標準/提出者別判別） `[namespaces]` `{DONE}`
- 脚注リンク解析（Fact ↔ 脚注テキスト紐付け） `[footnotes]` `{Tier B}`
- Filing サマリー（`stmts.summary()`） `[eda/summary]` `{Tier B}`

**Financial Statements**
- BS / PL / CF の三表組み立て `[statements/PL]` `[statements/BS]` `[statements/CF]` `{DONE}`
- J-GAAP / IFRS / US-GAAP 正規化 `[standards/normalize]` `{DONE}`
- 23 業種対応（ConceptSet 自動導出） `[taxonomy/concept_sets]` `{DONE}`
- 5 業種の専用科目（銀行/保険/証券/建設/鉄道） `[sector/*]` `{DONE}`
- 連結/個別切替（フォールバック付き、strict モード） `[dimensions/consolidated]` `{DONE}`
- 当期/前期選択（DEI ベース自動分類） `[dimensions/period_variants]` `{DONE}`
- 変則決算判定（6ヶ月/15ヶ月決算等） `[dimensions/fiscal_year]` `{Tier A}`
- 非標準科目の判定（`is_standard` + `shadowing_target`） `[taxonomy/custom_detection]` `{Tier A}`

**汎用 Fact アクセス（全 27 書類タイプ対応）** `[universal_access]` `{新規}`
- `stmts["保有割合の合計"]` — タクソノミ解決済みラベル（日本語/英語）or concept 名で完全一致取得
- `stmts.get("保有割合の合計")` — 完全一致取得（None 安全）
- `"保有割合の合計" in stmts` — 存在確認
- `stmts.search("保有割合")` — 部分一致検索（探索用）
- `stmts.items` — 全 LineItem（ラベル付き）
- `len(stmts)` / `for item in stmts` — Sequence プロトコル
- `stmts.to_dataframe()` — 全 Fact の DataFrame `[dataframe/facts]` `{DONE}`

**Text & Sections**
- テキストブロック抽出（`textBlockItemType`） `[text_blocks]` `{Tier B}`
- セクション名アクセス（`stmts.sections["事業等のリスク"]`） `[text_blocks/sections]` `{Tier B}`
- HTML 除去 → クリーンテキスト（LLM 前処理用） `[text_blocks/clean]` `{Tier B}`

**Taxonomy & Links**
- Calculation Linkbase（計算関係の木構造） `[calc_tree]` `{DONE}`
- Presentation Linkbase（表示順序の木構造） `[pres_tree]` `{DONE}`
- Definition Linkbase（Dimension 定義） `[def_links]` `{DONE}`
- ConceptSet 自動導出（23 業種、PL/BS/CF/SS/CI） `[taxonomy/concept_sets]` `{DONE}`
- ラベル解決（日英、標準/提出者別、フォールバックチェーン） `[taxonomy/labels]` `{DONE}`
- 非標準科目 → 標準科目の祖先マッピング `[taxonomy/standard_mapping]` `{Tier B}`

**Dimensions**
- 連結/個別フィルタ `[dimensions/consolidated]` `{DONE}`
- 当期/前期分類 `[dimensions/period_variants]` `{DONE}`
- 事業セグメント解析 `[dimensions/segments]` `{Tier B}`
- 地域セグメント解析 `[dimensions/geographic]` `{Tier B}`
- 変則決算判定 `[dimensions/fiscal_year]` `{Tier A}`

**Validation**
- 計算リンクに基づく加算チェック（丸め誤差考慮） `[validation/calc_check]` `{Tier A}`

**Filing Diff**
- 訂正前 vs 訂正後の Fact レベル差分 `[diff/revision]` `{Tier C}`
- 前期 vs 当期の科目増減 `[diff/period]` `{Tier C}`

**DataFrame & Export**
- `to_dataframe()` — 5 列 / 全カラム `[dataframe/facts]` `{DONE}`
- `to_csv()` / `to_parquet()` / `to_excel()` `[dataframe/export]` `{DONE}`

**Display**
- Rich ターミナル表示（階層表示、ConceptSet depth） `[display/rich]` `[display/statements]` `{DONE}`
- Jupyter HTML 表示（`_repr_html_`） `[display/html]` `{Tier B}`
- プレーンテキスト表示（Rich なしでも動作） `{DONE}`

**Cross-Cutting**
- Pydantic + frozen dataclass による型安全性 `[type_safety]` `{DONE}`
- .pyi スタブ（IDE 補完用） `[stubs]` `{DONE}`
- 構造化例外体系（`EdinetError` 階層） `[error_hierarchy]` `{DONE}`
- sync/async 全 I/O 対応 `[async_support]` `{DONE}`
- Arelle 非依存（lxml ベース軽量パーサー） `[no_arelle]` `{DONE}`

**FEATURES.md に対応なし（汎用パイプラインで代替）**
- `[doctype/tob]` — `stmts.search("買付")` / `stmts["買付け等の価格"]` で取得可能
- `[doctype/large_holding]` — `stmts.search("保有")` / `stmts["保有割合の合計"]` で取得可能
- `[doctype/shelf_registration]` — 汎用パイプラインで取得可能
- `[doctype/securities_notification]` — 財務諸表部分は三表パイプライン、届出書固有部分は汎用アクセス
- `[doctype/funds]` — タクソノミ体系が根本的に別。要望ベースで対応

### 8-4b. v0.1.0 の保守コスト影響

MAINTENANCE.md の既存保守カテゴリに対する影響:

| MAINTENANCE.md カテゴリ | v0.1.0 で追加される保守対象 |
|---|---|
| A. 自動生成マスタ | **なし** — company/lookup は既存 edinet_code.py を利用 |
| B. タクソノミ年次更新 | **微増** — notes/employees が jpcrp_cor の概念名を数件使用（既存 jgaap.py 83件と同カテゴリ） |
| C. 法令・API 仕様 | **なし** — fetch_pdf は既存 download.py の API パス追加のみ |
| D. 不変のハードコード | **なし** — text_blocks/sections の role URI 分類は concept_sets.py と同パターン |

**新しい保守カテゴリの追加はない。** 全 v0.1.0 追加機能は既存カテゴリに収まる。
universal_access（dict-like + search）はロジックのみでデータ保守ゼロ。
ラベルはタクソノミから自動解決されるため、タクソノミ更新に自動追従する。

### 8-5. v0.1.0 後に残るもの

| 項目 | 理由 |
|---|---|
| 株主資本等変動計算書 (SS) | 2次元テーブルの組み立てが複雑（Definition Linkbase 必須） |
| 包括利益計算書 (CI) | 利用頻度が低い |
| 注記テーブルパース (notes/*) | HTML テーブルのパースは堅牢性が低い。提出者ごとに構造が異なる |
| 書類タイプ別型付きオブジェクト | 保守コストに見合わない。汎用ラベルアクセスで代替可能。要望が来てから |
| タクソノミバージョニング | deprecated → 代替先の機械可読な参照がなく半自動推定が必要 |
| CLI | Python API のラッパー。優先度低 |
| MCP サーバー | AI 統合。v0.2.0+ で検討 |

### 8-6. 競合優位性

v0.1.0 リリース時点で、EDINET エコシステムにおいて以下の全項目で競合を上回る:

| 観点 | edinet v0.1.0 | 最大の競合 (edinet-tools, 27★) |
|---|---|---|
| 書類タイプ対応 | **35 全タイプ** | 30+ タイプ |
| 会計基準 | **J-GAAP + IFRS + US-GAAP** | J-GAAP + IFRS |
| 業種対応 | **23 業種 ConceptSet** | なし |
| Linkbase 解析 | **Calc + Pres + Def** | なし |
| セグメント分析 | **事業 + 地域** | なし |
| テキストブロック | **セクション + クリーン** | なし |
| 計算検証 | **calc_check** | なし |
| Filing Diff | **訂正 + 期間** | なし |
| 階層表示 | **ConceptSet depth** | なし |
| Jupyter 表示 | **_repr_html_** | なし |
| キャッシュ | **永続** | なし |
| Company 名前引き | **名前/銘柄コード/EDINET コード** | ticker/name |
| テスト | **1,267+** | 330 |
| 型安全性 | **Pydantic + .pyi** | 部分的 |

**これは「v0.1.0 にしては完璧」ではなく、「EDINET のディファクトスタンダードとして十分な v0.1.0」。**
