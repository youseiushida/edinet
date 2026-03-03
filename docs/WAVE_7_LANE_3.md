# Wave 7 / Lane 3 — Footnotes: 脚注リンク解析 (B9)

# エージェントが守るべきルール

## 並列実装の安全ルール（必ず遵守）

あなたは Wave 7 / Lane 3 を担当するエージェントです。
担当機能: footnotes（脚注リンク解析・Fact ↔ 脚注テキスト紐付け）

### 絶対禁止事項

1. **`__init__.py` の変更・作成を一切行わないこと**
   - `src/edinet/__init__.py` を変更してはならない
   - `src/edinet/xbrl/__init__.py` を変更してはならない
   - `src/edinet/xbrl/linkbase/__init__.py` を変更してはならない
   - `src/edinet/xbrl/taxonomy/__init__.py` を変更してはならない
   - `src/edinet/financial/__init__.py` を変更してはならない
   - `src/edinet/models/__init__.py` を変更してはならない
   - `src/edinet/api/__init__.py` を変更してはならない
   - 新たな `__init__.py` を作成してはならない
   - これらの更新は Wave 完了後の統合タスクが一括で行う

2. **他レーンが担当するファイルを変更しないこと**
   あなたが変更・作成してよいファイルは以下に限定される:
   - `src/edinet/xbrl/linkbase/footnotes.py` (新規)
   - `tests/test_xbrl/test_footnotes.py` (新規)
   - `tests/fixtures/footnotes/` (新規ディレクトリ)
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
   - テスト用フィクスチャが必要な場合は `tests/fixtures/footnotes/` に作成すること

### 推奨事項

6. **新モジュールの公開は直接 import で行うこと**
   - 例: `from edinet.xbrl.linkbase.footnotes import parse_footnote_links` （OK）
   - 例: `from edinet.xbrl.linkbase import footnotes` （NG — `__init__.py` の変更が必要）

7. **テストファイルの命名規則**
   - 自レーンのテストは `tests/test_xbrl/test_footnotes.py` に作成
   - 既存のテストファイルは変更しないこと

8. **他モジュールの利用は import のみ**
   - 他レーンが作成中のモジュールに依存してはならない
   - Wave 6 以前に存在が確認されたモジュールのみ import 可能:
     - `edinet.xbrl.parser` (ParsedXBRL, RawFact, RawFootnoteLink 等)
     - `edinet.xbrl._namespaces` (NS_LINK, NS_XLINK, NS_XML 等)
     - `edinet.exceptions` (EdinetError, EdinetParseError, EdinetWarning 等)
   - `edinet.xbrl._linkbase_utils` は本レーンでは使用しない（§0「使用しない既存基盤」参照）

9. **作業完了時の報告**
   - 作成・変更した全ファイルのパスを一覧で報告すること
   - `uv run pytest` の結果（pass/fail）を報告すること
   - 既存テストを壊していないことを確認すること

---

# LANE 3 — Footnotes: 脚注リンク解析 (B9)

## 0. 位置づけ

### FEATURES.md との対応

| Feature Key | 内容 |
|-------------|------|
| `footnotes` | Fact ↔ 脚注テキスト紐付け |

XBRL の `link:footnoteLink` 要素をパースし、Fact と脚注テキスト（※1, ※2 等）の紐付けを提供する。日本基準（J-GAAP）の BS/PL で使用される脚注番号の解決に対応。

### SCOPE.md との関係

SCOPE.md が定める「1件の XBRL → 構造化オブジェクト」変換パイプラインの一部。脚注は Fact に付随するメタデータであり、Fact の完全な理解に必要。

### 依存

| 依存先 | 用途 | 種類 |
|--------|------|------|
| `edinet.xbrl.parser` | `RawFootnoteLink.xml` から脚注リンクの XML 断片取得 | read-only |
| `edinet.xbrl._namespaces` | `NS_LINK`, `NS_XLINK`, `NS_XML` 定数 | read-only |
| `edinet.exceptions` | `EdinetParseError`, `EdinetWarning` | read-only |

他レーンとのファイル衝突なし。

### 使用しない既存基盤（意図的な非依存）

