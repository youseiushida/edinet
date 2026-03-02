## F-1b. DEI 要素の Context

### 質問への対応

q.md のサブ質問ごとに回答箇所を対応付ける。

| サブ質問 | 回答 |
|----------|------|
| F-1b.1 DEI 要素の Fact はどの Context に紐づくか | 全ての DEI Fact は **`FilingDateInstant`**（提出日の instant）に紐づく。`CurrentYearDuration` ではない。DEI は「提出日時点の書類情報」であり、会計期間のデータではないため、提出日を基準とする instant コンテキストが使われる。 |
| F-1b.2 DEI 専用の Context パターンはあるか | ある。`FilingDateInstant` は DEI 専用のパターンである。期末日の `CurrentYearInstant`（決算日時点）や会計期間の `CurrentYearDuration` とは異なり、**提出日（=書類を EDINET に提出した日）**を instant 日付とする。例えば 3 月決算企業が 6 月 12 日に有報を提出した場合、`CurrentYearInstant` は `2026-03-31`、`FilingDateInstant` は `2026-06-12` となる。 |
| F-1b.3 DEI の Fact に dimension は付与されるか | **通常の提出書類では付与されない**。`FilingDateInstant` の scenario は「設定なし」と仕様書に明記されている。ただし**大量保有報告書**は例外であり、共同保有者ごとの DEI に `jplvh_cor:FilersLargeVolumeHoldersAndJointHoldersAxis` ディメンションが使用される。 |

### FilingDateInstant の定義

報告書インスタンス作成ガイドライン 図表 5-4-8 に定義される `FilingDateInstant` コンテキスト:

```xml
<xbrli:context id="FilingDateInstant">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99001-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:instant>2026-06-12</xbrli:instant>
  </xbrli:period>
</xbrli:context>
```

- segment: 設定なし
- scenario: 設定なし
- instant: 提出日（YYYY-MM-DD 形式）

仕様書は `FilingDateInstant` の用途を「DEI、表紙、包括タグ（様式ツリーの『経理の状況』を除く。）、独立監査人の報告書等のコンテキストとして利用します。」と記載している。

### DEI 設定の実例

ガイドライン §5-6-7 の DEI 設定例:

```xml
<ix:nonnumeric name="jpdei_cor:EDINETCodeDEI" contextref="FilingDateInstant">X99001</ix:nonnumeric>
<ix:nonnumeric name="jpdei_cor:FundCodeDEI" contextref="FilingDateInstant" xsi:nil="true"></ix:nonnumeric>
<ix:nonnumeric name="jpdei_cor:SecurityCodeDEI" contextref="FilingDateInstant">11110</ix:nonnumeric>
<ix:nonnumeric name="jpdei_cor:FilerNameInJapaneseDEI" contextref="FilingDateInstant">A株式会社</ix:nonnumeric>
```

全 DEI 要素が `contextref="FilingDateInstant"` を使用していることが確認できる。

### 大量保有報告書の例外

大量保有報告書では、共通 DEI（提出者自身の情報）は通常通り `FilingDateInstant`（dimension なし）を使用するが、個別保有者の DEI は dimension 付きのコンテキストを使用する。

ガイドライン §5-6-7-2 より: 「大量保有報告書用 DEI でメンバーの追加及びディメンションを使用したタグ付けが必要となります。」

**共通 DEI（dimension なし）**:
```xml
<jpdei_cor:EDINETCodeDEI contextRef="FilingDateInstant">X99014</jpdei_cor:EDINETCodeDEI>
<jpdei_cor:FilerNameInJapaneseDEI contextRef="FilingDateInstant">Ｚ株式会社</jpdei_cor:FilerNameInJapaneseDEI>
```

**保有者別 DEI（dimension あり）**:
```xml
<jplvh_cor:EDINETCodeDEI contextRef="FilingDateInstant_jplvh010000-lvh_X99014-000FilerLargeVolumeHolder1Member">X99015</jplvh_cor:EDINETCodeDEI>
<jplvh_cor:FilerNameInJapaneseDEI contextRef="FilingDateInstant_jplvh010000-lvh_X99014-000FilerLargeVolumeHolder1Member">株式会社Ｊ産業</jplvh_cor:FilerNameInJapaneseDEI>
```

