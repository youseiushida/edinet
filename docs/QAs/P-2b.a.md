## P-2b. iXBRL (.htm) ファイルの冒頭・構造確認

### 質問への対応

P-2b は iXBRL .htm ファイルの ix: 名前空間宣言、ix:header、ix:hidden の存在、format/scale 属性を確認する。

### 情報源（Fact）

- [F1] スクリプト: `docs/QAs/scripts/P-2b.ixbrl_head.py` 実行結果 — トヨタ (S100VWVY) header .htm:
  - **ix: 名前空間宣言**: L.2 に `xmlns:ix="http://www.xbrl.org/2008/inlineXBRL"` が存在
  - **ixt 名前空間宣言**: L.2 に `xmlns:ixt="http://www.xbrl.org/inlineXBRL/transformation/2011-07-31"` が存在
  - **ix:header**: L.153 に存在。`<div style="display: none">` 内に配置
  - **ix:hidden**: L.154 に存在。DEI 要素（EDINETCode, SecurityCode, FilerName, AccountingStandards 等）が格納
  - ix:hidden 内の DEI 要素例:
    - `<ix:nonNumeric contextRef="FilingDateInstant" name="jpdei_cor:EDINETCodeDEI">E02144</ix:nonNumeric>`
    - `<ix:nonNumeric contextRef="FilingDateInstant" name="jpdei_cor:AccountingStandardsDEI">IFRS</ix:nonNumeric>`
    - `<ix:nonFraction contextRef="FilingDateInstant" decimals="0" scale="0" name="jpdei_cor:NumberOfSubmissionDEI" unitRef="pure">1</ix:nonFraction>`

- [F2] 同上 — 本文 .htm ファイルの分析:
  - 本文ファイル（0101010, 0102010, ... 等）には **ix:header なし、ix:hidden なし**
  - 各本文ファイルの L.2 に ix 名前空間宣言あり（header と同じ）
  - `ix:nonNumeric` / `ix:nonFraction` は本文内に直接埋め込み

- [F3] 同上 — format 属性の種類（全 .htm ファイルから集計）:
  - `ixt:numdotdecimal` — 数値のカンマ区切り表示（例: "1,234,567" → 1234567）

- [F4] 同上 — scale 属性の種類:
  - `scale="0"` — 円単位
  - `scale="6"` — 百万円単位

- [F5] 同上 — ix:nonFraction の使用例（header .htm 内）:
  - `<ix:nonFraction contextRef="FilingDateInstant" decimals="0" scale="0" name="jpdei_cor:NumberOfSubmissionDEI" unitRef="pure">1</ix:nonFraction>`
  - 本文 .htm 内: `<ix:nonFraction contextRef="..." decimals="..." scale="6" format="ixt:numdotdecimal" name="..." unitRef="JPY">1,234</ix:nonFraction>`

- [F6] 同上 — ix:nonNumeric の使用例:
  - header: `<ix:nonNumeric contextRef="FilingDateInstant" name="jpdei_cor:FilerNameInJapaneseDEI">トヨタ自動車株式会社</ix:nonNumeric>`
  - 本文: `<ix:nonNumeric contextRef="FilingDateInstant" name="jpcrp_cor:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock" escape="true">`（TextBlock 型、escape="true"）

### 推論（Reasoning）

1. [F1] より、ix:header は **表紙ファイルのみ** に存在し、`<div style="display: none">` で非表示にされている。これは仕様書 Instance Guideline L.2097 「表紙ファイルに設定します」と一致。
2. [F2] より、本文ファイルは ix:header を持たず、ix:nonNumeric / ix:nonFraction のみを本文 HTML 内に埋め込む。IXDS 構造では全ファイルの Context/Unit が表紙の ix:resources で一元管理される。
3. [F3]+[F4] より、format 属性は `ixt:numdotdecimal` のみ確認。scale は `0`（円単位）と `6`（百万円単位）。仕様書 Instance Guideline L.1691-1696 の scale 一覧（-2, 0, 3, 6）と整合。
4. [F6] より、TextBlock 型の ix:nonNumeric には `escape="true"` が付与され、HTML コンテンツを XBRL 値として格納している。

### 確信度

- 高（実ファイルの直接確認に基づく）
- 補足: format 属性は `ixt:numdotdecimal` のみ確認されたが、他の企業や書類種別で別の format が使用される可能性がある（確信度: 中）

### 検証

- 検証者: Claude Code (検証エージェント)
- 検証日: 2026-02-23
- 判定: OK
- 指摘事項:
  - テンプレート形式の軽微な逸脱: 「質問への対応」テーブルが省略されている。ただし q.md の構造上問題なし
  - [F1]-[F6] の内容はスクリプト（P-2b.ixbrl_head.py）のロジック確認で妥当性を確認。正規表現パターンは適切
  - [F3] format 属性 `ixt:numdotdecimal` のみ: 仕様書 Instance Guideline L.1697-1700 の記述と整合
  - [F4] scale 属性 `0` と `6`: 仕様書 L.1691-1696 の一覧（-2, 0, 3, 6）と整合。トヨタでは -2 と 3 が未使用だが、これは企業固有の事情であり問題なし
  - P-2.a.md との整合性: ix:header の位置（L.153）、ix:hidden の位置（L.154）、Context/Unit が表紙に集約される構造は両回答で一致
