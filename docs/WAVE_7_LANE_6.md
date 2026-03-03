# Wave 7 / Lane 6 — Segments: 事業セグメント + 地域セグメント (B4)

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 7 / Lane 6 を担当するエージェントです。
担当機能: segments（事業セグメント・地域セグメント解析）

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/financial/__init__.py` を変更してはならない
   - `src/edinet/financial/dimensions/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/financial/dimensions/segments.py` (新規)
   - `tests/test_xbrl/test_segments.py` (新規)
   - `tests/fixtures/segments/` (新規ディレクトリ)
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
   - テスト用フィクスチャが必要な場合は `tests/fixtures/segments/` に作成すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - 例: `from edinet.financial.dimensions.segments import extract_segments` （OK）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_segments.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 6 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact 等)
     - `edinet.xbrl.contexts` (StructuredContext, ContextCollection, DimensionMember, Period 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver, LabelInfo)
     - `edinet.xbrl._namespaces` (is_standard_taxonomy, is_filer_namespace 等)
     - `edinet.xbrl.linkbase.definition` (DefinitionTree, HypercubeInfo, AxisInfo, MemberNode)
     - `edinet.models.financial` (LineItem, FinancialStatement)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 6 — Segments: 事業セグメント + 地域セグメント (B4)

## 0. 位置づけ

### FEATURES.md との対応

| Feature Key | 内容 |
|-------------|------|
| `dimensions/segments` | 事業セグメント解析 |
| `dimensions/geographic` | 地域セグメント解析（`axis_local_name` 引数で任意の軸を指定可能） |
| `dimensions/list_axes` | Filing 内のディメンション軸一覧取得（軸名のハードコード不要） |

XBRL コンテキストの `xbrldi:explicitMember` ディメンションから事業セグメント・地域セグメント等を抽出し、セグメント別の売上高・利益・資産等を構造化する。`list_dimension_axes()` で Filing 内の全軸を日本語ラベル付きで発見できるため、ユーザーは XBRL の内部名を知る必要がない。

### SCOPE.md との関係

SCOPE.md が定める「1件の XBRL → 構造化オブジェクト」変換パイプラインの一部。セグメント情報は企業分析の基礎データ。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.contexts` | `StructuredContext.is_consolidated` で連結/個別判定、`Period` 型 | read-only |
| `edinet.models.financial` | `LineItem.dimensions` からディメンション読み取り、`.period` で期間フィルタ | read-only |
| `edinet.xbrl.taxonomy` | `TaxonomyResolver.resolve_clark()` でメンバーラベル解決 | read-only |
| `edinet.xbrl._namespaces` | `is_standard_taxonomy()` でメンバー名前空間判定 | read-only |
| `edinet.xbrl.linkbase.definition` | `DefinitionTree` → `HypercubeInfo` → `AxisInfo` → `MemberNode` でメンバー階層・順序・デフォルト取得（**optional**） | read-only |

他レーンとのファイル衝突なし。`financial/statements.py` は読み取りのみ。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| J-2 | **直接** | セグメント情報の完全な構造。OperatingSegmentsAxis、標準メンバー、提出者メンバー、概念名の同一性 |
| C-8 | **直接** | Definition Linkbase のディメンション構造。Heading → Table → Axis → Domain → Member の階層 |

---

## 1. 背景知識

### 1.1 セグメント情報の構造 (J-2 より)

EDINET のセグメント情報は XBRL のディメンション（次元）で表現される:

**ディメンション軸**: `jpcrp_cor:OperatingSegmentsAxis`

**セグメントの区別方法**: 同一の概念名（例: `jppfs_cor:NetSales`）が、異なるコンテキストの `scenario` 内の `explicitMember` でセグメントごとに分離される。

```xml
<!-- 自動車セグメントの売上高 -->
<jppfs_cor:NetSales contextRef="CurrentYearDuration_AutomotiveSegment"
    unitRef="JPY" decimals="-6">28000000000000</jppfs_cor:NetSales>

<!-- 金融サービスセグメントの売上高 -->
<jppfs_cor:NetSales contextRef="CurrentYearDuration_FinancialServicesSegment"
    unitRef="JPY" decimals="-6">2500000000000</jppfs_cor:NetSales>
```

コンテキスト定義:
```xml
<xbrli:context id="CurrentYearDuration_AutomotiveSegment">
  <xbrli:entity><xbrli:identifier scheme="...">E02144</xbrli:identifier></xbrli:entity>
  <xbrli:period>...</xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember dimension="jpcrp_cor:OperatingSegmentsAxis">
      jpcrp030000-asr_E02144-000:AutomotiveReportableSegmentMember
    </xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>
```

### 1.2 メンバー構造（2 層）(J-2 より)

| 層 | 名前空間 | 例 | 意味 |
|----|---------|-----|------|
| 標準メンバー | `jpcrp_cor` | `ReportableSegmentsMember` | セグメント区分の分類 |
| 標準メンバー | `jpcrp_cor` | `TotalOfReportableSegmentsAndOthersMember` | 報告セグメント＋その他合計 |
| 標準メンバー | `jpcrp_cor` | `UnallocatedAmoundsAndEliminationMember` | 未配分＋消去 |
| 標準メンバー | `jpcrp_cor` | `ReconciliationMember` | 調整額 |
| **提出者メンバー** | 提出者固有 | `AutomotiveReportableSegmentMember` | 個別事業セグメント |
| **提出者メンバー** | 提出者固有 | `FinancialServicesReportableSegmentMember` | 個別事業セグメント |