保有者別コンテキストの構造:
```xml
<xbrli:context id="FilingDateInstant_jplvh010000-lvh_X99014-000FilerLargeVolumeHolder1Member">
  <xbrli:entity>
    <xbrli:identifier scheme="http://disclosure.edinet-fsa.go.jp">X99014-000</xbrli:identifier>
  </xbrli:entity>
  <xbrli:period>
    <xbrli:instant>2026-08-10</xbrli:instant>
  </xbrli:period>
  <xbrli:scenario>
    <xbrldi:explicitMember dimension="jplvh_cor:FilersLargeVolumeHoldersAndJointHoldersAxis">jplvh010000-lvh_X99014-000:FilerLargeVolumeHolder1Member</xbrldi:explicitMember>
  </xbrli:scenario>
</xbrli:context>
```

注: 大量保有報告書の保有者別 DEI は `jplvh_cor`（大量保有府令語彙）名前空間の要素であり、`jpdei_cor` の標準 DEI 要素とは別の概念である。

### 情報源（Fact）

観察事実のみを記載する。推論や解釈は含めない。

- [F1] パス: `docs/仕様書/XBRL Instance Guideline 報告書インスタンス作成ガイドライン.md` L.1186-1197 -- 図表 5-4-8 `FilingDateInstant` コンテキストの定義。id=`FilingDateInstant`、instant=提出日、segment=設定なし、scenario=設定なし。説明:「DEI、表紙、包括タグ（様式ツリーの『経理の状況』を除く。）、独立監査人の報告書等のコンテキストとして利用します。」
- [F2] パス: 同上 L.2250-2278 -- §5-6-7 DEI の設定。XML 例で全 DEI 要素が `contextref="FilingDateInstant"` を使用
- [F3] パス: 同上 L.2266-2274 -- DEI 設定例の XML。EDINETCodeDEI, FundCodeDEI, SecurityCodeDEI, FilerNameInJapaneseDEI が全て `FilingDateInstant` コンテキストを参照
- [F4] パス: 同上 L.2288-2295 -- §5-6-7-2 大量保有報告書の DEI の設定。「大量保有報告書用 DEI でメンバーの追加及びディメンションを使用したタグ付けが必要となります。」
- [F5] サンプルファイル: `docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ/01_開示府令-有価証券届出書/S001XXXX/XBRL/PublicDoc/jpcrp020000-srs-001_X99001-000_2026-03-31_01_2026-11-20.xbrl` L.3183-3186 -- DEI Fact の実例。`<jpdei_cor:EDINETCodeDEI contextRef="FilingDateInstant">X99001</jpdei_cor:EDINETCodeDEI>` 等
- [F6] サンプルファイル: `docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ/18_大量保有府令-大量保有報告書/S019XXXX/XBRL/PublicDoc/jplvh010000-lvh-001_X99014-000_2026-08-07_01_2026-08-10.xbrl` L.82-85,108-114 -- 大量保有報告書の DEI 実例。共通 DEI（`FilingDateInstant`、dimension なし）と保有者別 DEI（`FilingDateInstant_...FilerLargeVolumeHolder1Member`、dimension あり）の両方が存在
- [F7] 同ファイル L.3-8,17-28 -- 大量保有報告書のコンテキスト定義。`FilingDateInstant` は scenario なし、`FilingDateInstant_...FilerLargeVolumeHolder1Member` は `jplvh_cor:FilersLargeVolumeHoldersAndJointHoldersAxis` ディメンション付き
- [F8] F-1.a.md -- 全 DEI 要素の完全一覧（全 34 要素）。全ての非 Abstract 要素は `periodType="instant"` であり、コンテキストは `FilingDateInstant` を使用する
- [F9] A-2.a.md -- Context ID 命名規則。`FilingDateInstant` は `{相対期間又は時点}{期間又は時点}` パターンに従い、`相対期間又は時点=FilingDate`、`期間又は時点=Instant` の組合せ

### 推論（Reasoning）

1. **F-1b.1 DEI の Context について**: [F1] より、`FilingDateInstant` は提出日を instant とするコンテキストであり、その説明に「DEI」が明記されている。[F2][F3] より、ガイドラインの DEI 設定例では全要素が `contextref="FilingDateInstant"` を使用している。[F5] より、サンプルインスタンスでも同様に確認できる。[F8] より、全 DEI 要素の `periodType` は `instant` である。以上から、全ての DEI Fact は `FilingDateInstant` コンテキストに紐づく。

