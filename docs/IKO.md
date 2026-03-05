# edinet → xbrl-core 移行作業方針

edinet ライブラリから汎用 XBRL 処理を `xbrl-core` パッケージに抽出する移行計画。

## 移行フェーズ

```
Phase 1:   xbrl-core を別パッケージとして作る（edinet は無関係）
Phase 1.5: edinet が xbrl-core に依存し、re-export で後方互換を維持
Phase 2:   deprecation warning を出す（1 マイナーバージョン）
Phase 3:   edinet 2.0 で re-export を削除（破壊的変更）
```

## Phase 1: xbrl-core の作成

### 目的

edinet に一切変更を加えずに xbrl-core を独立パッケージとして完成させる。

### 作業手順

#### 1. リポジトリ・プロジェクト構築

- 別リポジトリ（または monorepo の別ディレクトリ）に `xbrl-core` を作成
- `pyproject.toml` で依存を `lxml` のみに設定
- optional dependencies: `pandas`（dataframe 用）, `rich`（display 用）

#### 2. エラー体系の構築（最初にやる）

全ファイルが依存するため最初に確定させる。

```python
# xbrl_core/errors.py
class XbrlError(Exception):
    code: str
    context: dict

    def __init__(self, code: str, message: str, **context: object) -> None:
        self.code = code
        self.context = context
        super().__init__(message)

class XbrlParseError(XbrlError): ...
class XbrlValidationError(XbrlError): ...
class XbrlWarning(UserWarning): ...
```

エラーコード体系:

| プレフィックス | 対象 |
|-------------|------|
| `XBRL_PARSE_xxx` | パースエラー |
| `XBRL_CTX_xxx` | Context 構造化エラー |
| `XBRL_UNIT_xxx` | Unit 構造化エラー |
| `XBRL_LINK_xxx` | Linkbase パースエラー |
| `XBRL_VAL_xxx` | 検証エラー |
| `XBRL_IXBRL_xxx` | iXBRL パースエラー |

#### 3. コピー対象ファイルの移植

edinet の各ファイルを xbrl-core にコピーし、以下の変換を適用する:

| 変換 | 内容 |
|------|------|
| import パス | `from edinet.xbrl.xxx` → `from xbrl_core.xxx` |
| 例外クラス | `EdinetParseError` → `XbrlParseError` |
| エラーメッセージ | 日本語 → 英語 + エラーコード |
| docstring | 日本語 → 英語（Google Style 維持） |

#### 4. リファクタ対象ファイルの変更

##### contexts.py

- `_CONSOLIDATED_AXIS_LOCAL`, `_NON_CONSOLIDATED_MEMBER_LOCAL` を削除
- `is_consolidated`, `is_non_consolidated`, `has_extra_dimensions` プロパティを削除
- `ContextCollection.filter_consolidated()`, `filter_non_consolidated()`, `filter_no_extra_dimensions()` を削除
- 純粋な XBRL Context 構造化のみを提供

##### _namespaces.py

- `NS_XBRLI`, `NS_XBRLDI`, `NS_LINK`, `NS_XLINK`, `NS_XSI`, `NS_XML` を残す
- `NS_ISO4217`, `NS_XBRLDT`, `NS_NUM`, `NS_NONNUM`, `NS_UTR` を残す
- `EDINET_BASE`, `EDINET_TAXONOMY_BASE` を削除
- `NamespaceCategory`, `NamespaceInfo`, `classify_namespace()` を削除
- `is_standard_taxonomy()`, `is_filer_namespace()` を削除

##### _linkbase_utils.py

- `ROLE_LABEL`, `ROLE_TOTAL_LABEL` 等の標準ロール定数を残す
- `extract_concept_from_href()` の EDINET 固有ヒューリスティクスを削除

##### facts.py

- `TaxonomyResolver` 引数 → `LabelResolver | None` 引数
- `resolver=None` の場合: `LabelInfo(text=local_name, role=ROLE_LABEL, lang="", source=FALLBACK)`
- `label_ja` / `label_en` → `labels: tuple[LabelInfo, ...]`

##### models/financial.py

- `LineItem`: `label_ja`/`label_en` → `labels: tuple[LabelInfo, ...]` + `label()` メソッド
- `LabelInfo`: `source` フィールドの型を `LabelSource`（STANDARD/EXTENSION/FALLBACK）に変更
- `LabelInfo`, `LabelSource` の import 元を `xbrl_core.models.financial` に移動

