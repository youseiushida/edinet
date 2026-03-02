# 並列実装の安全ルール（必ず遵守）

あなたは Wave 1 / Lane 7 を担当するエージェントです。
担当機能: units

## 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/standards/__init__.py` を変更してはならない
   - `src/edinet/xbrl/dimensions/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   `src/edinet/xbrl/units.py` (新規), `tests/test_xbrl/test_units.py` (新規)
   上記以外の `src/` 配下のファイルは読み取り専用として扱うこと。

3. **既存インターフェースを破壊しないこと**
   - 既存の dataclass / class にフィールドを追加する場合は必ずデフォルト値を付与すること
   - 既存のフィールド名・型・関数シグネチャを変更してはならない
   - 既存の定数名を変更・削除してはならない（追加のみ可）

4. **`stubgen` を実行しないこと**
   - `uv run stubgen` は並列稼働中は使用禁止
   - stubs/ 配下のファイルを手動で変更してもいけない

5. **共有テストフィクスチャを変更しないこと**
   - `tests/fixtures/taxonomy_mini/` 配下の既存ファイルを変更してはならない
   - `tests/fixtures/xbrl_fragments/` 配下の既存ファイルを変更してはならない
   - テスト用フィクスチャが必要な場合は、自レーン専用のディレクトリを作成すること
   - ただし Lane 7 ではインラインリテラル方式を採用するため、フィクスチャディレクトリは不要

## 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.units import structure_units` （OK）
   - 例: `from edinet.xbrl import structure_units` （NG — __init__.py の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_units.py` に作成
   - 既存のテストファイル（test_contexts.py, test_facts.py, test_statements.py 等）は変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 0 で事前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawContext, RawUnit 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.financial.statements` (Statements, build_statements)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver)
     - `edinet.xbrl._namespaces` (NS_* 定数)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 7: units — 単位の解析と正規化

## 0. 位置づけ

FEATURES.md より:
> units: 単位の解析と正規化 [TODO]
>   - depends: facts
>   - detail: 通貨（JPY/USD/EUR）、株数、%、複合単位（per share 等）の型安全なハンドリング

Wave 1 の全 7 Lane のうち、比較的軽量な基盤モジュール。
現在のパイプラインでは `RawFact.unit_ref` が文字列（`"JPY"`, `"pure"` 等）のまま `LineItem.unit_ref` に転写されている。
このモジュールは `ParsedXBRL.units`（`RawUnit` のタプル）をパースし、型安全な `StructuredUnit` オブジェクトを生成する。

`structure_contexts()` が `RawContext` → `StructuredContext` を担うのと同じ位置づけで、
`structure_units()` が `RawUnit` → `dict[str, StructuredUnit]` を担う。

### 現在の状態

| コンポーネント | 現状 |
|---|---|
| `parser.py` | `RawUnit(unit_id, source_line, xml)` として生の XML 文字列を保持済み |
| `ParsedXBRL.units` | `tuple[RawUnit, ...]` で parser が抽出済み |
| `RawFact.unit_ref` | `str \| None` — unit_id を文字列参照（`"JPY"`, `"pure"`, `"shares"`, `"JPYPerShares"` 等） |
| `LineItem.unit_ref` | `str \| None` — RawFact からそのまま転写 |
| `xbrl/units.py` | 未作成 |

### 完了時のマイルストーン

