## H-4b. XML パース上の注意

### 質問への対応

| サブ質問 | 回答 |
|----------|------|
| H-4b.1 CDATA セクション | 2026 サンプル 466 ファイル中 0 件。CDATA は使われない |
| H-4b.2 XML エンティティ参照 | `&amp;` `&lt;` `&gt;` 等の標準エンティティのみ。lxml のデフォルト処理で十分 |
| H-4b.3 デフォルト名前空間 | iXBRL `.htm` は `xmlns="http://www.w3.org/1999/xhtml"`、manifest.xml は `xmlns="http://disclosure.edinet-fsa.go.jp/2013/manifest"` を使用。`.xbrl` / リンクベース / `.xsd` では不使用 |
| H-4b.4 UTF-8 BOM | `.htm`（iXBRL）は全ファイル BOM あり。`.xbrl` / `.xml` / `.xsd` は全ファイル BOM なし |
| H-4b.5 DOCTYPE 宣言 | 2026 サンプル 466 ファイル中 0 件。仕様で明示的に禁止 |

### 情報源（Fact）

- [F1] スクリプト: `docs/QAs/scripts/H-4b.xml_notes.py` 実行結果 — 466 ファイルの調査結果:
  - BOM: `.htm` 202/202 あり、`.xbrl` 0/56、`.xml` 0/152、`.xsd` 0/56
  - CDATA: 0/466
  - DOCTYPE: 0/466
  - デフォルト名前空間: 233/466（内訳: `.htm` 全 202 ファイル + `manifest*.xml` 31 ファイル）
- [F2] パス: `docs/仕様書/XBRL Instance Guideline 報告書インスタンス作成ガイドライン.md` L.1601-1603 — 「インライン XBRL ファイルでは、DOCTYPE 宣言の付与を禁止しています」
- [F3] パス: `docs/仕様書/XBRL Instance Guideline 報告書インスタンス作成ガイドライン.md` L.763 — 「文字コードを UTF-8 に指定する際に BOM(Byte Order Mark) を付与することを原則とします」
- [F4] パス: `docs/QAs/K-2.a.md` [F8] — iXBRL で DOCTYPE 禁止を確認。[F17] — XML 宣言あり（`<?xml version="1.0" encoding="utf-8"?>`）
- [F5] デフォルト名前空間の詳細確認: `.xml`/`.xsd` でデフォルト名前空間を持つのは `manifest_*.xml`（`http://disclosure.edinet-fsa.go.jp/2013/manifest`）のみ。リンクベース（`_lab.xml`, `_pre.xml` 等）と `.xsd` はプレフィックス付き名前空間のみ

### 推論（Reasoning）

1. **CDATA**: [F1] より CDATA セクションは一切使われていない。EDINET ではテキスト型 Fact（TextBlock 等）の内容は HTML エスケープ（`&lt;` `&gt;`）で埋め込まれるか、iXBRL では HTML として直接記述される。パーサーで CDATA の特別な処理は不要（lxml は標準で CDATA を処理するため、仮に存在しても問題ない）。

2. **エンティティ参照**: [F1] + [F2] より DOCTYPE 宣言が禁止されているため、カスタムエンティティ（`&custom;`）は定義できない。XML 標準の 5 エンティティ（`&amp;`, `&lt;`, `&gt;`, `&quot;`, `&apos;`）のみが使用される。lxml のデフォルト処理で十分。

3. **デフォルト名前空間**: [F1] + [F5] より、デフォルト名前空間が設定されるのは (a) iXBRL `.htm`（XHTML 名前空間）と (b) `manifest_*.xml`（EDINET 独自）のみ。パーサーが主に扱う `.xbrl` ファイルとリンクベース `.xml` ではデフォルト名前空間は使われていない。lxml での XPath/findall は `{namespace}localname` 形式か nsmap を使えば問題ない。iXBRL パース時は XHTML デフォルト名前空間に注意が必要（`{http://www.w3.org/1999/xhtml}table` 等）。

4. **BOM**: [F1] + [F3] より、iXBRL `.htm` は仕様どおり BOM 付き、EDINET 自動生成の `.xbrl` とタクソノミ XML は BOM なし。lxml の `etree.parse()`（ファイルパス指定）や `etree.fromstring()`（bytes 指定）は BOM を正しく処理する。ただし `bytes.decode('utf-8')` でテキストに変換してから `etree.fromstring()` に渡す場合は BOM が残り XML 宣言の前に不正文字が来るため、`utf-8-sig` でデコードするか bytes のまま lxml に渡すこと。

5. **DOCTYPE / XXE**: [F2] + [F4] より DOCTYPE は仕様で禁止されており、[F1] で実データにも存在しないことを確認。XXE 攻撃のリスクは低いが、防御的プログラミングとして `lxml.etree.XMLParser(resolve_entities=False)` を設定することを推奨。コストゼロで安全性を向上できる。

### 確信度

- 高（仕様書に明記 + スクリプトで 466 ファイルを全数確認）
