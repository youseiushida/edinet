# Wave 7 / Lane 1 — Text: テキストブロック抽出 (B1 + B2 + B3)

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 7 / Lane 1 を担当するエージェントです。
担当機能: text（テキストブロック抽出・セクション構造化・HTML クリーニング）

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/financial/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - ただし `src/edinet/xbrl/text/__init__.py` は**新規パッケージの初期化として作成可**
   - それ以外の `__init__.py` の更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/text/__init__.py` (新規)
   - `src/edinet/xbrl/text/blocks.py` (新規)
   - `src/edinet/xbrl/text/sections.py` (新規)
   - `src/edinet/xbrl/text/clean.py` (新規)
   - `tests/test_xbrl/test_text_blocks.py` (新規)
   - `tests/fixtures/text_blocks/` (新規ディレクトリ)
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
   - テスト用フィクスチャが必要な場合は `tests/fixtures/text_blocks/` に作成すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - `__init__.py` を変更できないため、利用者には直接パスで import させる
   - 例: `from edinet.xbrl.text.blocks import extract_text_blocks` （OK）
   - 例: `from edinet.xbrl.text import extract_text_blocks` （OK — 自レーンの `__init__.py` 経由）
   - 例: `from edinet.xbrl import text` （NG — 上位 `__init__.py` の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_text_blocks.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 6 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawRoleRef 等)
     - `edinet.xbrl.contexts` (StructuredContext, InstantPeriod, DurationPeriod 等)
     - `edinet.xbrl.facts` (build_line_items)
     - `edinet.xbrl.taxonomy` (TaxonomyResolver, LabelInfo)
     - `edinet.xbrl._namespaces` (NS_* 定数, is_standard_taxonomy, classify_namespace)
     - `edinet.xbrl._linkbase_utils` (extract_concept_from_href 等)
     - `edinet.models.financial` (LineItem, FinancialStatement, StatementType)
     - `edinet.exceptions` (EdinetError, EdinetParseError 等)

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 1 — Text: テキストブロック抽出 (B1 + B2 + B3)

## 0. 位置づけ

### FEATURES.md との対応

Wave 7 Lane 1 は FEATURES.md の以下の 3 機能に対応する:

| Feature Key | 内容 |
|-------------|------|
| `text_blocks` | textBlockItemType タグの構造的抽出 |
| `text_blocks/sections` | `stmts.sections["事業等のリスク"]` によるセクション名アクセス |
| `text_blocks/clean` | HTML → プレーンテキスト変換 |

DEFACTO.md §5-2 で定義された `xbrl/text/` パッケージ。XBRL の `textBlockItemType` Fact からセクション構造化テキストを抽出し、LLM 前処理用のクリーンテキスト変換を提供する。

### WAVE_7.md スケッチとの差異

WAVE_7.md §Lane 1 の TextBlock スケッチから以下の設計変更を加えた:

| WAVE_7.md スケッチ | 本計画 | 理由 |
|---|---|---|
| `role_uri: str` フィールド | 削除 | .xbrl の Fact は role URI を直接持たない。Presentation Linkbase の走査が必要で過剰 |
| `section_name: str \| None` フィールド | `SectionMap` に分離 | 関心の分離。TextBlock は生データ、セクション分類は別レイヤー |
| `clean_text: str` フィールド | `clean_html()` 関数に分離 | 遅延評価。不要な場合のコスト回避 |
| `build_section_map(role_refs=...)` | `build_section_map(blocks)` | concept 名ベースのマッピングで十分。role_refs からの紐付けは Presentation Linkbase が必要 |

### SCOPE.md との関係

SCOPE.md が定める「1件の XBRL → 構造化オブジェクト」変換パイプラインの一部。テキストブロックは有価証券報告書の注記・MD&A 等の非数値セクションであり、LLM/RAG パイプラインで最も需要が高い。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.parser` | `RawFact.value_raw` からテキストブロック HTML 取得 | read-only |
| `edinet.xbrl.contexts` | `StructuredContext.period` で期間取得 | read-only |
| `edinet.xbrl.taxonomy` | `TaxonomyResolver.resolve_clark()` で TextBlock concept の日本語ラベルをセクション名として取得（`facts.py` と同一パターン） | **使用** |

