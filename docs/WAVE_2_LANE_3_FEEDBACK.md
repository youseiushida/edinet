# WAVE_2_LANE_3_FEEDBACK — standards/jgaap: J-GAAP 科目の正規化マッピング 計画レビュー (Rev.2)

## 総評

**計画の完成度: ★★★★★ (5/5)**

Rev.1 のフィードバック反映が極めて高品質。13 項目のフィードバックが全て適切に反映され、計画の構造的欠陥は解消された。特に以下が秀逸:

1. **C-1 の解消**: §5.7 で canonical key を「権威的リファレンス」として位置づけ、Lane 4/5 との不整合と解消方針を具体的に記述。Lane 4 の `IFRSConceptMapping` 計画を確認したところ、`canonical_key: str` フィールドが追加され Lane 3 の値を参照する設計になっており、**実際に整合が取れている**
2. **C-2 の解消**: `label_ja` の値を JSON の `label_hint` と完全一致させた。`pl_jgaap.json` / `bs_jgaap.json` / `cf_jgaap.json` の全エントリと §5.2-5.4 を突き合わせ検証し、**全 44 concept で完全一致を確認**
3. **M-3 の解消**: `_validate_registry()` 検証関数方式の採用。`python -O` 耐性の確保は、Docker 本番環境での利用を想定するライブラリとして必須

前回 ★5 にならなかった唯一の理由（C-1: レーン間インターフェース不整合）が解消されたため、**★5** と評価する。

### 前回フィードバックの反映状況

| FB ID | 優先度 | 状態 | 検証結果 |
|-------|--------|------|----------|
| C-1 | CRITICAL | **解消** | §5.7 で方針明記。Lane 4 の `IFRSConceptMapping` も `canonical_key` フィールドを持ち Lane 3 のキー値を参照する設計に更新済み |
| C-2 | CRITICAL | **解消** | §5.2 の PL 15/16 の `label_ja` が JSON と完全一致。T18-T20 で `label_hint` 検証も追加 |
| H-1 | HIGH | **解消** | §5.4 に NOTE 追加済み |
| H-2 | HIGH | **解消** | §4.1 `reverse_lookup()` docstring に業種限定の明記 |
| H-3 | HIGH | **解消** | §9 Q8 追加。Lane 4 にも `IFRSProfile` が定義され対称的構造を採用 |
| M-1 | MEDIUM | **解消** | §2.2 NG-8（SS）追加 |
| M-2 | MEDIUM | **解消** | §2.2 NG-9（CI）追加、将来候補も記載 |
| M-3 | MEDIUM | **解消** | §6.3 で `_validate_registry()` 方式に変更 |
| M-4 | MEDIUM | **解消** | §8.3 に `label_hint` 検証追加 |
| M-5 | MEDIUM | **解消** | §4.3 docstring にモジュールグループ列挙 |
| L-1 | LOW | 未対応（妥当） | `canonical_key()` の短い名前は開発者体験に優れる |
| L-2 | LOW | **解消** | §4.2 に `None` の扱い明記 |
| L-3 | LOW | 未対応（妥当） | §3.1 docstring に記載済み |
| L-4 | LOW | 未対応（妥当） | 個別テスト名の明確さを優先 |

---

## HIGH（実装品質への影響）

### H-1. Lane 5 (US-GAAP) との canonical key 整合性は未解消のまま

**問題**:

§5.7 で Lane 5 への要求（`key` の値を Lane 3 と統一）が明記されているが、**Lane 5 の計画は未更新のまま**。Lane 5 の `USGAAPSummaryItem.key` は依然として `"revenues"`（複数形）を使用しており、`_USGAAP_SUMMARY_CONCEPTS` テーブル内のキー値が Lane 3 の canonical key と一致するかは未検証。

ただし、Lane 4 との整合が取れた時点で CRITICAL から HIGH に格下げする。理由:
- US-GAAP は包括タグ付け（BLOCK_ONLY）のため、`normalize.get_value(filing, "revenue")` で構造化パースする経路がそもそも存在しない（Lane 5 §0 で明記）
- US-GAAP で取得できるのは SummaryOfBusinessResults の要約指標のみであり、canonical key の整合性は「あれば便利」レベル