#### 5. 新規ファイルの作成

##### labels.py

```python
class LabelResolver(Protocol):
    def resolve(self, concept_qname: str, lang: str, role: str = ROLE_LABEL) -> LabelInfo | None: ...
    def resolve_batch(self, concept_qnames: Sequence[str], lang: str, role: str = ROLE_LABEL) -> dict[str, LabelInfo | None]: ...
```

##### linkbase/label.py

TaxonomyResolver 内の `_parse_lab_xml` 相当ロジックを切り出す。

```python
@dataclass(frozen=True, slots=True)
class RawLabel:
    concept_href: str
    text: str
    lang: str
    role: str

def parse_label_linkbase(xml_bytes: bytes) -> tuple[RawLabel, ...]: ...
```

##### linkbase/reference.py

Reference Linkbase パーサ。Presentation/Calculation と同パターンで実装。

##### schema/elements.py

```python
@dataclass(frozen=True, slots=True)
class ElementDefinition:
    name: str
    type_name: str | None
    period_type: str | None
    balance: str | None
    abstract: bool
    substitution_group: str | None
    nillable: bool

def parse_xsd_elements(xsd_bytes: bytes) -> dict[str, ElementDefinition]: ...
```

##### schema/resolver.py

```python
class SchemaResolver(Protocol):
    def resolve(self, namespace: str, schema_location: str) -> bytes | None: ...
```

##### ixbrl/format_registry.py

```python
class FormatRegistry:
    def register(self, format_code: str, transformer: Callable[[str], str]) -> None: ...
    def transform(self, format_code: str, raw_value: str) -> str: ...
```

#### 6. テストの移植

- edinet の `tests/test_xbrl/` から汎用モジュールのテストを移植
- import パスを `xbrl_core` に変更
- テストフィクスチャ（XML ファイル等）は xbrl-core 側に配置
- **テストの重複は禁止**。xbrl-core に移したモジュールのテストは edinet 側から削除（Phase 1.5 で実施）

#### 7. CI / リリース

- xbrl-core 単体で `pytest` が通ることを確認
- `ruff check` を通す
- PyPI への公開（テスト公開 → 正式公開）

---

## Phase 1.5: edinet の依存追加

### 目的

edinet が xbrl-core に依存するように変更し、re-export で後方互換を維持する。

### 作業手順

#### 1. pyproject.toml の変更

```toml
[project]
dependencies = [
    "xbrl-core>=0.1.0",
    "lxml>=5.0",
    "httpx>=0.27",
]
```

#### 2. re-export の設定

xbrl-core に移したモジュールを edinet 側から re-export する。

```python
# edinet/xbrl/parser.py (Phase 1.5)
"""後方互換のための re-export。

xbrl_core.parser を使用してください。このモジュールは edinet 2.0 で削除されます。
"""
from xbrl_core.parser import (
    ParsedXBRL as ParsedXBRL,
    RawFact as RawFact,
    RawContext as RawContext,
    RawUnit as RawUnit,
    parse_xbrl as parse_xbrl_facts,  # 関数名の互換
)
```

#### 3. 例外のラップ

```python
# edinet/exceptions.py (Phase 1.5)
from xbrl_core.errors import XbrlParseError

class EdinetParseError(EdinetError):
    """日本語メッセージでラップ。"""

    @classmethod
    def from_xbrl_error(cls, err: XbrlParseError) -> EdinetParseError:
        msg = _JA_MESSAGES.get(err.code, str(err))
        return cls(msg)
```

#### 4. TaxonomyResolver の LabelResolver 実装

```python
# edinet/xbrl/taxonomy/__init__.py (Phase 1.5)
from xbrl_core.labels import LabelResolver
from xbrl_core.linkbase.label import parse_label_linkbase

class TaxonomyResolver:
    """LabelResolver Protocol を実装。"""

    def resolve(self, concept_qname, lang, role=ROLE_LABEL):
        # 既存ロジックをそのまま維持
        ...

    def resolve_batch(self, concept_qnames, lang, role=ROLE_LABEL):
        return {q: self.resolve(q, lang, role) for q in concept_qnames}
```

内部の `_parse_lab_xml` は `parse_label_linkbase()` に委譲する。

#### 5. LineItem の互換対応

edinet 層で従来の `label_ja`/`label_en` アクセスを提供する方法:

**案 A: Statements 組み立て時に変換**

```python
# edinet/financial/statements.py
# LineItem を使う箇所で item.label("ja") を呼ぶ形にリファクタ
label_text = item.label("ja") or item.local_name
```