2. **F-1b.2 DEI 専用のパターンについて**: [F1] より、`FilingDateInstant` の用途は「DEI、表紙、包括タグ、独立監査人の報告書等」と明記されている。[F9] より、Context ID 命名規則では `FilingDate` は `CurrentYear`、`Prior1Year` 等と並ぶ独立した相対期間区分である。`FilingDateInstant` は期末日の `CurrentYearInstant` や会計期間の `CurrentYearDuration` とは完全に別のコンテキストであり、DEI 専用（他の用途も含む）パターンといえる。

3. **F-1b.3 DEI の dimension について**: [F1] より、`FilingDateInstant` の scenario は「設定なし」と明記されている。通常の提出書類では DEI に dimension は付与されない。ただし [F4] より、大量保有報告書は例外であり、保有者ごとの DEI に dimension が必要とされている。[F6][F7] より、実際のサンプルでは `jplvh_cor:FilersLargeVolumeHoldersAndJointHoldersAxis` ディメンションを持つコンテキストが使用されている。ただしこの例外は `jplvh_cor` 名前空間の大量保有報告書用 DEI であり、`jpdei_cor` の標準 DEI 要素自体には dimension は付かない。

### 確信度

- **F-1b.1 FilingDateInstant の使用**: 高 -- 仕様書の明記（[F1]）、設定例（[F2][F3]）、サンプルインスタンス（[F5]）の 3 箇所で確認
- **F-1b.2 DEI 専用パターン**: 高 -- 仕様書の Context 用途説明（[F1]）と命名規則（[F9]）で確認
- **F-1b.3 dimension なし（大量保有報告書の例外あり）**: 高 -- 仕様書の scenario=設定なし（[F1]）と大量保有報告書の例外規定（[F4]）の両方を確認。サンプルインスタンス（[F6][F7]）で例外の実例も確認

### 検証（自己検証）

- 検証者: Claude Code (Opus 4.6)（回答者と同一セッション）
- 検証日: 2026-02-23
- 判定: OK

#### Step 1. 完全性検証
- [x] 全サブ質問（F-1b.1, F-1b.2, F-1b.3）に対応する行が存在する
- [x] 具体的な XML 例を提示している

#### Step 2. Fact 検証
全 9 件の Fact を確認。
- [F1] OK -- ガイドライン L.1186-1197 に FilingDateInstant の定義が記載。DEI 用途が明記
- [F2] OK -- ガイドライン L.2250-2278 に §5-6-7 DEI の設定が記載
- [F3] OK -- ガイドライン L.2266-2274 に DEI 設定例の XML が記載
- [F4] OK -- ガイドライン L.2288-2295 に §5-6-7-2 大量保有報告書の DEI の設定が記載。ディメンション使用が明記
- [F5] OK -- サンプルインスタンス L.3183-3186 に DEI Fact の実例が存在
- [F6] OK -- 大量保有報告書サンプル L.82-85,108-114 に共通 DEI と保有者別 DEI の実例が存在
- [F7] OK -- 同ファイル L.3-8,17-28 にコンテキスト定義が存在
- [F8] OK -- F-1.a.md に全 34 要素の periodType=instant が記載
- [F9] OK -- A-2.a.md に Context ID 命名規則が記載

#### Step 3. 推論検証
- [x] 推論 1: [F1]+[F2]+[F3]+[F5]+[F8] から全 DEI が FilingDateInstant を使用することを導出 -- 論理的に妥当
- [x] 推論 2: [F1]+[F9] から FilingDateInstant が DEI 専用パターンであることを導出 -- 論理的に妥当
- [x] 推論 3: [F1]+[F4]+[F6]+[F7] から dimension の原則と例外を導出 -- 論理的に妥当

#### Step 4. 依存関係検証
- [x] F-1.a.md との整合: F-1.a.md で「全ての非 Abstract 要素は periodType="instant"」「コンテキストは FilingDateInstant」と記載されており、本回答と整合
- [x] A-2.a.md との整合: A-2.a.md の Context ID 命名規則の `FilingDate` + `Instant` パターンと整合

### 検証（独立検証）

- 検証者: Claude Code (Opus 4.6)（別セッション）
- 検証日: 2026-02-23
- 判定: OK
- 検証内容: ガイドライン L.1186-1197（FilingDateInstant 定義、scenario=設定なし）、L.2250-2278（§5-6-7 DEI 設定）、L.2266-2274（XML 例）、L.2288-2295（§5-6-7-2 大量保有報告書のディメンション使用）を直接読み確認。全て原文と一致。訂正事項なし