他レーンとのファイル衝突なし。

> **設計決定**: `_namespaces.is_standard_taxonomy()` は当初依存に含めていたが、3つの公開関数のいずれも使用しないため削除した。

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| A-9 | **直接** | TextBlock の HTML コンテンツ取り扱い。.xbrl ではエンティティエスケープされた HTML を XML パーサが自動デコードし、`value_raw` にデコード済み HTML が格納される |
| I-1 | **直接** | Role URI とステートメントのマッピング。1005 個の jppfs_rt + 449 個の jpcrp_rt。ELR 番号体系 |
| I-1b | 参考 | 提出者固有 roleType。サンプル 56 XSD 中 0 件。本計画は concept 名ベースのマッピングを採用したため role URI を使用せず、直接の影響なし |
| J-3 | **直接** | 注記構造。689 個の textBlockItemType（jpcrp_cor の 29.2%）。instant 352 + duration 337 |

---

## 1. 背景知識

### 1.1 TextBlock の XML 構造

XBRL インスタンスにおいて、textBlockItemType 型の Fact は HTML フラグメントを値として持つ。

**.xbrl ファイルでの格納形式** (A-9 より):
```xml
<jpcrp_cor:BusinessRisksTextBlock contextRef="CurrentYearDuration">
  &lt;table&gt;&lt;tr&gt;&lt;td&gt;当社グループの事業リスク...&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;
</jpcrp_cor:BusinessRisksTextBlock>
```

- HTML タグはエンティティエスケープされて格納（`&lt;table&gt;` 等）
- XML パーサ（lxml）がパース時にエンティティを自動デコードする
- デコード後のテキストは XML 子要素ではなく**テキストコンテンツ**として扱われる
- したがって **`RawFact.value_raw`** にデコード済み HTML（タグ付き文字列）が格納される
- `RawFact.value_inner_xml` は XML 子要素が存在する場合のみ値を持つため、エンティティエスケープ方式の .xbrl では **常に `None`**
- 参考: iXBRL (.htm) では `escape="true"` により生 XHTML が XML 子要素として埋め込まれるため `value_inner_xml` に HTML が入るが、Lane 1 は .xbrl のみ対象 (N1)

> **既存コメントとの不一致に関する注記**:
> `financial.py` L40-41 に「HTML タグを含む原文が必要な場合は `RawFact.value_inner_xml` を直接参照すること（TextBlock 等）」というコメントがあるが、
> これは iXBRL (`.htm`) を前提とした記述であり、`.xbrl` のエンティティエスケープ方式には当てはまらない。
> 本計画では A-9 の調査に基づき `value_raw` を正しいソースとして使用する。
> `financial.py` のコメント更新は Lane 1 のスコープ外のため、Wave 7 統合タスク I1 で対応する。

### 1.2 テキストブロック概念の規模 (J-3 より)

jpcrp_cor（有価証券報告書タクソノミ）に **689 個** の textBlockItemType 概念が存在:

| periodType | 件数 | 例 |
|-----------|------|-----|
| instant | 352 | `BusinessRisksTextBlock` |
| duration | 337 | `DescriptionOfBusinessTextBlock` |

**全注記テキストは jpcrp_cor に集中**。jppfs_cor（財務諸表タクソノミ）には textBlockItemType は **0 個**。

### 1.3 Role URI とセクション名 (I-1 より)

有価証券報告書の各セクションは Role URI で区別される。ELR（Extended Link Role）番号体系:

| 番号帯 | 内容 |
|--------|------|
| `3____` | 日本基準 |
| `5____` | IFRS |
| `4____` / `6____` | 注記 |

**セクション名の推定方法**: role URI の末尾パス要素から日本語セクション名を推定する。

例:
- `http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BusinessRisks` → 「事業等のリスク」
- `http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_DescriptionOfBusiness` → 「事業の内容」

### 1.4 提出者固有 roleType (I-1b より)

サンプル調査（56 XSD ファイル）の結果、提出者が独自に定義した roleType は **0 件**。全提出者が EDINET 標準の roleType（jpcrp_rt, jppfs_rt 等）を使用。