```python
from edinet.xbrl.parser import parse_xbrl_facts
from edinet.xbrl.units import structure_units, StructuredUnit, SimpleMeasure, DivideMeasure

parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)
unit_map = structure_units(parsed.units)

# 通貨単位
jpy = unit_map["JPY"]
assert isinstance(jpy.measure, SimpleMeasure)
assert jpy.measure.namespace_uri == "http://www.xbrl.org/2003/iso4217"
assert jpy.measure.local_name == "JPY"
assert jpy.is_monetary is True
assert jpy.is_pure is False

# 純粋数値
pure = unit_map["pure"]
assert isinstance(pure.measure, SimpleMeasure)
assert pure.is_pure is True

# 株式数
shares = unit_map["shares"]
assert isinstance(shares.measure, SimpleMeasure)
assert shares.is_shares is True

# 複合単位（EPS/BPS: 円/株）
eps_unit = unit_map["JPYPerShares"]
assert isinstance(eps_unit.measure, DivideMeasure)
assert eps_unit.measure.numerator.local_name == "JPY"
assert eps_unit.measure.denominator.local_name == "shares"
assert eps_unit.is_per_share is True

# unit_map を使って Fact の単位を型安全に判定
for fact in parsed.facts:
    if fact.unit_ref and fact.unit_ref in unit_map:
        unit = unit_map[fact.unit_ref]
        if unit.is_monetary:
            print(f"{fact.local_name}: 金額 ({unit.currency_code})")
        elif unit.is_per_share:
            print(f"{fact.local_name}: 1株当たり")
```

---

## 1. 入力と出力

### 入力

- `ParsedXBRL.units: tuple[RawUnit, ...]`
  - 各 `RawUnit` は `unit_id: str | None`, `source_line: int | None`, `xml: str` を持つ
  - `xml` は `<xbrli:unit id="JPY">...</xbrli:unit>` の完全な XML 断片

### 出力

- `dict[str, StructuredUnit]` — unit_id をキー、構造化されたユニットを値とする辞書
  - `structure_contexts()` と同じパターン

---

## 2. データモデル設計

### 2.1 Measure（measure 要素の値）

```python
@dataclass(frozen=True, slots=True)
class SimpleMeasure:
    """単純な measure 値。

    Attributes:
        namespace_uri: measure のプレフィックスが展開された名前空間 URI。
            例: "http://www.xbrl.org/2003/iso4217"（iso4217:JPY の場合）
        local_name: measure のローカル名。
            例: "JPY", "shares", "pure"
        raw_text: measure 要素のテキスト値（元のプレフィックス付き）。
            例: "iso4217:JPY", "xbrli:shares"
    """
    namespace_uri: str
    local_name: str
    raw_text: str
```

### 2.2 DivideMeasure（divide 構造）

```python
@dataclass(frozen=True, slots=True)
class DivideMeasure:
    """divide 構造の複合単位。

    Attributes:
        numerator: 分子の measure。
        denominator: 分母の measure。
    """
    numerator: SimpleMeasure
    denominator: SimpleMeasure
```

### 2.3 Measure 型エイリアス

`contexts.py` の `Period = InstantPeriod | DurationPeriod` と同様に、型エイリアスを定義する:

```python
Measure = SimpleMeasure | DivideMeasure
"""measure 型。SimpleMeasure または DivideMeasure。"""
```

利用者は `Measure` を型注釈に使用できる:

```python
from edinet.xbrl.units import Measure

def process_measure(m: Measure) -> str: ...
```

### 2.4 StructuredUnit（メインの出力型）

```python
@dataclass(frozen=True, slots=True)
class StructuredUnit:
    """構造化された Unit。

    Attributes:
        unit_id: Unit の ID。
        measure: 単純 measure または divide 構造。
        source_line: 元 XML の行番号。
    """
    unit_id: str
    measure: SimpleMeasure | DivideMeasure
    source_line: int | None
```

### 2.5 名前空間定数

```python
_ISO4217_URI = "http://www.xbrl.org/2003/iso4217"
```

`is_monetary` 等の判定に使用する。`NS_XBRLI` は `_namespaces.py` から import 済み。
将来的に他モジュールで通貨判定が必要になった場合は `_namespaces.py` に移動する。

### 2.6 便利プロパティ（StructuredUnit に実装）

**重要**: 全てのプロパティは `namespace_uri` + `local_name` で判定する。`raw_text` はプレフィックスがインスタンスごとに異なりうるため使用しない（§3.3 の動的解決原則と一致させる）。

