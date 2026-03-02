# Wave 2 / Lane 5 フィードバック — standards/usgaap（第2回）

## 総合評価

**★★★★★ (5/5)** — 前回フィードバック（T-1〜T-10, I-1〜I-4）を全て検討し、採用/不採用の判断根拠を §9 と §13 に明記した上で、**独自に発見した 2 つの CRITICAL 問題（C-1: concept 名の XSD 検証修正、C-16: contexts 必須化）を自力で解決**している点が極めて優秀。ディファクトスタンダードなライブラリに求められる正確性・型安全性・保守性の全てを満たす計画。

前回指摘の CRITICAL/HIGH/MEDIUM/LOW の全 14 項目について対応状況を確認した結果、**未解決の問題はゼロ**。以下は「さらに良くするための提案」であり、計画の品質自体は実装開始に十分。

---

## U-1 [MEDIUM] `_LABEL_JA_MAP` と `_SummaryConceptDef` のデータ二重管理

### 問題

§3.4 の `_USGAAP_SUMMARY_CONCEPTS` と §6 の `_LABEL_JA_MAP` は、同一の正規化キーで紐づく**並列データ構造**。キーの追加・変更時に両方を更新する必要があり、片方だけ更新するリスクがある。

現在:
```python
_USGAAP_SUMMARY_CONCEPTS = (
    _SummaryConceptDef("revenue", "RevenuesUSGAAP...", "NetSales"),
    ...
)
_LABEL_JA_MAP = {
    "revenue": "売上高",
    ...
}
```

### 提案

`_SummaryConceptDef` に `label_ja` フィールドを追加し、定義を一元化する:

```python
@dataclass(frozen=True, slots=True)
class _SummaryConceptDef:
    key: str
    concept_local_name: str
    jgaap_concept: str | None
    label_ja: str  # 追加

_USGAAP_SUMMARY_CONCEPTS = (
    _SummaryConceptDef("revenue", "RevenuesUSGAAP...", "NetSales", "売上高"),
    ...
)
```

`_LABEL_JA_MAP` は `_USGAAP_SUMMARY_CONCEPTS` から動的に構築:

```python
_LABEL_JA_MAP: dict[str, str] = {d.key: d.label_ja for d in _USGAAP_SUMMARY_CONCEPTS}
```

### メリット

1. **Single Source of Truth**: 1 つの定数テーブルに全情報が集約
2. **追加時の安全性**: `_SummaryConceptDef` の required フィールドなので、`label_ja` の未定義はコンパイルエラーで検知
3. **JMIS 拡張時**: `_JMIS_SUMMARY_CONCEPTS` も同じ dataclass で定義でき、ラベルが自動的に含まれる
4. **タクソノミ更新時**: 1 箇所のみ更新で済む

### 対応優先度

MEDIUM — 採用しなくても機能に問題はないが、保守性が微改善する。

---

## U-2 [LOW] `_extract_description()` の実装詳細が §5 に欠落

### 問題

§5.1 のメインフローで `_extract_description(usgaap_facts)` が呼ばれているが、この関数の実装ロジックが §5 に記載されていない。対象 concept 名は §1.2 の Description 要素（`DescriptionOfFactThatConsolidated...`）から推定可能だが、以下が不明:

1. 同一 concept で複数 fact が存在する場合の挙動（最初の 1 つ? 全て連結?）
2. 複数期間の fact が存在する場合の挙動（当期のみ? 最新のみ?）

### 提案

§5 に以下の程度の記述を追加:

```python
_DESCRIPTION_CONCEPT = (
    "DescriptionOfFactThatConsolidatedFinancialStatements"
    "HaveBeenPreparedInAccordanceWithUSGAAPFinancialInformation"
)

def _extract_description(usgaap_facts: list[RawFact]) -> str | None:
    """米国基準適用の説明文を抽出する。最初に見つかった値を返す。"""
    for fact in usgaap_facts:
        if fact.local_name == _DESCRIPTION_CONCEPT and fact.value_raw:
            return fact.value_raw
    return None
```

### 対応優先度

LOW — 実装時に自明に解決できるため計画書への追記は任意。

---

## U-3 [LOW] タクソノミ更新時の回帰テスト手段

### 問題

C-1 で 2025-11-01 タクソノミ XSD との直接検証を行った点は極めて優秀だが、**隔年のタクソノミ更新時に同じ検証を再現する手段**が計画に含まれていない。

T-9（JSON 外出し）を不採用とした判断は合理的だが、代わりに「Python 定数テーブルがタクソノミと一致していることの検証手段」があると保守性がさらに向上する。

### 提案

`tools/` 配下に検証スクリプトを作成する（本 Lane のスコープ外だが、将来の保守者向けメモとして §9 に記載しておくと良い）:

```python
# tools/verify_usgaap_concepts.py（将来の保守用、本 Lane では作成不要）
"""
jpcrp_cor XSD から "USGAAP" を含む全 element を抽出し、
usgaap.py の _USGAAP_SUMMARY_CONCEPTS + _TEXTBLOCK_STATEMENT_MAP と
差分を報告するスクリプト。

タクソノミ更新時に:
  EDINET_TAXONOMY_ROOT=... uv run python tools/verify_usgaap_concepts.py
で実行し、追加・削除・リネームされた concept を検知する。
"""
```

### 対応優先度

LOW — 本 Lane での実装は不要。§9 の設計判断に「将来の保守手段として `tools/verify_usgaap_concepts.py` のような検証スクリプトが有用」と一文追記するのみで十分。

---

## U-4 [LOW] `comprehensive_income` / `comprehensive_income_parent` の `jgaap_concept` が None

### 問題

§3.4 で以下の 2 つが `jgaap_concept=None` になっている:

```python
_SummaryConceptDef("comprehensive_income", "ComprehensiveIncomeUSGAAP...", None),
_SummaryConceptDef("comprehensive_income_parent", "ComprehensiveIncomeAttributableToOwnersOfParentUSGAAP...", None),
```

J-GAAP にも包括利益（`ComprehensiveIncome`）と親会社株主に係る包括利益（`ComprehensiveIncomeAttributableToOwnersOfParent`）が `jppfs_cor` に存在する（J-1 QA 参照）。

### 提案

マッピングを追加するか、意図的に None とする理由をコメントで明記:

```python
# 選択肢 A: マッピングを追加
_SummaryConceptDef("comprehensive_income", "...", "ComprehensiveIncome"),
_SummaryConceptDef("comprehensive_income_parent", "...", "ComprehensiveIncomeAttributableToOwnersOfParent"),

# 選択肢 B: 意図的に None（コメントで説明）
# 包括利益計算書は J-GAAP でも存在するが、SummaryOfBusinessResults 経由の
# 包括利益は有報の「主要な経営指標等の推移」セクション固有であり、
# 財務諸表の concept とは意味的に異なるため None とする。
```

### 対応優先度

LOW — Wave 3 の `standards/normalize` で再検討しても良い。選択肢 A が安全だが、B でも実用上問題なし。

---

## 設計の優れている点（変更不要）

前回フィードバック時点で優れていた 8 点に加え、**今回の改訂で特に評価すべき追加判断**:

1. **C-1: XSD 直接検証による 7 箇所の concept 名修正** — QA の推論だけに依存せず、一次資料（タクソノミ XSD + ラベルファイル）で確認した点が最高品質。`NetAssetsUSGAAP` → `EquityIncludingPortionAttributableToNonControllingInterestUSGAAP`（概念名の根本的な誤り）を発見・修正できたのはこの検証のおかげ

2. **C-16: contexts 必須化** — Period 型の `datetime.date`（Not Optional）制約から逆算して、フォールバック方式の型レベル不可能性を発見し、必須化というクリーンな解決策を導出。3 つの代替案の比較検討も明確

3. **T-9 不採用判断の論理的根拠** — 「34 要素は L3 の数百 concept とスケールが異なる」「FEATURES.md L112-115 は全会計基準合計の話」という精密な反論。JSON 化の提案に対して根拠付きで不採用とした判断力は高い

4. **§13 変更履歴** — 全 18 件の変更を対応元フィードバック番号と共に追跡可能にした透明性

5. **TextBlock `is_consolidated` → `is_semi_annual` の変更（C-11）** — 「US-GAAP TextBlock は全て連結なので `is_consolidated=True` は常に True で情報量ゼロ」という本質的な洞察に基づくフィールド変更

---

## チェックリスト

| # | 項目 | 重要度 | 対応 |
|---|------|--------|------|
| U-1 | `_SummaryConceptDef` に `label_ja` を統合 | MEDIUM | dataclass 修正 |
| U-2 | `_extract_description()` の実装詳細追記 | LOW | §5 追記（任意） |
| U-3 | タクソノミ検証スクリプトの存在をメモ | LOW | §9 一文追記（任意） |
| U-4 | `comprehensive_income` の jgaap_concept | LOW | マッピング追加またはコメント |

**全て LOW/MEDIUM であり、計画の承認を妨げるものはない。**

---

## 結論

**計画は実装開始可能。** 上記 U-1〜U-4 は実装中に適宜判断して反映すればよい。前回フィードバックの全項目を高品質に消化し、独自の CRITICAL 発見（C-1, C-16）も含めて計画を大幅に改善した。US-GAAP という特殊なデータ構造に対して、専用型（`USGAAPSummary`）を導入しつつ正規化キーで L3/L4 と接続するアーキテクチャは、Wave 3 統合を見据えた正しい設計。