| 基盤 | 不使用の理由 |
|------|-------------|
| `_linkbase_utils.extract_concept_from_href()` | 他リンクベースの loc は XSD への参照（`*.xsd#ConceptName`）だが、footnoteLink の loc は Fact ID への参照（`#IdFact1234`）。href 形式が根本的に異なるため適用不可 |
| `_linkbase_utils.ROLE_*` 定数 | ラベルリンクベース用の role URI（`totalLabel` 等）。脚注の role（`NotesNumber` 等）は別体系 |
| `TaxonomyResolver` | concept 名 → ラベルの解決器。本モジュールは Fact ID → 脚注テキストの対応付けであり、concept レイヤーの処理を含まない |
| `Statements` / `LineItem` | `LineItem` は `fact_id` フィールドを持たない（`RawFact → LineItem` 変換時に落とされる）。将来 `LineItem` に `fact_id` を追加すれば `FinancialStatement` レベルでの脚注アクセスが可能になるが、それは別タスク |

### QA 参照

| QA | 関連度 | 用途 |
|----|--------|------|
| A-5 | **直接** | footnoteLink の完全な XML 構造、arcrole、footnoteRole、order 属性の扱い |

---

## 1. 背景知識

### 1.1 footnoteLink の XML 構造 (A-5 より)

XBRL インスタンスのルート直下に `link:footnoteLink` 要素が出現する:

```xml
<link:footnoteLink xlink:type="extended"
    xlink:role="http://www.xbrl.org/2003/role/link">

  <!-- 1. Fact への参照（loc） -->
  <link:loc xlink:type="locator"
      xlink:href="#IdFact1234"
      xlink:label="fact_loc_1"/>

  <!-- 2. 脚注テキスト -->
  <link:footnote xlink:type="resource"
      xlink:label="fn_1"
      xlink:role="http://www.xbrl.org/2003/role/footnote"
      xml:lang="ja">
    ※1 当事業年度の減損損失の認識について...
  </link:footnote>

  <!-- 3. Fact → 脚注のアーク -->
  <link:footnoteArc xlink:type="arc"
      xlink:arcrole="http://www.xbrl.org/2003/arcrole/fact-footnote"
      xlink:from="fact_loc_1"
      xlink:to="fn_1"/>
</link:footnoteLink>
```

### 1.2 パースの 3 要素

| 要素 | 属性 | 意味 |
|------|------|------|
| `link:loc` | `xlink:href="#IdFact1234"` | Fact の id 属性への参照 |
| `link:loc` | `xlink:label="fact_loc_1"` | アーク接続用のラベル |
| `link:footnote` | `xlink:label="fn_1"` | アーク接続用のラベル |
| `link:footnote` | `xlink:role` | 脚注の種類（後述） |
| `link:footnote` | `xml:lang` | 言語（`"ja"` / `"en"` 等） |
| `link:footnoteArc` | `xlink:from` | loc のラベル |
| `link:footnoteArc` | `xlink:to` | footnote のラベル |
| `link:footnoteArc` | `xlink:arcrole` | `fact-footnote` **のみ** |

### 1.3 footnoteRole の種類

EDINET では以下の 3 種のみ使用される（A-5 [F3][F5][F8]）。
XBRL 2.1 仕様のデフォルト role (`http://www.xbrl.org/2003/role/footnote`) は
EDINET では使用されない（GFM Rule 1.2.20 が対象外、A-5 [F7]）。

| Role URI | 用途 | 例 |
|----------|------|-----|
| `http://disclosure.edinet-fsa.go.jp/role/jppfs/role/NotesNumber` | 注記番号 | 「※1」 |
| `.../NotesNumberPeriodStart` | 期首注記番号 | 前期の脚注 |
| `.../NotesNumberPeriodEnd` | 期末注記番号 | 当期の脚注 |

### 1.4 EDINET 固有の特性 (A-5 より)

- **arcrole は `fact-footnote` のみ**。XBRL 仕様で定義された `fact-explanatoryFact` は EDINET では使用しない
- **order 属性は使用されない** (GFM Rule 2.9.7 のオーバーライド)
- **J-GAAP の BS/PL でのみ使用**。IFRS セクションでは footnoteLink なし（個別部分の日本基準セクションのみ）
- 1 つの footnoteLink 内に複数の loc + footnote + arc が含まれる

### 1.5 既存基盤

parser.py が既に `link:footnoteLink` 要素を `RawFootnoteLink` として捕捉している:

```python
@dataclass(frozen=True, slots=True)
class RawFootnoteLink:
    role: str | None       # footnoteLink の xlink:role
    source_line: int | None
    xml: str               # footnoteLink 要素全体の XML 文字列
```

`ParsedXBRL.footnote_links` に `tuple[RawFootnoteLink, ...]` として格納済み。本 Lane はこの `xml` を再パースして構造化する。