**重要**: 個別の事業セグメント名（自動車、金融サービス等）は全て**提出者独自のメンバー**。日本語名は提出者の `_lab.xml` から TaxonomyResolver で取得する。

### 1.3 Definition Linkbase のディメンション構造 (C-8 より)

```
Heading (ConsolidatedBalanceSheetHeading)
  └─ Table (BalanceSheetTable)          [all]
       ├─ Axis (ConsolidatedOrNonConsolidatedAxis)  [hypercube-dimension]
       │    └─ Domain → Member hierarchy   [dimension-domain, domain-member]
       └─ Axis (OperatingSegmentsAxis)     [hypercube-dimension]
            └─ Domain → Member hierarchy   [dimension-domain, domain-member]
```

arcrole の階層:
- `all`: ルート → Table
- `hypercube-dimension`: Table → Axis
- `dimension-domain`: Axis → Domain
- `dimension-default`: デフォルトメンバー指定
- `domain-member`: ドメイン → メンバー（再帰的階層）

**contextElement**: 全て `"scenario"` (EDINET 固有)
**closed**: 全て `true`
**notAll**: EDINET では **使用されない** (0 件)

### 1.4 StructuredContext の既存基盤

`StructuredContext.dimensions` は `tuple[DimensionMember, ...]` で、各 `DimensionMember` は:
- `axis`: Clark notation（例: `"{http://...jpcrp_cor/...}OperatingSegmentsAxis"`）
- `member`: Clark notation（例: `"{http://...}AutomotiveReportableSegmentMember"`）

`ContextCollection.filter_by_dimension(axis, member)` で特定のディメンション軸+メンバーを持つコンテキストのみを絞り込める。

### 1.5 OperatingSegmentsAxis の Clark notation

```python
# jpcrp_cor の名前空間 URI（バージョン依存）
# 例: "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
# OperatingSegmentsAxis の Clark notation:
# "{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis"
```

名前空間 URI のバージョン部分が毎年変わるため、ハードコードではなく **ローカル名 `"OperatingSegmentsAxis"` + `classify_namespace()` のモジュールグループ `"jpcrp"` で検出** する。

---

## 2. ゴール

完了条件:

```python
from edinet.financial.dimensions.segments import (
    extract_segments,
    list_dimension_axes,
    DimensionAxisSummary,
    SegmentData,
)

# ---- 軸の発見（マジックストリング不要） ----
axes = list_dimension_axes(
    items=all_line_items,
    context_map=context_map,
    resolver=resolver,
)
# axes[0].label_ja == "事業セグメント"
# axes[0].label_en == "Operating segments"
# axes[0].local_name == "OperatingSegmentsAxis"
# axes[0].member_count == 6

assert len(axes) > 0
for ax in axes:
    assert isinstance(ax, DimensionAxisSummary)
    assert ax.label_ja  # 日本語ラベル（TaxonomyResolver で解決済み）

# ---- セグメント抽出 ----
segments = extract_segments(
    items=all_line_items,
    context_map=context_map,
    resolver=resolver,
    axis_local_name=axes[0].local_name,  # 発見した軸名をそのまま渡す
)

assert len(segments) > 0
for seg in segments:
    assert isinstance(seg, SegmentData)
    assert seg.name  # "省エネルギー関連事業" 等の日本語名
    assert len(seg.items) > 0

# ---- 特定セグメントの売上高 ----
seg0 = next(s for s in segments if not s.is_standard_member)
net_sales = next(i for i in seg0.items if i.concept == "NetSales")
assert net_sales.value > 0

# ---- ラベルでもアクセス可能 ----
sales_by_label = next(i for i in seg0.items if "売上高" in i.label_ja.text)
assert sales_by_label.value > 0
```

### 実データでの検証結果

SDSホールディングス (E05452, 2025-06-27 提出) で以下を確認済み:

| 検証項目 | 結果 |
|---|---|
| 軸のラベル解決（`resolve_clark()` で ja/en） | 全軸で成功。`OperatingSegmentsAxis` → "事業セグメント" / "Operating segments" |
| 提出者メンバーのラベル解決 | 成功。`SavingEnergyRelatedReportableSegmentsMember` → "省エネルギー関連事業" [filer] |
| 標準メンバーのラベル解決 | 成功。`ReportableSegmentsMember` → "報告セグメント" [standard] |
| `is_standard_taxonomy()` による標準/提出者判定 | 正確に分類 |
| 同一 Filing 内の他軸（役員、大株主、株式種類等）の発見 | 全 9 軸を発見、全てラベル解決成功 |

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 | 対応 |
|---|------|------|
| S1 | Filing 内の全ディメンション軸を日本語/英語ラベル付きで列挙 | `list_dimension_axes()` |
| S2 | 任意のディメンション軸でセグメント抽出（事業・地域等） | `extract_segments(axis_local_name=...)` |
| S3 | 各セグメントに属する LineItem の抽出 | `SegmentData.items` |
| S4 | セグメントメンバーの日本語ラベル解決 | TaxonomyResolver 経由 |
| S5 | 標準メンバー / 提出者メンバーの区別 | `SegmentData.is_standard_member` |
| S6 | 連結/個別の区別 | `extract_segments()` の `consolidated` 引数 |
| S7 | 期間フィルタ | `extract_segments()` の `period` 引数 |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | セグメント間の比較・集計・パーセント計算 | SCOPE.md: 年度横断集約はスコープ外。パーセントは `Decimal` 割り算で利用者側が容易に計算可能 |
| N2 | テキストブロック型セグメント情報の構造化 | Lane 1 が担当 |
| N3 | Definition Linkbase の新規パース処理の追加 | 既存の `parse_definition_linkbase()` と `DefinitionTree` をそのまま利用する |
| N4 | セグメント別財務諸表（FinancialStatement 型）の組み立て | v0.2.0 で検討。v0.1.0 ではフラットな SegmentItem リストで提供 |

