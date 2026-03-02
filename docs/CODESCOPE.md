# CODESCOPE

各モジュールが **何を検証/処理し、何を検証/処理しないか** をコードレベルで定義する。
レビュー時の判断基準として使用し、モジュール間の責務境界を明確にする。

ライブラリ全体のスコープ（何を作り何を作らないか）は SCOPE.md を参照。

---

## 1. parser.py — XBRL インスタンスパーサー

### 責務

XBRL インスタンス bytes から **RawFact / RawContext / RawUnit を正しく抽出する**。
XBRL 仕様全体のバリデータではない。

### 検証する項目（strict=True でエラー）

| # | カテゴリ | 検証内容 | 根拠 |
|---|---------|---------|------|
| S-1 | XML 構文 | XML パースエラー、非 XBRL ルート要素 | パース不能 |
| S-2 | schemaRef | 欠落・複数の link:schemaRef | XBRL 2.1 必須 |
| S-3 | Context ID | id 欠落・重複 | Fact の contextRef 解決に必須 |
| S-4 | Unit ID | id 欠落・重複 | Fact の unitRef 解決に必須 |
| S-5 | Fact contextRef | 欠落・空文字・未定義参照 | Fact として成立しない |
| S-6 | Fact unitRef | 空文字・未定義参照 | 参照整合性 |
| S-7 | Fact decimals | 不正な値（非整数かつ非 INF）、unitRef なしでの decimals 存在、unitRef ありでの decimals 欠落（非 nil 時） | 数値 Fact の属性整合（A-3.1） |
| S-8 | xsi:nil | 不正な属性値（true/false/1/0 以外）、nil=true なのに値が存在 | A-3.3 |
| S-9 | 非 nil 空値 | 非 nil Fact の値が空（テキスト・数値とも） | A-3.6「空文字 Fact は存在しない」 |
| S-10 | 数値 lexical 妥当性 | unitRef がある非 nil Fact の値が数値として解釈不能 | A-3.8「純粋な数値文字列」 |
| S-11 | 重複 Fact 値不整合 | 同一 (concept, contextRef, unitRef, xml:lang) で値が不一致 | A-3, F5/F6 |
| S-12 | 重複 Fact decimals 不整合 | 同一キーで decimals が不一致 | 整合性検証の一部 |
| S-13 | Fact id | 空文字・重複 | XML id の一意性 |

### 検証しない項目（意図的にスコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| N-1 | Context 構造 | entity/period の存在・形式 | RawContext として XML 断片を保持するのみ。→ §2 contexts の責務 |
| N-2 | Unit 構造 | measure/divide の存在・形式 | RawUnit として XML 断片を保持するのみ。→ §3 units の責務 |
| N-3 | 重複 Fact の精度等価性 | decimals 差を考慮した XBRL 2.1 v-equality | XBRL 2.1 §4.6.6 の完全実装は非スコープ |
| N-4 | ネスト Fact | ルート直下でない Fact 候補 | A-6: EDINET では tuple 非使用。警告 + ignored_elements 記録で十分 |
| N-5 | タクソノミ型検証 | dateItemType, booleanItemType 等 | タクソノミ参照が必要。→ §4 facts→LineItem の責務 |
| N-6 | Context ID 命名規則 | EDINET 仕様の命名パターン準拠 | 参照整合性（S-5）で十分 |
| N-7 | UTR 準拠 | Unit の measure が UTR 登録値か | A-4.6「パーサーでの UTR バリデーションは不要」 |

### 補足

- **ネスト Fact**: strict=True でも警告 + ignored_elements 記録。エラーにしない（A-6: EDINET では tuple 非使用）
- **重複 Fact 判定**: キー = (concept, contextRef, unitRef, xml:lang)。数値は Decimal 正規化比較。decimals はキーに含めないが不一致時は警告/エラー

---

## 2. contexts — Context 構造化（Day 10）

### 責務

RawContext の XML 断片をパースし、**period / entity / dimensions を型付きオブジェクトに構造化する**。
parser.py の N-1「Context 構造は上位レイヤーの責務」の受け皿。

### 出力イメージ