Calculation / Presentation / Definition Linkbase と同じパースパターン（XML 文字列 → lxml → dataclass）を踏襲する。

---

## 2. ゴール

完了条件:

```python
from edinet.xbrl.linkbase.footnotes import parse_footnote_links, FootnoteMap, Footnote

# パース
footnote_map = parse_footnote_links(parsed.footnote_links)

# Fact ID から脚注取得
notes = footnote_map.get("IdFact1234")
# → tuple[Footnote, ...] or ()

assert isinstance(notes[0], Footnote)
assert notes[0].text == "※1 当事業年度の減損損失の認識について..."
assert notes[0].lang == "ja"

# 全脚注の列挙
all_notes = footnote_map.all_footnotes()
assert len(all_notes) > 0

# 脚注が存在するかチェック
assert footnote_map.has_footnotes("IdFact1234")
assert not footnote_map.has_footnotes("NonExistentFactId")
```

---

## 3. スコープ / 非スコープ

### 3.1 スコープ

| # | 内容 | 対応 |
|---|------|------|
| S1 | `RawFootnoteLink.xml` から footnoteLink をパース | `parse_footnote_links()` |
| S2 | Fact ID → 脚注テキストのマッピング構築 | `FootnoteMap` |
| S3 | 脚注の言語（`xml:lang`）の保持 | `Footnote.lang` |
| S4 | 脚注の role（`xlink:role`）の保持 | `Footnote.role` |
| S5 | 複数 footnoteLink にまたがる脚注の統合 | `parse_footnote_links()` |

### 3.2 非スコープ

| # | 内容 | 理由 |
|---|------|------|
| N1 | 脚注テキストの自然言語解析 | SCOPE.md: パイプラインの外側 |
| N2 | `fact-explanatoryFact` arcrole の対応 | EDINET では使用されない (A-5) |
| N3 | order 属性による脚注の順序保証 | EDINET では使用されない (GFM Rule 2.9.7) |
| N4 | IFRS セクションの脚注対応 | IFRS セクションには footnoteLink がない (A-5) |
| N5 | 脚注テキストの HTML クリーニング | Lane 1 の `clean_html()` を利用可能だが、本 Lane では raw text のまま提供 |

---

## 4. 実装計画

### 4.1 Footnote dataclass

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Footnote:
    """脚注。

    XBRL の ``link:footnote`` 要素から抽出した脚注情報。

    Attributes:
        label: xlink:label 属性値（アーク接続用識別子）。
        text: 脚注テキスト（例: ``"※1 当事業年度の…"``）。
        lang: xml:lang 属性値（例: ``"ja"``）。
        role: xlink:role 属性値。
    """
    label: str
    text: str
    lang: str
    role: str
```

### 4.2 FootnoteMap

```python
@dataclass(frozen=True, slots=True)
class FootnoteMap:
    """Fact ID → 脚注のマッピング。

    ``parse_footnote_links()`` の返り値。
    Fact の id 属性値をキーに、紐付けられた脚注を検索できる。

    Attributes:
        _index: Fact ID → Footnote タプルの辞書（arc で紐付けられたもののみ）。
        _all: XML に存在する全 Footnote のタプル（arc による紐付けの有無に関わらず
              収集。重複除去済み。frozen dataclass のデフォルト __eq__ による
              全フィールド一致で判定）。
    """
    _index: dict[str, tuple[Footnote, ...]]
    _all: tuple[Footnote, ...]

    def get(self, fact_id: str) -> tuple[Footnote, ...]:
        """Fact ID から脚注を取得する。

        Args:
            fact_id: Fact の id 属性値。

        Returns:
            紐付けられた Footnote のタプル。見つからなければ空タプル。
        """
        return self._index.get(fact_id, ())

    def has_footnotes(self, fact_id: str) -> bool:
        """Fact に脚注が存在するかを返す。

        Args:
            fact_id: Fact の id 属性値。
        """
        return fact_id in self._index

    def all_footnotes(self) -> tuple[Footnote, ...]:
        """全脚注を返す。"""
        return self._all

    @property
    def fact_ids(self) -> tuple[str, ...]:
        """脚注が紐付けられた Fact ID の一覧を返す。"""
        return tuple(self._index.keys())

    def __len__(self) -> int:
        """脚注が紐付けられた Fact の数を返す。"""
        return len(self._index)

    def __contains__(self, fact_id: object) -> bool:
        """Fact に脚注が存在するかの確認。"""
        return fact_id in self._index
```

### 4.3 parse_footnote_links()

```python
import logging
import warnings
from collections.abc import Sequence

