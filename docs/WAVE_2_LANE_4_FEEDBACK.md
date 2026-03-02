# Wave 2 / Lane 4 — standards/ifrs フィードバック（第4版・実装レビュー）

## 総合評価

**実装の完成度は極めて高い**。第3版フィードバックの全指摘が適切に反映されており、XSD 検証に基づく計画からの逸脱（CF 5 概念化、concept 名の修正等）も正確かつ文書化されている。全 61 テストが Pass、ruff lint クリーン、既存テスト 995 件にも影響なし。

ディファクトスタンダードなライブラリの品質基準を満たしている。残る指摘は主に**防御的検証の強化**と**パフォーマンス上の一貫性**に関するもの。

---

## テスト・CI 結果

```
tests/test_xbrl/test_standards_ifrs.py  61 passed (3.77s)
全テスト                                995 passed, 7 skipped (70.65s)
ruff check src/edinet/xbrl/standards/ifrs.py  All checks passed!
```

---

## 第3版フィードバックの解消状況

| # | 重要度 | 内容 | 状態 | 実装の質 |
|---|--------|------|------|---------|
| H-1 | HIGH | `IFRSMapping` の冗長性 → A案統合 | **解消** | `jgaap_concept`/`mapping_note` 統合が正確 |
| H-2 | HIGH | `_JGAAP_ONLY_CONCEPTS` SYNC コメント | **解消** | コメントが詳細かつ正確 |
| H-3 | HIGH | `IncomeTaxesDeferred` の表記修正 | **解消** | IFRS 非対応として正しく分類 |
| M-1 | MEDIUM | BS concepts 網羅性 → Lane 3 と同程度 | **解消** | 15 concepts（XSD 検証済み） |
| M-2 | MEDIUM | NonControllingInterests の J-GAAP 対応修正 | **解消** | `jgaap_concept="ProfitLossAttributableToNonControllingInterests"` |
| M-3 | MEDIUM | `jgaap_to_ifrs_map()` のキー範囲明確化 | **解消** | docstring に明記 |
| M-4 | MEDIUM | CF `period_type` テスト T46/T47 | **解消** | T47 は XSD 不在に合わせてリデザイン（良い判断） |
| M-5 | MEDIUM | `all_canonical_keys()` キャッシュ | **解消** | `_ALL_CANONICAL_KEYS` として事前構築 |
| L-1 | LOW | `IFRSProfile.module_groups` docstring | **解消** | 「固有モジュール」の定義が明確 |
| L-2 | LOW | `is_ifrs_module()` 非対称性注記 | **解消** | Lane 3 との差異を NOTE に記載 |
| L-3 | LOW | T21 双方向テスト拡張 | **解消** | IFRS 固有科目の逆方向チェックを追加（L210-L218） |
| L-4 | LOW | T29-T31 `label_hint` 検証 | **解消** | concept/order/label_hint の全フィールド比較 |

---

## XSD 検証に基づく計画からの正当な逸脱

実装時の XSD 検証により、計画の暫定値が以下のように修正されている。**全て正確で適切な変更**:

| 計画の暫定値 | 実装の確定値 | 理由 |
|------------|-----------|------|
| `IssuedCapitalIFRS` | `ShareCapitalIFRS` | XSD に IssuedCapitalIFRS が存在しない |
| `CurrentLiabilitiesIFRS` | `TotalCurrentLiabilitiesIFRS` | XSD の正確な要素名 |
| `NoncurrentLiabilitiesIFRS` | `NonCurrentLabilitiesIFRS` | XSD のタイポ (Labilities) をそのまま採用（正しい判断） |
| `NoncurrentAssetsIFRS` | `NonCurrentAssetsIFRS` | XSD では NonCurrent（大文字C） |
| CF 7 concepts | CF 5 concepts | `CashAndCashEquivalentsAt{Beginning,End}OfPeriodIFRS` が XSD に不在 |
| `CashFlowsFromUsedIn...` | `NetCashProvidedByUsedIn...` | XSD の正確な concept 名 |

---

## CRITICAL（修正必須）

なし。

---

## HIGH（強く推奨）