---

## 4. 実装計画

### 4.1 DimensionAxisSummary dataclass

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DimensionAxisSummary:
    """Filing 内で検出されたディメンション軸の概要。

    ``list_dimension_axes()`` が返す。ユーザーが XBRL の内部名を
    知らなくても、日本語/英語ラベルで軸を選択できるようにする。

    Attributes:
        local_name: 軸のローカル名（例: ``"OperatingSegmentsAxis"``）。
            ``extract_segments(axis_local_name=...)`` にそのまま渡せる。
        clark: 軸の Clark notation
            （例: ``"{ns}OperatingSegmentsAxis"``）。
        label_ja: 日本語ラベル（例: ``"事業セグメント"``）。
        label_en: 英語ラベル（例: ``"Operating segments"``）。
        is_standard: 標準タクソノミの軸なら True。
        member_count: ユニークメンバー数。
        item_count: この軸を持つ LineItem の総数。
    """
    local_name: str
    clark: str
    label_ja: str
    label_en: str
    is_standard: bool
    member_count: int
    item_count: int
```

### 4.2 list_dimension_axes()

```python
from collections.abc import Sequence
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import StructuredContext
from edinet.xbrl.taxonomy import TaxonomyResolver, LabelSource


def list_dimension_axes(
    items: Sequence[LineItem],
    context_map: dict[str, StructuredContext],
    resolver: TaxonomyResolver,
    *,
    consolidated: bool = True,
) -> tuple[DimensionAxisSummary, ...]:
    """Filing 内の全ディメンション軸を日本語/英語ラベル付きで列挙する。

    LineItem.dimensions を走査してユニークな軸を収集し、
    TaxonomyResolver で各軸のラベルを解決する。
    ハードコードされた軸名は一切使用しない。

    Args:
        items: build_line_items() が返した全 LineItem。
        context_map: structure_contexts() が返した Context 辞書。
        resolver: ラベル解決用の TaxonomyResolver。
        consolidated: True なら連結、False なら個別の LineItem のみ対象。

    Returns:
        DimensionAxisSummary のタプル。item_count 降順（多い軸が先頭）。
        ディメンション軸が存在しなければ空タプル。
    """
```

**アルゴリズム**:

```
1. 全 LineItem を走査
   - context_map で連結/個別フィルタ
   - item.dimensions から軸の Clark notation を収集
   - axis_clark → {member_clark のセット, item_count} を集約
2. 各軸について:
   a. Clark notation からローカル名・名前空間を抽出
   b. resolver.resolve_clark(axis_clark, lang="ja") でラベル解決
      - LabelSource.FALLBACK ならローカル名をフォールバック
   c. resolver.resolve_clark(axis_clark, lang="en") で英語ラベル
   d. is_standard_taxonomy(namespace) で標準/提出者判定
3. item_count 降順でソートして返す
```

**実データ検証**（SDSホールディングス E05452）:

| 軸 | label_ja | label_en | メンバー数 | LineItem数 |
|---|---|---|---|---|
| `OperatingSegmentsAxis` | 事業セグメント | Operating segments | 6 | 85 |
| `ComponentsOfEquityAxis` | 純資産の内訳項目 | Components of net assets | 12 | 165 |
| `DirectorsAndOtherOfficersAxis` | 役員 | Directors (and other officers) | 8 | 90 |

全軸で `resolve_clark()` が `[standard]` ソースのラベルを返すことを確認済み。

### 4.3 SegmentItem dataclass (旧 4.1)

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from edinet.xbrl.contexts import Period
from edinet.xbrl.taxonomy import LabelInfo


@dataclass(frozen=True, slots=True)
class SegmentItem:
    """セグメント内の 1 科目。

    Attributes:
        concept: concept のローカル名（例: ``"NetSales"``）。
        label_ja: 日本語ラベル。
        label_en: 英語ラベル。
        value: 値。数値 Fact は Decimal、テキストは str、nil は None。
        period: 期間情報。
        context_id: contextRef 属性値（トレーサビリティ用）。
    """
    concept: str
    label_ja: LabelInfo
    label_en: LabelInfo
    value: Decimal | str | None
    period: Period
    context_id: str
```

### 4.4 SegmentData dataclass