ただし仕様上は提出者が `rol_{ElementName}(-{Modifier}/-{Number})` で定義可能。万一の場合のフォールバックとして、role URI に対応するラベルが見つからない場合は role URI 末尾をそのまま返す。

### 1.5 対象セクション例

| セクション | Role URI 末尾（推定） |
|-----------|---------------------|
| 企業の概況（事業の内容） | `DescriptionOfBusiness` |
| 事業等のリスク | `BusinessRisks` |
| 経営者による財政状態…の分析（MD&A） | `ManagementAnalysisOfFinancialPosition` |
| コーポレートガバナンスの状況 | `ExplanationAboutCorporateGovernance` |
| 経理の状況（注記事項） | `NotesToConsolidatedFinancialStatements` |
| 主要な経営指標等の推移 | `MajorManagementIndicators` |

---

## 2. ゴール

完了条件:

```python
from edinet.xbrl.text.blocks import extract_text_blocks, TextBlock
from edinet.xbrl.text.sections import build_section_map
from edinet.xbrl.text.clean import clean_html

# テキストブロック抽出
blocks = extract_text_blocks(parsed.facts, context_map)
assert len(blocks) > 0
assert isinstance(blocks[0], TextBlock)
assert blocks[0].html  # HTML コンテンツ

# セクション名でのアクセス（TaxonomyResolver で全 689 概念の日本語名を自動解決）
section_map = build_section_map(blocks, resolver)
risk_blocks = section_map.get("事業等のリスク")
# → TextBlock のタプル、またはセクション名が見つからなければ None

# HTML クリーニング
clean = clean_html(blocks[0].html)
assert isinstance(clean, str)
assert "<" not in clean  # HTML タグが除去されている
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 | 対応 |
|---|------|------|
| S1 | `RawFact` から textBlockItemType の Fact を抽出 | `extract_text_blocks()` |
| S2 | TextBlock の concept ラベル（TaxonomyResolver）→ 日本語セクション名マッピング | `build_section_map()` |
| S3 | HTML → プレーンテキスト変換（lxml ベース） | `clean_html()` |
| S4 | テーブル構造のタブ/改行保持 | `clean_html()` 内 |
| S5 | 期間情報（InstantPeriod / DurationPeriod）の付与 | TextBlock.period |
| S6 | 連結/個別の区別 | TextBlock.is_consolidated |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | iXBRL (.htm) からの直接抽出 | parser.py は .xbrl のみ対応。iXBRL は将来対応 |
| N2 | 自然言語処理（NER、感情分析等） | SCOPE.md: パイプラインの外側 |
| N3 | BeautifulSoup 依存 | lxml のみで完結する方針 |
| N4 | 画像・図表の抽出 | HTML 内の img/svg は除去 |
| N5 | セクション間の順序保証 | concept 名ベースのマッピングのみ。文書内順序は保証しない |
| N6 | テキストの差分比較（diff） | Lane 8 が担当 |

---

## 4. 実装計画

### 4.0 パッケージ構造

```
src/edinet/xbrl/text/
├── __init__.py       # re-export
├── blocks.py         # TextBlock dataclass + extract_text_blocks()
├── sections.py       # セクション名マッピング + build_section_map()
└── clean.py          # clean_html()
```

### 4.1 TextBlock dataclass (`blocks.py`)

```python
from __future__ import annotations

from dataclasses import dataclass
from edinet.xbrl.contexts import Period


@dataclass(frozen=True, slots=True)
class TextBlock:
    """テキストブロック Fact。

    textBlockItemType の Fact から抽出された HTML テキストブロック。
    有価証券報告書の注記・MD&A 等の非数値セクションを表す。

    Attributes:
        concept: concept のローカル名（例: ``"BusinessRisksTextBlock"``）。
        namespace_uri: 名前空間 URI。
        concept_qname: Clark notation の QName（例: ``"{http://...}BusinessRisksTextBlock"``）。
            ``resolve_clark()`` にそのまま渡せる形式。``RawFact.concept_qname`` から転写。
        html: HTML コンテンツ。RawFact.value_raw から取得（.xbrl のエンティティエスケープ HTML）。
        context_ref: contextRef 属性値。
        period: 期間情報。
        is_consolidated: 連結コンテキストかどうか。
        fact_id: Fact の id 属性値。
    """
    concept: str
    namespace_uri: str
    concept_qname: str
    html: str
    context_ref: str
    period: Period
    is_consolidated: bool
    fact_id: str | None = None