**影響**: Wave 3 normalize で `key` 値の不一致により、US-GAAP 企業のサマリーデータが canonical key で検索できない可能性がある。

**提案**: §5.7 に以下の記述を追加:

> **Lane 5 との整合性の重要度**: Lane 5 は包括タグ付けのみ（DetailLevel.BLOCK_ONLY）のため、normalize の構造化パースパスでは使用されない。canonical key の整合性は Wave 3 統合時に最終調整すれば足り、Lane 3 の実装をブロックしない。

### H-2. `ConceptMapping` と `IFRSConceptMapping` の型の分離

**問題**:

Lane 3 の `ConceptMapping` と Lane 4 の `IFRSConceptMapping` はフィールド構成がほぼ同一（`is_jgaap_specific` ↔ `is_ifrs_specific` の違いのみ）。Wave 3 normalize が両者を統一的に扱う際に、以下の型注釈が必要になる:

```python
# Wave 3 normalize での使用例
def _resolve_mapping(
    concept: str,
    standard: AccountingStandard,
) -> ConceptMapping | IFRSConceptMapping | None:  # 型の union が増殖
    ...
```

**影響**: 各レーンが独自の型を定義する現状では、Wave 3 で `Union[ConceptMapping, IFRSConceptMapping, ...]` が増殖し、型安全性のメリットが薄れる。

**提案**: §9 の設計判断に以下を追記:

> Q9: `ConceptMapping` と `IFRSConceptMapping` を統一すべきか？
>
> A: 現時点では各レーンが独自の型を定義する。理由:
> 1. `is_jgaap_specific` / `is_ifrs_specific` は会計基準固有のセマンティクスを持ち、単一フラグに統合すると意味が曖昧になる
> 2. 並列実装の制約上、共通型の定義場所がない（`__init__.py` 変更禁止）
> 3. Wave 3 normalize で共通 Protocol（`canonical_key`, `concept`, `label_ja`, `statement_type` を持つ型）を定義すれば、Union 型を避けつつ両方を統一的に扱える
>
> **Wave 3 での解決策**: `CanonicalMapping` Protocol を定義し、`ConceptMapping` と `IFRSConceptMapping` の両方がこれを満たすことで、normalize は Protocol 型のみを扱う。

---

## MEDIUM（API 品質・開発者体験の改善）

### M-1. `period_type` を文字列リテラルではなく型ヒントで制約する

**問題**: `ConceptMapping.period_type` は `str` 型だが、実際には `"instant"` または `"duration"` の 2 値のみ。現計画では文字列で定義しており、タイポ（`"duraiton"` 等）をコンパイル時に検出できない。

`_validate_registry()` でランタイム検証は可能だが、IDE の補完・型チェッカーの支援が効かない。

**提案**: `Literal` 型ヒントを使用:

```python
from typing import Literal

PeriodType = Literal["instant", "duration"]

@dataclass(frozen=True, slots=True)
class ConceptMapping:
    # ...
    period_type: PeriodType  # str → PeriodType に変更
```

Wave 1 の `edinet.xbrl.dei` に `PeriodType` Enum が既に存在する場合はそちらを使用してもよいが、Enum は JSON シリアライズ時に手間が増えるため `Literal` の方が軽量。

**追加**: `_validate_registry()` に period_type の値検証を追加:

```python
valid_period_types = {"instant", "duration"}
for m in _ALL_MAPPINGS:
    if m.period_type not in valid_period_types:
        raise ValueError(
            f"{m.concept} の period_type が不正です: {m.period_type!r}"
        )
```

### M-2. `all_mappings()` の返却順序の保証

**問題**: §4.2 の `all_mappings()` docstring で「PL → BS → CF → その他の順」と記述しているが、§6.1 の実装コード:

```python
_ALL_MAPPINGS = (*_PL_MAPPINGS, *_BS_MAPPINGS, *_CF_MAPPINGS, *_KPI_MAPPINGS)
```

