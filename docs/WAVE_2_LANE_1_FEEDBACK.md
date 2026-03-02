# WAVE 2 LANE 1 フィードバック（第3ラウンド）: 実装レビュー

## 総評

前回の CRITICAL/HIGH フィードバックが全て適切に修正されており、品質は非常に高い。

**実データ検証結果**:
- 53 テスト PASS（+ 7 skip）、既存 1000 テスト全 PASS。ruff clean
- 実タクソノミスモークテスト 7 件全 PASS
- PL: **75 concepts（65 non-abstract）、pl_jgaap.json 16 概念全カバー**
- BS: **83 concepts（68 non-abstract）、bs_jgaap.json 20 概念全カバー**
- CF: **4 バリアント取得**（direct/indirect × 連結/個別、bk1 から fallback）

**前回フィードバックの対応状況**:

| 前回ID | 状態 | 修正内容 |
|--------|------|----------|
| C-1 (PL variant) | **修正済** | `_tree_to_concept_set` がトップレベル LineItems ルートの children も収集するようになった。`seen` セットで重複防止。`base_depth` を `min()` で統一 |
| H-1 (CF fallback) | **修正済** | `_apply_cf_fallback` が 1 業種の全 CF バリアントを収集してから `return` するようになった |
| H-2 (get indirect/direct) | 未修正 | 後述 |
| M-4 (__repr__) | **修正済** | `role_uri` の短縮形を含む `__repr__` が実装された |

**全体判定: CRITICAL なし。MEDIUM 3 件を推奨するが、全てブロッカーではない。**

---

## MEDIUM（改善推奨。ブロッカーではない）

### M-1. `ConceptSetRegistry.get()` が indirect/direct を区別しない

**現象**: `get(StatementType.CASH_FLOW_STATEMENT, consolidated=True)` が 4 つの CF ConceptSet の中から最初に見つかったものを返す。返り値は dict の反復順序に依存し、非決定的。

**実測**: 現在は indirect（32 concepts）が返っている。一般事業会社の大半が indirect を使用するため実用上は問題ないが、保証がない。

**推奨修正**: 同一条件の複数候補がある場合、concepts 数が最大のものを返す:

```python
def get(self, statement_type, *, consolidated=True, industry_code="cns"):
    target = StatementCategory.from_statement_type(statement_type)
    candidates = [
        cs for cs in self._sets.get(industry_code, {}).values()
        if cs.category == target and cs.is_consolidated == consolidated
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda cs: len(cs.concepts))
```

**優先度**: 中。Wave 3 の `statements.py` 統合前に修正すればよい。

---

### M-2. CF fallback の banking 固有 concept が cns に混入

**現象**: bk1 から fallback した CF ConceptSet に銀行業固有の concept が含まれる:
- `IncreaseDecreaseInAllowanceForLoanLossesOpeCFBNK`
- `GainOnFundManagementOpeCFBNK`
- `FinancingExpensesOpeCFBNK`
- `LossGainRelatedToSecuritiesOpeCFBNK`
- `NetDecreaseIncreaseInLoansAndBillsDiscountedOpeCFBNK`
- `NetIncreaseDecreaseInDepositOpeCFBNK`
- `ProceedsFromFundManagementOpeCFBNK`
- `PaymentsForFinanceOpeCFBNK`
- `PurchaseOfSecuritiesInvCFBNK`
- `ProceedsFromSalesOfSecuritiesInvCFBNK`

**影響**: 実害は小さい。`concept_names()` をフィルタセットとして使用する場合、余分な concept は「拾わないだけ」で false positive を生まない。ただし `to_legacy_format()` の出力に銀行業固有概念が混在し、表示用途では不適切。

**推奨修正（短期）**: `source_info` に業種固有の旨を明記するのみで十分（現状 `"fallback from bk1"` で識別可能）。

**推奨修正（長期、Wave 3+）**: `_apply_cf_fallback` で BNK/INS 等のサフィックス付き concept をフィルタする。または Calculation Linkbase（`_cal_cf.xml`、cns にも存在する）から CF 概念セットを導出する方式に切り替える。

---

### M-3. `test_legacy_format_covers_existing_json` テストが未実装

計画 §4.4 で最重要テストとして定義された既存 JSON カバレッジテストが `TestRealTaxonomy` に存在しない。現在の `test_legacy_format_coverage` は件数チェックのみ。

**推奨追加**:

```python
def test_legacy_format_covers_existing_json(self, registry):
    """既存 JSON の全概念が ConceptSet に含まれること。"""
    import json
    for st, json_file in [
        (StatementType.BALANCE_SHEET, "src/edinet/xbrl/data/bs_jgaap.json"),
        (StatementType.INCOME_STATEMENT, "src/edinet/xbrl/data/pl_jgaap.json"),
    ]:
        cs = registry.get(st)
        assert cs is not None
        with open(json_file) as f:
            existing = {item["concept"] for item in json.load(f)}
        missing = existing - cs.concept_names()
        assert not missing, f"{st.name}: {missing}"
```

**注意**: CF は対象外とする（後述 LOW-1 参照）。

---

## LOW（計画変更不要、参考情報）

### L-1. cf_jgaap.json 自体に不正確な concept 名が含まれる

**発見**: cf_jgaap.json の 3 概念がタクソノミの XSD に存在しない:

