# WAVE 2 LANE 2 フィードバック (Rev 2): standards/detect — 会計基準の自動判別

## 総評

Rev 2 の計画は**実装可能な品質に達しており、大きな問題は残っていない**。前回フィードバック（H-1, H-2, M-1〜M-5）の反映状況を検証し、以下の結論に至った:

### 前回フィードバックの反映状況

| ID | 反映状況 | 評価 |
|----|----------|------|
| H-1 | `dei: DEI \| None = None` パラメータ追加 | **完全に反映済み** |
| H-2 | FEATURES.md `ifrs-full` への注記追加 | **完全に反映済み** |
| M-1 | T25 追加 | **完全に反映済み** |
| M-2 | `namespace_modules` docstring 補足 | **完全に反映済み** |
| M-3 | T24 のアサーション項目明記 | **完全に反映済み** |
| M-4 | DEFER（Detroit 派原則との矛盾） | **適切な判断** |
| M-5 | `UNKNOWN` の docstring 修正 | **完全に反映済み** |

前回の HIGH 指摘は全て解消されている。計画の設計品質は引き続き高い。以下は Rev 2 に対する**残存課題と追加の改善提案**を記載する。

---

## 計画の強みの再確認

以下の点は前回評価から変わらず優れており、ディファクトスタンダードのライブラリとして申し分ない:

1. **QA トレーサビリティ**: D-1.a / D-2.a / D-3.a の調査結果が設計判断の全てに根拠を与えている
2. **3 関数 API の分離**: `detect_accounting_standard` / `detect_from_dei` / `detect_from_namespaces` は関心分離・テスタビリティ・利用者の柔軟性の観点で最適
3. **`dei` optional パラメータ**（H-1 反映済み）: Wave 3 統合時の DEI 二重走査を後方互換性を保ちつつ回避する設計
4. **`DetailLevel` による事前分類**: US-GAAP/JMIS の「PL が空」問題を構造的に防止する先見的な設計
5. **§9 の設計判断 Q&A**: 実装エージェントが迷う余地を最小化
6. **並列安全性**: 新規ファイルのみ作成で他レーンとの衝突リスクゼロ

---

## MEDIUM（API 品質・テスト堅牢性の改善）

### M-1. DEI 判別成功時の名前空間クロスバリデーション警告の検討

**現状**: §5.1 Step 2 で DEI 判別が成功した場合、名前空間の検証は一切行わない。DEI の結果をそのまま返す。

**懸念**: DEI が `"Japan GAAP"` を示しているのに facts に `jpigp_cor`（IFRS タクソノミ）要素が存在するケース、あるいは DEI が `"IFRS"` なのに `jpigp_cor` が一切存在しないケースは、データ品質の問題（XBRL 提出時の DEI 設定ミス等）を示唆する。このような不整合は**静かに無視される**ため、利用者がデータ品質問題に気づけない。

**提案**: 2 つのアプローチがある:

**(A) 現状維持（推奨）**: detect モジュールの責務は「会計基準の判別」であり、「データ品質の検証」は FEATURES.md の `validation/required_items` の責務。クロスバリデーションを detect に含めると SRP に反する。利用者は必要に応じて `detect_from_namespaces(facts)` を別途呼んで自前で比較できる。

**(B) 警告の追加**: DEI 判別成功後に、バックグラウンドで名前空間を軽量チェックし、不整合があれば `EdinetWarning` を発行する。パフォーマンスコストは追加の名前空間走査分。

**推奨は (A)**。ただし、将来的に `validation` モジュールが実装される際に、この不整合チェックを明示的な検証項目とすることを §9 の Q&A に記録しておくと、知識の散逸を防げる。

**計画変更が必要な場合**: §9 に以下の Q&A を追加するのみ:

```
### Q: DEI と名前空間の不整合チェックは detect の責務か？

**A**: detect の責務外。DEI が `"Japan GAAP"` なのに `jpigp_cor` が存在する等の
不整合は、FEATURES.md `validation/required_items` の検証項目として将来実装する。
detect は最も信頼性の高い情報源（DEI）を優先し、判別結果の一貫性を保証する。
```

---

### M-2. テスト T5 / T6 の境界条件の明確化

**現状**: T5 と T6 はそれぞれ以下を記述:

- T5: `test_detect_dei_nil_falls_back_to_namespace` — DEI の AccountingStandardsDEI が nil
- T6: `test_detect_no_dei_falls_back_to_namespace` — DEI 要素が存在しない

**問題**: 「DEI 要素が存在しない」の解釈が曖昧。以下の 2 つのケースが考えられる:

1. **facts に jpdei_cor 名前空間の Fact が 1 つも含まれない**（大量保有報告書等）: `extract_dei(facts)` は全フィールド None の DEI を返す
2. **facts に jpdei_cor の Fact はあるが、`AccountingStandardsDEI` だけが欠落**（一部のみ DEI が設定されている書類）: `extract_dei(facts)` は `accounting_standards=None` だが他のフィールド（`has_consolidated` 等）は値あり