はタプルのアンパック順序に依存しており、順序保証は Python の言語仕様（タプルの順序維持）により担保される。これは正しいが、**テストでの順序検証が不足**。

**提案**: テスト計画に以下を追加:

```python
def test_all_mappings_order():
    """all_mappings() が PL → BS → CF → KPI の順で返されることを検証。"""
    mappings = all_mappings()
    statement_types = [m.statement_type for m in mappings]

    # PL が BS より前、BS が CF より前、CF が None (KPI) より前
    first_pl = next(i for i, st in enumerate(statement_types) if st == StatementType.INCOME_STATEMENT)
    first_bs = next(i for i, st in enumerate(statement_types) if st == StatementType.BALANCE_SHEET)
    first_cf = next(i for i, st in enumerate(statement_types) if st == StatementType.CASH_FLOW_STATEMENT)
    first_kpi = next(i for i, st in enumerate(statement_types) if st is None)
    assert first_pl < first_bs < first_cf < first_kpi
```

### M-3. `OperatingIncome` の `is_total` フラグ再考

**問題**: §5.2 で `OperatingIncome` は `is_total=True`（合計行）と定義されている。営業利益は「売上総利益 - 販管費」の結果であり、確かに小計行として機能する。しかし、`is_total=True` の他の科目（`GrossProfit`, `ProfitLoss`, `Assets` 等）と比較すると、**営業利益はしばしば「起点科目」としても使われる**（IFRS では営業利益の定義自体が異なる）。

**提案**: 問題ではなく観察。現設計で正しい。ただし、以下のような利用者の混乱を防ぐため、`is_total` の docstring を補強:

```python
is_total: bool
    """合計・小計行か。

    True の場合、この科目は他の科目の集約結果として算出される。
    例: 売上総利益 = 売上高 - 売上原価、営業利益 = 売上総利益 - 販管費。
    Calculation Linkbase の親ノードに該当する科目。
    """
```

---

## LOW（微細な改善、対応は任意）

### L-1. テスト T18-T20 のパス解決の堅牢性

**観察**: §8.3 のテストコードで JSON ファイルのパスを `Path(__file__).parent.parent.parent / "src" / ...` で解決している。この相対パス解決はテストファイルの配置に依存しており、テストディレクトリ構造の変更時に壊れる。

**提案**: `importlib.resources` を使用する方が堅牢（`statements.py` と同じ方式）:

```python
import importlib.resources
import json

def _load_legacy_json(filename: str) -> list[dict[str, object]]:
    ref = importlib.resources.files("edinet.xbrl.data").joinpath(filename)
    with importlib.resources.as_file(ref) as path:
        return json.loads(path.read_text(encoding="utf-8"))

def test_legacy_pl_matches_json(self):
    expected = _load_legacy_json("pl_jgaap.json")
    result = to_legacy_concept_list(StatementType.INCOME_STATEMENT)
    # ...
```

### L-2. `__all__` への `JGAAP_MODULE_GROUPS` の追加の再考

**観察**: 前回 M-5 で docstring への列挙を推奨し、対応済み。しかし、ライブラリのパワーユーザーが `is_jgaap_module()` の判定ロジックをカスタマイズしたい場合（例: `jpigp` をテスト的に含めたい場合）、`_JGAAP_MODULE_GROUPS` にアクセスできないと不便。

`_` プレフィックスは「非公開」を意味するが、Python では慣習であり強制力がない。現時点では docstring 列挙で十分だが、将来的にカスタマイズ需要が出た場合は公開を検討。対応不要。

### L-3. `jgaap_specific_concepts()` のドキュメント内科目リスト

**観察**: §8.2 T17 で `jgaap_specific_concepts()` が 5 件と定義。該当科目は:
1. `NonOperatingIncome`
2. `NonOperatingExpenses`
3. `OrdinaryIncome`
4. `ExtraordinaryIncome`
5. `ExtraordinaryLoss`

これらは §5.2 の表と一致している。ただし、`jgaap_specific_concepts()` の docstring（§4.2）に具体的な科目名が列挙されていない。

