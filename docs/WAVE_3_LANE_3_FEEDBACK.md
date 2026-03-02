# Wave 3 / Lane 3 フィードバック（第 4 回） — sector/insurance

レビュー日: 2026-03-01
対象: WAVE_3_LANE_3.md（第 3 回フィードバック反映済み版）
レビュー範囲: 計画全体 + jgaap.py 実装 + L2 banking 計画 + TEMP.md + SCOPE.md + FEATURES.md + 過去フィードバック 3 回分

---

## 総合評価

**非常に完成度の高い計画。過去 3 回のフィードバック（計 24 項目）が正確に反映されており、jgaap.py・banking.py との構造的整合性は極めて高い。** 以下は「ディファクトスタンダードなライブラリ」を目指す上で、最終実装前に詰めるべき残存課題を深刻度別に整理したもの。

---

## CRITICAL（実装前に修正すべき）

なし。前回 CRITICAL 3 件（C-1: 型統一、C-2: ギャップ方式、C-3: 構造差異コメント）は全て適切に反映済み。

---

## HIGH（実装品質に影響。修正を強く推奨）

### H-1: `is_jgaap_specific` に相当するフラグが不在 — jgaap.py との dataclass 対称性の欠落

**現状**: jgaap.py の `ConceptMapping` には `is_jgaap_specific: bool = False` フィールドがある。insurance.py の `InsuranceConceptMapping` にはこれに相当するフラグがない。

**問題**: INS-only ポリシーにより insurance.py の全マッピングは「保険業固有」であるため、`is_insurance_specific` フラグは常に `True` になり情報量ゼロ — **だからこそ不要**、という判断は正しい。

しかし、normalize レイヤーが `ConceptMapping` / `BankingConceptMapping` / `InsuranceConceptMapping` を duck-typing で処理する際、`is_jgaap_specific` / `is_sector_specific` 的なフラグの有無が非対称だと `hasattr` チェックが必要になる。

**推奨対処（2 択）**:
- **Option A（推奨・低コスト）**: 計画のセクション 7.4 のテーブルに「insurance.py は `is_jgaap_specific` に相当するフィールドを持たない。全マッピングが INS サフィックス付きであり、常に `True` 相当のため不要。normalize が必要とする場合は L1 側で `True` 定数を注入する」と明記
- **Option B**: `is_insurance_specific: bool = True` をデフォルト `True` で追加。banking の同等フラグがどうなるかと合わせて判断

### H-2: `_PROFILE` キャッシュインスタンスの構築パターンが計画に未記載

**現状**: L-2（第 3 回）で「実装時の自然な選択なので LOW」と判定。

**格上げ理由**: jgaap.py の実装を確認すると、`_PROFILE = JGAAPProfile(...)` がモジュールレベルで構築され、`get_profile()` はそれを返すだけのパターン。insurance.py で `canonical_key_count` を `len(all_canonical_keys())` から動的計算するか、`len(_ALL_MAPPINGS)` からモジュールロード時に構築するかで、初期化順序の依存が生じる。

**推奨対処**: セクション 3.6 に以下を追記:
```python
_PROFILE = InsuranceProfile(
    sector_id="insurance",
    name_ja="保険業",
    name_en="Insurance",
    industry_codes=INSURANCE_INDUSTRY_CODES,
    canonical_key_count=len(_CANONICAL_INDEX),
)

def get_profile() -> InsuranceProfile:
    return _PROFILE
```
`_CANONICAL_INDEX` はモジュールレベルで `_ALL_MAPPINGS` から構築されるため、依存順序は `_ALL_MAPPINGS` → `_CANONICAL_INDEX` → `_PROFILE` で問題ない。

### H-3: `to_legacy_concept_list()` に相当する機能の不要性が明記されていない

**現状**: jgaap.py は `to_legacy_concept_list()` を持っており（`__all__` にも含まれている）、JSON 互換の出力を提供する。insurance.py の計画にはこれへの言及がない。

**問題**: 保険業モジュールは Wave 3 で新規作成されるため、レガシー JSON 対応の必要は当然ない。しかし、jgaap.py の `__all__` に含まれている API が insurance.py に対応物を持たない理由を明記すべき。

**推奨対処**: セクション 2.3（スコープ外）に「`to_legacy_concept_list()` 相当のレガシー JSON 互換 API は不要（新規モジュールのため JSON 二重管理の歴史がない）」を追記。

### H-4: `InsuranceProfile.sector_id` と banking の `BankingProfile.industry_code` の命名差異に対する normalize 側の影響考察

