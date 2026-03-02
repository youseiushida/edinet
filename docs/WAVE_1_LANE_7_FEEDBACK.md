# WAVE 1 LANE 7 フィードバック（第2ラウンド）: units — 単位の解析と正規化

## 前回フィードバックの反映状況

第1ラウンドの全指摘事項（CR-1, H-1〜H-4, M-1〜M-6, L-1〜L-5）が計画に正しく反映されていることを確認した。特に:

- CR-1（便利プロパティの `raw_text` 依存 → `namespace_uri` + `local_name`）: §2.5 で修正済み。重要注記も追記されている
- H-1〜H-4（`EdinetWarning` カテゴリ、`.encode("utf-8")`、`logger.debug()`、`XMLSyntaxError` catch）: §3.1〜§3.4 で全て反映済み
- M-1〜M-6（乗算複合単位、`__all__`、日本語エラーメッセージ、フィクスチャ方針、マージ優先順位、XML構文エラーテスト）: §3.4, §5.2, §5.3, §6.1, §7.3, §7.4 で全て反映済み

**第1ラウンドの残存問題はゼロ。**

以下は第2ラウンドとして、反映済み計画に対する新たな指摘を記載する。

---

## HIGH（API設計の一貫性・堅牢性に影響）

### H-1. `Measure` 型エイリアスの欠落

**現状（§2）**: `SimpleMeasure` と `DivideMeasure` の2つの型を定義し、`StructuredUnit.measure` のアノテーションは `SimpleMeasure | DivideMeasure`。

**問題**: `contexts.py` では以下のように型エイリアスを定義している:

```python
Period = InstantPeriod | DurationPeriod
"""期間型。InstantPeriod または DurationPeriod。"""
```

`units.py` にはこれに相当する型エイリアスがない。利用者が型注釈で `SimpleMeasure | DivideMeasure` を毎回書く必要があり、API の対称性が崩れる。

**修正**: §2 のデータモデル設計に以下を追加:

```python
Measure = SimpleMeasure | DivideMeasure
"""measure 型。SimpleMeasure または DivideMeasure。"""
```

§6.1 の `__all__` にも `"Measure"` を追加:

```python
__all__ = [
    "SimpleMeasure",
    "DivideMeasure",
    "Measure",
    "StructuredUnit",
    "structure_units",
]
```

これにより利用者は以下のように書ける:

```python
from edinet.xbrl.units import Measure

def process_measure(m: Measure) -> str: ...
```

---

### H-2. measure 要素のテキストが空・None の場合のエラーハンドリング漏れ

**現状（§3.4）**: エラーハンドリング表に「measure 要素が見つからない → `EdinetParseError`」は記載されているが、measure 要素が存在するがテキストが空の場合（`<xbrli:measure></xbrli:measure>` や `<xbrli:measure/>`）の対処がない。

**問題**: measure 要素が見つかった後、§3.2 の手順 3 で「measure テキスト（例: `"iso4217:JPY"`）を `prefix:local` に分解」する。ここで `element.text` が `None` または空文字列の場合:

- `None` のまま `.split(":", 1)` を呼ぶと `AttributeError`
- `""` を `.split(":", 1)` すると `[""]` が返り、prefix="" / local_name="" となる

いずれも期待しない動作。

**修正**: §3.4 のエラーハンドリング表に以下を追加:

| 状況 | 対応 | メッセージ例 |
|---|---|---|
| measure 要素のテキストが空 | `EdinetParseError` | `f"measure 要素のテキストが空です (unit_id={uid!r})"` |

§3.2 の手順 3 の前に、テキストの None/空チェックを明記:

```python
measure_text = measure_elem.text
if measure_text is None or measure_text.strip() == "":
    msg = f"measure 要素のテキストが空です (unit_id={uid!r})"
    raise EdinetParseError(msg)
measure_text = measure_text.strip()
```

§5.3 の異常系テストにも以下を追加:

```
test_empty_measure_text_raises
    → measure 要素が存在するがテキストが空の場合に EdinetParseError
```

---

### H-3. `nsmap` の `None` キーのフィルタリング

**現状（§7.3, §9 Step 2）**: `{**_WELL_KNOWN_PREFIXES, **nsmap_from_element}` でマージ。

**問題**: lxml の `element.nsmap` はデフォルト名前空間（`xmlns="..."` 宣言）を `None` キーで返す:

```python
>>> elem.nsmap
{None: "http://www.xbrl.org/2003/instance", "iso4217": "http://www.xbrl.org/2003/iso4217"}
```

この `None` キーがマージ辞書に混入すると、`_WELL_KNOWN_PREFIXES`（全て文字列キー）とキーの型が不統一になる。measure テキストの prefix は常に文字列なので `resolved_nsmap.get(prefix)` でのルックアップに実害はないが、型ヒントとコードの明確性のために `None` キーをフィルタリングすべき。