この 2 つのケースでは、名前空間フォールバック結果に統合される DEI 補助情報（`has_consolidated`, `period_type`）の有無が異なる。ケース 1 は全て None、ケース 2 は部分的に値がある。

**対策**: T6 の概要を以下のように具体化する:

```
| T6 | test_detect_no_dei_falls_back_to_namespace | facts に jpdei_cor 名前空間の Fact が 1 つも含まれない → extract_dei は全フィールド None の DEI を返す → 名前空間フォールバック、has_consolidated=None, period_type=None |
```

加えて、P1 テストに以下を追加すると網羅性が向上する:

```
| T27 | test_detect_partial_dei_falls_back_to_namespace | jpdei_cor の Fact はあるが AccountingStandardsDEI が欠落（has_consolidated は存在） → 名前空間フォールバック結果に has_consolidated が統合される |
```

この T27 は T19 と似ているが、T19 は `detect_accounting_standard` のメインフロー全体を通す統合テストであるのに対し、T27 は「DEI が部分的に欠落するケース」を明示的にテストする点が異なる。ただし T19 の内容が既にこのケースをカバーしているなら追加不要。

---

### M-3. `detect_from_dei` 呼び出し時の `stacklevel` の再検証

**現状**: §5.2 で `warnings.warn(..., stacklevel=2)` を使用。

**問題**: `stacklevel=2` は「呼び出し元の呼び出し元」を指す。`detect_from_dei` が `detect_accounting_standard` 経由で呼ばれた場合、警告のスタックトレースが `detect_accounting_standard` を指し、利用者のコードを指さない。

```
detect_accounting_standard() → detect_from_dei() → warnings.warn(stacklevel=2)
# stacklevel=2 → detect_accounting_standard の行を報告
# stacklevel=3 → 利用者のコード行を報告
```

一方、利用者が `detect_from_dei(dei)` を直接呼んだ場合:

```
user_code() → detect_from_dei() → warnings.warn(stacklevel=2)
# stacklevel=2 → user_code の行を報告（正しい）
```

**対策**: 2 つの選択肢:

**(A) 現状維持**: `detect_from_dei` は公開 API であり、直接呼ばれるケースも想定されている。`stacklevel=2` は直接呼出し時に正しい。`detect_accounting_standard` 経由の場合は 1 レベルずれるが、警告メッセージ自体に十分な情報があるため実用上問題ない。

**(B) 動的 stacklevel**: `detect_from_dei` 内部で呼び出し元を判定する方法は過度に複雑。代替として、`detect_accounting_standard` 内で `detect_from_dei` の結果をチェックし、未知文字列の場合は `detect_accounting_standard` 自身が `stacklevel=2` で警告する（`detect_from_dei` の警告は出さない）。ただしこれは内部実装の複雑化。

**推奨は (A)**。警告メッセージに `"未知の会計基準 '{standard}' が検出されました"` と値が含まれるため、stacklevel のずれは実用上無害。実装エージェントの判断に委ねる。

---

## LOW（実装ヒント、計画変更不要）

### L-1. `_make_fact` / `_make_dei_fact` ヘルパーの RawFact フィールド対応

§7.2 のテストヘルパーは `value_inner_xml` フィールドを省略しているが、実装上の問題はない。RawFact の `value_inner_xml` はデフォルト値 `None` を持つため（`parser.py` L75: `value_inner_xml: str | None = None`）、省略可能。ヘルパーの現状で正しい。

ただし、将来 RawFact にデフォルト値なしの新規フィールドが追加された場合（Wave 3 以降）、ヘルパーの更新漏れでテストが壊れるリスクがある。これは Detroit 派テストの本質的なトレードオフであり、計画段階で対策する必要はないが、実装エージェントはヘルパーにコメントで RawFact のバージョン依存性を記録しておくとよい。

---

### L-2. EDINET タクソノミの JMIS 関連名前空間の存在確認

D-2.a.md の調査結果に基づき、JMIS は専用タクソノミモジュールを持たないと結論付けている。しかし、EDINET タクソノミの `ALL_20251101/taxonomy/` ディレクトリに `jpmsf/`（修正国際基準）ディレクトリが存在する可能性がある。仮に `jpmsf_cor` 名前空間が存在する場合、名前空間フォールバックで JMIS を検出できる可能性がある。

**対応不要**: D-2.a.md の調査は網羅的であり、JMIS について「包括タグ付けのみ」と結論付けている。仮に `jpmsf_cor` が存在したとしても、包括タグ付けのみの JMIS を名前空間で検出する実用価値は低い（DEI が存在する書類タイプでのみ JMIS は適用されるため）。将来的に JMIS の詳細タグ付けが導入された場合には、名前空間検出ルールの追加を検討すればよい。