from lxml import etree

from edinet.exceptions import EdinetParseError, EdinetWarning
from edinet.xbrl.parser import RawFootnoteLink
from edinet.xbrl._namespaces import NS_LINK, NS_XLINK, NS_XML

logger = logging.getLogger(__name__)

# Clark notation タグ名
_TAG_LOC = f"{{{NS_LINK}}}loc"
_TAG_FOOTNOTE = f"{{{NS_LINK}}}footnote"
_TAG_FOOTNOTEARC = f"{{{NS_LINK}}}footnoteArc"

_ATTR_HREF = f"{{{NS_XLINK}}}href"
_ATTR_LABEL = f"{{{NS_XLINK}}}label"
_ATTR_ROLE = f"{{{NS_XLINK}}}role"
_ATTR_FROM = f"{{{NS_XLINK}}}from"
_ATTR_TO = f"{{{NS_XLINK}}}to"
_ATTR_ARCROLE = f"{{{NS_XLINK}}}arcrole"
_ATTR_LANG = f"{{{NS_XML}}}lang"

_ARCROLE_FACT_FOOTNOTE = "http://www.xbrl.org/2003/arcrole/fact-footnote"


def parse_footnote_links(
    raw_links: Sequence[RawFootnoteLink],
) -> FootnoteMap:
    """RawFootnoteLink 群から FootnoteMap を構築する。

    各 RawFootnoteLink.xml を再パースし、loc / footnote / footnoteArc の
    3 要素を抽出して Fact ID → Footnote のマッピングを構築する。

    複数の footnoteLink にまたがる脚注は統合される（同一 Fact ID に対する
    脚注はタプルにまとめられる）。

    Args:
        raw_links: ParsedXBRL.footnote_links。

    Returns:
        構築された FootnoteMap。footnoteLink が空の場合は空の FootnoteMap を返す。

    Raises:
        EdinetParseError: XML パースに失敗した場合。
    """
```

**パースアルゴリズム**:

1. 各 `RawFootnoteLink.xml` を `etree.fromstring(raw.xml.encode("utf-8"))` でパース
   - `RawFootnoteLink.xml` は `str` 型（`_serialize_outer_xml()` の返り値）のため `bytes` に変換する
   - ルート要素が `footnoteLink` そのものになる。子要素を走査すればよい
2. `link:loc` 要素を走査 → `xlink:label` → `xlink:href` (Fact ID) の **1:N マッピング** を構築
   - `xlink:href` は `#IdFact1234` 形式。`#` を除去して Fact ID を取得
   - **重要**: XLink 仕様により、同一 `xlink:label` を持つ複数の loc が存在しうる
     （EDINET の実データでは `xlink:label="fact"` を共有する複数 loc が一般的。A-5 [F8]）
   - 型: `dict[str, list[str]]` (label → Fact ID リスト)
3. `link:footnote` 要素を走査 → `xlink:label` → `Footnote` のマッピング構築
   - テキストは `"".join(element.itertext())` で取得する（§5.3 参照）。`element.text` のみでは子要素内のテキストを取り逃すため `itertext()` が必須
   - 型: `dict[str, Footnote]` (label → Footnote)
   - **この dict の全値が `_all` の母集団となる**（arc による紐付けの有無に関わらず）
4. `link:footnoteArc` 要素を走査 → `xlink:from`(loc label) → `xlink:to`(footnote label) の紐付け
   - `xlink:arcrole` が `fact-footnote` であることを確認（それ以外は無視）
5. loc label → **全 Fact ID** → Footnote の間接参照を解決
   - 1 つの arc が from label に紐付く **全 Fact** を footnote に接続する
   - 結果: `dict[str, list[Footnote]]` (Fact ID → Footnote リスト)
6. 複数 footnoteLink の結果をマージ（同一 Fact ID のエントリは結合）
7. `_all` を構築する: step 3 で収集した全 footnote dict の values を集約し、`dict.fromkeys()` で重複除去してタプル化する
   - `_all` は **arc による紐付けの有無に関わらず、XML に存在する全脚注** を含む
   - 重複判定は frozen dataclass のデフォルト `__eq__`（全フィールド一致）による
8. ロギング: 各 footnoteLink の要素数を `logger.debug` で記録し、最終サマリーを `logger.info` で記録する（既存パーサーと同一パターン）

**エッジケース処理**:

- 不正な XML → `lxml.etree.XMLSyntaxError` を捕捉し `EdinetParseError` を送出（既存パターンと同一）
- `xlink:href` が `#` で始まらない場合 → `warnings.warn(EdinetWarning)` で警告を出して無視
- `xlink:from` / `xlink:to` が見つからない場合 → `warnings.warn(EdinetWarning)` で警告を出して無視
- `link:footnote` に `xlink:role` が欠落している場合、または空文字列の場合 → `warnings.warn(EdinetWarning)` で警告を出してスキップ（既存 calculation.py の missing role 処理と同一パターン。EDINET 実データでは常に明示されるが、防御的に処理する）。判定: `role = elem.get(_ATTR_ROLE)` → `if not role:` で `None` と `""` を同時にガード
- 空の footnote テキスト → `Footnote.text = ""`（除外しない）
- `xlink:href` が `#` のみ（Fact ID が空文字列になる） → `warnings.warn(EdinetWarning)` で警告を出して無視

---

## 5. 実装の注意点

### 5.1 既存パターンの踏襲

`calculation.py` および `definition.py` のパースパターンを踏襲する:

1. XML bytes → `etree.fromstring()`
2. Clark notation タグでの要素走査
3. `EdinetParseError` による構文エラー報告
4. 非致命的エラーは `warnings.warn(EdinetWarning)` + スキップ
5. `logger = logging.getLogger(__name__)` による運用ロギング（`logger.debug` で要素数、`logger.info` でパースサマリー）

**XLink 属性名のスタイル**: 既存パーサー（calculation.py, definition.py, presentation.py）は XLink 属性名をインライン f-string（`f"{{{NS_XLINK}}}role"`）で使用している。本モジュールではモジュールレベル定数（`_ATTR_ROLE = f"{{{NS_XLINK}}}role"`）として定義する。これは footnoteLink が loc/footnote/arc の 3 種の要素で同一属性を反復参照するため、可読性と DRY の観点から定数化が有利であるため。

ただし footnoteLink は linkbase ファイルではなく**インスタンス内に埋め込まれている**点が異なる。入力は `RawFootnoteLink.xml`（XML 文字列）であり、ファイルパスではない。

**関数シグネチャの意図的な逸脱**: 既存の `parse_calculation_linkbase(xml_bytes: bytes)` / `parse_definition_linkbase(xml_bytes: bytes)` は単一のリンクベースファイルを受け取るが、`parse_footnote_links()` は `Sequence[RawFootnoteLink]` を受け取る。これは footnoteLink がインスタンス内に複数埋め込まれており、parser.py が既に個別の `RawFootnoteLink` に分割済みであるため。この逸脱は意図的な設計判断である。

### 5.2 Fact ID の参照形式

`link:loc` の `xlink:href` 属性値は `#IdFact1234` のようにフラグメント識別子形式。先頭の `#` を除去して Fact ID とする。

parser.py が抽出した `RawFact.fact_id` と照合可能。`fact_id` が `None` の Fact には脚注を紐付けられないが、EDINET では通常全 Fact に id が付与される。

### 5.3 テキスト抽出

`link:footnote` 要素のテキストは `element.text` に入る場合と、子要素のテキストとして入る場合がある。`"".join(element.itertext())` で全テキストを取得するのが安全。

### 5.4 空の footnote_links

`ParsedXBRL.footnote_links` が空タプルの場合（IFRS filing 等）、空の `FootnoteMap` を返す。

---

## 6. テスト計画

### 6.1 テストファイル

`tests/test_xbrl/test_footnotes.py` に全テストを作成する。

### 6.2 テストフィクスチャ

`tests/fixtures/footnotes/` に以下のフィクスチャを作成:

| ファイル | 内容 |
|---------|------|
| `simple.xml` | 1 つの Fact に 1 つの脚注が紐付いた最小構造 |
| `multiple_facts.xml` | 複数の Fact にそれぞれ脚注が紐付いた構造 |
| `multi_footnotes_per_fact.xml` | 1 つの Fact に複数の脚注（※1, ※2）が紐付いた構造（`shared_footnote` の逆パターン） |
| `shared_footnote.xml` | 同一 label の複数 loc が 1 つの footnote を共有する構造（EDINET 実データの典型パターン: `xlink:label="fact"` を共有する複数 loc → 1 arc → 1 footnote） |
| `multiple_links.xml` | 複数の footnoteLink 要素がある構造 |
| `no_arcs.xml` | loc と footnote はあるが arc がない構造 |
| `empty.xml` | `link:footnoteLink` 要素はあるが子要素（loc/footnote/arc）がない構造 |
| `html_in_text.xml` | 脚注テキストに HTML タグ（`<br/>`, `<span>` 等）を含む構造（`itertext()` 検証用） |
| `malformed.xml` | 不正な XML（`EdinetParseError` 検証用） |