| プロパティ | 型 | ロジック |
|---|---|---|
| `is_monetary` | `bool` | `SimpleMeasure` かつ `namespace_uri == _ISO4217_URI` |
| `is_pure` | `bool` | `SimpleMeasure` かつ `namespace_uri == NS_XBRLI and local_name == "pure"` |
| `is_shares` | `bool` | `SimpleMeasure` かつ `namespace_uri == NS_XBRLI and local_name == "shares"` |
| `is_per_share` | `bool` | `DivideMeasure` かつ `numerator.namespace_uri == _ISO4217_URI` かつ `denominator.namespace_uri == NS_XBRLI and denominator.local_name == "shares"` |
| `currency_code` | `str \| None` | `is_monetary` → `local_name`（"JPY" 等）、それ以外 → `None` |

---

## 3. パース処理の詳細

### 3.1 `structure_units()` 関数

```python
import logging
logger = logging.getLogger(__name__)

def structure_units(raw_units: Sequence[RawUnit]) -> dict[str, StructuredUnit]:
    """RawUnit のシーケンスを構造化して辞書で返す。

    Args:
        raw_units: parse_xbrl_facts() が抽出した RawUnit のシーケンス。

    Returns:
        unit_id をキー、StructuredUnit を値とする辞書。
        unit_id が None の RawUnit はスキップする。
        重複 unit_id は後勝ち。

    Raises:
        EdinetParseError: XML パースエラー、measure 要素の欠落、
            divide 構造の不正など。
    """
```

`structure_contexts()` と同様に、`logger.debug()` でスキップ・重複を記録する:

```python
# unit_id が None の場合
logger.debug(
    "unit_id が None の RawUnit をスキップします (source_line=%s)",
    raw.source_line,
)

# 重複 unit_id の場合
logger.debug(
    "重複した unit_id=%r を検出しました。後勝ちで上書きします",
    raw.unit_id,
)
```

### 3.2 XML パースロジック

RawUnit.xml の構造は以下のいずれか:

**パターン A: 単純 measure**
```xml
<xbrli:unit id="JPY">
  <xbrli:measure>iso4217:JPY</xbrli:measure>
</xbrli:unit>
```

**パターン B: divide 構造**
```xml
<xbrli:unit id="JPYPerShares">
  <xbrli:divide>
    <xbrli:unitNumerator>
      <xbrli:measure>iso4217:JPY</xbrli:measure>
    </xbrli:unitNumerator>
    <xbrli:unitDenominator>
      <xbrli:measure>xbrli:shares</xbrli:measure>
    </xbrli:unitDenominator>
  </xbrli:divide>
</xbrli:unit>
```

パースの手順:

1. `lxml.etree.fromstring(raw_unit.xml.encode("utf-8"))` で XML をパース（`# noqa: S320`）
   - `XMLSyntaxError` を catch して `EdinetParseError` に変換する（`contexts.py` と同パターン）:
     ```python
     try:
         elem = etree.fromstring(raw_unit.xml.encode("utf-8"))  # noqa: S320
     except etree.XMLSyntaxError as exc:
         msg = f"Unit の XML パースに失敗しました (unit_id={uid!r})"
         raise EdinetParseError(msg) from exc
     ```
2. 子要素として `{NS_XBRLI}divide` が存在するか確認
   - **存在しない場合** → 直下の `{NS_XBRLI}measure` のテキストを取得 → `SimpleMeasure` を構築
     - **注意**: 複数の `<measure>` 要素が存在する場合（XBRL 2.1 §4.8 の乗算複合単位）は、最初の `<measure>` のみを `SimpleMeasure` として扱い、警告を発行する（EDINET では未出現だが堅牢性のため）
   - **存在する場合** → `unitNumerator/measure` と `unitDenominator/measure` をそれぞれ取得 → `DivideMeasure` を構築