```python
@dataclass(frozen=True, slots=True)
class StructuredContext:
    context_id: str
    period: InstantPeriod | DurationPeriod
    entity_id: str                               # identifier の値（例: "X99001-000"）
    dimensions: tuple[DimensionMember, ...]       # 空 = 全ディメンションがデフォルト
    source_line: int | None

@dataclass(frozen=True, slots=True)
class DimensionMember:
    axis: str       # Clark notation（例: "{ns}ConsolidatedOrNonConsolidatedAxis"）
    member: str     # Clark notation（例: "{ns}NonConsolidatedMember"）
```

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| C-1 | Period パース | instant → `date`、duration → `(start_date, end_date)` | A-2.9: YYYY-MM-DD 固定 |
| C-2 | Entity パース | entity/identifier のテキスト値を抽出 | A-2.2 |
| C-3 | Dimension パース | scenario 内の `xbrldi:explicitMember` を全て抽出。axis・member を Clark notation で保持 | A-2.3〜A-2.5 |
| C-4 | Fact 結合 | RawFact の contextRef から StructuredContext を引く `dict[str, StructuredContext]` を提供 | Day 10 の主目的 |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| CN-1 | 日付論理整合性 | start < end の検証 | EDINET データは金融庁検証済み。`date.fromisoformat()` でフォーマットは自然に検証される |
| CN-2 | Entity identifier フォーマット | EDINET コードパターンの検証 | 値の抽出で十分。命名規則検証は EDINET 固有であり汎用パーサーの責務外 |
| CN-3 | Entity scheme 検証 | scheme が EDINET のものか | 1種類しかないので検証する意味がない（A-2.2） |
| CN-4 | Context ID 命名規則 | ID 文字列のパターン解析 | period/scenario の XML 構造から直接値を取得する方が確実（A-2 推論2） |
| CN-5 | Typed Dimension | `xbrldi:typedMember` の解析 | EDINET では Explicit Dimension のみ使用（A-2.5）。v1.0.0 で IFRS 対応時に必要になれば拡張する |
| CN-6 | Segment 要素 | `xbrli:segment` の解析 | EDINET では scenario を使用し segment は不使用（A-2.3） |
| CN-7 | Dimension の意味解釈 | 連結/個別の判定、セグメント名の解決 | dimensions/ モジュール（FEATURES.md）の責務。contexts は axis/member の QName を保持するのみ |

### 設計判断の記録

- **Dimension を Context 内で構造化する理由**: Day 15 の PL 組み立てで連結/個別フィルタが即座に必要。dimensions/ モジュールは StructuredContext を消費する上位レイヤーであり、contexts モジュールは axis/member の抽出のみ行う
- **`dimensions` を `tuple[DimensionMember, ...]` にする理由**: `dict[str, str]` だと Typed Dimension 拡張時に型変更が必要。DimensionMember dataclass なら `TypedDimensionMember` サブクラス追加で対応可能。v1.0.0 での手戻りを防ぐ
- **バリデーションを最小限にする理由**: `date.fromisoformat()` がフォーマット検証を兼ねる。period 要素欠落や不正 XML は自然にエラーになる。明示的な検証コードを追加すると parser.py と同じ「なぜXを検証しないのか」問題が再燃する。必要になった時点で `validate()` メソッドを後付けすればよい（additive change）

---

## 3. units — Unit 構造化（Day 10 / 将来）

### 責務

RawUnit の XML 断片をパースし、**通貨・株数・純粋数値・複合単位を型付きオブジェクトに構造化する**。
parser.py の N-2「Unit 構造は上位レイヤーの責務」の受け皿。

> Day 10 の主要スコープは contexts であり、units は必要に応じて実装する。
> Day 15 では unitRef の文字列値（"JPY" 等）で十分なため、構造化の優先度は低い。

### スコープの概要（実装時に詳細化する）

- **処理する**: measure のテキスト値抽出、divide 構造（numerator/denominator）の解析
- **処理しない**: UTR 準拠検証（A-4.6）、通貨コードの正当性検証

---

## 4. facts → LineItem — 型変換と正規化（Day 13）

### 責務

RawFact + TaxonomyResolver から **LineItem（型付き・ラベル付き）を生成する**。
parser.py の N-5「タクソノミ型検証はパーサーの責務外」の受け皿。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| F-1 | 数値変換 | unitRef がある Fact の `value_raw: str` → `Decimal` | parser.py S-10 で lexical 妥当性は検証済み。ここでは変換のみ |
| F-2 | ラベル付与 | TaxonomyResolver から `LabelInfo` を取得し設定 | PLAN.md Day 12-13 |
| F-3 | context_id 保持 | RawFact.context_ref をそのまま LineItem に保持 | トレース可能性（PLAN.md §4） |
| F-4 | dimensions 保持 | StructuredContext から dimensions を LineItem に転写 | トレース可能性（PLAN.md §4） |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| FN-1 | 日付型の変換 | dateItemType の値を `date` オブジェクトに変換 | タクソノミ型情報なしでは数値 Fact と日付テキスト Fact を区別できない。unitRef の有無で数値は判別可能だが、日付/boolean はタクソノミ XSD の type 属性が必要（A-3.5） |
| FN-2 | Boolean 型の変換 | booleanItemType の "true"/"false" を `bool` に変換 | 同上 |
| FN-3 | テキスト Fact の型変換 | unitRef なし Fact の値を何らかの型に変換 | テキストはそのまま `str` で保持する。型変換はタクソノミ連携後に行う |

