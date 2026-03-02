実際の実装中に起きたPLAN.mdの不整合や懸念点を記録する。

## Day 4

- **書類種別コードの情報源**:
  - `PLAN.md` では「様式コードリスト ESE140327.xlsx」を参照するとしていたが、これは誤り。`ESE140327.xlsx` は提出時に使用する「様式コード (formCode)」の定義リストであり、API で取得できる「書類種別コード (docTypeCode)」とは体系が異なる。
  - 正しい情報源は **EDINET API 仕様書 (ESE140206.pdf)** であるため、Day 4 の実装時にはこちらを使用した。

- **例外と警告クラスの配置場所**:
  - `EdinetWarning` や `EdinetError` などは `doc_types.py` や `_config.py` に散在させるのではなく、**`src/edinet/exceptions.py`** を新規作成してそこに集約すべきという方針に変更。
  - これは PLAN.md に記述がなかったが、実装時に修正を行う（ユーザーにて修正予定）。

- **コード定義の自動生成と手動管理の方針**:
  - **`DocType` (書類種別コード)**: API 仕様書 (ESE140206.pdf) に従い、信頼性のため **手動定義** とする（Day 4）。
  - **`OrdinanceCode` (府令コード)**: 件数が少なく（6件）、かつ PDF 記載のため、**手動定義** とする。
  - **`EdinetCode` (EDINETコード)、`FormCode` (様式コード)、`FundCode` (ファンドコード)**:
    - 定義数が多く更新頻度もあるため、**メタプログラミング（スクリプトによる自動生成）** を採用する。
    - **生成フロー**:
      1. ユーザーが公式サイトから定義ファイル（CSV/Excel）をダウンロードし、ローカル（`data/source/` 等）に配置する。
      2. スクリプトがそのファイルを読み取り、`src/edinet/models/*.py` を生成する。
      3. 自動ダウンロード・解凍は行わない（URL変更・環境依存のリスク低減）。
    - 生成されたファイルには「自動生成である旨のコメント」を冒頭に付与し、Git 管理する。
  - この自動生成タスクは Day 4 の主要スコープ外とし、別途（Day 4.5 や Day 6以降）実施する。

- **取り下げ済み書類等のフィールド欠損について**:
  - 実データ検証（2026-02-06分）において、`doc_id=S100XJNI` (`withdrawal_status=1`, 取り下げ済み) のレコードで、`docTypeCode`, `ordinanceCode`, `formCode`, `filerName`, `docDescription` が `None` となるケースを確認した（368件中1件）。
  - これらは当初必須フィールド (`str`) として定義していたが、実態に合わせて `Optional[str]` (`str | None`) に変更した。API 仕様書上は必須に見えても、ステータスによっては主要フィールドすら欠損しうる点に注意が必要。

## Day 5

- **例外型の安定性（公開 API 契約）**:
  - Day5 の ZIP ヘルパー（`list_zip_members`, `find_primary_xbrl_path`, `extract_zip_member`, `extract_primary_xbrl`）では、入力不正・ZIP 不正は `ValueError` に統一する。
  - 特に `zipfile` 由来の低レベル例外（`BadZipFile`, `zlib.error` など）がそのまま外部へ漏れないようにし、利用者が例外型で安定的にハンドリングできる状態を維持する。

- **原因追跡の維持（デバッグ性）**:
  - 低レベル例外を `ValueError` に正規化する際は必ず `raise ValueError(...) from exc` とし、`__cause__` を保持する。
  - これにより公開契約を守りつつ、保守時には根本原因（CRC 破損、解凍失敗等）を追跡できる。

- **Day5 -> Day6 の境界方針**:
- Day5 の ZIP ヘルパーは `ValueError` 契約を維持し、`download_document()` は通信層失敗を `EdinetError` として透過する。
- Day6 の `Filing.fetch()` 境界で、`download_document()` 由来 ZIP の解析 `ValueError` を `EdinetAPIError` へ正規化する。
- 正規化時も `raise ... from exc` を維持し、公開契約の安定性と原因追跡性を両立させる。

## Day 6

- **最終目標（PLAN）と当日実装スコープの切り分け**:
  - Day6 実装では `Company(edinet_code="...")` を正として採用し、`Company("7203")` の自動変換は入れなかった。
  - 理由は Day6 仕様で「証券コード→edinet_code 変換は非スコープ」と明記されているため。
  - `PLAN.md` を最終目標として維持する運用は妥当で、実装時の制約差分は `MEMO.md` 側で管理するのが安全。