3. measure テキストの None/空チェックを実施（`element.text` が `None` または空文字列 → `EdinetParseError`）。`.strip()` で前後空白を除去する:
   ```python
   measure_text = measure_elem.text
   if measure_text is None or measure_text.strip() == "":
       msg = f"measure 要素のテキストが空です (unit_id={uid!r})"
       raise EdinetParseError(msg)
   measure_text = measure_text.strip()
   ```
4. measure テキスト（例: `"iso4217:JPY"`）を `prefix:local` に分解
5. prefix → namespace_uri の解決には、XML 要素の `nsmap` を使用する（§3.3 参照）

### 3.3 名前空間解決

measure テキスト `"iso4217:JPY"` のプレフィックス `iso4217` は XML の名前空間宣言で解決する必要がある。
`lxml` の `element.nsmap` から prefix → namespace_uri のマッピングを取得できる。

| プレフィックス（典型） | 名前空間 URI | 備考 |
|---|---|---|
| `iso4217` | `http://www.xbrl.org/2003/iso4217` | 通貨コード |
| `xbrli` | `http://www.xbrl.org/2003/instance` | shares, pure |
| `utr` | `http://www.xbrl.org/2009/utr` | tCO2e 等 |

**注意**: プレフィックスはインスタンスごとに異なりうる（H-2）。`nsmap` に基づいて動的に解決すること。

### 3.4 エラーハンドリング

全ての `warnings.warn()` に `EdinetWarning` カテゴリを指定する（ライブラリ全体の一貫性）。
エラーメッセージは日本語（CLAUDE.md 準拠）。

| 状況 | 対応 | メッセージ例 |
|---|---|---|
| XML パースエラー | `EdinetParseError` | `f"Unit の XML パースに失敗しました (unit_id={uid!r})"` |
| `unit_id` が None | スキップ + `logger.debug()` | — |
| 重複 unit_id | 後勝ち + `logger.debug()` | — |
| `measure` 要素が見つからない | `EdinetParseError` | `f"measure 要素が見つかりません (unit_id={uid!r})"` |
| `measure` 要素のテキストが空/None | `EdinetParseError` | `f"measure 要素のテキストが空です (unit_id={uid!r})"` |
| 複数 measure 要素（乗算複合） | 最初の measure を採用 + `warnings.warn(..., EdinetWarning, stacklevel=2)` | `f"複数の measure 要素が検出されました。最初の要素のみ使用します (unit_id={uid!r})"` |
| measure テキストにプレフィックスがない | ローカル名のみで `SimpleMeasure` を構築（`namespace_uri=""`）、`warnings.warn(..., EdinetWarning, stacklevel=2)` | `f"measure にプレフィックスがありません (unit_id={uid!r})"` |
| measure プレフィックスが `nsmap` に存在しない | `namespace_uri=""` として構築、`warnings.warn(..., EdinetWarning, stacklevel=2)` | `f"measure プレフィックスが nsmap に存在しません: {prefix!r} (unit_id={uid!r})"` |
| divide 内に numerator がない | `EdinetParseError` | `f"unitNumerator が見つかりません (unit_id={uid!r})"` |
| divide 内に denominator がない | `EdinetParseError` | `f"unitDenominator が見つかりません (unit_id={uid!r})"` |
| divide 内の measure が空 | `EdinetParseError` | `f"divide 内の measure が空です (unit_id={uid!r})"` |

---

## 4. EDINET で出現する全ユニットパターン

A-4.a.md の調査結果より:

| unit_id | 構造 | measure | 用途 |
|---|---|---|---|
| `JPY` | 単純 | `iso4217:JPY` | 日本円の金額 |
| `{通貨3文字}` | 単純 | `iso4217:{通貨3文字}` (例: USD) | 外貨の金額 |
| `pure` | 単純 | `xbrli:pure` | 割合(%)、整数、小数、人数 |
| `shares` | 単純 | `xbrli:shares` | 株式数 |
| `JPYPerShares` | divide | `iso4217:JPY / xbrli:shares` | 1株当たり金額（EPS/BPS 等） |
| `tCO2e` | 単純 | `utr:tCO2e` | CO2換算温室効果ガス排出量（2025年版追加） |