### H-1. `jgaap_to_ifrs_map()` に `_JGAAP_ONLY_CONCEPTS` と `jgaap_concept` の重複を検知する仕組みがない

`jgaap_to_ifrs_map()` の実装（L860-L866）:

```python
def jgaap_to_ifrs_map() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for m in _ALL_MAPPINGS:
        if m.jgaap_concept is not None:
            result[m.jgaap_concept] = m.concept  # ← IFRS concept 名を設定
    for jgaap_concept in _JGAAP_ONLY_CONCEPTS:
        result[jgaap_concept] = None              # ← None で上書き！
    return result
```

**問題**: `_JGAAP_ONLY_CONCEPTS` に含まれる概念が `_ALL_MAPPINGS` の `jgaap_concept` にも存在する場合、2番目のループが最初のマッピングを **静かに `None` で上書き** する。これはデータ破損バグの温床。

現在は `ShareholdersEquity` を `_JGAAP_ONLY_CONCEPTS` から正しく除外しているが（L619-L621 のコメント）、将来の変更で誤って追加されると双方向マッピングが壊れる。テスト T21 は `ifrs_to_jgaap_map()` 起点の整合性しか検証しておらず、この特定の破損パターンを検知できない。

**推奨**: `_validate_registry()` に重複チェックを追加:

```python
# _validate_registry() に追加
jgaap_concepts_in_mappings = {
    m.jgaap_concept for m in _ALL_MAPPINGS if m.jgaap_concept is not None
}
overlap = jgaap_concepts_in_mappings & _JGAAP_ONLY_CONCEPTS
if overlap:
    raise ValueError(
        f"_JGAAP_ONLY_CONCEPTS と _ALL_MAPPINGS.jgaap_concept に "
        f"重複があります: {overlap}"
    )
```

---

## MEDIUM（推奨）

### M-1. `get_ifrs_concept_set()` が毎回 `frozenset` を再構築する

L799-L811:
```python
def get_ifrs_concept_set(statement_type: StatementType) -> frozenset[str]:
    return frozenset(m.concept for m in _STATEMENT_INDEX.get(statement_type, ()))
```

`_ALL_CANONICAL_KEYS` は M-5 対応でモジュールレベルで事前構築されているのに、`get_ifrs_concept_set()` は呼び出しのたびに新しい `frozenset` を生成する。同じ設計原則の適用漏れ。

**推奨**: モジュールレベルで事前構築:

```python
_CONCEPT_SETS: dict[StatementType, frozenset[str]] = {
    st: frozenset(m.concept for m in mappings)
    for st, mappings in _STATEMENT_INDEX.items()
}

def get_ifrs_concept_set(statement_type: StatementType) -> frozenset[str]:
    return _CONCEPT_SETS.get(statement_type, frozenset())
```

Lane 3 が同じパターンを使っている場合は一貫性のためそのまま合わせてもよい。

---

### M-2. `ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` が毎回新しい辞書を生成する

L819-L866 の両関数は呼び出しのたびに新しい `dict` を構築する。`_ALL_MAPPINGS` と `_JGAAP_ONLY_CONCEPTS` は不変なので結果も不変。

**推奨**: 2つの選択肢:

**A案**: `@functools.cache` を付与（`_load_json` と同パターン）:
```python
@functools.cache
def ifrs_to_jgaap_map() -> dict[str, str | None]:
    ...
```

**B案**: モジュールレベルで事前構築し、関数はコピーを返す:
```python
_IFRS_TO_JGAAP: dict[str, str | None] = {m.concept: m.jgaap_concept for m in _ALL_MAPPINGS}
_JGAAP_TO_IFRS: dict[str, str | None] = ...

def ifrs_to_jgaap_map() -> dict[str, str | None]:
    return dict(_IFRS_TO_JGAAP)  # 防御的コピー
```

A案の方が簡潔。ただし戻り値が `dict`（mutable）なので、呼び出し元が変更する可能性を考慮すると B案のコピーが安全。あるいは `MappingProxyType` で不変ビューを返す方法もある。

Lane 3 が毎回生成しているならそのまま合わせてもよい（一貫性 > 最適化）。

---

### M-3. `ifrs_specific_concepts()` の結果がキャッシュされない