```python
@dataclass(frozen=True, slots=True)
class SegmentData:
    """1 つのセグメントのデータ。

    Attributes:
        name: セグメント名（日本語ラベル。例: ``"自動車"``）。
        member_concept: メンバーのローカル名
            （例: ``"AutomotiveReportableSegmentMember"``）。
        member_qname: メンバーの Clark notation
            （例: ``"{ns}AutomotiveReportableSegmentMember"``）。
        is_standard_member: 標準メンバー（jpcrp_cor）なら True。
            提出者独自メンバーなら False。
        items: セグメント内の科目タプル。
        axis_concept: ディメンション軸のローカル名
            （デフォルト: ``"OperatingSegmentsAxis"``）。
        depth: DefinitionLinkbase から取得したメンバー階層の深さ。
            0 = ドメインルート、1 = 直下メンバー、2 = 個別セグメント 等。
            DefinitionLinkbase 未提供時は 0（フラット）。
        is_default_member: AxisInfo.default_member と一致する場合 True。
            EntityTotalMember（全社合計）の識別に使用。
            DefinitionLinkbase 未提供時は False。
    """
    name: str
    member_concept: str
    member_qname: str
    is_standard_member: bool
    items: tuple[SegmentItem, ...]
    axis_concept: str = "OperatingSegmentsAxis"
    depth: int = 0
    is_default_member: bool = False
```

### 4.5 extract_segments()

```python
from collections.abc import Sequence
from edinet.models.financial import LineItem
from edinet.xbrl.contexts import Period, StructuredContext
from edinet.xbrl.linkbase.definition import DefinitionTree
from edinet.xbrl.taxonomy import TaxonomyResolver


_OPERATING_SEGMENTS_AXIS_LOCAL = "OperatingSegmentsAxis"


def extract_segments(
    items: Sequence[LineItem],
    context_map: dict[str, StructuredContext],
    resolver: TaxonomyResolver,
    *,
    consolidated: bool = True,
    period: Period | None = None,
    axis_local_name: str = _OPERATING_SEGMENTS_AXIS_LOCAL,
    definition_trees: dict[str, DefinitionTree] | None = None,
) -> tuple[SegmentData, ...]:
    """LineItem 群からセグメント別データを抽出する。

    指定されたディメンション軸（デフォルト: OperatingSegmentsAxis）の
    メンバーごとに LineItem をグルーピングし、SegmentData として返す。

    Args:
        items: build_line_items() が返した全 LineItem。
        context_map: structure_contexts() が返した Context 辞書。
            連結/個別フィルタ（``StructuredContext.is_consolidated``）に使用。
        resolver: ラベル解決用の TaxonomyResolver。
            提出者ラベルは事前に load_filer_labels() しておくこと。
        consolidated: True なら連結、False なら個別。
        period: 対象期間。None なら全期間のセグメントを抽出。
        axis_local_name: ディメンション軸のローカル名。
            デフォルトは ``"OperatingSegmentsAxis"``。
            ``"GeographicAreasAxis"`` 等を指定可能（将来拡張）。
        definition_trees: parse_definition_linkbase() の戻り値（任意）。
            指定した場合、DefinitionLinkbase のメンバー階層から以下を付与:
            (a) ``SegmentData.depth`` — メンバーの階層深度
            (b) ``SegmentData.is_default_member`` — デフォルトメンバー判定
            (c) 並び順をタクソノミ定義順（domain-member arc の order）に変更
            None の場合は depth=0, is_default_member=False、
            並び順は元文書の出現順（LineItem.order ベース）にフォールバック。
            既存パターン: ``custom.py`` の ``detect_custom_items()`` と同方式。

    Returns:
        SegmentData のタプル。セグメントが見つからなければ空タプル。
        順序は definition_trees 提供時はタクソノミ定義順、
        未提供時は元文書内の出現順（各セグメント内で最小の
        ``LineItem.order`` を持つセグメントが先頭）。
    """
```

**アルゴリズム**:

```
0. [optional] definition_trees が提供された場合:
   a. 全 DefinitionTree を走査し、HypercubeInfo.axes から
      axis_concept == axis_local_name の AxisInfo を検索
   b. 見つかれば AxisInfo.domain の MemberNode ツリーを深さ優先走査し、
      member_concept → (depth, order) のインデックスを構築
   c. AxisInfo.default_member を記録
   d. 見つからなければ definition_trees は無効として扱い、フォールバック動作

1. 全 LineItem を走査する
   - context_map.get(item.context_id) で StructuredContext を引く
   - context_id が context_map に存在しない場合はその LineItem をスキップする
2. item.dimensions（LineItem が直接保持する DimensionMember タプル）から
   指定 axis のメンバーを持つ LineItem を抽出する
   - axis の判定: DimensionMember.axis の Clark notation からローカル名を抽出し、
     axis_local_name と照合
   ※ LineItem.dimensions は StructuredContext.dimensions と同一内容を転写済み
3. 連結/個別フィルタ: context_map から取得した StructuredContext.is_consolidated で絞り込み
   （LineItem 自体は is_consolidated を持たないため context_map が必要）
4. 期間フィルタ: period が指定されていれば ``item.period == period`` で等価比較
   - InstantPeriod 同士: instant 日付が一致
   - DurationPeriod 同士: start_date と end_date がともに一致
   - InstantPeriod vs DurationPeriod: マッチしない（型が異なるため __eq__ は False）
5. メンバーの Clark notation をキーとしてグルーピング
6. 各メンバーについて:
   a. メンバーの Clark notation からローカル名を抽出
   b. TaxonomyResolver でメンバーの日本語ラベルを解決
   c. is_standard_taxonomy() でメンバーの名前空間を判定
   d. グループ内の LineItem を SegmentItem に変換
      - concept: item.local_name を転写
      - label_ja / label_en: item.label_ja / item.label_en をそのまま転写（再解決しない）
      - value / period / context_id: item から転写
   e. [optional] step 0 のインデックスからメンバーの depth を取得（未ヒットなら 0）
   f. [optional] default_member と一致すれば is_default_member=True
7. SegmentData タプルとして返す
   - 順序:
     - definition_trees あり: step 0 のインデックス order で昇順ソート（タクソノミ定義順）
       インデックスに存在しないメンバーは末尾に document order で追加
     - definition_trees なし: 各セグメント内の最小 LineItem.order で昇順ソート（元文書の出現順）
```

