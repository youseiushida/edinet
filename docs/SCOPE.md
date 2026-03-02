# SCOPE

edinet ライブラリのスコープ原則と境界線を定義する。

## 原則

ライブラリの責務は **「1件の XBRL → 構造化オブジェクト → DataFrame」の変換パイプライン** である。

- 入力: 1件の Filing（EDINET API からの ZIP / ローカルファイル）
- 出力: 型安全な Python オブジェクト、または pandas DataFrame
- パイプライン内の全ステップ（取得・パース・正規化・表示）はライブラリが担う
- パイプラインの外側（永続化・バッチ実行・年度横断集約）はユーザーが担う

## スコープ内

- EDINET API からの書類一覧取得・ZIP ダウンロード
- 1件の XBRL インスタンスのパース（Fact / Context / Unit / Namespace）
- タクソノミリンクベースの解析（Calculation / Presentation / Definition）
- 会計基準の判別と科目名の正規化（J-GAAP / IFRS / US-GAAP）
- 1件の Filing 内の前期比較データの取得
- 訂正チェーンの解決（latest / at_time）
- 複数のパース済みオブジェクトを受け取る比較ユーティリティ（diff, compare）
- DataFrame への変換とエクスポート（Parquet / CSV / Excel）
- ターミナル・Jupyter での表示
- CLI（1件の Filing に対する操作）

機能の詳細は FEATURES.md を参照。

## スコープ外

以下はライブラリの責務外とし、ユーザー側で実装する領域とする。

### 永続化・ストレージ

- store: ローカル DB / データウェアハウスへの書き込み
  - 理由: ユーザーの技術スタックに依存する（SQLite / PostgreSQL / BigQuery / Parquet on S3 等）。ライブラリが特定のストレージを強制すべきではない
  - 代替: `filing.to_dataframe()` の出力を任意の方法で永続化する

### バッチ処理・オーケストレーション

- batch_orchestration: 全銘柄一括処理、定期実行、リトライ、進捗表示
  - 理由: ワークフローエンジン（Temporal / Prefect / Airflow）や tqdm 等のツールが適切に担う領域。ライブラリがジョブ管理に介入すると技術選定の自由度を奪う
  - 代替: ユーザーが `for filing in filings:` ループを書き、好みのツールで進捗管理・リトライを行う
- cache_incremental: EDINET API の差分更新（前回取得以降の新着のみ取得）
  - 理由: 「前回いつ取得したか」の状態管理はアプリケーション層の責務
  - 代替: ユーザーが取得済み doc_id を管理し、未取得分のみ `fetch()` する

### 年度横断・時系列集約

- dataframe/financials: 全銘柄横断の財務データパネル構築
  - 理由: 数千件の Filing を逐次パースし結合する処理はバッチオーケストレーションそのもの
  - 代替: ユーザーが複数 Filing を個別にパースし、DataFrame を concat する
- dataframe/time_series: 単一企業の時系列データ構築（5期推移等）
  - 理由: 複数年度の Filing 取得・パース・結合はバッチ処理であり、上記と同じ理由でスコープ外
  - 代替: ユーザーが年度ごとの Filing をパースし、period の日付をキーに結合する
- company/history: 企業の組織変遷（合併・分割・コード変更）の追跡
  - 理由: 時間軸をまたぐエンティティ解決はアプリケーション固有のロジック
  - 代替: EDINET コードの変更は API のメタデータで検知可能。ユーザーがマッピングテーブルを管理する

### マーケットデータ・指標計算

- market_data: 株価・時価総額・出来高等の市場データ取得
  - 理由: EDINET は開示データのソースであり、市場データは別のデータソース（jquants / Yahoo Finance 等）から取得すべき
- market_ratios: PER / PBR / 配当利回り等のバリュエーション指標
  - 理由: 株価データが必要であり、EDINET のスコープ外
- edinet_ratios: ROE / ROA / 自己資本比率等の財務指標
  - 理由: 計算式自体は単純であり、ユーザーが DataFrame から算出する方が透明性が高い。ライブラリが「正しい計算式」を規定すると議論が発散する
  - 代替: `filing.to_dataframe()` の出力から `df["ROE"] = df["当期純利益"] / df["自己資本"]` のように計算する

### その他

- universe: 全上場企業のユニバース管理（上場廃止・新規上場の追跡）
  - 理由: サバイバーシップバイアスの制御はバックテストフレームワークの責務
- pit_general: 汎用 Point-in-Time データベースの構築
  - 理由: いつ何が入手可能だったかの時間管理はアプリケーション層の関心事。ただし `at_time()` による1件の訂正チェーン解決はスコープ内
- stock_adjustment: 株式分割・併合の遡及調整
  - 理由: EPS 等の1株当たり指標の調整は市場データとの組み合わせが必要。EDINET データ単体では完結しない
