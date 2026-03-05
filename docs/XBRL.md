# xbrl-core 実装計画

汎用 XBRL ライブラリ `xbrl-core` の設計と実装計画を定義する。

## 概要

- **PyPI 名**: `xbrl-core`
- **import 名**: `xbrl_core`
- **依存**: lxml のみ（pandas は optional）
- **対象仕様**: XBRL 2.1 + iXBRL 1.1
- **エラーメッセージ言語**: 英語（エラーコード付き。上位層がローカライズ可能）
- **ライセンス**: edinet と同一

## ポジショニング

Arelle（リファレンス実装）を置き換えるものではない。

| 観点 | Arelle | xbrl-core |
|------|--------|-----------|
| 対象ユーザー | 規制当局、監査法人、タクソノミ開発者 | クオンツ、データサイエンティスト、財務分析者 |
| 目的 | 仕様準拠の検証 | XBRL → 構造化データ → DataFrame |
| API 設計 | ModelXbrl オブジェクトグラフ | frozen dataclass、immutable、型ヒント完備 |
| 依存 | 重い（GUI、Plugin 等） | lxml のみ |
| DTS 解決 | 完全（再帰的 HTTP fetch） | L1-L2（element 定義読み取り + Protocol で拡張） |
| Validation | Formula, XULE, Assertion, 計算検証 | 計算検証のみ |
| 出力 | XML レポート、DB | DataFrame / CSV / Parquet / Excel |

## 責務の境界

```
xbrl-core の責務:
┌─────────────────────────────────────────────┐
│  bytes                                       │
│    ↓ parse                                   │
│  RawFact / RawContext / RawUnit              │
│    ↓ structure                               │
│  StructuredContext / StructuredUnit           │
│    ↓ resolve labels (LabelResolver Protocol) │
│  LineItem (labels: tuple[LabelInfo, ...])    │
│    ↓                                         │
│  DataFrame / CSV / Parquet / Excel           │
│                                              │
│  + Linkbase 解析 (pre/cal/def/label/ref)     │
│  + XSD element 定義 (L1)                     │
│  + 計算検証                                   │
│  + テキストブロック抽出                         │
│  + iXBRL 対応                                 │
│  + 表示ユーティリティ (Rich/HTML)              │
└─────────────────────────────────────────────┘

上位層（edinet, tdnet 等）の責務:
  - データ取得（API, ZIP 展開, ファイル探索）
  - DEI 抽出（タクソノミ固有の要素マッピング）
  - 会計基準検出・概念正規化（CK enum 等）
  - 財務諸表の組み立て（PL/BS/CF 分類）
  - 名前空間の標準/提出者分類（ドメイン固有 URI パターン）
  - タクソノミパス解決（ファイルシステム構造固有）
```

## パッケージ構造

```
xbrl_core/
├── __init__.py
├── errors.py                 # XbrlError(code, message, **context)
│                             #   XbrlParseError, XbrlValidationError
│
├── parser.py                 # parse_xbrl(bytes) → ParsedXBRL
├── ixbrl_parser.py           # parse_ixbrl(bytes) → ParsedXBRL
├── contexts.py               # structure_contexts() → StructuredContext, ContextCollection
├── units.py                  # structure_units() → StructuredUnit
├── periods.py                # InstantPeriod, DurationPeriod
├── facts.py                  # build_line_items(resolver=None 可) → LineItem
├── labels.py                 # LabelResolver Protocol
├── _namespaces.py            # NS_XBRLI, NS_XLINK 等の XBRL 標準定数のみ
├── _linkbase_utils.py        # ROLE_LABEL 等の標準ロール定数のみ
│
├── models/
│   ├── __init__.py
│   └── financial.py          # LineItem, LabelInfo, LabelSource, StatementType
│
├── schema/
│   ├── __init__.py
│   ├── elements.py           # parse_xsd_elements(bytes) → dict[str, ElementDefinition]
│   └── resolver.py           # SchemaResolver Protocol（L2 拡張用）
│
├── linkbase/
│   ├── __init__.py
│   ├── presentation.py       # PresentationTree
│   ├── calculation.py        # CalculationTree
│   ├── definition.py         # HypercubeInfo 等
│   ├── label.py              # parse_label_linkbase(bytes) → tuple[RawLabel, ...]
│   ├── reference.py          # parse_reference_linkbase()
│   └── footnotes.py          # parse_footnote_links()
│
├── ixbrl/
│   └── format_registry.py    # FormatRegistry（標準 format 組み込み）
│
├── text/
│   ├── __init__.py
│   ├── blocks.py             # extract_text_blocks()
│   └── clean.py              # clean_html()
│
├── validation/
│   ├── __init__.py
│   └── calc_check.py         # validate_calculations()
│
├── display/
│   ├── __init__.py
│   ├── statements.py         # build_display_rows()
│   ├── rich.py               # render_statement()
│   └── html.py               # to_html()
│
└── dataframe/
    ├── __init__.py
    ├── facts.py              # line_items_to_dataframe()
    └── export.py             # to_csv(), to_parquet(), to_excel()
```