`contexts.py` の `_resolve_qname()` では nsmap を `dict[str | None, str]` として受け取っているが、units.py ではマージ辞書の型を `dict[str, str]` に統一するのが望ましい。

**修正**: §9 Step 2 のマージロジックを以下に変更:

```python
# lxml の nsmap から None キー（デフォルト名前空間）を除外
nsmap_str = {k: v for k, v in elem.nsmap.items() if k is not None}
resolved_nsmap = {**_WELL_KNOWN_PREFIXES, **nsmap_str}
```

---

## MEDIUM（実装の明確性・テスト品質の向上）

### M-1. `uid` 変数の定義パターンの明示

**現状（§3.2, §3.4）**: エラーメッセージで `unit_id={uid!r}` を使用しているが、`uid` 変数がどこで定義されるかが明示されていない。

**問題**: `contexts.py` では `_parse_single_context()` の冒頭で以下のパターンを使用:

```python
cid = raw.context_id or "(unknown)"
```

`_parse_single_unit()` でも同様のパターンが必要だが、計画に記載がない。実装エージェントが `raw.unit_id` を直接使うと、`unit_id=None` のケースでエラーメッセージが `unit_id=None` となり情報量が低い。

**修正**: §9 Step 2 の `_parse_single_unit()` の冒頭に以下を明記:

```python
uid = raw.unit_id or "(unknown)"
```

---

### M-2. テストの P0/P1 分類

**現状（§5.3）**: テストケースが「正常系」「異常系」「統合テスト」のカテゴリで分類されている。

**問題**: `test_contexts.py` は `TestStructureContextsP0`（14件、必須テスト群）と `TestStructureContextsP1`（8件、推奨テスト群）の2クラスに分かれている。`test_units.py` でもこのパターンを踏襲すべき。

**提案**: 以下の分類を推奨:

**P0（必須）**:
- `test_simple_measure_jpy`, `test_simple_measure_pure`, `test_simple_measure_shares`
- `test_divide_measure_jpy_per_shares`
- `test_structure_units_returns_dict`, `test_structure_units_empty`
- `test_xml_syntax_error_raises`, `test_no_measure_element_raises`
- `test_divide_missing_numerator_raises`, `test_divide_missing_denominator_raises`
- `test_convenience_properties`
- `test_structure_units_multiple`

**P1（推奨）**:
- `test_simple_measure_usd`, `test_simple_measure_tco2e`
- `test_structure_units_skip_none_id`, `test_structure_units_duplicate_id`
- `test_source_line_preserved`
- `test_unknown_prefix_warns`, `test_no_prefix_measure`, `test_multiple_measure_elements_warns`
- `test_empty_measure_text_raises`（H-2 で追加）
- `test_roundtrip_with_parse_xbrl_facts`（統合テスト）

---

### M-3. divide 内の numerator/denominator に複数 measure がある場合の方針

**現状（§7.4）**: 直下に複数の `<measure>` 要素がある場合（乗算複合単位）は最初の要素のみ採用 + 警告と明記されている。

**問題**: 同様のケースが divide 構造内の `unitNumerator` / `unitDenominator` 内でも発生しうる（XBRL 2.1 §4.8.2: unitNumerator/unitDenominator にも複数 measure を並べた乗算が許可される）。

```xml
<xbrli:divide>
  <xbrli:unitNumerator>
    <xbrli:measure>utr:m</xbrli:measure>
    <xbrli:measure>utr:m</xbrli:measure>  <!-- m² -->
  </xbrli:unitNumerator>
  <xbrli:unitDenominator>
    <xbrli:measure>xbrli:pure</xbrli:measure>
  </xbrli:unitDenominator>
</xbrli:divide>
```

EDINET では未出現だが、§7.4 と同様に「最初の measure のみ採用 + 警告」の方針を divide 内にも適用すべき。

**修正**: §7.4 に以下を追記:

```
同様に、divide 構造内の unitNumerator / unitDenominator に複数の measure 要素が
存在する場合も、最初の要素のみを SimpleMeasure として扱い、警告を発行する。
```

---

## LOW（実装ヒント、計画変更不要）

### L-1. `measure_text.strip()` の適用

contexts.py では日付テキストに `.strip()` を適用している（`test_strips_whitespace_in_date` テストあり）。measure テキストにも同様に `.strip()` を適用すべき。`<xbrli:measure> iso4217:JPY </xbrli:measure>` のような前後空白を許容する。

§3.2 の手順 3 に `measure_text = measure_text.strip()` を含めること。テストケースに `test_strips_whitespace_in_measure_text` を追加するかは任意（EDINET では未出現のため）。

