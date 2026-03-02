## C-1c. common モジュールの役割

### 質問への対応

| サブ質問 | 回答 |
|----------|------|
| C-1c.1 このファイルの役割は何か | 目次項目アイテムスキーマ。abstract 要素 `iod:identifierItem` を1つだけ定義し、各モジュールの目次項目(Heading)要素の substitutionGroup の基底として機能する |
| C-1c.2 他のタクソノミモジュールからどのように参照されるか | 16個の `_cor_` XSD（jpcrp, jppfs, jpigp 等）が iod namespace を import し、目次要素を `substitutionGroup="iod:identifierItem"` として宣言する |
| C-1c.3 パーサーで処理する必要があるか | データ抽出目的であれば無視してよい。identifierItem 自体が abstract=true であり、派生する Heading 要素も全て abstract=true のため、インスタンス文書に Fact として出現しない |

### 情報源（Fact）

- [F1] パス: `/mnt/c/Users/nezow/Downloads/ALL_20251101/taxonomy/common/2013-08-31/identificationAndOrdering_2013-08-31.xsd` — ファイル全体が10行、991 bytes。定義されている要素は `identifierItem` の1つのみ:
  ```xml
  <xsd:element name="identifierItem" id="iod_identifierItem"
    type="xbrli:stringItemType" substitutionGroup="xbrli:item"
    abstract="true" nillable="true" xbrli:periodType="duration"/>
  ```
- [F2] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1023-1029 — 図表 3-2-5「目次項目アイテムスキーマ」:
  - ファイル名: `identificationAndOrdering_[タクソノミ日付].xsd`
  - 名前空間 URI: `http://disclosure.edinet-fsa.go.jp/taxonomy/common/[タクソノミ日付]/iod`
  - 名前空間プレフィックス: `iod`
- [F3] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1088 — 図表 3-2-12「substitutionGroup」No.4: `iod:identifierItem` — 「目次を表す項目に設定する。」
- [F4] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.1127-1142 — 図表 3-2-17「目次項目を表す要素」:
  - name: `{文字列}Heading`, substitutionGroup: `identifierItem`, abstract: `true`
- [F5] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.585 — 「目次項目アイテムスキーマ | 目次項目の substitutionGroup に設定する目次専用のアイテム (identifierItem) が定義されています。」
- [F6] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.602 — 「語彙スキーマ（DEI 語彙スキーマを除く。）は、目次項目アイテムスキーマとも関連付けられています。」
- [F7] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.609 — 「目次項目アイテムスキーマに定義されている主な内容」節: 「目次項目は...提出書類全体構造と、詳細タグ付けされる提出書類内の特定部分とを関連付ける際にも利用」
- [F8] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.1707 — 提出者別タクソノミの名前空間宣言一覧 No.12: `iod | http://disclosure.edinet-fsa.go.jp/taxonomy/common/[タクソノミ日付]/iod | 目次項目アイテムスキーマの名前空間宣言`
- [F9] パス: `docs/仕様書/提出者別タクソノミ作成ガイドライン.md` L.1743 — 「語彙スキーマインポート時は、目次項目アイテムスキーマも同時にインポートされます。」
- [F10] パス: `docs/仕様書/EDINETタクソノミの設定規約書.md` L.2299 — FRTA 非準拠理由 1.3.27: 「目次要素に設定する目次項目アイテム(identifierItem)を使用するため。」（FRTA は substitutionGroup が xbrli:item / xbrldt:* のいずれかであることを要求するが、iod:identifierItem は xbrli:item の派生なので XBRL 仕様上は合法だが FRTA ベストプラクティスには非準拠）
- [F11] スクリプト: `docs/QAs/scripts/C-1c.common_refs.py` 実行結果 — iod namespace を import/参照する XSD は 22 ファイル（うち `_cor_` XSD が 16 ファイル、`_dep_` が 4 ファイル、common 自身が 1 ファイル、その他 1）。参照元 `_cor_` XSD: jpcrp, jpcrp-esr, jpcrp-sbr, jpctl, jpigp, jplvh, jppfs, jpsps, jpsps-esr, jpsps-sbr, jptoi, jptoo-pst, jptoo-toa, jptoo-ton, jptoo-tor, jptoo-wto
- [F12] スクリプト: 同上 — `substitutionGroup="iod:identifierItem"` を持つ要素の例: `CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo3AnnualSecuritiesReportHeading` 等、いずれも名前末尾が `Heading` で abstract=true

### 推論（Reasoning）

1. [F1] より、`identificationAndOrdering_2013-08-31.xsd` は単一の abstract 要素 `iod:identifierItem` のみを定義する極めて小さなスキーマ（10行）である。targetNamespace は `http://disclosure.edinet-fsa.go.jp/taxonomy/common/2013-08-31/iod`。

2. [F2] + [F3] + [F4] より、このファイルの仕様上の役割は「目次項目アイテムスキーマ」であり、EDINET タクソノミにおける substitutionGroup の4種類（xbrli:item, xbrldt:hypercubeItem, xbrldt:dimensionItem, iod:identifierItem）のうちの1つを提供する。具体的には、各モジュールの目次項目（`*Heading` 要素）が `substitutionGroup="iod:identifierItem"` を宣言することで、XBRL プロセッサが「この要素は目次用途である」と識別できるようにしている。

3. [F11] より、DEI を除く全ての `_cor_` XSD（16モジュール）が iod namespace を import している。[F6] + [F9] の記述「語彙スキーマインポート時は、目次項目アイテムスキーマも同時にインポートされます」と整合する。DTS 解決の連鎖で、提出者別タクソノミ → `_cor_` XSD → `identificationAndOrdering_2013-08-31.xsd` の順に到達する。

4. [F1]（abstract="true"）+ [F4]（派生要素も abstract=true）+ [F12]（実際の Heading 要素も abstract=true）より、iod:identifierItem 自体およびそこから派生する全ての Heading 要素は abstract であるため、インスタンス文書に Fact として出現することはない。したがってデータ抽出パーサーにおいてこれらの要素から値を読み取る必要はない。

5. [F7] より、目次項目は Presentation linkbase における「提出書類全体構造」と「詳細タグ付け部分」の関連付けに利用される。つまり Presentation ツリーの構造的なナビゲーション（どの章・節に属するか）を表現するために存在する。財務データの抽出が目的であれば、Heading 要素は Presentation ツリーのノードとして認識するだけで十分であり、iod namespace のスキーマを特別に解析する必要はない。

6. [F10] より、EDINET は FRTA 1.3.27（substitutionGroup は xbrli:item/xbrldt:* のいずれかであるべき）に非準拠であることを明示している。これは iod:identifierItem が xbrli:item の substitutionGroup に属する（つまり XBRL 仕様上は xbrli:item の一種）にもかかわらず、FRTA のベストプラクティスルールには適合しないことを意味する。パーサー実装上、substitutionGroup の解決において iod:identifierItem → xbrli:item の連鎖を辿れば問題ない。

### 確信度

- 高（仕様書に明記 + 実ファイルで完全に確認済み）
- ファイルの役割、参照関係、abstract 属性はいずれも仕様書の記述 [F2]-[F4] と実ファイル [F1][F11][F12] の両方で裏付けられている
