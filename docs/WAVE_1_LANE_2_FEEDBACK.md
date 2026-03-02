# WAVE 1 / LANE 2 フィードバック（第5ラウンド）

## 総合評価

計画は **4 ラウンドのフィードバックを経て非常に高い完成度** に到達している。データモデル設計、エラーハンドリング、テスト計画、下流互換性の考慮など全方位にわたり十分に成熟している。

ただし、擬似コードに **実装時に確実にバグとなる名前空間の誤り** が 1 件残存している。これを修正すれば実装開始可能。

CRITICAL 指摘はない。HIGH 1 件、MEDIUM 2 件、LOW 1 件を以下に記載する。

---

## HIGH（実装前に計画に反映すべき）

### T-1. `order` / `weight` 属性は xlink 名前空間ではない — 擬似コードの名前空間誤り

**問題**: §3.2 step c の `order` 取得擬似コードが以下のようになっている:

```python
order_str = arc_elem.get(f"{{{NS_XLINK}}}order")
```

しかし、`order` と `weight` は **XLink 名前空間に属さない属性** である。XLink 1.0 仕様でアーク要素に定義される属性は `type`, `arcrole`, `title`, `show`, `actuate`, `from`, `to` の 7 つのみ。`order` と `weight` は XBRL 2.1 仕様が `calculationArc` 要素型に直接定義した属性であり、名前空間プレフィックスを持たない。

§1.3 の XML 例でも確認できる:

```xml
<link:calculationArc xlink:type="arc"
    xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
    xlink:from="Assets" xlink:to="CurrentAssets"
    order="1.0" weight="1"/>
<!--  ↑ xlink: なし    ↑ xlink: なし -->
```

このまま実装すると:
1. `arc_elem.get(f"{{{NS_XLINK}}}order")` は **常に `None`** を返す
2. S-1 フォールバックにより全アークが `order=0.0` になる
3. `children_of()` の `order` 昇順ソートが意味をなさなくなり、テストが flaky 化する
4. `weight` についても同様の誤りがあれば全アークがスキップされる（weight が取得できない → `float(None)` → `TypeError` またはスキップ）

**提案**: §3.2 step c の擬似コードを以下のように修正する:

```python
# order と weight は XLink 名前空間ではなく、XBRL 2.1 が定義した直接属性
order_str = arc_elem.get("order")  # NOT f"{{{NS_XLINK}}}order"
weight_str = arc_elem.get("weight")  # NOT f"{{{NS_XLINK}}}weight"

# 一方、from / to は XLink 名前空間
from_label = arc_elem.get(f"{{{NS_XLINK}}}from")
to_label = arc_elem.get(f"{{{NS_XLINK}}}to")
```

参考: Lane 1 の `presentation.py` 計画でも `order` は名前空間なしで取得する設計になっている。

---

## MEDIUM（品質向上のため推奨）

### T-2. `arcrole` 属性のバリデーション（防御的コーディング）

**問題**: §3.2 step 3c では `link:calculationArc` 要素を無条件にイテレーションしている。EDINET 仕様上、計算リンクベースの arcrole は `summation-item` の 1 種類のみ（C-7.6）だが、提出者タクソノミはリキャスト方式で独自作成されるため、仕様外の arcrole が混入する可能性がゼロではない。

仮に未知の arcrole を持つアークを処理した場合、`weight` の意味が異なる可能性があり、計算木の正確性に影響する。

**提案**: `calculationArc` のイテレーション時に arcrole をチェックし、`summation-item` 以外はスキップ + `EdinetWarning` とする:

```python
ARCROLE_SUMMATION = "http://www.xbrl.org/2003/arcrole/summation-item"

arcrole = arc_elem.get(f"{{{NS_XLINK}}}arcrole")
if arcrole != ARCROLE_SUMMATION:
    warnings.warn(EdinetWarning(
        f"計算リンク: 未知の arcrole '{arcrole}' をスキップします"
    ))
    continue
```

§3.4 のエラーハンドリング表にも以下を追加:

| エラー条件 | 対応 | メッセージ例 |
|-----------|------|-------------|
| `calculationArc` の `arcrole` が `summation-item` でない | `warnings.warn(EdinetWarning)` + スキップ | `"計算リンク: 未知の arcrole '{arcrole}' をスキップします"` |

既存の他のエラーハンドリング（`weight` 検証、`loc` 参照不在等）と同一粒度の防御であり、コスト対効果が高い。

---

### T-3. `_XSD_PREFIX_RE` 正規表現の greedy/non-greedy の意図を明確化

**問題**: §3.3 の正規表現:

```python
_XSD_PREFIX_RE = re.compile(r"^(.+?)_\d{4}-\d{2}-\d{2}\.xsd$")
```

既存の `taxonomy/__init__.py` の同等正規表現:

```python
_XSD_PREFIX_RE = re.compile(r"(.+)_(\d{4}-\d{2}-\d{2})\.xsd$")
```