**現状**: セクション 7.4 のテーブルに「insurance は複数コードを束ねるため `sector_id`」と記載。banking は `industry_code: str` ("bk1"/"bk2")。

**問題**: 命名と型が異なる:
- insurance: `sector_id: str` = `"insurance"` （1 プロファイルで in1/in2 を束ねる）
- banking: `industry_code: str` = `"bk1"` or `"bk2"` （2 プロファイルが存在）

normalize (L1) がプロファイルを統一的に扱う際、`profile.sector_id` vs `profile.industry_code` の非対称アクセスが必要になる。これは L1 の責務だが、L3 計画が認識していることを明記すべき。

**推奨対処**: セクション 7.4 のテーブル末尾に注記を追加: 「Profile の識別フィールド命名が banking と非対称（`sector_id` vs `industry_code`）。これは設計意図（insurance は in1/in2 を束ねる構造。banking は bk1/bk2 で CF method が異なるため個別プロファイル）であり、統一的アクセスのアダプテーションは L1 normalize の責務」

---

## MEDIUM（改善すれば品質向上）

### M-1: `OperatingIncomeINS` の `canonical_key` が `ordinary_revenue_ins` — 「OperatingIncome」と「ordinary_revenue」の乖離に対する保守者向け警告が不足

**現状**: セクション 3.2 に「タクソノミ名は "Operating" だが意味は「経常収益」≠ 一般事業の OperatingIncome（営業利益）」とコメントあり。`mapping_note` にも根拠記載。

**改善案**: `_validate_registry()` の docstring に「concept 名と canonical_key の意味的乖離は保険業タクソノミの命名慣習によるもの」と記載するか、セクション 7（注意点・設計判断）に独立した項として以下を追加:

> **7.7 保険業タクソノミの命名上の注意**
> 保険業タクソノミでは `Operating` が「経常」（ordinary）の意味で使用される。これは一般事業の `OperatingIncome`（営業利益）とは異なる概念であるにもかかわらず、同一の英語接頭辞が使われている。本モジュールの `canonical_key` はタクソノミの concept 名ではなく**経済的意味**に基づいて命名している（`ordinary_revenue_ins`）ため、concept 名との乖離が生じる。保守時に concept 名だけを見て canonical_key を推測しないこと。

### M-2: `_validate_registry()` に `display_order` のギャップ内整合性チェックがない

**現状**: セクション 3.4 の検証項目は「display_order が statement_type 内で一意であること」。

**改善案**: ギャップ方式を採用している以上、以下の追加チェックが有用:
- `display_order > 0`（0 はデフォルト値であり、意図的に設定されていないことを示す）
- 同一 statement_type 内で `display_order` が昇順であること（タプルの定義順と display_order の整合性）

jgaap.py の実装でもこのチェックは行われていないが、セクターモジュールではギャップ方式を採用するため、0 が残っていると「設定忘れ」の可能性がある。

### M-3: テスト `test_insurance_specific_keys_not_in_jgaap` のスコープが曖昧

**現状**（セクション 5.1）:
> 明示的に保険固有と定義した canonical_key のみを対象とする

**問題**: 「明示的に保険固有と定義した」の判定基準が不明確。`general_equivalent` が `None` かつ `canonical_key` が `_ins` で終わるもの？ それとも `general_equivalent` が `None` のもの全て？

`OrdinaryProfitINS` は `general_equivalent="ordinary_income"` を持ち、`canonical_key="ordinary_income"` で jgaap にも存在する。これはテスト対象外。一方、`OperatingIncomeINS` は `general_equivalent="revenue"` を持つが `canonical_key="ordinary_revenue_ins"` で jgaap には存在しない。

**改善案**: テスト docstring に判定基準を明記: 「`canonical_key` が `_ins` サフィックスで終わるマッピングのみを対象とする。これらは保険業固有の新規キーであり、jgaap.py に同名のキーが存在してはならない」

### M-4: `InsuranceConceptMapping` と `ConceptMapping` (jgaap) の `is_total` のセマンティクス差異

**現状**: insurance.py では `OperatingIncomeINS`（経常収益）に `is_total=True` を設定。jgaap.py では `NetSales`（売上高）には `is_total=False`。

**問題**: 両方とも「収益の最上位合計」だが、`is_total` の付与基準が異なるように見える。これは構造的差異（保険業では経常収益が本当に「合計行」として表示される）による正しい判断かもしれないが、判断基準が文書化されていない。

**改善案**: セクション 4 に `is_total` の付与基準を明記: 「プレゼンテーションリンクベースで合計行（= 子要素の集約行）として表示される concept に `is_total=True` を設定する。保険業では `OperatingIncomeINS`（経常収益）が保険引受収益+資産運用収益+その他の合計として表示されるため `True`」