```

### 4.2 extract_text_blocks() (`blocks.py`)

```python
from collections.abc import Sequence
from edinet.xbrl.parser import RawFact
from edinet.xbrl.contexts import StructuredContext

_TEXTBLOCK_SUFFIX = "TextBlock"


def extract_text_blocks(
    facts: Sequence[RawFact],
    context_map: dict[str, StructuredContext],
) -> tuple[TextBlock, ...]:
    """RawFact 群から textBlockItemType の Fact を抽出する。

    textBlockItemType の判定は concept のローカル名が ``"TextBlock"`` で
    終わることを条件とする（EDINET タクソノミの命名慣例）。

    Args:
        facts: parse_xbrl_facts() が返した RawFact のシーケンス。
        context_map: structure_contexts() が返した Context 辞書。

    Returns:
        TextBlock のタプル。元の facts の出現順を保持する。

    Raises:
        EdinetParseError: ``context_ref`` が ``context_map`` に
            見つからない RawFact が存在した場合。
            既存の ``build_line_items()`` と同一の動作。
    """
```

**TextBlock 判定ロジック**:

1. `local_name` が `"TextBlock"` で終わる
2. `unit_ref` が `None`（テキスト Fact）
3. `value_raw` が `None` でなく、空白のみでもない（空テキストブロックを除外）
4. `is_nil` が `False`

**なぜ `value_raw` か**: .xbrl ファイルでは HTML タグがエンティティエスケープされて格納される（`&lt;table&gt;` 等）。lxml はエンティティを自動デコードするが、結果はテキストコンテンツであり XML 子要素ではない。そのため `value_inner_xml`（XML 子要素がある場合のみ有効）は `None` になり、デコード済み HTML は `value_raw` に格納される。

**注意**: EDINET の命名慣例では textBlockItemType の concept は必ず `...TextBlock` で終わる。XSD の `type="nonnum:textBlockItemType"` を直接検証するのはタクソノミ XSD の追加パースが必要で複雑すぎるため、命名慣例ベースの判定で十分。

### 4.3 セクション名マッピング (`sections.py`)

> **設計決定: ハードコード辞書の廃止**
>
> 当初計画では `_SECTION_NAMES` (16エントリ) で concept 名フラグメント → 日本語名を手動マッピングしていた。
> しかし EDINET タクソノミのラベルリンクベースを調査した結果、**全 689 個** の textBlockItemType concept に対して
> 標準ラベル (`role/label`) がそのままセクション名として使えることが判明した:
>
> | concept | 標準ラベル (ja) | verbose ラベル (ja) |
> |---|---|---|
> | `BusinessRisksTextBlock` | `事業等のリスク` | `事業等のリスク [テキストブロック]` |
> | `DescriptionOfBusinessTextBlock` | `事業の内容` | `事業の内容 [テキストブロック]` |
> | `CompanyHistoryTextBlock` | `沿革` | `沿革 [テキストブロック]` |
>
> `TaxonomyResolver` は既に `jpcrp_cor` のラベルを読み込み済み。`resolver.resolve_clark()` を呼ぶだけで
> 全 689 概念の日本語セクション名が自動取得できる（`facts.py` と同一パターン）。
>
> | | 旧案 (ハードコード) | 新案 (TaxonomyResolver) |
> |---|---|---|
> | 保守エントリ | 16（手動） | **0** |
> | 日本語セクション名カバー率 | 16/689 (2.3%) | **689/689 (100%)** |
> | 年次タクソノミ更新 | 突合必要 | **自動追従** |
> | MAINTENANCE.md 影響 | 追記必要 | **なし** |

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from edinet.xbrl.taxonomy import LabelSource, TaxonomyResolver

from edinet.xbrl.text.blocks import _TEXTBLOCK_SUFFIX


@dataclass(frozen=True, slots=True)
class SectionMap:
    """セクション名 → TextBlock リストのマッピング。

    Attributes:
        _index: セクション名をキー、TextBlock タプルを値とする辞書。
        _unmatched: セクション名を推定できなかった TextBlock のタプル。
            ``extract_text_blocks()`` 経由で作成された TextBlock は全て
            ``"TextBlock"`` サフィックスを持つため通常は空。
            ユーザーが直接 ``TextBlock`` を構築して ``build_section_map()`` に
            渡した場合のセーフティネットとして存在する。
    """
    _index: dict[str, tuple[TextBlock, ...]]
    _unmatched: tuple[TextBlock, ...]

    @property
    def sections(self) -> tuple[str, ...]:
        """利用可能なセクション名の一覧を返す。"""
        return tuple(self._index.keys())

    def get(self, section_name: str) -> tuple[TextBlock, ...] | None:
        """セクション名で TextBlock を取得する。

        Args:
            section_name: セクション名（日本語ラベルまたは英語フォールバック名）。

        Returns:
            TextBlock のタプル。セクションが見つからなければ None。
        """
        return self._index.get(section_name)

    def __getitem__(self, section_name: str) -> tuple[TextBlock, ...]:
        """セクション名で TextBlock を取得する。

        Raises:
            KeyError: セクションが見つからない場合。
        """
        if section_name not in self._index:
            available = ", ".join(self._index.keys())
            raise KeyError(
                f"セクション '{section_name}' が見つかりません。"
                f"利用可能なセクション: {available}"
            )
        return self._index[section_name]

    def __contains__(self, section_name: object) -> bool:
        """セクションの存在確認。"""
        return section_name in self._index

    def __len__(self) -> int:
        """セクション数を返す。"""
        return len(self._index)

    @property
    def unmatched(self) -> tuple[TextBlock, ...]:
        """セクション名を推定できなかった TextBlock を返す。"""
        return self._unmatched


def _resolve_section_name(
    block: TextBlock,
    resolver: TaxonomyResolver,
) -> str | None:
    """TaxonomyResolver で concept の日本語ラベルをセクション名として取得する。

    ``facts.py`` の ``build_line_items()`` と同じパターンで
    ``resolver.resolve_clark()`` に Clark notation QName を渡す。

    1. ``resolver.resolve_clark(block.concept_qname)`` で標準ラベル（``role/label``）を取得
    2. ``source`` が ``FALLBACK`` でなければセクション名として返す
    3. ``FALLBACK`` なら ``None`` を返す（フォールバック側で処理）

    Args:
        block: TextBlock。concept_qname を使用。
        resolver: TaxonomyResolver インスタンス。

    Returns:
        日本語セクション名、またはラベル未解決時は None。

    実装例::

        info = resolver.resolve_clark(block.concept_qname, lang="ja")
        if info.source == LabelSource.FALLBACK:
            return None
        return info.text
    """


def _fallback_section_name(concept: str) -> str | None:
    """concept 名から "TextBlock" サフィックスを除去してフォールバック名を生成する。

    resolver でラベルが取得できなかった場合に使用。

    Args:
        concept: concept のローカル名（例: ``"BusinessRisksTextBlock"``）。

    Returns:
        サフィックス除去後の英語名。
        ``"TextBlock"`` サフィックスを持たない場合は None（_unmatched 行き）。
    """


def build_section_map(
    blocks: Sequence[TextBlock],
    resolver: TaxonomyResolver,
) -> SectionMap:
    """TextBlock 群をセクション名でグルーピングする。

    セクション名の解決は以下の優先順位で行う:

    1. **TaxonomyResolver**: concept の標準ラベル（日本語）を取得。
       全 689 個の jpcrp_cor textBlockItemType concept に対応。
    2. **英語フォールバック**: resolver でラベルが見つからない場合、
       concept 名から ``"TextBlock"`` サフィックスを除去した英語名を使用。
       提出者独自の TextBlock concept（filer namespace）はこのパスを通る。
    3. **_unmatched**: ``"TextBlock"`` サフィックスすら持たない異常ケース。
       ``extract_text_blocks()`` 経由なら発生しないが、ユーザーが直接
       ``TextBlock`` を構築した場合のセーフティネット。

    Args:
        blocks: extract_text_blocks() が返した TextBlock のシーケンス。
        resolver: TaxonomyResolver インスタンス。

    Returns:
        SectionMap。
    """
```