パーサーは上記に限定せず、任意の measure/divide 構造をパースできる汎用設計とする。
便利プロパティ（`is_monetary` 等）のみが EDINET 固有のセマンティクスを持つ。

---

## 5. テスト設計

### 5.1 テストファイル

`tests/test_xbrl/test_units.py`

### 5.2 テストフィクスチャ

テスト内でインライン XML リテラルとして定義する（`test_contexts.py` と同一パターン）。
`RawUnit.xml` は短い文字列のため、外部ファイルの管理コストに見合わない。
`tests/fixtures/units/` ディレクトリは作成しない。

統合テスト（`test_roundtrip_with_parse_xbrl_facts`）では、既存の `tests/fixtures/xbrl_fragments/` 内に unit 要素を含むフィクスチャがあればそれを流用する。なければテスト内で完全な XBRL インスタンスの XML bytes リテラルを構築する。

### 5.3 テストケース一覧

`test_contexts.py` の `TestStructureContextsP0` / `TestStructureContextsP1` パターンに倣い、P0（必須）/ P1（推奨）でクラスを分割する。

テストクラスには `@pytest.mark.small` / `@pytest.mark.unit` を付与（既存テストの規約に合わせる）。
統合テストには `@pytest.mark.medium` / `@pytest.mark.integration` を付与。

```
# --- TestStructureUnitsP0 --- (@pytest.mark.small, @pytest.mark.unit)
# 必須テスト群: 基本パース + 基本エラー

test_simple_measure_jpy
    → "iso4217:JPY" が SimpleMeasure にパースされ、is_monetary=True, currency_code="JPY"

test_simple_measure_pure
    → "xbrli:pure" が SimpleMeasure にパースされ、is_pure=True

test_simple_measure_shares
    → "xbrli:shares" が SimpleMeasure にパースされ、is_shares=True

test_divide_measure_jpy_per_shares
    → divide 構造が DivideMeasure にパースされ、is_per_share=True

test_structure_units_returns_dict
    → structure_units() が dict[str, StructuredUnit] を返す

test_structure_units_multiple
    → 複数 RawUnit を含むリストから全 unit が辞書に格納される

test_structure_units_empty
    → 空リスト → 空辞書

test_convenience_properties
    → is_monetary, is_pure, is_shares, is_per_share, currency_code の網羅テスト

test_xml_syntax_error_raises
    → 壊れた XML 文字列で EdinetParseError が送出される

test_no_measure_element_raises
    → measure 要素がない unit XML で EdinetParseError

test_divide_missing_numerator_raises
    → divide 構造で unitNumerator がない場合に EdinetParseError

test_divide_missing_denominator_raises
    → divide 構造で unitDenominator がない場合に EdinetParseError

# --- TestStructureUnitsP1 --- (@pytest.mark.small, @pytest.mark.unit)
# 推奨テスト群: エッジケース + 警告 + 防御的処理

test_simple_measure_usd
    → "iso4217:USD" が SimpleMeasure にパースされ、is_monetary=True, currency_code="USD"

test_simple_measure_tco2e
    → "utr:tCO2e" が SimpleMeasure にパースされ、is_monetary=False, is_pure=False

test_structure_units_skip_none_id
    → unit_id=None の RawUnit はスキップされる（caplog で debug ログを検証）

test_structure_units_duplicate_id
    → 重複 unit_id は後勝ち（caplog で debug ログを検証）

test_source_line_preserved
    → StructuredUnit.source_line が RawUnit.source_line と一致

test_unknown_prefix_warns
    → nsmap に存在しないプレフィックスの measure で EdinetWarning を発行

test_no_prefix_measure
    → プレフィックスなしの measure テキスト（理論上起こりにくいが堅牢性のため）

test_multiple_measure_elements_warns
    → 複数 measure 要素（乗算複合単位）で EdinetWarning を発行し、最初の要素を採用

test_empty_measure_text_raises
    → measure 要素が存在するがテキストが空/Noneの場合に EdinetParseError

# --- TestStructureUnitsIntegration --- (@pytest.mark.medium, @pytest.mark.integration)
test_roundtrip_with_parse_xbrl_facts
    → parse_xbrl_facts() の出力の units を structure_units() に渡してパース成功
```