**案 B: edinet 固有の拡張 LineItem**（非推奨）

```python
# 継承は避ける。xbrl_core.LineItem をそのまま使い、
# アクセス側で .label("ja") を呼ぶ
```

推奨は**案 A**。edinet 内部のコードを `.label("ja")` 呼び出しに統一する。←案A採用する！！

#### 6. contexts.py の連結判定復元

xbrl-core の StructuredContext には連結判定がないため、edinet 層でユーティリティを提供する。

```python
# edinet/xbrl/contexts_ext.py
CONSOLIDATED_AXIS_SUFFIX = "ConsolidatedOrNonConsolidatedAxis"
NON_CONSOLIDATED_MEMBER_SUFFIX = "NonConsolidatedMember"

def is_consolidated(ctx: StructuredContext) -> bool:
    for dim in ctx.dimensions:
        if dim.axis.endswith(CONSOLIDATED_AXIS_SUFFIX):
            return not dim.member.endswith(NON_CONSOLIDATED_MEMBER_SUFFIX)
    return True
```

あるいは ContextCollection のサブクラス/ラッパーとして提供。

#### 7. テスト更新

- xbrl-core に移したテストを edinet 側から削除
- edinet 側には xbrl-core + edinet の結合テストのみ残す
- re-export 経由のテスト: `from edinet.xbrl.parser import parse_xbrl_facts` が動くことを確認

---

## Phase 2: Deprecation Warning

### 目的

ユーザーに移行猶予を与える。1 マイナーバージョン（例: edinet 1.9.0）で実施。

### 作業

re-export モジュールに deprecation warning を追加する。

```python
# edinet/xbrl/parser.py (Phase 2)
import warnings

def __getattr__(name):
    warnings.warn(
        f"edinet.xbrl.parser.{name} は edinet 2.0 で削除されます。"
        f"xbrl_core.parser.{name} を使用してください。",
        DeprecationWarning,
        stacklevel=2,
    )
    import xbrl_core.parser
    return getattr(xbrl_core.parser, name)
```

### ドキュメント

- CHANGELOG に移行ガイドを記載
- README にマイグレーションセクションを追加

---

## Phase 3: edinet 2.0

### 目的

re-export を削除し、edinet を純粋な EDINET 固有層にする。

### 作業

- `edinet/xbrl/parser.py` 等の re-export モジュールを削除
- `edinet/xbrl/__init__.py` の公開 API を edinet 固有のものだけに整理
- SemVer メジャーバージョンアップ

### edinet 2.0 のパッケージ構造

```
edinet/
├── __init__.py
├── _config.py
├── _http.py
├── _validators.py
├── exceptions.py              # EdinetError, EdinetParseError.from_xbrl_error()
├── public_api.py
│
├── api/                       # EDINET API クライアント
│   ├── documents.py
│   ├── download.py
│   └── cache.py
│
├── models/                    # EDINET 固有モデル
│   ├── filing.py
│   ├── company.py
│   ├── doc_types.py
│   └── ...
│
├── xbrl/                      # EDINET 固有の XBRL 拡張
│   ├── dei.py                 # jpdei_cor DEI 抽出
│   ├── namespaces.py          # EDINET URI 分類 (classify_namespace)
│   ├── contexts_ext.py        # 連結判定ユーティリティ
│   ├── taxonomy/              # TaxonomyResolver (implements LabelResolver)
│   └── text/sections.py       # jpcrp_cor セクションマッピング
│
├── financial/                 # 財務諸表組み立て
│   ├── statements.py          # PL/BS/CF 組み立て
│   ├── extract.py
│   ├── mapper.py
│   └── standards/
│       ├── detect.py
│       ├── normalize.py
│       ├── canonical_keys.py
│       ├── statement_mappings.py
│       └── summary_mappings.py
│
├── display/                   # edinet 固有の表示カスタマイズ（必要なら）
└── dataframe/                 # edinet 固有の DataFrame カスタマイズ（必要なら）
```

---

## Phase 1.5 補足: アダプタが必要な 5 箇所

Phase 1.5 で edinet を xbrl-core に依存させる際、以下 5 箇所に薄いアダプタが必要。
いずれも数行の変更で済み、ふるまいの変化はゼロ。

### A1. StructuredContext の連結判定（§6 で既述）

xbrl-core の StructuredContext には `is_consolidated` 等がない。
edinet 側で `has_dimension()` を使った判定関数を提供する。