## 主要 Protocol / Interface

### LabelResolver

```python
class LabelResolver(Protocol):
    """ラベル解決のプロトコル。上位層が実装する。"""

    def resolve(
        self,
        concept_qname: str,
        lang: str,
        role: str = ROLE_LABEL,
    ) -> LabelInfo | None: ...

    def resolve_batch(
        self,
        concept_qnames: Sequence[str],
        lang: str,
        role: str = ROLE_LABEL,
    ) -> dict[str, LabelInfo | None]:
        """バッチ解決。デフォルト実装を提供。"""
        return {q: self.resolve(q, lang, role) for q in concept_qnames}
```

- `resolver=None` の場合は `LabelInfo(text=local_name, ..., source=FALLBACK)` で埋める
- EDINET 層の `TaxonomyResolver` がこの Protocol を実装する

### SchemaResolver

```python
class SchemaResolver(Protocol):
    """import/include 先の XSD を解決する。上位層が実装する。"""

    def resolve(self, namespace: str, schema_location: str) -> bytes | None: ...
```

- L1（単一 XSD 内の element 定義読み取り）では不要
- L2（import 追跡）で使用。将来の拡張点

### FormatRegistry

```python
class FormatRegistry:
    """iXBRL transformation format の登録・解決。"""

    def register(self, format_code: str, transformer: Callable[[str], str]) -> None: ...
    def transform(self, format_code: str, raw_value: str) -> str: ...
```

- 標準 format（`ixt:numdotdecimal` 等）は組み込み
- 地域固有（`ixt-jpn:` 等）は上位層で `registry.register()` する
- 標準 format（ixt:numdotdecimal 等）は汎用層に組み込む。
- _DATE_CJK_PATTERN ("2026年3月4日" → ISO変換) のような日本固有フォーマットはコアには含めず、上位層（edinet）が初期化時に ixt-jpn:kanjidate として registry.register() で注入する設計とする。これにより多言語・多国籍対応を維持する。

## 主要データモデル

### LabelInfo / LabelSource

```python
class LabelSource(enum.Enum):
    STANDARD = "standard"       # 標準タクソノミ由来
    EXTENSION = "extension"     # 提出者/拡張タクソノミ由来
    FALLBACK = "fallback"       # local_name 等のフォールバック

@dataclass(frozen=True, slots=True)
class LabelInfo:
    text: str
    role: str
    lang: str
    source: LabelSource
```

### LineItem

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LineItem:
    concept: str                          # Clark notation QName
    namespace_uri: str
    local_name: str
    labels: tuple[LabelInfo, ...]         # 言語・ロール可変
    value: Decimal | str | None
    unit_ref: str | None
    decimals: int | Literal["INF"] | None
    context_id: str
    period: Period
    entity_id: str
    dimensions: tuple[DimensionMember, ...]
    is_nil: bool
    source_line: int | None
    order: int

    def label(self, lang: str = "en", role: str | None = None) -> str | None:
        """指定言語・ロールのラベルテキストを返す。"""
        for lb in self.labels:
            if lb.lang == lang and (role is None or lb.role == role):
                return lb.text
        return None
