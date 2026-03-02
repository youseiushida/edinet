# Day 7 — 振り返り + テスト（公開契約の固定）

## 0. 位置づけ

Day 7 は「Week 1 の実装を止血して、Week 2 に安全に入るための契約固定日」。

Day 6 までで `edinet.documents()` と `Filing.fetch()` は動作しており、単体テストも通っている。
一方で `docs/MEMO.md` にある通り、**欠損行の扱い（skip か error か）** と **Large テスト運用** が未確定のままなので、ここを明文化して固定する。

---

## 1. 現在実装の確認結果（2026-02-18）

実コード・テストを確認した結果、Day 7 の論点は次の通り。

### 1.1 品質ゲートの現状

- `uv run pytest` は **227 passed**（約37秒）
- `uv run ruff check src tests` は **All checks passed**
- 現状の mainline は壊れていない

### 1.2 `documents()` の欠損行契約

- `src/edinet/public_api.py` は、フィルタ未指定時に `results` の壊れ行で `EdinetParseError` を返す strict 寄り実装
- `doc_type` / `edinet_code` 指定時は raw 先絞りが入るため、同じ日付でも呼び方次第で成功/失敗体験が変わる
- `docs/MEMO.md` の Day7 持ち越し事項（欠損行の公開契約）が未解決

### 1.3 テスト運用（size/scope）の不足

- `pyproject.toml` の marker は `slow`, `data_audit` のみ
- `pytest.mark.large` は未導入
- Plan の Day7 要件「Large テストを分離し、デフォルト skip」と未整合
- `tests/` は unit 中心で、外部 API / 実 ZIP を使う test tier が明確に分離されていない

---

## 2. Day 7 のゴール

1. `documents()` の欠損行契約を公開 API として固定する
2. Large テスト 2-3 件を追加し、通常テストから分離する
3. `large` marker を導入し、デフォルト実行から除外する
4. Day8 以降に持ち越す項目（async, taxonomy 本実装, marker 体系の本格整備）を明示して境界を守る

---

## 3. スコープ / 非スコープ

### 3.1 Day 7 のスコープ

- `documents()` の invalid row 処理方針（`error` / `skip`）確定
- 例外契約・warning 契約の明文化
- Large テスト導入（実 API / 実 ZIP を使う最小 smoke）
- `large` marker の追加と実行導線整備
- ドキュメント更新（`docs/Day7.md`, `docs/MEMO.md`）

### 3.2 Day 7 でやらないこと

- XBRL パーサー本実装（Day 9 以降）
- TaxonomyResolver 実装（Day 12）
- async API 追加（Day8 仕様読解後に再検討）
- 証券コード→EDINETコード自動変換の拡張
- `small` / `medium` / `unit` / `integration` / `e2e` marker の導入（Week2 冒頭で整備）

---

## 4. 実装対象ファイル（今日触る候補）

| ファイル | 変更種別 | 目的 |
|---|---|---|
| `src/edinet/public_api.py` | 追記 | `documents()` の invalid row 契約（`on_invalid`） |
| `stubs/edinet/public_api.pyi` | 同時追記 | 公開シグネチャ追従（実装と同時に更新） |
| `src/edinet/__init__.py` | 必要時のみ | 公開 API export 追従確認 |
| `tests/test_api/test_public_api.py` | 追記 | `on_invalid` の挙動テスト |
| `tests/test_large/test_documents_smoke.py` | 新規 | 実 API を使う Large smoke |
| `tests/test_large/test_filing_fetch_smoke.py` | 新規（任意） | `Filing.fetch()` 実 ZIP smoke |
| `tests/test_large/conftest.py` | 新規 | Large 実行条件のガード（APIキー未設定時 skip） |
| `tests/conftest.py` | 追記（必要時） | Large 用 fixture 追加 |
| `pyproject.toml` | 追記 | `large` marker 定義とデフォルト実行方針 |
| `docs/MEMO.md` | 追記 | Day7 の決定事項を差分記録 |
| `docs/Day7.md` | 本書 | 当日タスクと完了条件 |

---

## 5. 仕様固定（Day7 で決めるべきこと）