### 4.6 _resolve_member_label() ヘルパー

```python
def _resolve_member_label(
    member_qname: str,
    resolver: TaxonomyResolver,
) -> str:
    """メンバーの Clark notation から日本語ラベルを解決する。

    Args:
        member_qname: メンバーの Clark notation。
        resolver: TaxonomyResolver。

    Returns:
        日本語ラベル文字列。ラベルが見つからない場合はローカル名を返す。
    """
```

**フォールバックチェーン**:
1. `TaxonomyResolver.resolve_clark(member_qname, lang="ja")` でラベルを取得
   - resolve_clark() は内部で標準タクソノミ → 提出者ラベル（load_filer_labels() 済み）の順で検索する
   - `LabelInfo.source` が `LabelSource.FALLBACK` でなければその `.text` を返す
2. フォールバック時（ラベル未解決）はローカル名から `"Member"` サフィックスを `removesuffix("Member")` で除去して返す
   - 例: `"AutomotiveReportableSegmentMember"` → `"AutomotiveReportableSegment"`
   - 標準メンバー（`ReconciliationMember` 等）も同じルールで `"Reconciliation"` になるが、
     これらは通常 resolve_clark() で解決されるため実際にはフォールバックに至らない

### 4.7 _extract_local_name_from_clark() ヘルパー

```python
def _extract_local_name_from_clark(clark: str) -> str:
    """Clark notation からローカル名を抽出する。

    Args:
        clark: ``"{namespace}localName"`` 形式。

    Returns:
        ローカル名。
    """
    # "{ns}local" → "local"
    # 既存コードベース（dataframe/facts.py L80-81）と同じ rsplit パターンを採用
    # NOTE: 将来的にコードベース全体で Clark 操作ユーティリティを共通化する候補
    return clark.rsplit("}", 1)[-1]
```

### 4.8 _extract_namespace_from_clark() ヘルパー

```python
def _extract_namespace_from_clark(clark: str) -> str:
    """Clark notation から名前空間 URI を抽出する。

    Args:
        clark: ``"{namespace}localName"`` 形式。

    Returns:
        名前空間 URI。
    """
    if clark.startswith("{"):
        return clark[1:clark.index("}")]
    return ""
```

### 4.9 _find_axis_info() ヘルパー

```python
from edinet.xbrl.linkbase.definition import (
    AxisInfo,
    DefinitionTree,
    MemberNode,
)


def _find_axis_info(
    definition_trees: dict[str, DefinitionTree],
    axis_local_name: str,
) -> AxisInfo | None:
    """全 DefinitionTree から指定軸の AxisInfo を検索する。

    最初にヒットした AxisInfo を返す。C-8 QA によると
    OperatingSegmentsAxis は複数 role に出現するが、メンバー階層は
    同一であるため最初のヒットで十分。

    Args:
        definition_trees: parse_definition_linkbase() の戻り値。
        axis_local_name: 対象のディメンション軸ローカル名。

    Returns:
        AxisInfo。見つからなければ None。
    """
    for tree in definition_trees.values():
        for hc in tree.hypercubes:
            for axis in hc.axes:
                if axis.axis_concept == axis_local_name:
                    return axis
    return None
```

### 4.10 _build_member_index() ヘルパー

```python

@dataclass(frozen=True, slots=True)
class _MemberMeta:
    """DefinitionLinkbase から取得したメンバーのメタ情報。"""
    depth: int
    order: float

def _build_member_index(
    definition_trees: dict[str, DefinitionTree] | None,
    axis_local_name: str,
) -> tuple[dict[str, _MemberMeta], str | None]:
    """DefinitionLinkbase からメンバーのメタ情報インデックスを構築する。

    全 DefinitionTree を走査し、指定軸の AxisInfo を検索。
    MemberNode ツリーを深さ優先で走査して
    member_concept → _MemberMeta のインデックスを構築する。

    既存パターン: ``custom.py`` の ``_build_parent_index()`` と同方式
    （DefinitionTree を走査してインデックス構築）。

    Args:
        definition_trees: parse_definition_linkbase() の戻り値。
            None の場合は空辞書を返す。
        axis_local_name: 対象のディメンション軸ローカル名。

    Returns:
        (メンバーインデックス, デフォルトメンバーのローカル名 or None) のタプル。
    """
    if definition_trees is None:
        return {}, None

    # 全 DefinitionTree から対象軸の AxisInfo を検索（最初のヒットで終了）
    target_axis = _find_axis_info(definition_trees, axis_local_name)

    if target_axis is None or target_axis.domain is None:
        return {}, None

    # MemberNode ツリーを深さ優先走査
    index: dict[str, _MemberMeta] = {}
    counter = 0.0  # グローバル順序カウンタ

    def _walk(node: MemberNode, depth: int) -> None:
        nonlocal counter
        index[node.concept] = _MemberMeta(depth=depth, order=counter)
        counter += 1.0
        for child in node.children:  # children は order 昇順ソート済み
            _walk(child, depth + 1)

    _walk(target_axis.domain, depth=0)

    return index, target_axis.default_member
```