### 5.4 テスト方針

- **デトロイト派**: 内部実装に依存せず、公開 API の入出力でテスト
- `RawUnit` をテスト内で直接構築して `structure_units()` に渡すパターンが主体
- XML 文字列は短いためテスト内のヘルパー関数で生成
- 統合テストでは `parse_xbrl_facts()` を使って実際の XML バイトからの一貫性を確認

---

## 6. ファイル構成

### 6.1 作成ファイル

| ファイル | 種別 | 内容 |
|---|---|---|
| `src/edinet/xbrl/units.py` | 新規 | `SimpleMeasure`, `DivideMeasure`, `Measure`, `StructuredUnit`, `structure_units()`, `__all__` |
| `tests/test_xbrl/test_units.py` | 新規 | 上記テストケース（フィクスチャはインラインリテラル） |

`units.py` の `__all__` 定義（`contexts.py` と同パターン）:

```python
__all__ = [
    "SimpleMeasure",
    "DivideMeasure",
    "Measure",
    "StructuredUnit",
    "structure_units",
]
```

### 6.2 依存するファイル（読み取り専用）

| ファイル | 使用する型・関数 |
|---|---|
| `src/edinet/xbrl/parser.py` | `RawUnit`, `ParsedXBRL` |
| `src/edinet/xbrl/_namespaces.py` | `NS_XBRLI` |
| `src/edinet/exceptions.py` | `EdinetParseError`, `EdinetWarning` |

### 6.3 変更しないファイル

- `src/edinet/xbrl/__init__.py` — 変更禁止（Wave 完了後の統合タスクで更新）
- `src/edinet/xbrl/facts.py` — unit_ref は引き続き `str | None` で保持。StructuredUnit との紐付けは下流（Wave 2 以降）の責務
- `src/edinet/models/financial.py` — LineItem.unit_ref は変更しない
- `stubs/` — stubgen 禁止

---

## 7. 設計判断

### 7.1 なぜ `unit_ref: str` を `StructuredUnit` に置換しないのか

現在の `LineItem.unit_ref` は `str | None` で、unit_id 文字列をそのまま保持している。
このフィールドを `StructuredUnit | None` に変更すると:

- `build_line_items()` のシグネチャ変更が必要（`unit_map` 引数の追加）
- `LineItem` の frozen dataclass のフィールド型変更 → 後方互換性破壊
- `FinancialStatement.to_dataframe()` / `to_dict()` にも影響

これは **Lane 7 のスコープ外** であり、Wave 完了後の統合タスク（または Wave 2）で実施すべき。
Lane 7 では `structure_units()` を **独立したユーティリティ** として提供し、利用者は `unit_map[item.unit_ref]` で型安全な情報を引けるようにする。

### 7.2 なぜ measure の名前空間を動的解決するのか

EDINET の実データでは `iso4217:JPY` のプレフィックス `iso4217` は安定的だが、XBRL 仕様上プレフィックスはインスタンスごとに自由（H-2）。
`nsmap` を使った動的解決により、非標準的なプレフィックスのインスタンスにも対応できる。

ただし `RawUnit.xml` は `<xbrli:unit>` 要素の断片のみで、ルート要素の名前空間宣言が失われている可能性がある。
この場合の対策:
- `lxml.etree.fromstring()` 時に名前空間宣言がパース対象の XML 断片内に含まれていなければ `nsmap` が不完全になる
- **対策**: parser.py は `etree.tostring()` で `RawUnit.xml` を生成しており、名前空間宣言は要素に付随する（lxml のデフォルト挙動）。実際のパース結果を確認し、必要であればフォールバック辞書（well-known プレフィックス → URI）を用意する