- **`edinet_code.py` で「できること / まだ無いこと」**:
  - 現在の公開関数は `get_edinet_code(code)`（edinet_code -> エントリ）であり、`sec_code -> edinet_code` の公開関数は未実装。
  - テーブルには `sec_code` が含まれるため変換機能の実装自体は可能。
  - 実データ確認時点では `sec_code` / 4桁 ticker の重複は見つからなかったが、将来データ更新で衝突し得るため「一意前提」の固定は避けるべき。

- **例外契約の整理（Day5 との接続）**:
  - Day6 で `EdinetParseError` を追加し、`Filing.fetch()` 境界で ZIP 解析失敗・primary 不在・`download_document()` 由来 `ValueError` を `EdinetParseError` に正規化した。
  - `download_document()` 由来の `EdinetError` / `EdinetAPIError` はラップせず透過し、通信/API 障害と解析障害を型で分離した。
  - Day5 メモにある「`raise ... from exc` で原因追跡を保持する」方針は維持している。

- **公開 `documents()` の契約強化**:
  - 公開 API は `type=2` 固定で `include_details` を受けない設計にし、`list[Filing]` 契約を単純化した。
  - `metadata.resultset.count` と `results` 件数の一致を検証し、外部レスポンス異常を `EdinetParseError` で fail-fast するようにした。
  - `doc_type` / `edinet_code` 指定時は raw JSON を先絞りしてから `Filing` 化し、非対象の壊れ行で全体失敗しないようにした。

- **実データゆらぎへの対応継続**:
  - 取り下げ済み（`withdrawalStatus=1`）レコードで主要項目が `None` になるケースを引き続き許容する。

- **追加の実データゆらぎ（2026-02-18 確認）**:
  - `2025-06-26` の `documents(type=2)` 実データで、`submitDateTime=None` の行を 27 件確認した（総件数 1845）。
  - 当該行は `docTypeCode=None`, `filerName=None`, `edinetCode=None` など主要項目が同時に欠損しているケースがあった。
  - 既存実装では `Filing.from_api_list()` 内で `datetime.strptime(None, ...)` が発生し `TypeError` がそのまま外に漏れていたため、`TypeError` も `ValueError` へ正規化するよう修正した。
  - 手動確認スクリプト `src/scratch.py` の Day4 では、`submitDateTime` 欠損行を事前に除外してから `Filing.from_api_list()` に渡すよう変更した（スキップ件数を表示）。

- **Day7 持ち越し（欠損行の公開契約）**:
  - 現在の `edinet.documents()` は、非フィルタ取得時に壊れ行を 1 件でも含むと日次全体を `EdinetParseError` で失敗させる（strict fail-fast）。
  - 一方で `doc_type` / `edinet_code` を指定した場合は raw 先絞りの影響で成功しうるため、同じ日付でも呼び方で体験がぶれる。
  - Day7 で「欠損行を `skip` するか、`error` で落とすか」を公開 API 契約として明文化する（必要なら `on_invalid='skip'|'error'` 相当を追加）。
  - `skip` を採用する場合は、戻り値またはログで「スキップ件数・代表 doc_id」を利用者に返す設計を併せて決める。

- **Day7 以降の async 化タイミング（持ち越しメモ）**:
  - 取得レイヤ（`documents` / `download`）は大量同時処理の恩恵が大きいため、将来的な async 化の価値は高い。
  - ただし Day6 時点では欠損行契約が未確定のため、先に Day7 で同期 API 契約（欠損行・例外・フィルタ）を固定する。
  - 実施タイミングは「Day8 の仕様読解後、Day9 着手前」が最適。XBRL 解析（Day9 以降）と同時に transport 層を変更すると切り分けが難しくなるため。
  - 方針は「非破壊追加」: 既存 sync API は維持し、`adocuments` / `aget_documents` / `adownload_document` を追加して段階移行する。
  - 着手条件（目安）: 日付レンジ大量取得、複数企業並列収集、収集時間が運用上のボトルネックになっていること。

- **今後の懸念 / 提案**:
  - 証券コード入力を正式サポートする場合は、`resolve_edinet_code_from_sec_code()` 相当を追加し、未検出・複数候補・非上場の扱いを先に契約化する。
  - 変換機能を `edinet_code.py` ベースで実装する場合、参照データの更新タイミング（どの CSV 版を前提にするか）を仕様として明示する必要がある。

- **追加メモ（実装中に判明した運用上の注意）**:
  - `edinet.models.edinet_code` は巨大な自動生成モジュールであるため、証券コード変換を `Company(...)` 初期化時に毎回素直に走らせると import/検索コストが効きやすい。逆引きが必要なら、生成時に逆引きテーブルを同梱するか、初回のみ lazy にキャッシュ構築する設計が望ましい。
  - `PLAN.md` の機械置換は Mermaid 記法を壊しやすい（例: 文字列中の `"` の入れ子）。一括置換を使う場合は、置換後に Mermaid ブロックを目視確認する手順を明示しておく方が安全。