```

- `label_ja` / `label_en` の固定フィールドを廃止し `labels` tuple に一般化
- `label()` メソッドで O(N) 探索（N は高々 4-6 個）
- edinet 層は `item.label("ja")` で従来と同等のアクセスを提供
- LabelResolver 非依存のフォールバック挙動　build_line_items(resolver=None) が渡された場合でもエラーにはせず、concept のローカル名（例: NetSales）を利用して、自動的に LabelInfo(text=local_name, lang="en", source=LabelSource.FALLBACK) というダミーラベルを生成し labels タプルに格納する。これにより、タクソノミが手元にない軽量な分析スクリプトでも単独で動作を完結できる。

### ElementDefinition（XSD L1）

```python
@dataclass(frozen=True, slots=True)
class ElementDefinition:
    name: str
    type_name: str | None           # e.g. "xbrli:monetaryItemType"
    period_type: str | None         # "instant" | "duration"
    balance: str | None             # "debit" | "credit"
    abstract: bool
    substitution_group: str | None  # e.g. "xbrli:item"
    nillable: bool
```

### RawLabel（Label Linkbase パーサ出力）

```python
@dataclass(frozen=True, slots=True)
class RawLabel:
    concept_href: str      # "#jppfs_cor_NetSales"
    text: str              # "売上高"
    lang: str              # "ja"
    role: str              # ROLE_LABEL
```

### エラー体系

```python
class XbrlError(Exception):
    code: str              # e.g. "XBRL_PARSE_001"
    context: dict          # 構造化されたエラーコンテキスト

    def __init__(self, code: str, message: str, **context: object) -> None:
        self.code = code
        self.context = context
        super().__init__(message)