---

## LOW（改善すれば洗練されるが現状でも問題なし）

### L-1: `insurance_specific_concepts()` の返却値ソートが未定義

**現状**: 「general_equivalent が None の InsuranceConceptMapping のタプル」と記載。ソート順が未記載。

**改善案**: `_ALL_MAPPINGS` の定義順（PL → BS → CF）を維持する、または `display_order` 順とする。実装時に自然に決まるため LOW。

### L-2: セクション 7.4 のテーブルに `is_total` の比較が不足

**現状**: jgaap / banking / insurance 間の統一フィールドテーブルに `is_total` の行がない。

**改善案**: テーブルに追加: 「`is_total` | `bool = False` | `bool = False` | 共通。合計行・小計行に True」

### L-3: Step 1 の成果物フォーマットが未定義

**現状**: 「主要科目リスト（PL 20-40 件、BS 15-25 件、CF 0-10 件）の確定」と記載。成果物をどこに記録するか（コード内コメント？ 別ファイル？ 計画更新？）が未定義。

**改善案**: 「Step 1 の成果物はコード内のマッピングタプルそのものとして直接反映する。調査過程のメモは不要（実装が真実のソース）」と追記。

---

## 計画として明示的に良い点（変更不要）

1. **前回フィードバック全 14 項目の反映が正確**。セクション 11 のサマリーが追跡可能で、各修正箇所にタグ（`【C-1 第3回反映】` 等）が付与されている
2. **INS-only ポリシー**が一貫しており、jgaap.py へのフォールバック設計が明確
3. **`mapping_note` の追加**（H-4 反映）により、banking.py との対称性が確保された。`OrdinaryProfitINS` と `CommissionsAndCollectionFeesOEINS` への根拠記載は保守者にとって非常に有用
4. **`INSURANCE_INDUSTRY_CODES` のモジュールレベル定数化**（M-1 反映）。テストからも参照可能で一元管理されている
5. **`__all__` の 14 エントリ**（H-3 反映）。`INSURANCE_INDUSTRY_CODES` 定数を含めた点が適切
6. **Step 1 の確認項目 6-9**（H-1/H-2/H-5/M-2 反映）が具体的な concept 名候補を含んでおり、実装者が迷わない
7. **マイルストーン完了条件 23 項目**が網羅的かつ検証可能。特に条件 20 の「Step 1 確認項目の全実施」が品質ゲートとして機能する
8. **テスト方針**: Detroit 派・公開 API のみテスト・フィクスチャ不要の 3 点が明確で、リファクタリング耐性が高い
9. **セクション 10 の「例示」注記**（L-1 反映）。L1 の実装自由度を適切に確保している
10. **`InsuranceSubType` enum 不採用（YAGNI）** の判断が banking.py と一貫している

---

## 修正推奨サマリー

| ID | 深刻度 | 概要 | 推奨対処 |
|----|--------|------|----------|
| H-1 | HIGH | `is_jgaap_specific` 相当フラグの不在 | 不要理由をセクション 7.4 に明記 |
| H-2 | HIGH | `_PROFILE` キャッシュ構築パターンが未記載 | セクション 3.6 に構築コードを追記 |
| H-3 | HIGH | `to_legacy_concept_list()` 不要の理由が未記載 | セクション 2.3 に追記 |
| H-4 | HIGH | `sector_id` vs `industry_code` の非対称性の影響考察 | セクション 7.4 に注記追加 |
| M-1 | MEDIUM | concept 名と canonical_key の乖離に対する保守者向け警告 | セクション 7 に新項追加 |
| M-2 | MEDIUM | `display_order > 0` と昇順整合性のバリデーション | セクション 3.4 に検証項目追加 |
| M-3 | MEDIUM | `test_insurance_specific_keys_not_in_jgaap` のスコープ明確化 | テスト docstring に判定基準を明記 |
| M-4 | MEDIUM | `is_total` の付与基準の文書化 | セクション 4 に基準を明記 |
| L-1 | LOW | `insurance_specific_concepts()` のソート順 | 実装時に決定で OK |
| L-2 | LOW | 統一テーブルに `is_total` 行不足 | テーブル行追加 |
| L-3 | LOW | Step 1 成果物フォーマット | 追記（LOW） |

**CRITICAL 0 件**。HIGH 4 件は全て文書化・明記レベルの修正であり、設計変更は不要。修正コストは低い。全体として計画は実装着手可能な水準に十分達しており、上記を反映すれば完成度は最高レベルに到達する。