---

### L-2. `test_unknown_prefix_warns` で使うプレフィックスの明確化

§5.3 の `test_unknown_prefix_warns` が意図通り動作するには、以下の条件を満たす XML を構築する必要がある:

1. measure テキスト内のプレフィックスが `_WELL_KNOWN_PREFIXES`（`iso4217`, `xbrli`, `utr`）に含まれない
2. かつ XML の名前空間宣言にも存在しない

注意: measure テキストは XML 要素のテキスト内容であり、XML 名前空間宣言とは独立している。したがって `<xbrli:measure>custom:FOO</xbrli:measure>` と書いても lxml は XML パースエラーを起こさない（`custom` は要素名のプレフィックスではないため）。

テストでは以下のような XML を使用すればよい:

```python
'<xbrli:unit id="X" xmlns:xbrli="http://www.xbrl.org/2003/instance">'
'<xbrli:measure>unknown_prefix:SomeUnit</xbrli:measure>'
'</xbrli:unit>'
```

---

### L-3. `_parse_single_unit` のアクセスレベルについて

計画では `_parse_single_unit()` を内部関数（アンダースコアプレフィックス）として記載しているが、`contexts.py` の `_parse_single_context()` と同様にモジュールレベルの private 関数として実装すべき（ネストされた関数ではなく）。これはテスト容易性の面でも有利。計画の記述はこのパターンと一致しているが、念のため明記する。

---

## 他レーンフィードバックとの一貫性チェック（第2ラウンド）

| パターン | contexts.py | 現計画 (units.py) | 判定 |
|----------|-------------|-------------------|------|
| 型エイリアス (`Period` / `Measure`) | `Period = InstantPeriod \| DurationPeriod` | **未定義 (H-1)** | 要追加 |
| 空テキストのバリデーション | `_parse_date()` で None/空チェック | **measure テキスト未チェック (H-2)** | 要追加 |
| `nsmap` None キーフィルタ | `dict[str \| None, str]` で受け取り | **未フィルタ (H-3)** | 要追加 |
| `uid`/`cid` 変数パターン | `cid = raw.context_id or "(unknown)"` | **未明記 (M-1)** | 推奨 |
| テスト P0/P1 分類 | `TestStructureContextsP0` / `P1` | **未分類 (M-2)** | 推奨 |
| `.strip()` 適用 | 日付テキスト / QName テキスト | **measure テキスト (L-1)** | 推奨 |

---

## 今回のフィードバック優先度まとめ

| ID | 優先度 | 概要 | 影響 |
|----|--------|------|------|
| H-1 | **HIGH** | `Measure` 型エイリアスの追加 | contexts.py の `Period` エイリアスとの API 対称性。利用者の型注釈の簡潔さ |
| H-2 | **HIGH** | measure 要素の空テキスト処理 | 空 measure テキストで `AttributeError` または無意味な `SimpleMeasure` が生成される |
| H-3 | **HIGH** | `nsmap` の `None` キーフィルタリング | 型安全性の向上。`dict[str, str]` としてマージ辞書を統一 |
| M-1 | MEDIUM | `uid` 変数定義パターンの明示 | contexts.py パターンとの一貫性。`None` 時のエラーメッセージ品質 |
| M-2 | MEDIUM | テスト P0/P1 分類 | test_contexts.py パターンとの一貫性 |
| M-3 | MEDIUM | divide 内の複数 measure 方針 | §7.4 との一貫性。EDINET 未出現だが方針の文書化 |
| L-1 | LOW | measure テキストの `.strip()` | 防御的プログラミング |
| L-2 | LOW | `test_unknown_prefix_warns` の構築ヒント | 実装ガイダンス |
| L-3 | LOW | `_parse_single_unit` のスコープ明示 | contexts.py パターンとの一貫性 |

---

## 総合判定

**計画は第1ラウンドのフィードバックを完璧に反映しており、非常に高品質。**

第2ラウンドの指摘は全て「contexts.py との微細なパターン一貫性」と「エッジケースの防御的処理」に関するもので、設計の根幹に影響するものはない。

H-1（`Measure` 型エイリアス）と H-2（空テキスト処理）を反映すれば、`structure_contexts()` と完全に対称な、ディファクトスタンダードにふさわしい API となる。

H-3 は実害こそ小さいが、lxml の nsmap の挙動を正しく理解した上でのコード品質向上として反映を推奨する。

MEDIUM/LOW は実装エージェントへのガイダンスとして有用だが、計画テキストへの反映は任意。

**計画品質: 5段階で ★★★★★ (5/5) — 第1ラウンドのフィードバック反映が完璧であり、残存する指摘は全て細部の改善。このまま実装を開始しても問題ない。**