**セクション名解決の戦略**:

```
resolver.resolve_clark(block.concept_qname, lang="ja")
    → source != FALLBACK  →  日本語ラベル（689/689 カバー）
    → source == FALLBACK  ↓
concept.removesuffix("TextBlock")  →  英語フォールバック
         ↓ (サフィックスなし)
_unmatched  →  セーフティネット
```

> **根拠**: `facts.py:67` の `resolver.resolve_clark(fact.concept_qname, lang="ja")` と同一パターン。
> `resolve()` は第1引数に namespace **prefix**（`"jpcrp_cor"` 等）を要求するが、
> TextBlock は `namespace_uri`（完全 URI）を保持するため `resolve_clark()` が正しい。

- **標準 taxonomy 概念** (`jpcrp_cor`): `TaxonomyResolver` が 100% カバー。ハードコードゼロ
- **提出者独自概念** (filer namespace): `TaxonomyResolver` が提出者ラベル (`_lab.xml`) から解決。それも失敗すれば英語フォールバック
- **年次タクソノミ更新**: `TaxonomyResolver` がラベルリンクベースを動的読み込みするため **自動追従**。MAINTENANCE.md への追記不要

### 4.4 HTML クリーニング (`clean.py`)

```python
from lxml import etree


def clean_html(html: str) -> str:
    """HTML フラグメントをプレーンテキストに変換する。

    lxml の ``tostring(method="text")`` をベースに、テーブル構造を
    タブ/改行で保持する。

    変換ルール:
    - ``<br>``, ``<br/>`` → 改行
    - ``<p>``, ``</p>`` → 改行
    - ``<td>`` → タブ区切り
    - ``<tr>`` → 改行
    - ``<table>`` → 改行
    - ``<img>``, ``<svg>`` → 除去
    - 連続する空行 → 1 つの空行に正規化
    - 先頭・末尾の空白 → strip

    Args:
        html: HTML フラグメント文字列。

    Returns:
        プレーンテキスト。空の入力には空文字列を返す。
    """
```