Lane 2 は **non-greedy** `.+?`、既存コードは **greedy** `.+` を使用している。EDINET の標準タクソノミ XSD ファイル名（例: `jppfs_cor_2025-11-01.xsd`）ではどちらも同一結果を返すため、機能的な差異はない。

ただし、Wave 完了後の統合タスク（§9 で言及済み）で L1/L2/L3 の `_extract_concept_from_href()` を共有ユーティリティに集約する際、greedy と non-greedy のどちらを採用するかの判断が必要になる。

**提案**: 以下のいずれかを選択し、§3.3 に理由を 1 行追記する:

- **案A（推奨）**: 既存 `taxonomy/__init__.py` と同一の greedy `.+` に統一し、統合時の差分を最小化する
- **案B**: 現状の non-greedy `.+?` を維持する。R-5 で追記された「非貪欲マッチの挙動の補足コメント」で意図は明確化済みだが、「既存コードとは greedy/non-greedy が異なるが、EDINET のファイル名体系では等価である」旨の 1 行注記を追加する

どちらを選んでも実装上の問題はないが、暗黙の不整合を残さないことが統合時のコストを下げる。

---

## LOW（参考情報）

### T-4. テストケース `test_multiple_roles` の「テスト内 bytes リテラル」の規模感

**問題ではないが情報として**: §6.1 の `test_multiple_roles` は M-4 の採用により「テスト内 bytes リテラルで構築」と定義されている。連結 BS + 連結 PL を含む XML bytes を 1 テスト関数内にインラインで書くと、§6.3 の PL ツリー（16 ノード）+ BS ツリー（8 ノード）で **50-80 行程度の XML bytes リテラル** になる。

テストの可読性を維持するため、実装時には以下の工夫を推奨:

1. テストファイル冒頭にモジュールレベルの `_MULTI_ROLE_XML = b"""..."""` 定数として定義する（テスト関数内にインラインで書くのを避ける）
2. または、BS と PL を別々のフィクスチャ XML（`standard_bs.xml`, `standard_pl.xml`）で読み込み、パース結果を `CalculationLinkbase` のコンストラクタで結合するテストに変更する（ただしこれは「複数 role を含む単一ファイルのパース」のテストにはならない）

これは実装エージェントの判断に委ねてよい。

---

## 計画の強み（変更不要の優れた点）

1. **4 ラウンドの変更ログの透明性**: 各フィードバック項目の採用/不採用/部分採用の判断理由が明記されており、設計意図の追跡性が非常に高い。他レーンの計画よりも成熟している
2. **`CalculationLinkbase` ラッパー + 内部インデックス設計**: `children_of` / `parent_of` が O(1)、`ancestors_of` が O(depth) という性能特性が下流の `standard_mapping`（全科目に対して `ancestors_of` を呼ぶ）で重要になる。Lane 1 の `dict` 返却とは異なるがユースケースに最適化された正しい判断
3. **concept 名の source of truth を `xlink:href` フラグメントに統一**: `_2` サフィックス問題を根本解決しつつ、Lane 1 との不整合を §2.1 で明確に認識・文書化している
4. **`Literal[1, -1]` による型レベルの値域制約 + `float()` 経由パース**: 型安全性と `xsd:decimal` 表記への堅牢なパースを両立
5. **`ancestors_of` の `visited = {concept}` 初期化**: 自己参照と循環参照を同一ロジックで防御する elegance
6. **非スコープの明確な線引き**: validation/calc_check、マージ、他リンクベース、TaxonomyResolver 統合を全て明示的に除外し scope creep を防止
7. **実データ規模感（§11）の記載**: 185 アーク / 8 ロールという具体値が実装エージェントにパフォーマンス感覚を与える
8. **エラーハンドリング表（§3.4）の網羅性**: S-1（order フォールバック）、M-5（href フラグメント不在）を含む 8 条件が定義済みで、既存コードベースのパターンと完全に一貫

---

## フィードバック優先度まとめ

| ID | 優先度 | 概要 | 影響 |
|----|--------|------|------|
| **T-1** | HIGH | `order` / `weight` は xlink 名前空間ではない。擬似コードの `f"{{{NS_XLINK}}}order"` → `"order"` に修正 | 修正しないと全アークが `order=0.0` になり `children_of` のソートが壊れる |
| T-2 | MEDIUM | `arcrole` が `summation-item` であることの検証を追加 | 仕様外データへの防御。他の属性検証（weight, loc 参照）と同粒度 |
| T-3 | MEDIUM | `_XSD_PREFIX_RE` の greedy/non-greedy を既存コードと統一、または差異を注記 | 統合タスク時の暗黙の不整合を予防 |
| T-4 | LOW | `test_multiple_roles` の bytes リテラル規模感。テストの可読性維持の工夫を推奨 | 実装エージェントの判断に委ねてよい |

**総括**: HIGH 1 件（T-1: 名前空間の誤り）は擬似コードのバグであり、計画への反映が必須。このまま実装エージェントが擬似コードを忠実に実装すると `order` が常に `0.0` になるサイレントバグを引き起こす。T-1 を修正すれば **実装開始を強く推奨する**。
