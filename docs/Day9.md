# Day 9 — Fact 抽出パーサー（instance XBRL MVP）

## 0. 位置づけ

Day 9 は、Week 2 の最初の実装日として「XBRL 解析の入口」を作る日。  
Day 7.5 までで API/取得層（`documents`, `Filing.fetch()`, async 含む）は固まっているため、ここで `Filing.fetch()` が返す `(.xbrl path, bytes)` をそのまま消費する Fact 抽出パーサーを実装する。`parse_xbrl_facts()` は Day 9 では **instance XBRL 専用 API** として固定し、iXBRL は v0.2.0 で `parse_ixbrl_facts(bundle)` 系 API を別途追加する。

Day 9 完了時のマイルストーン:

```python
from edinet import documents
from edinet.xbrl.parser import parse_xbrl_facts

filing = documents("2025-06-18", doc_type="120")[0]
path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=path)

print(parsed.fact_count)
print(parsed.facts[0].concept_qname, parsed.facts[0].value_raw)
```

この時点では「Fact を漏れなく抽出し、最小メタデータを保持する」ことに集中し、Context の意味付け・期間判定・財務諸表組み立ては Day 10 以降で扱う。

---

## 1. 現在実装の確認結果（2026-02-24）

| ファイル | 現状 | Day 9 で必要な変更 |
|---|---|---|
| `src/edinet/xbrl/parser.py` | 1 行 docstring のみ | Fact 抽出ロジック本体を実装 |
| `src/edinet/xbrl/__init__.py` | 1 行 docstring のみ | parser の公開シンボルをエクスポート |
| `src/edinet/models/financial.py` | 1 行 docstring のみ | Day 9 では未着手（Day 10 以降） |
| `tests/test_xbrl/` | ディレクトリのみで空 | `test_parser.py` を新規追加 |
| `tests/fixtures/xbrl_fragments/` | 未作成 | `simple_pl.xbrl` 等の手書き fixture を追加 |
| `pyproject.toml` | marker は `slow`, `data_audit`, `large` のみ | Week2 冒頭方針に従い marker を正式拡張して反映（Day9 Done 条件） |
| `src/edinet/models/filing.py` | `fetch()/afetch()` が `(path, bytes)` を返す | Day 9 は parser 側でこの契約を利用（`Filing` 本体は原則変更しない） |
| `src/edinet/api/download.py` | `find_primary_xbrl_path()` 実装済み | Day 9 は前提として利用（修正しない） |

補足:
- 取得層はすでに `EdinetParseError` 契約を持っているため、parser も同じ例外体系に合わせる。
- 現時点で xbrl 系 `.pyi` は実質空。Day 9 の公開 API 変更後に stub 追従が必要。

---

## 2. Day 9 のゴール

1. `.xbrl` bytes から Fact 要素を汎用抽出する関数を実装する
2. concept 名・`contextRef`・`unitRef`・`decimals`・`xsi:nil`・`id` を保持できる最小データモデルを定義する
3. 特定 concept や特定 Context ID に依存しない（ハードコードしない）
4. Small/Unit（in-memory）+ Medium/Unit（fixture）で抽出契約を固定する
5. 実データ（1 filing）で手動スモーク確認を行い、Day 10 へ引き渡せる形にする

---

## 3. スコープ / 非スコープ

### 3.1 Day 9 のスコープ

- `xbrl/parser.py` の Fact 抽出実装
- parser が返す最小データ構造（`RawFact`, `ParsedXBRL` 相当）
- hand-written fixture (`tests/fixtures/xbrl_fragments/`)
- `tests/test_xbrl/test_parser.py`（Small/Unit + Medium/Unit）
- 必要最小限の公開エクスポート（`edinet.xbrl`）

### 3.2 Day 9 でやらないこと

- Context の意味解釈・期間分類（Day 10）
- TaxonomyResolver（Day 12）
- Fact → LineItem 変換（Day 13）
- PL/BS/CF 組み立て（Day 15）
- iXBRL (`.htm`) 直接パース（v0.2.0+。`parse_ixbrl_facts(bundle)` 系 API で対応）
- CSV 取得 API を使った代替導線の実装（K-3 で「完全代替不可」）

---

## 4. QA 反映方針（Day 9 に直結するもの）