### 設計判断の記録

- **数値変換のみ行う理由**: `unitRef` の有無だけで「数値 Fact か否か」を判別でき、タクソノミ参照が不要。日付・boolean はタクソノミ XSD の `type` 属性がないと判別できない（A-3.5）。v0.1.0 ではタクソノミ型参照を前提としない
- **parser.py S-10 との関係**: parser.py が lexical 妥当性を検証済みなので、ここでの `Decimal(value_raw)` は安全に成功する前提。失敗した場合は parser.py のバグ

---

## 5. statements — 財務諸表の組み立て（Day 15）

### 責務

RawFact + StructuredContext + ラベル情報から **PL / BS / CF の FinancialStatement オブジェクトを組み立てる**。
「どの Fact を選び、どう並べるか」のルールを明示的にコード化する。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| ST-1 | Fact 選択 | 選択ルール（下記）に基づいて Fact を選択する | PLAN.md Day 15 |
| ST-2 | 科目分類 | JSON データファイルの concept 集合で PL/BS/CF に分類する | PLAN.md Day 15 |
| ST-3 | 並び順 | JSON の `order` に従う。JSON にない科目は末尾に出現順で追加する | PLAN.md Day 15 |
| ST-4 | ラベル解決 | TaxonomyResolver から LabelInfo を取得し LineItem に設定する | PLAN.md Day 12-13 |
| ST-5 | 重複候補の警告 | 選択ルール適用後も複数 Fact が残る場合、候補数と除外理由を含む warning を出す | PLAN.md Day 15 |

### Fact 選択ルール（v0.1.0）

```
1. period:       引数 period が None なら最新期間を選択
2. consolidated: 引数 consolidated=True なら連結を優先。連結がなければ個別にフォールバック
3. dimensions:   dimension なし（全社合計）の Fact のみ採用
4. 重複:         上記ルール適用後も複数 Fact が残る場合は warnings.warn()
```

- 「なぜその値を選んだか」が利用者にもコードにも説明可能であること
- ルールに合致しない Fact は捨てない。`ParsedXBRL.facts` に全て残る

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| SN-1 | 欠損科目の補填 | JSON 定義にあるが XBRL にない科目を None で出力すること | 1社の PL を見るのが主用途。欠損科目は正常な状態。企業間比較は dataframe/compare レイヤーで列揃えする |
| SN-2 | 非標準科目の除外 | 拡張科目を PL から除外するオプション | v0.1.0 では末尾追加で固定。データ欠落を防ぐ方が優先。v0.2.0 で `include_custom` オプションを検討 |
| SN-3 | Presentation Linkbase 並び順 | pres_tree による正式な表示順 | v0.1.0 では JSON の order で代替。pres_tree は Taxonomy & Links モジュール（FEATURES.md）の責務 |
| SN-4 | IFRS / US-GAAP 対応 | 非 J-GAAP の科目分類 | v0.1.0 は J-GAAP 一般事業会社のみ（PLAN.md §1） |
| SN-5 | 特定業種対応 | 銀行・保険・証券・建設・鉄道の勘定科目 | v0.1.0 は一般事業会社のみ。業種固有は sector/ モジュール（FEATURES.md）の責務 |
| SN-6 | 複数期間比較 | 当期 vs 前期の並列出力 | v0.1.0 では単一期間。Fact は全期間保持しているので v0.2.0 で拡張可能 |
| SN-7 | Calculation Linkbase 検算 | 親科目 = 子科目の合計の検証 | validation/ モジュール（FEATURES.md）の責務 |

### 設計判断の記録

- **欠損科目をスキップする理由**: `LineItem.value: Decimal` を `Decimal | None` に変えると下流全体に影響する破壊的変更。企業間比較は DataFrame merge 時に NaN が自然に出るので PL オブジェクト側で吸収する必要がない
- **非標準科目を末尾に追加する理由**: PLAN.md 記載どおり。後から `include_custom=True`（デフォルト）を足しても既存コードの挙動は変わらない（後方互換）
- **全 Fact を保持する理由**: 選択ルールで落ちた Fact もユーザーが独自に再抽出可能。「PL」ではなく「このルールで抽出した PL ビュー」というスタンス