---

## 5. 実装の注意点

### 5.1 OperatingSegmentsAxis の検出

OperatingSegmentsAxis の Clark notation は名前空間バージョンに依存:
- `{http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor}OperatingSegmentsAxis`

**バージョン非依存の検出方法**:
`DimensionMember.axis` の Clark notation からローカル名を抽出し、`"OperatingSegmentsAxis"` と照合する。名前空間のバージョンに依存しない。

### 5.2 提出者メンバーのラベル解決

提出者独自のセグメントメンバー（`AutomotiveReportableSegmentMember` 等）の日本語ラベルは、ZIP 内の提出者 `_lab.xml` から取得する。`TaxonomyResolver.load_filer_labels()` が事前に呼ばれていることが前提。

呼び出し側（Filing.xbrl() パイプライン）が既に filer labels をロード済みのため、本 Lane では追加のラベルロードは不要。

### 5.3 セグメントが存在しない Filing

全ての Filing にセグメント情報があるわけではない（単一セグメント企業、個別財務諸表のみの提出等）。セグメントが見つからない場合は空タプルを返す。

### 5.4 調整額・消去メンバー

`ReconciliationMember` や `UnallocatedAmoundsAndEliminationMember` はセグメント情報の一部だが、事業セグメントとは性質が異なる。SegmentData として一律に返し、`is_standard_member=True` でマークする。ユーザーが必要に応じてフィルタする。

### 5.5 軸の発見と選択

ユーザーは `list_dimension_axes()` で Filing 内の全軸を発見し、その `local_name` を `extract_segments(axis_local_name=...)` に渡す。XBRL の内部名（`"OperatingSegmentsAxis"` 等）を直接知る必要はない。

```python
axes = list_dimension_axes(items, ctx_map, resolver)
for ax in axes:
    print(f"{ax.label_ja}: {ax.member_count} メンバー")
# → 事業セグメント: 6 メンバー
# → 純資産の内訳項目: 12 メンバー

# 事業セグメントを選択して抽出
seg_axis = next(ax for ax in axes if "セグメント" in ax.label_ja)
segments = extract_segments(items, ctx_map, resolver, axis_local_name=seg_axis.local_name)
```

`extract_segments()` のデフォルト引数 `axis_local_name="OperatingSegmentsAxis"` は、`list_dimension_axes()` を使わない直接利用のために残す。

### 5.6 DefinitionLinkbase 連携（optional）

`definition_trees` 引数は `custom.py` の `detect_custom_items(definition_linkbase=...)` と同じオプショナルパターン。

**提供される場合**:
- 提出者の `_def.xml` をパースした `dict[str, DefinitionTree]` を渡す
- 提出者の定義リンクベースには標準メンバー＋提出者固有メンバーの完全な階層が含まれる
- `_build_member_index()` で `AxisInfo.domain` → `MemberNode` ツリーを走査し、メンバーの depth と canonical order を取得
- `AxisInfo.default_member`（通常 `"EntityTotalMember"`）をデフォルトメンバーとして記録

**提供されない場合**:
- `depth=0`, `is_default_member=False` のフラットな結果
- 並び順は元文書の出現順（`LineItem.order` ベース）
- 基本的なセグメント抽出機能に影響なし

**注意**: `_build_member_index()` は `AxisInfo.domain.children` の order 属性（DefinitionArc.order）を走査順に利用するため、MemberNode ツリーが order 昇順ソート済みであることに依存する（`definition.py` の実装で保証済み）。

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_xbrl/test_segments.py` に全テストを作成する。

### 6.2 テストフィクスチャ

`tests/fixtures/segments/` に以下のフィクスチャを作成:

テストは LineItem, StructuredContext, TaxonomyResolver のモック/フィクスチャデータを直接構築する方式。XML フィクスチャは使用しない（デトロイト派: 入出力境界でテスト）。

ヘルパー関数でテストデータを構築:

| ヘルパー | 内容 |
|---------|------|
| `_make_context(context_id, *, ...)` | テスト用 StructuredContext 生成 |
| `_make_line_item(concept, context_id, value, *, ...)` | テスト用 LineItem 生成 |

**ヘルパーシグネチャ例**:

```python
_JPCRP_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
_FILER_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp030000-asr_E02144-000"
_CONSOLIDATED_AXIS = "{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedOrNonConsolidatedAxis"
_CONSOLIDATED_MEMBER = "{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}ConsolidatedMember"
_NON_CONSOLIDATED_MEMBER = "{http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor}NonConsolidatedMember"


def _make_context(
    context_id: str,
    *,
    consolidated: bool = True,
    segment_member_clark: str | None = None,
    axis_clark: str = f"{{{_JPCRP_NS}}}OperatingSegmentsAxis",
    period: Period | None = None,
) -> StructuredContext:
    """テスト用 StructuredContext を生成する。

    consolidated=True/False で ConsolidatedOrNonConsolidatedAxis の
    メンバーを自動設定。segment_member_clark が指定されていれば
    OperatingSegmentsAxis ディメンションも付与。
    """
    ...


def _make_line_item(
    concept: str,
    context_id: str,
    value: Decimal | str | None = Decimal("1000"),
    *,
    namespace_uri: str = _JPCRP_NS,
    dimensions: tuple[DimensionMember, ...] = (),
    period: Period | None = None,
    order: int = 0,
) -> LineItem:
    """テスト用 LineItem を生成する。"""
    ...