**実装方針**:

1. `lxml.html.fragment_fromstring()` で HTML をパース
2. テーブル要素（`<table>`, `<tr>`, `<td>`）に対してタブ/改行を挿入
3. `etree.tostring(method="text")` でテキスト抽出
4. 連続空行の正規化

**BeautifulSoup 不要**: lxml の HTML パーサで十分。依存ライブラリを増やさない方針。lxml は XBRL パースで既に依存済み。

### 4.5 `__init__.py`

```python
"""テキストブロック抽出パッケージ。

textBlockItemType の Fact からセクション構造化テキストを抽出し、
HTML → プレーンテキスト変換を提供する。

利用例::

    from edinet.xbrl.text import extract_text_blocks, build_section_map, clean_html

    blocks = extract_text_blocks(parsed.facts, context_map)
    section_map = build_section_map(blocks, resolver)

    risk = section_map["事業等のリスク"]
    for block in risk:
        print(clean_html(block.html))
"""
from edinet.xbrl.text.blocks import TextBlock as TextBlock
from edinet.xbrl.text.blocks import extract_text_blocks as extract_text_blocks
from edinet.xbrl.text.clean import clean_html as clean_html
from edinet.xbrl.text.sections import SectionMap as SectionMap
from edinet.xbrl.text.sections import build_section_map as build_section_map

__all__ = [
    "TextBlock",
    "extract_text_blocks",
    "SectionMap",
    "build_section_map",
    "clean_html",
]
```

---

## 5. 実装の注意点

### 5.1 TextBlock 判定の精度

concept 名末尾 `"TextBlock"` による判定は EDINET タクソノミの命名慣例に依存する。精度は高い（J-3 の調査で 689 個全てが `...TextBlock` で終わる）が、提出者が独自に `...TextBlock` でない textBlockItemType 型の concept を定義する可能性はゼロではない。