---

## 6. taxonomy — タクソノミラベル解決（Day 12）

### 責務

EDINET 標準タクソノミの `_lab.xml` / `_lab-en.xml` をパースし、**concept → ラベルの辞書を構築する**。
提出者別タクソノミのラベルを追加読み込みし、拡張科目のラベルも解決する。
§4 facts→LineItem の F-2「ラベル付与」の基盤。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| T-1 | 標準ラベル構築 | `_lab.xml` / `_lab-en.xml` の loc→arc→label 接続からラベル辞書を構築 | C-10 |
| T-2 | 多言語対応 | `lang="ja"` / `lang="en"` でラベルを切り替え | C-5.6 |
| T-3 | 複数ロール対応 | 標準ラベル・冗長ラベル・合計ラベル等を role 指定で取得 | C-5.1 |
| T-4 | 提出者ラベル追加 | `load_filer_labels()` で提出者 `_lab.xml` bytes を追加読み込み | E-6 |
| T-5 | Clark notation 解決 | `resolve_clark()` で namespace URI + local_name からラベルを解決 | RawFact.concept_qname との接続 |
| T-6 | pickle キャッシュ | `platformdirs.user_cache_dir` 配下にキャッシュ保存。初回 ~3秒 → 2回目以降 ~50ms | H-9b |
| T-7 | フォールバック | 指定 role → 標準ラベル → local name の順でフォールバック | C-5.5 |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| TN-1 | Concept 辞書 | type, periodType, balance 等の属性 | H-9b L1。必要になった時点で追加 |
| TN-2 | Presentation / Calculation / Definition ツリー | リンクベースの木構造解析 | FEATURES.md の別モジュール（calc_tree, pres_tree, def_links）の責務 |
| TN-3 | arc override の完全実装 | `use="prohibited"` / `priority` の完全処理 | v0.1.0 では検出時 warning のみ。C-5.4 |
| TN-4 | lang フォールバック | 英語ラベルがない場合に日本語にフォールバック | C-5.6 で標準タクソノミは日英完全一致 |

### 設計判断の記録

- **`resolve()` の引数を `(prefix, local_name)` にする理由**: `_lab.xml` 内に namespace URI は存在しない。ラベル辞書のキーは必然的に prefix ベース。Clark notation からの解決は `resolve_clark()` で提供
- **提出者ラベルの管理**: `_filer_labels` を `_standard_labels` とは独立して管理。`clear_filer_labels()` で明示的にクリアするライフサイクル
- **prefix 抽出のフォールバック**: 標準 XSD パターン `{prefix}_{date}.xsd` に加え、提出者 XSD のファイル名形式にも対応するため fragment の `_[A-Z]` パターンで分割するフォールバックを備える
- **バージョン違い namespace のフォールバック（Day 14 追加）**: EDINET タクソノミの namespace URI にはバージョン日付が含まれる（例: `.../jpcrp/2024-11-01/jpcrp_cor`）。タクソノミパッケージ `ALL_20251101` は `2025-11-01` 版だが、実データの多くは前年の `2024-11-01` 版を使用する。`resolve_clark()` で完全一致に失敗した場合、日付部分を除去した正規化キーで再検索する。これにより FALLBACK 率が 91% → 0% に改善。H-3 で予見されていた問題の実装レベルの解決

---

## モジュール間の責務フロー

```
parser.py          contexts            facts→LineItem       statements
─────────          ────────            ────────────        ──────────
RawFact ───────────────────────────→ LineItem ──────────→ Fact 選択
RawContext ─────→ StructuredContext ─→ dimensions 転写 ──→ 期間・連結フィルタ
RawUnit ────────────────────────────────────────────────→ unitRef 文字列で十分（v0.1.0）
                                       ↑                   ↓
                    TaxonomyResolver ──→ ラベル付与     FinancialStatement
```

- §1 parser.py は **抽出** に専念し、構造解釈はしない
- §2 contexts は **構造化** に専念し、意味解釈（連結判定等）はしない
- §4 facts→LineItem は **型変換** に専念し、数値 Fact のみ変換する
- §5 statements は **選択と組み立て** に専念し、ルールを明示する
- §7 display は **表示フォーマット** に専念し、ビジネスロジックは持たない

---

## 7. display — 表示レイヤー（Day 16）

### 責務