**提案**: docstring の Returns セクションに代表的な科目を例示:

```python
def jgaap_specific_concepts() -> tuple[ConceptMapping, ...]:
    """J-GAAP 固有の概念（他会計基準に対応概念がないもの）を返す。

    対象科目: 営業外収益（NonOperatingIncome）、営業外費用（NonOperatingExpenses）、
    経常利益（OrdinaryIncome）、特別利益（ExtraordinaryIncome）、
    特別損失（ExtraordinaryLoss）。
    """
```

---

## 他レーンとの整合性確認（更新）

### Lane 1 (concept_sets) との関係: 良好（前回と変わらず）

§0 のレイヤー構造図による分離が明確。変更なし。

### Lane 2 (standards/detect) との関係: 良好（前回と変わらず）

detect → jgaap のディスパッチフローが §10 で明示。変更なし。

### Lane 4 (standards/ifrs) との関係: **解消** (前回: 要注意)

Lane 4 の計画を確認した結果:
- `IFRSConceptMapping` に `canonical_key: str` フィールドが追加済み
- Lane 3 の §5.2-5.5 のキー値を使用する旨が明記（§3.1 docstring: 「Lane 3 §5.2-5.5 で定義された J-GAAP の正規化キーと同一値を使用する」）
- `IFRSProfile` が `JGAAPProfile` と対称的なフィールド構成
- `to_legacy_concept_list()` も同様のブリッジ関数として提供

**結論**: C-1（前回 CRITICAL）は完全に解消。

### Lane 5 (standards/usgaap) との関係: 注意（前回: 要注意 → 格下げ）

Lane 5 の `USGAAPSummaryItem.key` は依然として独自命名の可能性がある（H-1 参照）。ただし US-GAAP は包括タグ付けのみで構造化パース不可能なため、影響は限定的。Wave 3 統合時に最終調整すれば足りる。

---

## フィードバック一覧

| ID | 優先度 | 種別 | 概要 |
|----|--------|------|------|
| H-1 | HIGH | アーキテクチャ | Lane 5 との canonical key 整合性は未解消だが影響は限定的。§5.7 への追記推奨 |
| H-2 | HIGH | アーキテクチャ | `ConceptMapping` vs `IFRSConceptMapping` の型分離。§9 Q9 として設計判断を記録推奨 |
| M-1 | MEDIUM | 型安全 | `period_type: str` → `Literal["instant", "duration"]` への変更推奨 |
| M-2 | MEDIUM | テスト | `all_mappings()` の返却順序テストの追加 |
| M-3 | MEDIUM | ドキュメント | `is_total` の docstring 補強（観察レベル、現設計で正しい） |
| L-1 | LOW | テスト | T18-T20 のパス解決を `importlib.resources` に変更 |
| L-2 | LOW | API | `_JGAAP_MODULE_GROUPS` の公開は現時点では不要 |
| L-3 | LOW | ドキュメント | `jgaap_specific_concepts()` docstring に具体的科目を例示 |

---

## 総合判定

**計画は実装可能な状態に達している。** 前回の CRITICAL 2 件は完全に解消され、アーキテクチャ上の構造的欠陥はない。

今回のフィードバック H-1/H-2 は「あれば品質が 1 段上がる」レベルの改善であり、実装をブロックするものではない。H-1 は Lane 5 側の問題であり Lane 3 の責務ではなく、H-2 は Wave 3 で Protocol として解決される設計判断が既に Q8 で記録されている。

M-1（`Literal` 型ヒント）は型安全性の面で推奨度が高く、実装コストも `str` → `Literal["instant", "duration"]` の置換のみなので対応を推奨する。

**推奨アクション**:
1. **H-2**: §9 に Q9 を追記（`ConceptMapping` と `IFRSConceptMapping` の型分離の設計判断）
2. **M-1**: `period_type` に `Literal` 型ヒントを使用し、`_validate_registry()` に値検証を追加
3. **M-2**: テスト計画に `all_mappings()` の順序検証テストを追加
4. 上記は実装時に対応可能。**即時実装開始を推奨**