v0.1.0 ではこれを許容する。将来的にタクソノミ XSD を直接参照する判定に切り替え可能。

### 5.2 HTML の壊れた構造への耐性

提出者が作成する HTML は必ずしも well-formed ではない。lxml の HTML パーサ（`lxml.html`）は壊れた HTML を自動修復するため、`lxml.etree` ではなく `lxml.html` を使用する。

### 5.3 空テキストブロック

`value_raw` が `None` または空白のみの TextBlock は抽出しない。`is_nil=True` の Fact も除外する。

### 5.4 セクション名マッピングと保守

`TaxonomyResolver` による動的ラベル解決を採用したため、ハードコードのセクション名辞書は存在しない。

**保守コスト**: **ゼロ**。タクソノミ年次更新時も `TaxonomyResolver` がラベルリンクベースを動的に読み込むため、コード変更は不要（MAINTENANCE.md の「自動追従するファイル」カテゴリと同等）。

**フォールバック**: resolver でラベルが見つからない提出者独自概念は `concept.removesuffix("TextBlock")` の英語名がセクション名になる。機能的には問題ない。

### 5.5 lxml.html の fragment_fromstring のラップ動作

`lxml.html.fragment_fromstring()` は入力 HTML を `<html><body>` で自動ラップする動作がある。`create_parent` 引数でラップ要素を制御できる。テキストのみのフラグメント（タグなし入力）では `str` を返す場合があり、`Element` を期待するコードが壊れる。

`create_parent=True` または `create_parent="div"` を指定してラップ要素を強制し、常に `Element` が返るようにすること。この動作をテストケースで明示的に検証する。

> **補足**: `lxml.html` は `lxml>=5.0`（本プロジェクトの既存依存）に含まれるため、import エラーの心配は不要。ただしプロジェクト内で `lxml.html` を使用するのは Lane 1 が初となる。

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_xbrl/test_text_blocks.py` に全テストを作成する。

### 6.2 テストフィクスチャ

`tests/fixtures/text_blocks/` に以下のフィクスチャを作成する。

**方針**: CLAUDE.md に「古典派（デトロイト派）」と指定されているため、`extract_text_blocks()` と `build_section_map()` のテストでは `RawFact` / `StructuredContext` をテスト内で直接構築する。XML ファイルのパースに依存しない。フィクスチャファイルは `clean_html()` のテスト入力用 HTML のみとする。

| ファイル | 内容 | 使用先 |
|---------|------|--------|
| `html_table.html` | テーブルを含む HTML フラグメント | `TestCleanHtml` |
| `html_nested.html` | ネストした HTML 構造 | `TestCleanHtml` |
| `html_broken.html` | 壊れた HTML（タグ未閉じ等） | `TestCleanHtml` |
| `html_empty.html` | 空 HTML | `TestCleanHtml` |

> **注**: 当初 `simple.xml` 等の XBRL フィクスチャを予定していたが、
> `extract_text_blocks()` の入力は `Sequence[RawFact]` であり、
> テスト内で `RawFact(...)` を直接構築する方がパース基盤への依存がなく堅牢なため廃止した。

### 6.3 テストケース一覧（~28 件）

```python
class TestExtractTextBlocks:
    def test_extract_single_textblock(self):
        """単一の TextBlock Fact が正しく抽出される。"""

    def test_extract_multiple_textblocks(self):
        """複数の TextBlock Fact が出現順で抽出される。"""

    def test_skip_non_textblock(self):
        """TextBlock でない Fact（monetaryItemType 等）は除外される。"""

    def test_skip_nil_fact(self):
        """is_nil=True の Fact は除外される。"""

    def test_skip_empty_value(self):
        """value_raw が None または空白のみの Fact は除外される。"""

    def test_html_content_preserved(self):
        """TextBlock.html に HTML コンテンツが保持される。"""

    def test_period_from_context(self):
        """TextBlock.period が StructuredContext から正しく転写される。"""

    def test_consolidated_flag(self):
        """TextBlock.is_consolidated が正しく設定される。"""

    def test_concept_name(self):
        """TextBlock.concept がローカル名で設定される。"""

    def test_empty_facts(self):
        """空の facts では空タプルが返る。"""

    def test_missing_context_raises(self):
        """context_map に存在しない contextRef で EdinetParseError が発生する。
        既存の build_line_items() と同一の動作。"""