FinancialStatement を人間が読みやすい形式で表示する。**表示のためのフォーマット変換のみ** を行い、
ビジネスロジック（Fact 選択・並び順の決定等）は §5 statements の責務。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| D-1 | プレーンテキスト | `FinancialStatement.__str__()` で Rich なしでもまともな表示 | PLAN.LIVING.md Day 16 |
| D-2 | Rich テーブル | `render_statement()` + `__rich_console__()` | PLAN.LIVING.md Day 16 |
| D-3 | DataFrame 変換 | `to_dataframe()` で pandas DataFrame に変換 | PLAN.LIVING.md Day 16 |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| DN-1 | HTML / Jupyter | `_repr_html_()` による Jupyter インライン表示 | FEATURES.md display/html → v0.2.0 |
| DN-2 | 複数期間並列表示 | 当期 vs 前期の並列テーブル | CODESCOPE.md SN-6 → v0.2.0 |
| DN-3 | decimals スケーリング | 百万円・千円表示 | 値は XBRL 原値のまま。スケーリングは利用者の責務 |
| DN-4 | 階層インデント | 小計・内訳の階層構造 | Presentation Linkbase の木構造がない（SN-3）。v0.2.0 |

### 設計判断の記録

- **描画ロジックを `display/rich.py` に集約する理由**: `models/financial.py` に Rich の import を持ち込まない。
  `__rich_console__` は 2 行のブリッジのみ。Rich がない環境でも `models/financial.py` の import は成功する
- **`render_statement()` を公開 API にする理由**: Rich Table オブジェクトを取得しカスタマイズしたい利用者向け
- **`to_dataframe()` のカラムを 5 列に絞る理由**: 利用者が最も頻繁に必要とする情報に限定。メタデータは `LineItem` から直接取得可能

---

## 8. E2E 統合 — Filing.xbrl() / Company.latest()（Day 17）

### 責務

Filing → Statements のフルパイプラインを提供する **オーケストレーター**。
新規のビジネスロジックは持たず、既存モジュール（§1〜§7）の接続のみを行う。

### 処理する項目

| # | カテゴリ | 内容 | 根拠 |
|---|---------|------|------|
| INT-1 | Filing.xbrl() | ZIP → parse → labels → statements のパイプライン | PLAN.LIVING.md Day 17 |
| INT-2 | Filing.axbrl() | xbrl() の非同期版 | async_support 方針 |
| INT-3 | Company.latest() | 最新 Filing の取得 | PLAN.LIVING.md Day 17 |
| INT-4 | 提出者ラベル抽出 | ZIP 内の _lab.xml / _lab-en.xml / .xsd の自動抽出 | Filing.xbrl() の内部ステップ |

### 処理しない項目（スコープ外）

| # | カテゴリ | 内容 | スコープ外の理由 |
|---|---------|------|----------------|
| INTN-1 | Company("7203") 糖衣構文 | ティッカーからの Company 構築 | EDINET コード一覧 CSV ベースの検索 → v0.2.0 |
| INTN-2 | xbrl() キャッシュ | パース結果の Filing 内キャッシュ | v0.1.0 では不要（fetch() の ZIP キャッシュで十分） |
| INTN-3 | iXBRL 対応 | .htm/.xhtml のパース | v0.2.0 |

### 設計判断の記録

- **Filing がパイプラインのオーケストレーターである理由**: Filing は ZIP をダウンロードし、XBRL bytes を持つ主体。パイプラインの入力（ZIP）と出力（Statements）を繋ぐのは Filing の責務として自然
- **TaxonomyResolver を xbrl() 内で毎回 new する理由**: pickle キャッシュにより 2 回目以降 ~50ms。ステートレスで提出者ラベルの漏洩を防ぐ
- **`_extract_filer_taxonomy_files()` のスコープ**: PublicDoc 配下のみ探索。監査報告書 XSD（`jpaud` 系）は `"audit" not in lower` で除外。ラベルファイル / XSD とも先勝ち（最初にマッチしたファイルを採用）

---

## 更新履歴

- 2026-02-24: 初版作成。parser.py (A-STRICT.a.md から移動) + contexts (Day 10) + statements (Day 15)
- 2026-02-24: §4 facts→LineItem (Day 13) を追加。型変換境界の明確化
- 2026-02-25: §6 taxonomy (Day 12) を追加。ラベル解決の責務境界を明確化
- 2026-02-27: §7 display (Day 16) を追加。表示レイヤーの責務境界を定義
- 2026-02-27: §8 E2E 統合 (Day 17) を追加。Filing.xbrl() / Company.latest() の責務境界を定義