- **公開 API 層分離と import-time 回帰対応（2026-02-17 追記）**:
  - `src/edinet/__init__.py` に業務ロジック（`documents()` 本体）を置くと、`import edinet.models.edinet_code` のようなサブモジュール import でもトップレベル初期化コストを支払うことになり、`test_import_time_acceptable` を壊しやすい。
  - 実装は `src/edinet/public_api.py` に分離し、`src/edinet/__init__.py` は facade（再エクスポート）専用に寄せるのが安全。
  - facade 側でも eager import を避けること。`documents` だけでなく `configure` も lazy export にしないと import-time 予算超過が再発し得る。
  - 同様に `src/edinet/models/__init__.py` も eager import すると `import edinet.models.edinet_code` に巻き込まれるため、`__getattr__` ベースの lazy export が有効。
  - lazy export（`__getattr__`）を採用する場合、型チェッカーと `stubgen` は公開シンボルを自動推論できないことがある。`src/edinet/__init__.py` / `src/edinet/models/__init__.py` には `if TYPE_CHECKING:` の明示 import を置き、実行時性能を維持したまま型公開面（`.pyi`）を安定化させる。
  - `Company.get_filings()` は `from edinet import documents` を維持することで、既存テストの `monkeypatch.setattr("edinet.documents", ...)` と互換を保てる。実装モジュールを直接 import するとテスト契約が壊れる点に注意。
  - 新規モジュール追加時は `.pyi` も同時追加する（今回 `stubs/edinet/public_api.pyi` を追加）。`stub` の追従漏れは型ヒント利用者にとって実質的な破壊的変更になる。
  - import-time テスト（2.0s）は環境負荷で揺れやすい。単発 pass/fail だけで判断せず、同条件で複数回確認して傾向を見る運用が必要。

- **計画外で増えたファイル（2026-02-17 時点）**:
  - `docs/Day6.md` の「実装対象ファイル」には明記されていないが、層分離のため以下を追加した。
  - `src/edinet/public_api.py`: `documents()` 本体と補助関数を `__init__.py` から移設するための実装モジュール。
  - `stubs/edinet/public_api.pyi`: 上記モジュール追加に伴う型スタブ追従。
  - 参考: `edinet_code` 正規化ヘルパーは当初 `src/edinet/models/validators.py` に置いたが、「非公開ヘルパーは `_` 接頭辞で明示する」方針に合わせて `src/edinet/_validators.py`（stub: `stubs/edinet/_validators.pyi`）へ移設した。
  - 今後、同様の計画外追加が発生した場合は、`DayX.md` の実装対象ファイル表にも追記して計画との差分を先に可視化する。


find_primary_xbrl_pathの実装はzipファイルの構造を把握したうえでやるべき（week7で行う）

テストの規模と範囲を厳密に管理する
テストにはsize（テストケースの実行に必要なリソースを指し、メモリー、プロセス、時間等）とscope（検証している特定のコードパス）という２つの重要な軸がある。
sizeはテスト規模でありテストの速度と決定性に関連する。
小テストは単一のプロセス内で実行されるしシングルスレッド内で実行されなければならないしテストコードと対象となるコードが同一スレッドで行われなければならないし、外部のサーバーを起動して接続したりデータベースなどのサードパーティプログラムを実行できない。sleepできないI/Oもできないその他あらゆるブロックする関数呼び出しができない。
中テストは小テストの制約から複数プロセスにひろがれるスレッド使えるlocalhostへのネットワーク呼び出しを含むブロックする関数を使える。残る制約はlocalhost以外のシステムへのネットワーク呼び出しができない。つまり単一マシンに収まる必要がある。
大テストは複数マシンにまたがることができる。

scopeはテスト範囲でありユニットテスト、インテグレーションテスト、E2Eテストでいわゆるテストピラミッドが推奨される。

以上の3x3=9通りのどれに各テストがあたるかラベル等で明確に分類し実行タイミングの管理ができるようにするべき（ファイルを分けてもいいかも）

以降の実装に対して影響が少ないならasyncへの移行を検討する

（タクソノミの解決）やるなら略称で変換やった方がいいよ
総称だと同じ指標なのに別になっちゃう

日本の会計基準でやってる会社と米国の会計基準でやってる会社があるからその差分を吸収するのも略称で行けるらしい。

## Day 7