| QA | Day 9 への反映 |
|---|---|
| K-2, P-1, B-1 | v0.1.0 は EDINET 自動生成 `.xbrl`（instance）を対象にする。`find_primary_xbrl_path()` は現状維持 |
| K-3 | CSV は補助的。Fact 抽出の本線は XBRL parser で継続 |
| H-10 | 入力は `bytes` を正とし、`Filing.fetch()` の返り値契約に合わせる |
| H-11 | ブートストラップ順のうち Day 9 は Step1（XML parse）と Step6（Fact 抽出）の最小実装 |
| A-3, A-4, A-8 | `contextRef`, `unitRef`, `decimals`, `xsi:nil`, `id` を抽出対象に含める |
| A-7 | duplicate Fact は Day 9 では削除しない。出現順で保持 |
| A-2 | Context ID 文字列パターンへ依存しない（Fact 側は `contextRef` 参照のみ保持） |
| H-2 | prefix ではなく namespace URI ベースで concept を識別する |
| H-4, H-4b | UTF-8 前提。parser は bytes 入力で BOM 混在に耐える。DOCTYPE/XXE は防御的設定 |
| H-5 | 13MB 級でも `etree.parse()` で十分。`iterparse` は採用しない |
| K-1 | `has_xbrl` は前段フィルタとして信頼可能（Day 9 parser 側では未判定） |

---

## 5. 実装対象ファイル

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/xbrl/parser.py` | 実装 | Fact 抽出ロジック + 最小データモデル |
| `src/edinet/xbrl/__init__.py` | 追記 | `parse_xbrl_facts` のみ再エクスポート（`RawFact`/`ParsedXBRL` は再エクスポートしない） |
| `tests/fixtures/xbrl_fragments/simple_pl.xbrl` | 新規 | 基本+主要エッジケース集約 fixture（`-6`, `INF`, nil, text, empty, xml:lang, IFRS namespace を同梱） |
| `tests/fixtures/xbrl_fragments/invalid_xml.xbrl` | 新規 | 壊れた XML の失敗系検証 |
| `tests/fixtures/xbrl_fragments/non_xbrl_root.xbrl` | 新規 | ルート要素が `xbrli:xbrl` でない失敗系検証 |
| `tests/test_xbrl/test_parser.py` | 新規 | Small/Unit + Medium/Unit テスト |
| `pyproject.toml` | 追記（必須） | Week2 marker 体系の導入 |
| `stubs/edinet/xbrl/parser.pyi` | 追記 | parser 公開型の追従 |
| `stubs/edinet/xbrl/__init__.pyi` | 追記 | エクスポート追従 |

---

## 6. parser 設計詳細

### 6.1 公開 I/F（Day 9 版）

```python
@dataclass(frozen=True, slots=True)
class RawFact:
    concept_qname: str              # "{namespace}local"（Clark notation）
    namespace_uri: str
    local_name: str
    context_ref: str
    unit_ref: str | None
    decimals: int | Literal["INF"] | None
    value_raw: str | None           # xsi:nil の場合は None
    is_nil: bool
    fact_id: str | None
    xml_lang: str | None
    order: int                      # 文書出現順

@dataclass(frozen=True, slots=True)
class ParsedXBRL:
    source_path: str | None
    source_format: Literal["instance"]  # Day 9 時点では instance のみ
    facts: tuple[RawFact, ...]

    @property
    def fact_count(self) -> int: ...