```

**注意**: テストフィクスチャのディメンション軸には実データと同じ `"OperatingSegmentsAxis"`（`jpcrp_cor` 名前空間）を使用すること。既存 `test_contexts.py` が使用する `"BusinessSegmentsAxis"`（`jppfs_cor`）は別の軸であり、混同しないこと。

### 6.3 テストケース一覧（~40 件）

```python
class TestListDimensionAxes:
    def test_single_axis(self):
        """1 軸のみの LineItem 群で DimensionAxisSummary が 1 件返る。"""

    def test_multiple_axes(self):
        """複数軸が存在する場合、全軸が返る。"""

    def test_label_resolved(self):
        """TaxonomyResolver で軸の日本語/英語ラベルが解決される。"""

    def test_label_fallback_to_local_name(self):
        """ラベル未解決時はローカル名がフォールバック。"""

    def test_is_standard_true(self):
        """標準タクソノミの軸で is_standard=True。"""

    def test_is_standard_false(self):
        """提出者タクソノミの軸で is_standard=False。"""

    def test_member_count(self):
        """member_count がユニークメンバー数を正しく反映する。"""

    def test_item_count(self):
        """item_count がその軸を持つ LineItem 数を正しく反映する。"""

    def test_ordered_by_item_count_desc(self):
        """結果が item_count 降順でソートされる。"""

    def test_no_dimensions(self):
        """ディメンションなしの LineItem のみで空タプルが返る。"""

    def test_consolidated_filter(self):
        """consolidated=True で連結コンテキストの軸のみ返る。"""


class TestExtractSegments:
    def test_single_segment(self):
        """1 セグメントの LineItem が正しく抽出される。"""

    def test_multiple_segments(self):
        """複数セグメントが正しくグルーピングされる。"""

    def test_segment_name_from_resolver(self):
        """TaxonomyResolver でメンバーの日本語ラベルが解決される。"""

    def test_segment_name_fallback_to_local(self):
        """ラベルが見つからない場合はローカル名がセグメント名になる。"""

    def test_is_standard_member_true(self):
        """標準メンバー（jpcrp_cor）で is_standard_member=True。"""

    def test_is_standard_member_false(self):
        """提出者メンバーで is_standard_member=False。"""

    def test_consolidated_filter(self):
        """consolidated=True で連結コンテキストのみ抽出される。"""

    def test_non_consolidated_filter(self):
        """consolidated=False で個別コンテキストのみ抽出される。"""

    def test_period_filter(self):
        """period 指定で該当期間のみ抽出される。"""

    def test_no_segments(self):
        """セグメント情報がない Filing で空タプルが返る。"""

    def test_items_contain_values(self):
        """SegmentItem に正しい value が設定される。"""

    def test_items_contain_labels(self):
        """SegmentItem に label_ja, label_en が設定される。"""

    def test_items_preserve_period(self):
        """SegmentItem に period が正しく設定される。"""

    def test_custom_axis(self):
        """axis_local_name を変更して別の軸でセグメント抽出できる。"""

    def test_reconciliation_member_included(self):
        """ReconciliationMember が SegmentData に含まれる。"""

    def test_multiple_items_per_segment(self):
        """1 セグメントに複数の科目が含まれる。"""

    def test_context_id_not_in_map_skipped(self):
        """context_map に存在しない context_id の LineItem はスキップされる。"""

    def test_result_ordered_by_document_appearance(self):
        """definition_trees なしでは元文書の出現順でソートされる。"""


class TestDefinitionLinkbaseIntegration:
    """DefinitionLinkbase 連携テスト（definition_trees 引数）。"""

    def test_depth_from_member_hierarchy(self):
        """definition_trees 提供時に depth がメンバー階層深度を反映する。"""

    def test_is_default_member_true(self):
        """AxisInfo.default_member と一致するメンバーで is_default_member=True。"""

    def test_is_default_member_false_without_definition(self):
        """definition_trees=None の場合は is_default_member=False。"""

    def test_ordering_by_taxonomy_definition(self):
        """definition_trees 提供時にタクソノミ定義順でソートされる。"""

    def test_unknown_member_appended_at_end(self):
        """インデックスに存在しないメンバーはタクソノミ定義順の末尾に追加される。"""

    def test_definition_trees_none_fallback(self):
        """definition_trees=None なら depth=0, is_default_member=False, 文書出現順。"""


class TestSegmentData:
    def test_dataclass_frozen(self):
        """SegmentData が frozen dataclass。"""

    def test_member_qname(self):
        """member_qname に Clark notation が設定される。"""

    def test_axis_concept_default(self):
        """axis_concept のデフォルト値が OperatingSegmentsAxis。"""

    def test_depth_default_zero(self):
        """depth のデフォルト値が 0。"""

    def test_is_default_member_default_false(self):
        """is_default_member のデフォルト値が False。"""