### 7.3 well-known プレフィックスのフォールバック

名前空間解決が失敗した場合のフォールバック辞書:

```python
_WELL_KNOWN_PREFIXES: dict[str, str] = {
    "iso4217": "http://www.xbrl.org/2003/iso4217",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "utr": "http://www.xbrl.org/2009/utr",
}
```

これにより、nsmap に名前空間宣言がない XML 断片でも正しく解決できる。

**マージ優先順位**: `nsmap`（XML 要素から取得）が優先される。`_WELL_KNOWN_PREFIXES` は `nsmap` にプレフィックスが存在しない場合のフォールバックとしてのみ使用する。

**注意**: lxml の `element.nsmap` はデフォルト名前空間（`xmlns="..."` 宣言）を `None` キーで返す。マージ辞書の型を `dict[str, str]` に統一するために `None` キーをフィルタリングする:

```python
# lxml の nsmap から None キー（デフォルト名前空間）を除外
nsmap_str = {k: v for k, v in elem.nsmap.items() if k is not None}
resolved_nsmap = {**_WELL_KNOWN_PREFIXES, **nsmap_str}
```

(`{**fallback, **primary}` により、`primary` 側の値が優先される)

### 7.4 乗算複合単位（multiply-composed measure）への対応方針

XBRL 2.1 §4.8 では `<unit>` 直下に複数の `<measure>` 要素を並べることで乗算複合単位（例: m²）を表現できる。EDINET の実データでは出現しない（A-4 の調査結果に含まれていない）が、遭遇した場合の方針:

- 最初の `<measure>` 要素のみを `SimpleMeasure` として扱い、2つ目以降は無視する
- `EdinetWarning` で警告を発行する
- EDINET で出現した場合は `MultipliedMeasure` 型の追加を検討する（現時点では YAGNI）

同様に、divide 構造内の `unitNumerator` / `unitDenominator` に複数の `<measure>` 要素が存在する場合（XBRL 2.1 §4.8.2: 乗算が許可される）も、最初の要素のみを `SimpleMeasure` として扱い、警告を発行する。

---

## 8. スコープ / 非スコープ

### 8.1 スコープ

| # | 内容 |
|---|---|
| U-1 | `RawUnit.xml` のパースによる `StructuredUnit` 生成 |
| U-2 | 単純 measure（iso4217:*, xbrli:shares, xbrli:pure, utr:* 等）の構造化 |
| U-3 | divide 構造（JPYPerShares 等）の構造化 |
| U-4 | measure テキストのプレフィックス → 名前空間 URI 解決 |
| U-5 | 便利プロパティ（is_monetary, is_pure, is_shares, is_per_share, currency_code） |
| U-6 | `structure_units()` 関数の提供（`structure_contexts()` と同パターン） |
| U-7 | エラーハンドリング（measure 欠落、divide 不正構造） |
| U-8 | テスト（正常系・異常系・統合） |

### 8.2 非スコープ

| # | 内容 | 理由 |
|---|---|---|
| UN-1 | `LineItem.unit_ref` の型変更 | 後方互換性破壊。統合タスクの責務 |
| UN-2 | `build_line_items()` への unit_map 引数追加 | 同上 |
| UN-3 | UTR バリデーション | A-4.a.md: 「パーサーでの UTR バリデーションは不要」 |
| UN-4 | decimals の丸め処理 | validation/calc_check の責務（Phase 9） |
| UN-5 | 単位の等価性判定（v-equality） | XBRL 2.1 §4.10 の等価判定。parser.py のスコープ外と同様 |
| UN-6 | `__init__.py` の更新 | Wave 完了後の統合タスク |

---

## 9. 実装手順