def parse_xbrl_facts(
    xbrl_bytes: bytes,
    *,
    source_path: str | None = None,
) -> ParsedXBRL: ...
```

方針:
- Day 10 で `models.financial.Fact` が入るまで、parser 内の軽量 dataclass でつなぐ。
- 値の厳密な型変換（`Decimal`, `date`, `bool`）は Day 10/13 へ先送りし、Day 9 は「抽出の正しさ」を優先。

### 6.2 抽出ルール

1. `lxml.etree.parse(BytesIO(xbrl_bytes), parser=XMLParser(...))` で DOM 構築
2. ルートが XBRL Instance（`{http://www.xbrl.org/2003/instance}xbrl`）であることを検証（それ以外は `EdinetParseError`）
3. Fact 候補は「**ルート直下の子要素**」から抽出する（深い階層は見に行かない）
4. ルート直下の子要素のうち、`xbrli:*` / `link:*` を除外し、かつ `contextRef` 属性を持つ要素を Fact とみなす
5. 候補要素ごとに `QName` 分解し、namespace URI と local name を保存
6. `xsi:nil="true"` 判定時は `value_raw=None`, `is_nil=True`
7. `unitRef` が無い Fact（テキスト系）を許容
8. `decimals` は `None`/`INF`/整数の3系統で保持（不正値は `EdinetParseError`）。負の整数（例: `-6`）を正常系として扱う。`INF` は `Literal["INF"]` として保持する
9. 空タグ Fact（`<tag contextRef="..."></tag>`）は `value_raw=None`, `is_nil=False` として扱う（`xsi:nil` と区別）
10. `id` と `xml:lang` は optional で保持（Day 9 では参照しないが落とさない）
11. 同一 key の duplicate Fact は削除しない（A-7 に合わせて出現順保持）
12. Fact が 0 件でもエラーにしない（`facts=()` で返す）

### 6.3 例外契約

- `ValueError` を外に漏らさず、公開境界では `EdinetParseError` に正規化
- `lxml.etree.XMLSyntaxError` は `EdinetParseError` へ変換（`raise ... from exc`）
- bare except は使わない
- エラーメッセージ契約:
  - `source_path`（与えられていれば）を含める
  - 不正属性が原因の場合は「属性名」と「原因値」を含める（例: `decimals='abc'`）
  - 可能なら対象 concept または root tag を含める

### 6.4 v0.2.0 拡張方針（iXBRL）

- Day 9 の `parse_xbrl_facts()` は instance 専用 API として固定する
- iXBRL は別 API で追加する:

```python
def parse_ixbrl_facts(bundle: XbrlBundle, *, source_path: str | None = None) -> ParsedXBRL: ...
```

- これにより、`bytes` 単一入力（instance）と IXDS 複数ファイル入力（iXBRL）を無理に同居させず、I/F を単純に保てる

### 6.5 セキュリティ / 安定性設定

`XMLParser` 設定（Day 9 推奨）:
- `resolve_entities=False`
- `no_network=True`
- `recover=False`

理由:
- H-4b で DOCTYPE/CDATA 非使用だが、防御的に XXE 面を閉じる。
- UTF-8 BOM は lxml 側で処理可能だが、テストでは `simple_pl.xbrl` の bytes 先頭に BOM を付与した入力を作って回帰確認する。

### 6.6 公開エクスポート方針

- `edinet.xbrl`（`src/edinet/xbrl/__init__.py`）は `parse_xbrl_facts` のみを公開する
- `RawFact` / `ParsedXBRL` は `edinet.xbrl.parser` からの明示 import でのみ利用可能とし、トップレベル再エクスポートしない
- Day 10 で `models.financial.Fact` に移行する際、公開表面の変化を最小化する

---

## 7. テスト計画（size/scope）

### 7.1 追加テストケース（P0: Day 9 必須）

1. `test_parse_xbrl_extracts_all_facts`
2. `test_parse_xbrl_uses_root_children_only_for_fact_detection`
3. `test_parse_xbrl_parses_decimals_negative_and_inf_literal`（`-6` と `INF` を明示的に検証）
4. `test_parse_xbrl_handles_xsi_nil_fact`
5. `test_parse_xbrl_handles_empty_text_fact_as_none_non_nil`
6. `test_parse_xbrl_raises_parse_error_on_invalid_xml`
7. `test_parse_xbrl_rejects_non_xbrl_root`
8. `test_parse_xbrl_error_message_includes_source_path`

### 7.2 追加テストケース（P1: Day 9 推奨、時間不足なら Day 10 冒頭に繰越可）

1. `test_parse_xbrl_handles_text_fact_without_unitref`
2. `test_parse_xbrl_preserves_duplicate_facts`
3. `test_parse_xbrl_is_prefix_independent`（prefix 変更 fixture）
4. `test_parse_xbrl_rejects_invalid_decimals_with_attribute_context`
5. `test_parse_xbrl_keeps_ifrs_namespace_facts_without_jppfs_assumption`
6. `test_parse_xbrl_returns_empty_tuple_when_no_fact`
7. `test_parse_xbrl_handles_utf8_bom`（テスト内で BOM 付き bytes を生成）

### 7.3 marker 方針

Week2 冒頭方針（`docs/MEMO.md`）に合わせ、Day 9 では以下で分類する:
- `small` + `unit`: `etree.fromstring()` など in-memory 入力のみ
- `medium` + `unit`: `tests/fixtures/xbrl_fragments/*` を読むテスト
- `large`: 実 API を叩く既存 smoke テスト（現状維持）

注意:
- fixture ファイル読み込みテストは `small` にしない（MEMO の定義と整合）
- `integration` / `e2e` marker は Day 9 時点で **定義だけ追加** し、利用は Day 10+ から開始する
- Day 9 の Done 条件に `pyproject.toml` の marker 定義完了を含める（任意にしない）

### 7.4 fixture ヘルパー方針（DX）

`tests/conftest.py` か `tests/test_xbrl/conftest.py` に fixture 読み込みヘルパーを置いて重複を避ける。

```python
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "xbrl_fragments"

def load_xbrl_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()
```

---

## 8. 当日の作業手順（チェックリスト）

### Phase 1: テスト土台

1. `tests/fixtures/xbrl_fragments/` を作成
2. `simple_pl.xbrl`（主要エッジケース集約）+ `invalid_xml.xbrl` + `non_xbrl_root.xbrl` の 3 file を先に作る
3. `tests/test_xbrl/test_parser.py` で P0 テスト（§7.1）を先に固定する
4. fixture 共通ヘルパー `load_xbrl_bytes()` を追加する
5. `pyproject.toml` に `small` / `medium` / `unit` / `integration` / `e2e` marker を追加

### Phase 2: parser 実装

1. `parser.py` に dataclass と `parse_xbrl_facts()` を実装
2. ルート直下抽出 + `xbrli:*` / `link:*` 除外 + `contextRef` 条件を実装
3. 例外正規化（`EdinetParseError`）を実装
4. エラーメッセージ契約（`source_path`、属性名、原因値）を実装

### Phase 3: 公開導線・型

1. `xbrl/__init__.py` を更新
2. `.pyi` を更新（必要なら `stubgen` 再生成）

### Phase 4: 検証

1. `uv run pytest tests/test_xbrl/test_parser.py`
2. `uv run pytest`（既存回帰）
3. `uv run ruff check src tests`
4. 手動スモーク: 実 filing 1件で `fact_count` と数件の抽出結果を確認
5. P1 テスト（§7.2）を追加し、時間不足なら Day 10 冒頭へ繰越

---

## 9. 受け入れ基準（Done の定義）

- `parse_xbrl_facts()` は Fact 0 件を許容し、空の場合は `facts=()` を返す（例外にしない）
- 既知 fixture（`simple_pl.xbrl` 等）と実 filing 1件では `fact_count > 0` を確認できる
- `contextRef` / `unitRef` / `decimals` / `xsi:nil` / `id` を欠落なく保持できる
- concept 判定が namespace URI ベースで実装されている（prefix 非依存）
- Fact 抽出が「ルート直下 + `xbrli:*`/`link:*` 除外 + `contextRef` 条件」で実装されている
- duplicate Fact を消さず出現順で保持する
- 異常 XML で `EdinetParseError` を返す
- 不正属性エラー時に `source_path` / 属性名 / 原因値を含むメッセージを返す
- `pyproject.toml` に Day 9 で使う marker（`small`, `medium`, `unit`, `integration`, `e2e`）が定義済み
- P0 テスト（§7.1）が全て pass
- P1 テスト（§7.2）は同日完了が望ましい。未完の場合は Day 10 冒頭で完了させる
- 既存テストスイートが回帰なし
- ruff で警告なし
- `PLAN.LIVING.md` の parser I/F 記述が Day 9 方針（instance 専用 + iXBRL 別 API）に更新済み

---

## 10. 実行コマンド（Day 9）

```bash
uv run pytest tests/test_xbrl/test_parser.py
uv run pytest
uv run ruff check src tests
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 11. Day 10 への引き継ぎ

Day 9 完了後、Day 10 は以下を前提に着手する:

1. parser が `RawFact` を安定供給できる
2. Day 10 は Context/Unit 抽出を追加し、`context_ref` を実体解決する
3. `models/financial.py` に `Fact`, `Period` を導入し、Day 9 の dataclass から置換または変換する
4. 当期/前期 ID 文字列に依存せず period 値（`startDate/endDate/instant`）で分類する
5. Day 9 の `RawFact` は暫定モデルのため、Day 10 で `models.financial.Fact` へ移行する際は変換アダプタを維持し、呼び出し側の破壊的変更を避ける
6. iXBRL 対応は `parse_xbrl_facts()` を拡張せず、`parse_ixbrl_facts(bundle)` 系 API を別追加する
7. Day 10 の Context/Unit は **xbrl_bytes を再パース** して抽出する（Day 9 では `raw_contexts` を保持しない）