class XbrlParseError(XbrlError): ...
class XbrlValidationError(XbrlError): ...
class XbrlWarning(UserWarning): ...
```

- メッセージは英語
- エラーコードにより上位層がローカライズ可能

## ファイル分類マップ

edinet の各ファイルが xbrl-core のどこに対応するかのマッピング。

### そのままコピー + import 書換え（層 A: 24 ファイル）

| edinet 側 | xbrl-core 側 | 備考 |
|-----------|-------------|------|
| `xbrl/parser.py` | `parser.py` | |
| `xbrl/ixbrl_parser.py` | `ixbrl_parser.py` | CJK 日付パターンは FormatRegistry に委譲 |
| `xbrl/units.py` | `units.py` | |
| `xbrl/periods.py` | `periods.py` | |
| `xbrl/linkbase/presentation.py` | `linkbase/presentation.py` | |
| `xbrl/linkbase/calculation.py` | `linkbase/calculation.py` | |
| `xbrl/linkbase/definition.py` | `linkbase/definition.py` | |
| `xbrl/linkbase/footnotes.py` | `linkbase/footnotes.py` | |
| `xbrl/validation/calc_check.py` | `validation/calc_check.py` | |
| `xbrl/text/blocks.py` | `text/blocks.py` | |
| `xbrl/text/clean.py` | `text/clean.py` | |
| `display/statements.py` | `display/statements.py` | |
| `display/rich.py` | `display/rich.py` | |
| `display/html.py` | `display/html.py` | |
| `dataframe/facts.py` | `dataframe/facts.py` | |
| `dataframe/export.py` | `dataframe/export.py` | |
| `financial/diff.py` | — | 汎用性を再評価。入れるなら `utils/diff.py` |
| `financial/summary.py` | — | 汎用性を再評価。入れるなら `utils/summary.py` |
| `financial/dimensions/period_variants.py` | — | DEI 依存を確認の上で判断 |
| `financial/dimensions/fiscal_year.py` | — | 同上 |
| `financial/dimensions/segments.py` | — | Definition Linkbase 依存のみなら含める |
| `financial/notes/employees.py` | — | concept 名が固有なら edinet 側に残す |

### リファクタが必要（層 B）

| edinet 側 | xbrl-core 側 | 作業内容 |
|-----------|-------------|---------|
| `xbrl/contexts.py` | `contexts.py` | 連結判定プロパティを削除。汎用 Context 構造のみ |
| `xbrl/_namespaces.py` | `_namespaces.py` | XBRL 標準定数のみ抽出。EDINET URI 分類は edinet 側に残す |
| `xbrl/_linkbase_utils.py` | `_linkbase_utils.py` | 標準ロール定数のみ抽出。href ヒューリスティクスは edinet 側 |
| `xbrl/facts.py` | `facts.py` | `TaxonomyResolver` → `LabelResolver Protocol`。`label_ja`/`label_en` → `labels` tuple |
| `models/financial.py` | `models/financial.py` | `LineItem` の labels 一般化。`LabelInfo` に `LabelSource` 追加 |

- context.pyについての備考：（理由）TDnetとEDINETで連結軸の名前（ConsolidatedNonconsolidatedAxis と ConsolidatedOrNonConsolidatedAxis）が異なるなど、タクソノミ固有の命名に依存するとバグの温床になるため。ビジネスロジック判定は上位層へ委ねる。

### 新規作成

| ファイル | 内容 |
|---------|------|
| `errors.py` | `XbrlError` + エラーコード体系 |
| `labels.py` | `LabelResolver` Protocol |
| `schema/elements.py` | XSD L1 パーサ (`parse_xsd_elements`) |
| `schema/resolver.py` | `SchemaResolver` Protocol（将来用） |
| `linkbase/label.py` | Label Linkbase パーサ（TaxonomyResolver から切り出し） |
| `linkbase/reference.py` | Reference Linkbase パーサ |
| `ixbrl/format_registry.py` | `FormatRegistry` |

### edinet 側に残るもの（層 C）

| モジュール | 理由 |
|-----------|------|
| `api/*` | EDINET API クライアント |
| `models/*` (financial 以外) | Filing, DocType, Company 等 |
| `_config.py`, `_http.py`, `_validators.py` | EDINET API 設定 |
| `xbrl/dei.py` | jpdei_cor 固有 |
| `xbrl/taxonomy/*` | TaxonomyResolver（パス解決・マージ・キャッシュ） |
| `xbrl/_namespaces.py` の分類部分 | EDINET URI パターン |
| `xbrl/text/sections.py` | jpcrp_cor セクションマッピング |
| `financial/statements.py` | PL/BS/CF 組み立て |
| `financial/extract.py` | CK 正規化パイプライン |
| `financial/mapper.py` | ConceptMapper |
| `financial/standards/*` | detect, normalize, canonical_keys, mappings |
| `exceptions.py` | `EdinetParseError.from_xbrl_error()` でローカライズ |

## 実装優先順位

### Phase 1: 基盤（xbrl-core 単体で動く最小構成）

1. `errors.py` — エラーコード体系
2. `_namespaces.py` — XBRL 標準定数
3. `_linkbase_utils.py` — 標準ロール定数
4. `parser.py` — XBRL パーサ
5. `contexts.py` — Context 構造化（連結判定なし）
6. `units.py` — Unit 構造化
7. `periods.py` — Period 型
8. `models/financial.py` — LabelInfo, LabelSource, LineItem（labels 一般化）
9. `labels.py` — LabelResolver Protocol
10. `facts.py` — build_line_items（resolver=None 対応）

### Phase 2: リンクベース + XSD

11. `linkbase/label.py` — Label Linkbase パーサ（TaxonomyResolver から切り出し）
12. `linkbase/presentation.py`
13. `linkbase/calculation.py`
14. `linkbase/definition.py`
15. `linkbase/footnotes.py`
16. `linkbase/reference.py` — 新規
17. `schema/elements.py` — XSD L1 パーサ
18. `schema/resolver.py` — SchemaResolver Protocol

### Phase 3: iXBRL + テキスト + 検証

19. `ixbrl_parser.py` — iXBRL パーサ
20. `ixbrl/format_registry.py` — FormatRegistry
21. `text/blocks.py`
22. `text/clean.py`
23. `validation/calc_check.py`

### Phase 4: 出力層

24. `dataframe/facts.py`
25. `dataframe/export.py`
26. `display/statements.py`
27. `display/rich.py`
28. `display/html.py`

## 設計原則

1. **frozen dataclass + tuple**: 全データモデルは immutable。dict は使わない
2. **lxml 単一依存**: pandas, rich 等は optional
3. **Protocol ベースの拡張**: LabelResolver, SchemaResolver, FormatRegistry
4. **エラーコード**: 全例外に機械可読なコードを付与。上位層がローカライズ可能
5. **resolver=None 許容**: タクソノミなしでも Fact → LineItem が動く
6. **logging のみ**: ライブラリは `logging.getLogger(__name__)` のみ。ハンドラは上位層が設定