### 5.1 `documents()` の欠損行契約

#### デフォルト `skip` の根拠

実データ（2025-06-26）で 1845 件中 27 件が `submitDateTime=None` であり、`edinet.documents("2025-06-26")` と書いただけで初見ユーザーが `EdinetParseError` を食らう。ディファクトスタンダードを目指すライブラリとして初回体験で例外が飛ぶのは致命的（edinet-tools の `FileNotFoundError` と同じ轍）。pandas の `errors="coerce"` / `on_bad_lines="warn"` と同じ思想で、壊れた行はライブラリの責任範囲外。

#### 引数仕様

- 新引数: `on_invalid: Literal["skip", "error"] = "skip"`
- 既定値は **`skip`**（利用者を巻き込まない）
- `error` は「全行の健全性を保証したい」上級ユースケース向け

#### 2つの失敗モードの区別

欠損行の失敗は 2 種類あり、`on_invalid` は両方を統一的に制御する:

| 失敗モード | 内容 | 発生箇所 |
|---|---|---|
| **(A) 行が dict でない** | API レスポンスの `results` 要素が非 dict | `_prepare_response_for_filing_parse()` |
| **(B) dict だが Filing 変換に失敗** | `submitDateTime=None` 等で `from_api_response()` が例外 | `Filing.from_api_list()` → `from_api_response()` |

現行実装ではフィルタ有無で (A) の扱いが異なる（フィルタ有→黙殺、フィルタ無→`EdinetParseError`）が、Day7 で `on_invalid` を導入し **フィルタ有無に関係なく同じ契約** を適用する。

#### `skip` の挙動

- (A)(B) いずれの場合も、該当行を除外して変換成功分のみ返す
- `warnings.warn(..., EdinetWarning, stacklevel=2)` でスキップ件数と代表 `docID` を通知
  - warning カテゴリに `EdinetWarning` を使うことで `warnings.filterwarnings("ignore", category=EdinetWarning)` による制御が可能
- 返り値型 `list[Filing]` は変更しない（破壊的変更を避ける）

#### `error` の挙動

- (A)(B) いずれの場合も、対象行に 1 件でも変換不能があれば `EdinetParseError`
- 原因追跡のため `raise ... from exc` を維持
- **エラーメッセージにアクション誘導を含める**:
  ```
  documents(2025-06-26): Filing変換に失敗 (docID=S100XXXX).
  on_invalid='skip' を指定すると不正行をスキップできます。
  ```

#### 整合性ルール

- フィルタ有無で「壊れ行判定の対象」がぶれないよう、**必ずフィルタ後集合に対して同じ契約**を適用
- これにより「同じ日付で呼び方により挙動が変わる」問題を収束させる

### 5.2 テスト marker（Day7 の最小導入）

Day7 では **`large` marker のみ追加**する。既存の `slow` / `data_audit` はそのまま残す。

- 新規の実 API テストに `@pytest.mark.large` を付与
- `addopts = "-m 'not large'"` でデフォルト除外
- `small` / `medium` / `unit` / `integration` / `e2e` は **Week2 冒頭（Day8 or Day9）で正式導入**する（§9 参照）
  - 理由: Week1 のテストは実質ほぼ全部 small/unit であり、ここに marker を貼っても情報量がゼロ。Week2 で parser が入ると medium（ローカルファイル I/O）と integration（複数モジュール結合）が初めて区別に意味を持つ

### 5.3 Large テスト（2-3件）

テスト日付: **`2025-01-15`（水曜日）** — 十分に古く、データが安定しており、平日のため API レスポンスがある。

候補:

1. `test_documents_real_api_smoke`
   `edinet.documents("2025-01-15")` が `list` を返し、最小項目が壊れていないこと

2. `test_documents_with_filter_smoke`
   `doc_type="120"` などでフィルタ系導線が実データで通ること

3. `test_filing_fetch_smoke`（任意）
   実在 `doc_id` で `fetch()` が `(path, bytes)` を返し、`.xbrl` が取得できること

実行条件:

- `EDINET_API_KEY` 未設定なら `pytest.skip`
- ネットワーク依存のためデフォルトでは実行しない（`addopts` で除外）
- 各テストに明示的な `timeout` を設定し、ネットワーク障害時のハングを防止

配置: `tests/test_large/` ディレクトリにまとめる（size による分類軸を一貫させるため、scope 別ディレクトリには混ぜない）

---

## 6. 当日の作業手順（チェックリスト）

依存関係を考慮した順序:

**Phase 1: インフラ整備**
1. `pyproject.toml` に `large` marker を追加し、`addopts = "-m 'not large'"` を設定
2. `tests/test_large/` ディレクトリと `conftest.py`（API キーガード）を作成

**Phase 2: `on_invalid` 実装（本丸）**
3. `public_api.documents()` に `on_invalid` 引数を追加（失敗モード A/B の両方を統一的に制御）
4. `skip` / `error` の分岐実装: `EdinetWarning` による警告、エラーメッセージへのアクション誘導
5. `stubs/edinet/public_api.pyi` を**同時に更新**（後回しにしない）
6. `tests/test_api/test_public_api.py` に `on_invalid` テストを追加

**Phase 3: Large テスト**
7. `tests/test_large/test_documents_smoke.py` を追加し `@pytest.mark.large` を付与
8. （任意）`tests/test_large/test_filing_fetch_smoke.py` を追加

**Phase 4: 検証 + ドキュメント**
9. `uv run pytest`（通常）と `uv run ruff check src tests` を実行
10. `EDINET_API_KEY` がある環境で `uv run pytest -m large` を確認
11. `docs/MEMO.md` に Day7 決定事項を追記

---

## 7. 受け入れ基準（Done の定義）

- `documents()` の欠損行契約が docstring / stub / test で一致
- `on_invalid="skip"` と `on_invalid="error"` の両方に回帰テストがある
- `on_invalid="skip"` 時の warning に `EdinetWarning` カテゴリが使われている
- `on_invalid="error"` 時のエラーメッセージに `on_invalid='skip'` の案内が含まれている
- `pytest` デフォルト実行で Large が混入しない
- `pytest -m large` で少なくとも 2 件の smoke が走る（条件未充足時は skip 明示）
- `uv run ruff check src tests` が All checks passed
- `docs/MEMO.md` に「なぜその契約にしたか」が記録されている

---

## 8. コマンド運用（Day7 時点）

通常開発（Large 除外）:

```bash
uv run pytest
uv run ruff check src tests
```

Large のみ:

```bash
uv run pytest -m large
```

stub 更新が必要な変更をした場合:

```bash
uv run stubgen src/edinet --include-docstrings -o stubs
```

---

## 9. Day8 への引き継ぎメモ

Day7 完了後に Day8 へ渡す前提:

- 同期公開 API の契約（例外・欠損行・テスト tier）が固定済み
- Week2 は XBRL 仕様読解に集中できる
- async 化は「同期契約固定後」に判断する（Day9 着手前に再評価）

### Week2 冒頭で対応: テスト marker 体系の本格整備

Day7 では `large` のみ導入したが、Week2 で parser が入ると size/scope の区別が実質的に必要になる:

| テスト例 | size | scope | 理由 |
|---|---|---|---|
| `parse_fact(etree.fromstring(xml_str))` | small | unit | メモリ上の文字列、I/O なし |
| `TaxonomyResolver(fixture_path)` | medium | unit | ローカルファイル読み込み |
| fixture の `.xbrl` を丸ごとパース | medium | integration | 複数モジュール結合 + ファイルI/O |
| 実 ZIP → パース → Statement | large | e2e | ネットワーク + 全レイヤー |

**Day8 or Day9 冒頭** で以下を実施する:

1. `pyproject.toml` に `small` / `medium` / `large` + `unit` / `integration` / `e2e` を正式定義
2. `conftest.py` にヘルパー（fixture path の解決等）追加
3. **「新規テストには必ず size marker を付ける」** ルールを `MEMO.md` に明記
4. 既存 Week1 テストへの遡及適用は **やらない**（全部 small/unit なので情報量ゼロ）