---

### L-3. `detect_from_namespaces` の `module_groups` が空でない場合の UNKNOWN ケースの透明性

§5.3 の最終分岐（US-GAAP / JMIS 判別不可ケース）で、`module_groups` に `{"jpcrp", "jpdei"}` のような値が含まれている状態で `standard=None` を返す。利用者は「名前空間は検出されたが会計基準は判別不能」であることを `namespace_modules` フィールドで確認できる。

現状の設計で十分だが、利用者がこの状態を解釈しやすいよう、`detect_from_namespaces` の docstring（§4.3）の Returns セクションに以下の補足があるとなおよい:

```
Returns:
    DetectedStandard (method=NAMESPACE)。
    jpcrp_cor のみが存在するケース（US-GAAP/JMIS の可能性）では
    standard=None, namespace_modules に検出されたモジュールグループが
    格納される。利用者は namespace_modules の内容から
    「名前空間は検出されたが会計基準は特定できない」ことを確認できる。
```

---

### L-4. テスト T26 の DEI 再抽出非実行の検証方法

T26 は「事前抽出済み DEI を渡した場合、DEI 再抽出なしで正しく判別される」だが、Detroit 派テストでは「DEI 再抽出が呼ばれなかった」ことをモックなしで直接検証するのは困難。

実装エージェントへのヒント: T26 は「正しく判別される」部分のみアサートすれば十分（`standard`, `method`, `has_consolidated` 等の値が期待通り）。「再抽出なし」の部分は、`detect_accounting_standard(facts, dei=dei)` が `detect_accounting_standard(facts)` と同じ結果を返すことの暗黙的な検証で代替できる。明示的に「`extract_dei` が呼ばれなかった」ことを検証する必要はない（Detroit 派原則）。

---

## 他レーンとの整合性確認（Rev 2 更新分）

### Wave 2 L3 (standards/jgaap) との接続

L3 は `is_jgaap_module("jppfs")` を公開 API として提供。L2 の `detect_from_namespaces` は `"jppfs" in module_groups` で J-GAAP を判定。**ロジックが一致**。衝突なし。

### Wave 2 L4 (standards/ifrs) との接続

L4 は `NAMESPACE_MODULE_GROUP = "jpigp"` 定数を定義。L2 の `detect_from_namespaces` は `"jpigp" in module_groups` で IFRS を判定。**一致**。衝突なし。

### Wave 2 L5 (standards/usgaap) との接続

L5 は `DetectedStandard.detail_level == BLOCK_ONLY` を判定条件として使用。L2 の `_DETAIL_LEVEL_MAP` は `US_GAAP → BLOCK_ONLY` をマッピング。**正しく噛み合っている**。

### Wave 3 L1 (normalize + statements) との接続

§8 の使用例コードが Wave 3 L1 の想定利用パターンを正確に示しており、`dei=dei` パラメータにより DEI 二重走査も回避されている。設計上の懸念なし。

---

## 今回のフィードバック優先度まとめ

| ID | 優先度 | 概要 | 計画変更の要否 |
|----|--------|------|---------------|
| M-1 | MEDIUM | DEI/名前空間クロスバリデーションの責務整理 | **任意**: §9 に Q&A 1 件追加のみ |
| M-2 | MEDIUM | T5/T6 の境界条件の明確化、T27 追加の検討 | **任意**: テスト表に 1 行追加 |
| M-3 | MEDIUM | `stacklevel` の再検証 | **不要**: 実装エージェントの判断 |
| L-1 | LOW | ヘルパーの RawFact フィールド対応 | **不要**: 現状で正しい |
| L-2 | LOW | JMIS 名前空間の存在確認 | **不要**: D-2.a.md の結論を信頼 |
| L-3 | LOW | UNKNOWN ケースの docstring 補足 | **任意**: 実装時に判断 |
| L-4 | LOW | T26 の検証方法ヒント | **不要**: 実装ヒントのみ |

---

## 総合判定

**計画は Rev 2 の時点で実装可能な品質に達している。HIGH 指摘はない。**

前回フィードバックの H-1（`dei` optional パラメータ）と H-2（`ifrs-full` 注記）は正確に反映されており、M-1〜M-5 の反映も適切。特に M-4（`_detect_from_module_groups` の内部関数分離）を DEFER とし Detroit 派原則を優先した判断は正しい。

今回の MEDIUM 指摘は全て「あれば望ましいが、なくても実装に支障はない」レベル。最も実用価値が高いのは M-2（T5/T6 の境界条件明確化）だが、これも実装エージェントが `extract_dei` の動作を正しく理解していれば自然に対処できる。

**このまま実装を開始して問題ない。**