class TestHelpers:
    def test_extract_local_name_from_clark(self):
        """Clark notation からローカル名が正しく抽出される。"""

    def test_extract_namespace_from_clark(self):
        """Clark notation から名前空間 URI が正しく抽出される。"""

    def test_resolve_member_label_standard(self):
        """標準メンバーのラベルが解決される。"""

    def test_find_axis_info_found(self):
        """_find_axis_info() が最初にヒットした AxisInfo を返す。"""

    def test_find_axis_info_not_found(self):
        """_find_axis_info() で対象軸が存在しない場合は None を返す。"""

    def test_build_member_index_with_definition(self):
        """DefinitionTree から member_concept → (depth, order) インデックスが構築される。"""

    def test_build_member_index_none(self):
        """definition_trees=None で空辞書と None が返る。"""

    def test_build_member_index_axis_not_found(self):
        """対象軸が DefinitionTree に存在しない場合は空辞書と None が返る。"""
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/financial/dimensions/segments.py` | 新規 | `DimensionAxisSummary`, `list_dimension_axes()`, `SegmentItem`, `SegmentData`, `extract_segments()`, `_find_axis_info()`, `_build_member_index()` + ヘルパー群 |
| `tests/test_xbrl/test_segments.py` | 新規 | ~40 テストケース |
| ~~`tests/fixtures/segments/`~~ | ~~新規~~ | レビュー C2 により削除。XML フィクスチャは不使用、テストデータはヘルパー関数で生成するためディレクトリ不要 |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `segments.py` | ~500 行 |
| テスト | ~780 行 |
| **合計** | **~1,280 行** |

---

## 8. 検証手順

1. `uv run pytest tests/test_xbrl/test_segments.py -v` で新規テスト全 PASS
2. `uv run pytest` で全テスト PASS（既存テスト破壊なし）
3. `uv run ruff check src/edinet/financial/dimensions/segments.py tests/test_xbrl/test_segments.py` でリント PASS

---

## 9. 保守負荷評価

### 新規ハードコード

| 定数 | 値 | カテゴリ（MAINTENANCE.md 準拠） |
|------|----|----|
| `_OPERATING_SEGMENTS_AXIS_LOCAL` | `"OperatingSegmentsAxis"` | **不変**（EDINET 制度上の構造定数。`contexts.py` の `_CONSOLIDATED_AXIS_LOCAL` と同レベル） |

### 保守不要の理由

- **concept マッピングなし**: ラベル解決は全て `TaxonomyResolver` 経由（タクソノミ更新時に自動追従）
- **名前空間バージョン非依存**: ローカル名マッチング + `is_standard_taxonomy()` による動的判定
- **`list_dimension_axes()` はハードコードゼロ**: 軸名を一切ハードコードせず、LineItem.dimensions から動的に収集。新しい軸が追加されてもコード変更不要で自動追従
- **年次更新の影響なし**: MAINTENANCE.md の保守チェックリストへの追記は不要

### フォールバックラベルの仕様

`_resolve_member_label()` でラベルが解決できない場合、ローカル名から `"Member"` サフィックスを `removesuffix("Member")` で除去した英語文字列を返す。例: `"AutomotiveReportableSegmentMember"` → `"AutomotiveReportableSegment"`。これ以上のクリーニング（`"Reportable"` の除去等）は行わない。通常は `TaxonomyResolver.resolve_clark()` で日本語ラベルが解決されるため、フォールバックに至ることは稀。

---

## 10. レビュー記録（2026-03-03）

### 総合評価: 承認（軽微な指摘のみ）

既存コードベースのパターン（`custom.py` の `_build_parent_index()`、`contexts.py` の `is_consolidated`）に忠実で、QA (J-2, C-8) の知見を正確に反映している。

### レビュー指摘一覧

#### C1. `DimensionAxisSummary.label_ja: str` vs `SegmentItem.label_ja: LabelInfo` — 型の不統一（許容）

- `DimensionAxisSummary.label_ja` は `str`（§4.1）
- `SegmentItem.label_ja` は `LabelInfo`（§4.3）

同じ `label_ja` という名前で型が異なる。ただし意図的な設計であり許容とする:
- `DimensionAxisSummary` は発見・表示用のサマリー型であり、簡潔な `str` が適切
- `SegmentItem` は `LineItem` から転写した詳細データであり、`LabelInfo`（ソース情報付き）が適切
- **結論: そのまま（案1）。名前の不統一は Docstring の型注釈で十分に区別可能**

#### C2. `tests/fixtures/segments/` ディレクトリの空振り → 削除

§6.2 で「XML フィクスチャなし」「ヘルパー関数によるテストデータ生成」と明記されており、ディレクトリ自体が不要。§7 の変更ファイル一覧から削除済み。

#### C3. `_extract_local_name_from_clark()` の重複（許容、将来の統合候補）

`dataframe/facts.py` L80-81 に同等の `rsplit("}", 1)[-1]` が既に存在する。Lane 6 で3箇所目のコピーになるが、以下の理由で現時点は許容:
- 各モジュールが独立ヘルパーとして持つのは並列開発の安全性に寄与
- 計画 §4.7 のコメントに「将来的に共通化する候補」と既に記載済み
- **統合タスク I1 時に `_namespaces.py` 等への共通ユーティリティ抽出を検討すること**

#### C4. テストケース追加提案（任意）

以下の2件を追加すると堅牢性が向上する（実装者の判断に委ねる）:
- `test_nil_value_in_segment_item` — `is_nil=True` / `value=None` の LineItem がセグメントに含まれるケース
- `test_text_fact_in_segment` — `value: str` の LineItem がセグメントに含まれるケース（型定義上は許容だが稀）

### 保守影響確認

**MAINTENANCE.md の更新は不要。** 新規ハードコードは `_OPERATING_SEGMENTS_AXIS_LOCAL` 1件のみ（「不変」カテゴリ）。concept マッピングなし、名前空間バージョン依存なし、全ラベル解決が TaxonomyResolver 経由で自動追従。