### 6.3 テストケース一覧（~27 件）

```python
class TestParseFootnoteLinks:
    def test_parse_single_footnote(self):
        """1 Fact : 1 脚注の基本パースが正しく動作する。"""

    def test_parse_multiple_facts(self):
        """複数 Fact への脚注がそれぞれ正しく紐付けられる。"""

    def test_parse_multi_footnotes_per_fact(self):
        """1 つの Fact に複数の脚注（※1, ※2）が紐付けられる。"""

    def test_parse_shared_footnote(self):
        """N 個の loc が同一 xlink:label を共有 → 1 arc → 1 footnote で、N 個の Fact ID 全てから脚注を取得できる。"""

    def test_parse_multiple_footnote_links(self):
        """複数の footnoteLink 要素の脚注が統合される。"""

    def test_parse_empty_sequence(self):
        """空のシーケンス（[]）で空の FootnoteMap が返る。"""

    def test_parse_empty_footnote_link(self):
        """子要素のない footnoteLink で空の FootnoteMap が返る。"""

    def test_parse_no_arcs(self):
        """arc がない footnoteLink では _index は空だが、all_footnotes() には脚注が含まれる。"""

    def test_footnote_text_extracted(self):
        """脚注テキストが正しく抽出される。"""

    def test_footnote_lang(self):
        """xml:lang 属性が正しく取得される。"""

    def test_footnote_role(self):
        """xlink:role 属性が正しく取得される。"""

    def test_href_fragment_parsing(self):
        """#IdFact1234 形式の href から Fact ID が正しく抽出される。"""

    def test_ignore_non_fact_footnote_arcrole(self):
        """fact-footnote 以外の arcrole は無視される。"""

    def test_malformed_xml_raises_parse_error(self):
        """不正な XML で EdinetParseError が発生する。"""

    def test_missing_footnote_role_warns(self):
        """link:footnote に xlink:role が欠落または空文字列の場合に EdinetWarning が発生しスキップされる。"""

    def test_href_fragment_only_hash(self):
        """xlink:href が '#' のみの場合に EdinetWarning が発生し無視される。"""

    def test_footnote_text_with_html_tags(self):
        """脚注テキストに HTML タグ（<br/>, <span> 等）が含まれる場合に itertext() で全テキストが抽出される。"""

    def test_same_fact_across_multiple_links(self):
        """同一 Fact ID が複数の footnoteLink にまたがって紐付けられた場合に脚注がマージされる。"""


class TestFootnoteMap:
    def test_get_existing(self):
        """存在する Fact ID で Footnote タプルが取得できる。"""

    def test_get_nonexistent(self):
        """存在しない Fact ID で空タプルが返る。"""

    def test_has_footnotes_true(self):
        """脚注がある Fact ID で True が返る。"""

    def test_has_footnotes_false(self):
        """脚注がない Fact ID で False が返る。"""

    def test_all_footnotes(self):
        """全脚注が取得できる。"""

    def test_all_footnotes_deduplication(self):
        """all_footnotes() が重複を除去する（frozen dataclass の __eq__ で判定）。"""

    def test_fact_ids(self):
        """脚注が紐付けられた Fact ID の一覧が取得できる。"""

    def test_len(self):
        """__len__ が脚注付き Fact 数を返す。"""

    def test_contains(self):
        """__contains__ が正しく動作する。"""
```

---

## 7. 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `src/edinet/xbrl/linkbase/footnotes.py` | 新規 | `Footnote`, `FootnoteMap`, `parse_footnote_links()` |
| `tests/test_xbrl/test_footnotes.py` | 新規 | ~27 テストケース |
| `tests/fixtures/footnotes/` | 新規 | 9 フィクスチャファイル |

### 変更行数見積もり

| ファイル | 行数 |
|---------|------|
| `footnotes.py` | ~230 行 |
| テスト | ~430 行 |
| フィクスチャ | ~280 行 |
| **合計** | **~940 行** |

---

## 8. 検証手順

1. `uv run pytest tests/test_xbrl/test_footnotes.py -v` で新規テスト全 PASS
2. `uv run pytest` で全テスト PASS（既存テスト破壊なし）
3. `uv run ruff check src/edinet/xbrl/linkbase/footnotes.py tests/test_xbrl/test_footnotes.py` でリント PASS