```python
# edinet/xbrl/contexts_ext.py
def is_consolidated(ctx: StructuredContext) -> bool:
    for dim in ctx.dimensions:
        if dim.axis.endswith("ConsolidatedOrNonConsolidatedAxis"):
            return not dim.member.endswith("NonConsolidatedMember")
    return True
```

影響範囲: `ContextCollection.filter_consolidated()` 等を使っている箇所。

### A2. LineItem の label_ja / label_en アクセス

**案 A 採用決定済み**（§5 参照）。edinet 内部を `.label("ja")` に統一する。

書き換え対象の grep パターン:
```
item.label_ja.text  →  item.label("ja") or item.local_name
item.label_en.text  →  item.label("en") or item.local_name
item.label_ja       →  (LabelInfo を直接使う箇所は labels タプルから検索)
```

影響範囲:
- `edinet/financial/statements.py` — FinancialStatement 組み立て
- `edinet/display/statements.py` — 表示行構築
- `edinet/display/html.py` — HTML 出力
- `edinet/display/rich.py` — Rich テーブル出力
- `edinet/dataframe/facts.py` — DataFrame カラム生成
- `edinet/models/financial.py` — FinancialStatement の to_dataframe / render 等

### A3. TaxonomyResolver → LabelResolver Protocol 実装（§4 で既述）

`resolve_clark()` のシグネチャを `LabelResolver.resolve()` に合わせる。

```python
# TaxonomyResolver に追加（既存の resolve_clark を委譲するだけ）
def resolve(self, concept_qname: str, lang: str, role: str = ROLE_LABEL) -> LabelInfo | None:
    result = self.resolve_clark(concept_qname, role=role, lang=lang)
    if result.source == LabelSource.FALLBACK:
        return None  # xbrl-core は「見つからない」を None で表現
    return result

def resolve_batch(self, concept_qnames, lang, role=ROLE_LABEL):
    return {q: self.resolve(q, lang, role) for q in concept_qnames}
```

注意: edinet の `resolve_clark()` は常に LabelInfo を返す（FALLBACK 含む）。
xbrl-core の `LabelResolver.resolve()` は見つからなければ None を返し、
フォールバック生成は `build_line_items()` 側が担当する。この責務分離に注意。

### A4. iXBRL の CJK 日付フォーマット注入

xbrl-core の FormatRegistry に CJK 日付変換は組み込まれていない（設計上の意図）。
edinet 側で初期化時に注入する。

```python
# edinet 側の iXBRL パース呼び出し箇所
from xbrl_core.ixbrl.format_registry import FormatRegistry
from xbrl_core.ixbrl_parser import parse_ixbrl_facts

registry = FormatRegistry()
registry.register("ixt-jpn:kanjidate", _convert_kanji_date)  # 既存の _DATE_CJK_PATTERN ロジック
result = parse_ixbrl_facts(data, format_registry=registry)
```

`_convert_kanji_date` は現在 `edinet/xbrl/ixbrl_parser.py` の `_DATE_CJK_PATTERN` +
`_normalize_cjk_date()` をそのまま関数化するだけ。

### A5. TextBlock.is_consolidated の復元

xbrl-core の TextBlock には `is_consolidated` フィールドがない。
edinet 側で context_map から導出する。

```python
# edinet 側
block = extract_text_blocks(facts, context_map)
is_consolidated = is_consolidated(context_map[block.context_ref])  # A1 の関数を使用
```

影響範囲: `edinet/xbrl/text/blocks.py` の呼び出し元。

---

## 移行で得られる具体的メリット（ElementDefinition の活用）

Phase 1.5 で xbrl-core に移行すると、`parse_xsd_elements()` による
ElementDefinition が使えるようになる。**edinet は現在 XSD のメタデータを
一切読んでおらず、concept 名の suffix に頼った推測をしている。**

### 推測→正確な判定に置き換えられる 3 箇所

| 現状（推測） | 該当箇所 | xbrl-core で置換 |
|---|---|---|
| `concept.endswith("Abstract") or concept.endswith("Heading")` | `edinet/xbrl/linkbase/presentation.py:472` | `ElementDefinition.abstract == True` |
| `local_name.endswith("TextBlock")` | `edinet/xbrl/text/blocks.py` | `ElementDefinition.type_name == "nonnum:textBlockItemType"` |
| `preferred_label` の role URI だけで合計行判定 | `edinet/xbrl/linkbase/presentation.py` | `ElementDefinition.balance` (debit/credit) と組み合わせ |