### Step 1: データモデル定義

`src/edinet/xbrl/units.py` に以下を定義:
- `__all__` リスト
- `_ISO4217_URI` 定数
- `_WELL_KNOWN_PREFIXES` フォールバック辞書
- `SimpleMeasure`, `DivideMeasure` dataclass（全て `@dataclass(frozen=True, slots=True)` で不変）
- `Measure = SimpleMeasure | DivideMeasure` 型エイリアス
- `StructuredUnit` dataclass（`@dataclass(frozen=True, slots=True)` で不変）
- `logger = logging.getLogger(__name__)`

### Step 2: パースロジック実装

`_parse_single_unit()` モジュールレベル private 関数（`contexts.py` の `_parse_single_context()` と同様にネストではなくモジュールレベルに配置）:
0. `uid = raw.unit_id or "(unknown)"` でエラーメッセージ用変数を定義（`contexts.py` の `cid = raw.context_id or "(unknown)"` と同パターン）
1. `lxml.etree.fromstring(raw_unit.xml.encode("utf-8"))` で XML をパース（`# noqa: S320`）
   - `XMLSyntaxError` を catch して `EdinetParseError` に変換
2. `nsmap` からプレフィックス→名前空間の辞書を構築。`None` キーをフィルタリングしてマージ:
   ```python
   nsmap_str = {k: v for k, v in elem.nsmap.items() if k is not None}
   resolved_nsmap = {**_WELL_KNOWN_PREFIXES, **nsmap_str}
   ```
3. divide 要素の有無で分岐
   - divide なしの場合: 複数 measure 要素の検出 → 警告（`EdinetWarning`）+ 最初の要素を採用
4. measure テキストを `prefix:local` に分割、名前空間解決
5. `StructuredUnit` を返す

### Step 3: `structure_units()` 関数

`RawUnit` のシーケンスをイテレートし、`_parse_single_unit()` を呼び出して辞書を構築。
`unit_id=None` のスキップ、重複 `unit_id` の後勝ちは `logger.debug()` で記録（`structure_contexts()` と同パターン）。

### Step 4: 便利プロパティ

`StructuredUnit` に `@property` で `is_monetary`, `is_pure`, `is_shares`, `is_per_share`, `currency_code` を実装。
**全て `namespace_uri` + `local_name` で判定する**（`raw_text` は使用しない）。

### Step 5: テスト

`tests/test_xbrl/test_units.py` に §5.3 のテストケースを実装。
- RawUnit をテスト内のインライン XML リテラルで構築し、`structure_units()` の入出力を検証
- `@pytest.mark.small` / `@pytest.mark.unit` マーカーを付与
- `caplog` フィクスチャでスキップ・重複の debug ログを検証
- `pytest.warns(EdinetWarning)` で警告発行を検証

### Step 6: 統合テスト

`parse_xbrl_facts()` の出力と組み合わせた統合テストを追加。
テスト内リテラルで XBRL インスタンスの XML bytes を構築。
`@pytest.mark.medium` / `@pytest.mark.integration` マーカーを付与。

### Step 7: 検証

- `uv run pytest` — 全テスト PASS
- `uv run ruff check src tests` — Clean
- 既存テストが壊れていないことを確認

---

## 10. 工数見積もり

| Step | 内容 | 規模感 |
|---|---|---|
| 1 | データモデル + 定数 | 小（3 dataclass + 定数, ~50 行） |
| 2 | パースロジック | 中（XML パース + 名前空間解決 + エラーハンドリング, ~80 行） |
| 3 | structure_units() | 小（ループ + logger.debug, ~30 行） |
| 4 | 便利プロパティ | 小（5 property, ~25 行） |
| 5-6 | テスト | 中（~18 テストケース, ~250 行） |
| 合計 | | ~185 行 (src) + ~250 行 (test) |

Wave 1 の 7 Lane 中で最も軽量な部類。他レーンとの依存・衝突なし。