| cf_jgaap.json の概念名 | 正しい concept 名 (XSD) | 備考 |
|------------------------|------------------------|------|
| `CashAndCashEquivalentsAtEndOfPeriod` | `CashAndCashEquivalents` | instant 型。期首/期末は context の期間で区別される |
| `CashAndCashEquivalentsAtBeginningOfPeriod` | `CashAndCashEquivalents` | 同上 |
| `IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeInScopeOfConsolidation` | `IncreaseDecreaseInCashAndCashEquivalentsResultingFromChangeOfScopeOfConsolidationCCE` | "ChangeIn" → "ChangeOf" + "CCE" サフィックス |

**意味**: ConceptSet が cf_jgaap.json の 3 概念を「カバーしない」のは ConceptSet のバグではなく、**cf_jgaap.json のほうが不正確**。`CashAndCashEquivalents` は ConceptSet に含まれている（4 バリアント全てで確認済み）。

**対応**: cf_jgaap.json の修正は本 Lane のスコープ外。Wave 3 L1 で `_load_concept_definitions()` を ConceptSet に置換する際に自然解消する。

### L-2. `Quarterly` prefix 未対応

計画に記載の `Quarterly` prefix が `classify_role_uri()` に未実装。ただし標準タクソノミの `_pre.xml` には `Quarterly` 付き role URI が存在しないため現時点で影響なし。

### L-3. SS (株主資本等変動計算書) の ConceptSet が導出されない

cns には `_pre_ss.xml` が存在しない。SS は提出者の `_pre.xml` にのみ存在する。本 Lane は標準タクソノミの `_pre.xml` のみが対象であるため、スコープ内。Wave 3+ で必要な場合は提出者 _pre パースとの統合で対応。

### L-4. キャッシュの `_CACHE_VERSION` と `__version__` の二重安全策は良い設計

ライブラリバージョンアップとキャッシュフォーマット変更の両方でキャッシュが自動無効化される。

### L-5. `all_for_industry()` の返り値型が計画と異なる（dict vs list）

計画では `list[ConceptSet]` だが実装は `dict[str, ConceptSet]`。情報量が多く良い判断。

---

## 実データ検証結果サマリー

```
業種数: 23（全業種カバー）

cns ConceptSets:
  BS 連結: 83 concepts (68 non-abstract) ← bs_jgaap.json 20 concepts 全カバー ✓
  BS 個別: 97 concepts (79 non-abstract)
  PL 連結: 75 concepts (65 non-abstract) ← pl_jgaap.json 16 concepts 全カバー ✓
  PL 個別: (走査対象)
  CF 連結(direct):   26 concepts (fallback from bk1)
  CF 連結(indirect): 32 concepts (fallback from bk1) ← get() がこちらを返す
  CF 個別(direct):   23 concepts (fallback from bk1)
  CF 個別(indirect): 29 concepts (fallback from bk1)

cf_jgaap.json 8 concepts:
  5/8 カバー ✓ (CashAndCashEquivalents として包含)
  3/8 は cf_jgaap.json 側の不正確な concept 名 (L-1 参照)
```

---

## コード品質の評価

**優秀な点**:
1. `classify_role_uri()` の 4 ステップ分解（`std_` 除去 → `SemiAnnual` 除去 → `Consolidated` 検出 → キーワードマッチ）が洗練されている
2. `_tree_to_concept_set` の variant LineItems 収集ロジック + `seen` セットでの重複防止が堅実
3. `_apply_cf_fallback` が 1 業種の全バリアントを収集する設計が正しい
4. `_parse_and_merge_group` のエラーハンドリング（warn して続行）が堅牢
5. テストフィクスチャが実際の EDINET 構造を忠実に再現している
6. `ConceptSetRegistry` の API が REPL フレンドリー（`__repr__` に概念数・連結/個別を表示）
7. `_group_pre_files` の正規表現グルーピングがシンプルかつ正確
8. PL バリアントのマージ順序（ファイル名長でソート → メインファイル優先）が自然

---

## 総合判定

**マイルストーン完了条件の達成状況**:

| # | 条件 | 状態 |
|---|------|------|
| 1 | classify_role_uri が BS/PL/CF/SS/CI を正しく分類 | ✓ |
| 2 | rol_std_ と rol_ の両方に対応 | ✓ |
| 3 | 半期/中間プレフィックスに対応 | ✓ (Quarterly 除く) |
| 4 | derive_concept_sets_from_trees が動作 | ✓ |
| 5 | depth が LineItems からの相対深さ | ✓ |
| 6 | dimension ノードが除外 | ✓ |
| 7 | is_total/is_abstract が正しく識別 | ✓ |
| 8 | PL バリアントマージ後に概念数が増加 | ✓ |
| 9 | to_legacy_format が正しい形式 | ✓ |
| 10 | 既存 JSON の concept を全てカバー | ✓ (BS/PL。CF は JSON 側が不正確) |
| 11 | 非財務 role URI がフィルタリング | ✓ |
| 12 | ConceptSetRegistry が動作 | ✓ |
| 13 | get() が条件検索可能 | ✓ |
| 14 | from_statement_type が動作 | ✓ |
| 15 | 全業種の走査 | ✓ (23 業種) |
| 16 | pickle キャッシュが動作 | ✓ |
| 17 | 35+ テスト PASS | ✓ (53 PASS + 7 skip) |
| 18 | ruff clean | ✓ |
| 19 | 既存テスト全 PASS | ✓ (1000 PASS) |

**判定: APPROVE。** MEDIUM 3 件は全て Wave 3 統合前の改善事項であり、本 Lane の完了をブロックしない。