L767-L776:
```python
def ifrs_specific_concepts() -> tuple[IFRSConceptMapping, ...]:
    return tuple(m for m in _ALL_MAPPINGS if m.is_ifrs_specific)
```

`_ALL_MAPPINGS` は不変なので結果も毎回同じ。M-5 / M-1 と同じ設計原則。

**推奨**: モジュールレベルの事前構築:
```python
_IFRS_SPECIFIC: tuple[IFRSConceptMapping, ...] = tuple(
    m for m in _ALL_MAPPINGS if m.is_ifrs_specific
)

def ifrs_specific_concepts() -> tuple[IFRSConceptMapping, ...]:
    return _IFRS_SPECIFIC
```

---

### M-4. テストが `_load_json` をプライベート API として import している

L16: `from edinet.financial.standards.ifrs import _load_json`

テストが `_` プレフィックスのプライベート関数を直接 import している。Detroit-school テストは公開 API のみをテストする原則だが、テストフィクスチャの準備（キャッシュクリア）と JSON 比較のために使用しており、用途は理解できる。

**推奨**: 2つの選択肢:

**A案**: JSON 比較テスト (T29-T31) を `importlib.resources` 経由で直接 JSON を読むようにリファクタ:
```python
import importlib.resources, json

def _read_json(filename: str) -> list[dict]:
    ref = importlib.resources.files("edinet.xbrl.data").joinpath(filename)
    with importlib.resources.as_file(ref) as path:
        return json.loads(path.read_text(encoding="utf-8"))
```

**B案**: 現状維持。テストが内部実装の詳細に依存するリスクは低い（JSON ファイル読み込みのインターフェースは安定）。キャッシュクリアの fixture は `_load_json` が `@functools.cache` である限り必要。

B案の方が実用的だが、Lane 3 の対応を確認して揃えるのが望ましい。

---

## LOW（任意）

### L-1. `equity_parent` と `shareholders_equity` の canonical_key 分離が Wave 3 に暗黙の要件を課す

IFRS `EquityAttributableToOwnersOfParentIFRS` は `canonical_key="equity_parent"`、J-GAAP `ShareholdersEquity` は `canonical_key="shareholders_equity"` を使用する。概念的に近似だが等価ではないため異なるキーとする設計判断は正しい。

しかし、この結果 Wave 3 の `normalize` レイヤーは `reverse_lookup("equity_parent")` が IFRS のみ、`reverse_lookup("shareholders_equity")` が J-GAAP のみでヒットすることを認識し、cross-standard クエリ時に両者を「近似マッピング」として特別扱いする必要がある。

**推奨**: 既存の `jgaap_concept="ShareholdersEquity"` と `mapping_note` で十分に文書化されているため、コード変更は不要。ただし Wave 3 の normalize 計画時にこの点を明示的に考慮すること。

---

### L-2. `_load_json` の `@functools.cache` は引数が有限なので問題ないが、テスト間クリアの必要性が分かりにくい

L36-L39 の `_clear_ifrs_cache` fixture がテスト全体に `autouse=True` で適用されている。`_load_json` は 3 種類のファイル名しか受け付けないため、テスト間でキャッシュが汚染されるリスクは実質ゼロ。

**推奨**: 現状維持で問題ないが、fixture のコメントに「JSON ファイルの内容自体は不変のため safety measure」と明記すると意図が伝わりやすい。

---

### L-3. `_JGAAP_ONLY_CONCEPTS` の 5 + 6 構造がコメントのみで保証されている

`_JGAAP_ONLY_CONCEPTS` は Lane 3 の `is_jgaap_specific=True` の 5 概念 + IFRS 非対応の 6 概念で構成されている。テスト T45 は前者の 5 概念のみパラメタライズで検証しているが、後者の 6 概念（IncomeTaxesDeferred, DeferredAssets 等）が `jgaap_to_ifrs_map()` で `None` にマッピングされることは個別テストされていない。

**推奨**: T45 のパラメタライズに IFRS 非対応の代表的な概念を追加:

```python
@pytest.mark.parametrize(
    "jgaap_concept",
    [
        # is_jgaap_specific=True
        "OrdinaryIncome",
        "NonOperatingIncome",
        "NonOperatingExpenses",
        "ExtraordinaryIncome",
        "ExtraordinaryLoss",
        # IFRS 非対応
        "IncomeTaxesDeferred",
        "DeferredAssets",
        "LiabilitiesAndNetAssets",
    ],
)
```

---

## 実装品質の優れた点

以下は計画・実装の両面で特に高品質と判断した点:

1. **XSD 検証の徹底**: 計画の暫定 concept 名を全て XSD で検証し、6 箇所を修正。EDINET のタイポ（`NonCurrentLabilitiesIFRS`）も発見・文書化
2. **ShareholdersEquity の _JGAAP_ONLY_CONCEPTS 除外判断**: 計画に含まれていたが、`jgaap_to_ifrs_map()` の上書き問題を正確に認識して除外。コメントで理由を説明
3. **T47 のリデザイン**: 計画は「cash_beginning/cash_end が duration であること」を検証する予定だったが、XSD に概念自体が存在しないことを発見し、「IFRS CF にこれらが存在しないこと」を検証するドキュメンテーションテストに変更
4. **CF 概念名の修正**: 計画の `CashFlowsFromUsedIn...` → XSD の正確な `NetCashProvidedByUsedIn...` に修正
5. **`_validate_registry()` パターン**: `assert` ではなく `ValueError` を使用し、`python -O` でもスキップされない設計
6. **モジュール構造の対称性**: Lane 3 と完全対称な `__all__`、lookup/reverse_lookup/mappings_for_statement/get_profile API
7. **`functools` の `import` は行 28 にあるが `_load_json` 以外では使用されておらず、不要な `@cache` の乱用がない**: 必要な箇所にのみキャッシュを適用

---

## チェックリスト

- [ ] H-1: `_validate_registry()` に `_JGAAP_ONLY_CONCEPTS` と `jgaap_concept` の重複チェックを追加
- [ ] M-1: `get_ifrs_concept_set()` をモジュールレベルで事前構築（または Lane 3 との一貫性を優先）
- [ ] M-2: `ifrs_to_jgaap_map()` / `jgaap_to_ifrs_map()` のキャッシュ（または Lane 3 との一貫性を優先）
- [ ] M-3: `ifrs_specific_concepts()` のキャッシュ（または Lane 3 との一貫性を優先）
- [ ] M-4: テストの `_load_json` import を解消（または現状維持を明示的に判断）
- [ ] L-1: Wave 3 normalize 計画時に `equity_parent` / `shareholders_equity` 分離を考慮
- [ ] L-2: `_clear_ifrs_cache` fixture のコメント改善（任意）
- [ ] L-3: T45 の IFRS 非対応概念をパラメタライズ対象に追加

---

## 計画と実装の差分サマリー

| 項目 | 計画 | 実装 | 評価 |
|------|------|------|------|
| CF 概念数 | 7 | 5 | **正しい逸脱**（XSD 検証） |
| CF concept 名 | `CashFlowsFromUsedIn...` | `NetCashProvidedByUsedIn...` | **正しい逸脱**（XSD 検証） |
| BS `IssuedCapitalIFRS` | 暫定 | `ShareCapitalIFRS` | **正しい逸脱**（XSD 検証） |
| BS `CurrentLiabilitiesIFRS` | 暫定 | `TotalCurrentLiabilitiesIFRS` | **正しい逸脱**（XSD 検証） |
| BS `NoncurrentAssetsIFRS` | 暫定 | `NonCurrentAssetsIFRS` | **正しい逸脱**（XSD 検証） |
| BS `NoncurrentLiabilitiesIFRS` | 暫定 | `NonCurrentLabilitiesIFRS` | **正しい逸脱**（XSD タイポ） |
| `_JGAAP_ONLY_CONCEPTS` | `ShareholdersEquity` 含む | 除外 | **正しい逸脱**（双方向整合性） |
| テスト T47 | cash_beginning/end の duration 検証 | IFRS CF に不在を検証 | **正しい逸脱**（XSD 不在対応） |
| テスト数 | 47 予定 | 61 | **計画超過**（追加テスト充実） |