### ElementDefinition で将来強化できる機能

| フィールド | 活用 |
|---|---|
| `balance` (debit/credit) | 財務諸表の符号自動判定。借方概念が貸方に出ていたら警告 |
| `type_name` | monetaryItemType / stringItemType / dateItemType の型安全な判別。現状は `unit_ref is not None` で推測 |
| `period_type` | インスタンスの context period と XSD 定義の整合性検証 |
| `nillable` | nillable=false な概念に nil fact があれば警告 |
| `substitution_group` | tuple vs item の区別（現状は考慮なし） |

### TaxonomyResolver での ElementDefinition 統合案

```python
# TaxonomyResolver.__init__() で XSD もパースする
from xbrl_core.schema.elements import parse_xsd_elements

class TaxonomyResolver:
    def __init__(self, taxonomy_path, ...):
        # 既存のラベル辞書構築
        self._standard_labels, self._ns_to_prefix = _build_label_dict(taxonomy_dir)

        # 新規: XSD 要素定義の読み込み
        self._elements: dict[str, ElementDefinition] = {}
        for xsd_path in taxonomy_dir.glob("*/[0-9]*/*.xsd"):
            elements = parse_xsd_elements(xsd_path.read_bytes())
            self._elements.update(elements)

    def get_element(self, local_name: str) -> ElementDefinition | None:
        return self._elements.get(local_name)

    def is_abstract(self, local_name: str) -> bool:
        elem = self._elements.get(local_name)
        return elem.abstract if elem is not None else False
```

これにより PresentationNode 構築時の abstract 判定が
`concept.endswith("Abstract")` → `resolver.is_abstract(concept)` に改善される。

### BUG-6（PL に SS/CF 混入）への示唆

ElementDefinition 単独では直せない（period_type は instant/duration しか言わない）。
ただし Presentation Linkbase の role URI 分類と組み合わせれば：

```python
# role URI → StatementCategory の分類は既に edinet にある
for role_uri, tree in presentation_trees.items():
    category = classify_role_uri(role_uri)
    # category が "income_statement" の role に属する concept だけを PL に含める
    # → SS/CF の concept が PL に混入しなくなる
```

現在の ConceptSet ベースの分類は既にこの方向だが、
xbrl-core の PresentationTree をそのまま使えるのでコードが簡潔になる。

---

## Phase 1 完了状況（実績）

Phase 1 は 2026-03-06 時点でコード面は完了。

- ソース: `src/xbrl_core/` — 38 ファイル
- テスト: `tests_xbrl/` — 26 テストファイル、262 テスト全パス
- フィクスチャ: `tests_xbrl/fixtures/` — edinet の `tests/fixtures/` から独立コピー済み
- ruff: クリーン（0 errors）
- 照合: `tools/xbrl_core_verify.py` で edinet vs xbrl-core の出力を 49 項目突き合わせ、全パス
  - 唯一の意図的差異: iXBRL の CJK 日付（edinet は変換、xbrl-core は FormatRegistry 未注入時は生値）
- 残作業: pyproject.toml 作成、README、PyPI リリース（別リポ切り出し時に実施）

---

## 注意事項

### やらないこと

- Phase 1 中に edinet のコードを変更しない
- Phase 1 中に edinet が xbrl-core に依存しない
- テストを両方のリポジトリで重複させない
- xbrl-core に EDINET 固有のロジックを入れない

### リスク管理

| リスク | 対策 |
|-------|------|
| PyPI 名 `xbrl-core` が取られる | 早期に名前を確保（空パッケージでも可） |
| Phase 1.5 で予期しない非互換 | re-export のテストを充実させる |
| LineItem の labels 変更が広範囲に波及 | Phase 1.5 で edinet 内部を `.label("ja")` に統一し、外部 API は re-export で吸収 |
| xbrl-core のバージョンアップで edinet が壊れる | edinet の pyproject.toml でバージョン上限を設定 (`xbrl-core>=0.1,<1.0`) |

### タイムライン目安

| フェーズ | 期間 | 前提 |
|---------|------|------|
| Phase 1 | 2-3 週間 | xbrl-core の初回リリース |
| Phase 1.5 | 1-2 週間 | edinet の依存追加 + re-export |
| Phase 2 | 1 マイナーリリース分 | deprecation warning 追加 |
| Phase 3 | メジャーリリース | edinet 2.0 |
