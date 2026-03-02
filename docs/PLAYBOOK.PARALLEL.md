# 並列実装プレイブック（Wave / Lane 運用）

## 1. 目的

この文書は、`FEATURES.md` の依存関係を前提に、コーディングエージェント並列実装を高速かつ安全に回すための運用ルールを定義する。

前提:

- 並列数は実質無制限
- 速度ボトルネックは「依存」と「マージコンフリクト」
- したがって運用の中心は `Wave` 設計と `Lane` の編集境界管理

## 2. 用語定義

- `Wave`: 同じ基準コミットから同時に着手する実装バッチ
- `Lane`: Wave 内の独立作業単位（1 feature または 1 micro-feature）
- `Contract Freeze Wave`: 契約（I/F, 型, 例外, 選択ルール）を先に凍結する Wave
- `Hard dependency`: 先行 feature の契約未確定で、先にマージすると高確率で破壊される依存
- `Soft dependency`: 依存はあるが最小契約が凍結済みで、adapter 経由で先行実装できる依存
- `Independent`: 当該 Wave 内で他 lane に依存しない実装

## 3. Hard / Soft 判定基準

原則:

- 契約未確定フェーズは「ほぼ全部 Hard」で運用する
- 例外的に、契約テストが書ける依存のみ Soft 扱いにできる

実務判定:

- 契約テストを書けない依存は `Hard`
- 契約テストを書ける依存は `Soft`

最小契約として凍結する項目:

- 入出力型
- `None` / 空値の扱い
- 例外型と送出条件
- 順序保証（例: 文書順保持）
- 代表的選択ルール（例: 連結優先）

## 4. Wave 計画ルール

1. Wave 開始前に基準コミット（`wave-base`）を固定する。
2. Wave は「依存の閉包」を満たす lane 群で編成する。
3. Lane は feature でなく「編集パスの衝突最小化」で分割する。
4. 共有ホットスポットは統合 lane 以外編集禁止にする。

共有ホットスポット例（統合 lane 専用）:

- `src/edinet/__init__.py`
- `src/edinet/public_api.py`
- `src/edinet/xbrl/__init__.py`
- `pyproject.toml`
- `stubs/edinet/**`

## 5. Lane 仕様テンプレート

各 lane は着手前に以下を定義する。

```yaml
lane_id: W1-L3
feature: contexts
depends_on: [facts]
edit_allowlist:
  - src/edinet/xbrl/contexts.py
  - tests/test_xbrl/test_contexts.py
edit_denylist:
  - src/edinet/__init__.py
  - pyproject.toml
acceptance:
  - 対応テスト追加
  - 既存回帰なし
  - FEATURES ステータス更新案を記述
```

## 6. 実行フロー（1 Wave）

1. `Plan`: lane 定義、依存確認、allowlist 確定
2. `Kickoff`: lane ごとに branch 作成し並列実装開始
3. `Run`: 各 lane は allowlist 内で実装・テスト
4. `Integrate`: 統合 lane が順次マージして競合解消
5. `Close`: Wave 完了判定、ドキュメント更新、次 Wave を計画

ブランチ命名例:

- Wave: `wave/01-xbrl-core`
- Lane: `lane/01-contexts`, `lane/01-units`

## 7. マージゲート

### Lane 完了ゲート

- 対応 feature の受け入れ条件を満たす
- 対応テストが追加・更新されている
- lane 単独で `pytest` の該当スコープが通る
- allowlist 外編集がない

### Wave 完了ゲート

- 全 lane が統合済み
- フル回帰テスト成功
- `FEATURES.md` ステータス更新
- `PLAN.LIVING.md` の次 Wave 反映

## 8. 新規依存発見時のフォールバック

規則:

1. 発見後 15 分以内に `DEP-ALERT` を発行する
2. 依存を `Hard` / `Soft` に分類する
3. `Hard` なら lane を「契約スキャフォールド」までで停止し micro-lane を新設
4. `Soft` なら adapter + TODO + テスト stub を残して継続
5. 依存グラフ（`FEATURES.md` / `PLAN.LIVING.md`）を更新する

報告テンプレート:

```text
[DEP-ALERT]
lane: W1-L3
feature: contexts
new_dependency: namespaces
type: Hard
evidence: context->dimension 解釈に namespace 分類が必要
impact: contexts 完了条件の一部を満たせない
fallback_plan: W1-L7 namespaces-micro を追加し先行実装
```

## 9. 推奨初期運用

1. まず `Contract Freeze Wave` を 1 回実施する
2. Freeze では「契約テスト作成」を成果物にする
3. Freeze 完了後の Wave から Soft 許可を開始する

初期は以下の順で運用する:

1. Wave CF-0: `facts -> contexts/units/namespaces/dei` の契約凍結
2. Wave 1: `contexts/units/namespaces/dei` 並列実装
3. Wave 2: `standards/detect -> standards/* -> standards/normalize`
4. Wave 3: `statements/PL` と `dataframe/facts` の統合

## 10. 失敗パターンと禁止事項

- 契約未凍結のまま Soft 判定を乱用しない
- 全 lane で `__init__.py` を同時編集しない
- 依存追加を黙って実装し続けない（必ず `DEP-ALERT`）
- Wave 未完了のまま次 Wave を開始しない

## 11. 運用メモ

- 本文書は「最速運用」を優先した初版。運用しながら毎 Wave 終了時に更新する。
- 詳細な feature 依存の正本は `docs/FEATURES.md` を参照する。