- **テスト marker 導入タイミングの判断（2026-02-21）**:
  - Day7 では `large` marker のみ追加。`small` / `medium` / `unit` / `integration` / `e2e` は Week2 冒頭（Day8 or Day9）で正式導入する。
  - 理由: Week1 のテストは実質ほぼ全部 small/unit であり、marker を貼っても情報量がゼロ。Week2 で parser が入ると medium（ローカルファイル I/O）と integration（複数モジュール結合）が初めて区別に意味を持つ。
  - Week1 の最初に方針を決めるべきだったが、テストが均質（ほぼ全 small/unit）だったため実害は出ていない。多様な size が混在し始める前に入れれば十分間に合う。
  - 既存の `slow` / `data_audit` marker はそのまま残す（壊さない）。

- **Large テストの日付選定**:
  - テスト日付は `2025-01-15`（水曜日）を採用。十分に古くデータが安定しており、平日のため API レスポンスがある。
  - 土日は EDINET API にデータがないため、Large テストの固定日付には必ず平日を選ぶこと。

- **`on_invalid` 契約の確定（2026-02-22 実装）**:
  - `edinet.documents()` に `on_invalid: Literal["skip", "error"] = "skip"` を追加。
  - デフォルト `"skip"`: 非 dict 行および `Filing` 変換失敗行をスキップし、`EdinetWarning` で件数・代表 docID を通知。
  - `"error"`: 最初の不正行で `EdinetParseError` を送出（メッセージに `on_invalid='skip'` のガイダンスを含む）。
  - `_prepare_response_for_filing_parse()` をフィルタ有無に関係なく同じ契約に統一。以前はフィルタなし時のみ非 dict で即エラー、フィルタあり時は黙殺という不整合があった。
  - `Filing.from_api_list()` の一括呼び出しを廃止し、行ごとに `Filing.from_api_response()` を呼ぶループに変更。モデル層の `from_api_list()` 自体は変更せず維持。
  - Large テスト（`2025-01-15`）で実 API 確認: 101 件の不正行がスキップされ正常動作を確認。

- **Large テスト基盤の導入**:
  - `pyproject.toml` に `large` marker と `addopts = "-m 'not large'"` を追加。通常の `pytest` 実行では Large テストが除外される。
  - `tests/test_large/` に conftest（API キーガード）と smoke テスト 3 本を配置。
  - 実行: `uv run pytest -m large`（API キーが環境変数にある場合のみ）。

## Day 7.5

- **async API 追加（非破壊的並列化）**:
  - 既存の同期 API は一切変更せず、`async def` 版を追加した。同期テストが 1 件も壊れていない。
  - `_http.py`: リトライ判定を `_evaluate_response()` 純粋関数に抽出し、sync/async で共通化。`_RetryDecision` データクラスで判定結果を表現。
  - `_http.py`: `aget()`, `ainvalidate_client()`, `aclose()`, `_reset_async_state_for_testing()` を追加。async レート制限は `asyncio.Lock` でシリアライズ。
  - `api/documents.py`: レスポンス検証を `_validate_documents_response()` に共通化し、`aget_documents()` を追加。
  - `api/download.py`: 入力バリデーションを `_validate_and_normalize_download_params()`、レスポンス検証を `_validate_download_response()` に共通化し、`adownload_document()` を追加。
  - `public_api.py`: `adocuments()` を追加（`documents()` のミラー、日付ループ内は逐次 `await`）。
  - `models/filing.py`: `afetch()` を追加（`fetch()` のミラー、`_zip_cache` / `_xbrl_cache` は同期版と共有）。
  - `__init__.py`: `adocuments`, `aclose` を lazy export に追加。

- **テスト基盤の拡張**:
  - `pytest-asyncio>=0.25` を dev 依存に追加、`asyncio_mode = "auto"` を設定。
  - `conftest.py` の teardown に `_reset_async_state_for_testing()` を追加。
  - 新規 async テスト 10 件 + `_evaluate_response` 単体テスト 6 件 = 計 16 件を追加。
  - Large テストに `test_adocuments_real_api_smoke` を追加。

- **ベンチマーク拡張**:
  - `bench_bulk_download.py` に `--mode sync|async` と `--concurrency N` を追加。
  - async モードは `asyncio.Semaphore` + `asyncio.gather` で並列ダウンロードを実行。
  - 末尾に `edinet.aclose()` でクリーンアップ。

- **設計判断**:
  - `adocuments()` は日付範囲を逐次 `await` する。日付範囲の並列化は利用者側の責務。
  - ZIP ヘルパーは async 化しない（CPU バウンドでメモリ上の処理のため）。
  - `_reset_async_state_for_testing()` は同期関数。イベントループが閉じている可能性があるため `aclose()` は呼ばず参照を切るだけにする。