class TestSectionMap:
    def test_build_section_map_resolver_labels(self):
        """TaxonomyResolver の日本語ラベルでセクション名が付与される。"""

    def test_build_section_map_instant_and_duration_in_same_section(self):
        """同一 concept の instant / duration TextBlock が同一セクションにグルーピングされる。
        J-3: textBlockItemType は instant 352 + duration 337。"""

    def test_section_map_getitem(self):
        """__getitem__ でセクション名から TextBlock タプルを取得できる。"""

    def test_section_map_get_none(self):
        """存在しないセクション名で get() が None を返す。"""

    def test_section_map_getitem_keyerror(self):
        """存在しないセクション名で __getitem__ が KeyError を発生させる。"""

    def test_section_map_contains(self):
        """__contains__ でセクションの存在確認ができる。"""

    def test_section_map_sections_property(self):
        """sections プロパティでセクション名一覧が取得できる。"""

    def test_section_map_unmatched_no_textblock_suffix(self):
        """'TextBlock' サフィックスを持たない直接構築の TextBlock が unmatched に入る。
        extract_text_blocks() 経由なら発生しないセーフティネットの検証。"""

    def test_section_map_resolver_miss_fallback_to_english(self):
        """resolver でラベルが見つからない場合、TextBlock サフィックス除去の英語名になる。"""

    def test_section_map_len(self):
        """__len__ がセクション数を返す。"""


class TestCleanHtml:
    def test_clean_simple_text(self):
        """単純なテキスト（タグなし）がそのまま返る。"""

    def test_clean_paragraph_tags(self):
        """<p> タグが改行に変換される。"""

    def test_clean_table_structure(self):
        """テーブルがタブ区切り + 改行に変換される。"""

    def test_clean_br_tags(self):
        """<br> タグが改行に変換される。"""

    def test_clean_nested_html(self):
        """ネストした HTML が正しくフラット化される。"""

    def test_clean_broken_html(self):
        """壊れた HTML でもエラーにならない。"""

    def test_clean_empty_string(self):
        """空文字列が空文字列を返す。"""

    def test_clean_whitespace_normalization(self):
        """連続する空行が 1 つの空行に正規化される。"""

    def test_clean_img_svg_removed(self):
        """<img> と <svg> が除去される。"""

    def test_clean_preserves_japanese_text(self):
        """日本語テキストが正しく保持される。"""

    def test_clean_plain_text_without_tags(self):
        """タグなしのプレーンテキスト入力でも正常動作する。
        lxml.html.fragment_fromstring のラップ動作に影響されない。"""
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/xbrl/text/__init__.py` | 新規 | パッケージ re-export |
| `src/edinet/xbrl/text/blocks.py` | 新規 | `TextBlock` dataclass + `extract_text_blocks()` |
| `src/edinet/xbrl/text/sections.py` | 新規 | `SectionMap`, `build_section_map()`, TaxonomyResolver 連携 |
| `src/edinet/xbrl/text/clean.py` | 新規 | `clean_html()` |
| `tests/test_xbrl/test_text_blocks.py` | 新規 | ~28 テストケース |
| `tests/fixtures/text_blocks/` | 新規 | 4 HTML フィクスチャファイル（`clean_html()` テスト用） |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `__init__.py` | ~30 行 |
| `blocks.py` | ~100 行 |
| `sections.py` | ~200 行 |
| `clean.py` | ~100 行 |
| テスト + フィクスチャ | ~550 行 |
| **合計** | **~930 行** |

---

## 8. 検証手順

1. `uv run pytest tests/test_xbrl/test_text_blocks.py -v` で新規テスト全 PASS
2. `uv run pytest` で全テスト PASS（既存テスト破壊なし）
3. `uv run ruff check src/edinet/xbrl/text/ tests/test_xbrl/test_text_blocks.py` でリント PASS
