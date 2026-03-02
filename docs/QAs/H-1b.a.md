# H-1b.a: DTS 解決アルゴリズム ★最重要

## 質問

URL→ローカルパス変換ルール、import 連鎖の全体像、XBRL 国際標準スキーマの所在を確定する。（7問）

## 品質

確度: **A（実証済み）** — 2026サンプル XSD + ALL_20251101 ローカルファイルで検証。

## 回答

### H-1b.1: xs:import の schemaLocation は相対パスか絶対 URL か

**結論: 全て絶対 URL。**

- [F1] 2026サンプル XSD（`jpcrp030000-asr-001_X99001-000_2026-03-31_01_2026-06-12.xsd`）の `xs:import` は **8件全てが絶対 URL**。相対パスは0件。
- EDINET URL 6件 + XBRL.org URL 2件
- P-3.a.md [F3] のトヨタ実データでも同様（12件全て絶対 URL）
- **出典**: `H-1b.dts_resolve.py` 実行結果、`提出者別タクソノミ作成ガイドライン.md` L.1736-1768

### H-1b.2: URL → ローカルパスのマッピング表 ★KEY

**変換ルール: `http://disclosure.edinet-fsa.go.jp/taxonomy/{path}` → `ALL_20251101/taxonomy/{path}`**

- [F2] 具体的なマッピング（全て存在確認済み）:

| URL | ローカルパス | 存在 |
|---|---|---|
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor_2013-08-31.xsd` | `taxonomy/jpdei/2013-08-31/jpdei_cor_2013-08-31.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_rt_2013-08-31.xsd` | `taxonomy/jpdei/2013-08-31/jpdei_rt_2013-08-31.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd` | `taxonomy/jpcrp/2025-11-01/jpcrp_cor_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_rt_2025-11-01.xsd` | `taxonomy/jpcrp/2025-11-01/jpcrp_rt_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd` | `taxonomy/jppfs/2025-11-01/jppfs_cor_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2025-11-01/jppfs_rt_2025-11-01.xsd` | `taxonomy/jppfs/2025-11-01/jppfs_rt_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_cor_2025-11-01.xsd` | `taxonomy/jpigp/2025-11-01/jpigp_cor_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2025-11-01/jpigp_rt_2025-11-01.xsd` | `taxonomy/jpigp/2025-11-01/jpigp_rt_2025-11-01.xsd` | OK |
| `http://disclosure.edinet-fsa.go.jp/taxonomy/common/2013-08-31/identificationAndOrdering_2013-08-31.xsd` | `taxonomy/common/2013-08-31/identificationAndOrdering_2013-08-31.xsd` | OK |

- [F3] linkbaseRef URL も同じルールで変換可能（例: `http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/label/jpcrp_2025-11-01_lab.xml` → `taxonomy/jpcrp/2025-11-01/label/jpcrp_2025-11-01_lab.xml`）
- **出典**: `H-1b.dts_resolve.py` 実行結果

### H-1b.3: import 連鎖の深さ

- [F4] import 連鎖グラフの構造:
  ```
  提出者 XSD (depth=0)
  ├── jpdei_cor (depth=1)
  │   ├── xbrl-instance [EXTERNAL]
  │   └── nonNumeric [EXTERNAL]
  ├── jpdei_rt (depth=1, リーフ)
  ├── jpcrp_cor (depth=1)
  │   ├── xbrl-instance [EXTERNAL]
  │   ├── nonNumeric [EXTERNAL]
  │   ├── numeric [EXTERNAL]
  │   ├── types [EXTERNAL]
  │   ├── common/iod (depth=2)
  │   │   └── xbrl-instance [EXTERNAL]
  │   └── xbrldt [EXTERNAL]
  ├── jpcrp_rt (depth=1, リーフ)
  ├── jppfs_cor (depth=1)
  │   ├── xbrl-instance [EXTERNAL]
  │   ├── jppfs_pe (depth=2)
  │   │   └── xbrl-linkbase [EXTERNAL]
  │   ├── ref [EXTERNAL]
  │   ├── nonNumeric [EXTERNAL]
  │   ├── common/iod (depth=2, visited)
  │   └── xbrldt [EXTERNAL]
  ├── jppfs_rt (depth=1, リーフ)
  ├── xbrl-instance [EXTERNAL]
  └── nonNumeric [EXTERNAL]
  ```
- [F5] **最大深さ: 2**（提出者XSD → cor XSD → common/iod or jppfs_pe）
- [F6] EDINET ローカルノード数: **10**（提出者XSD含む）、外部URL参照: **16回**（重複含む）
- **出典**: `H-1b.dts_resolve.py` 実行結果

### H-1b.4: 各 import のローカルパス

- [R1] [F2] の表の通り、EDINET URL は全て `ALL_20251101/taxonomy/` 配下に存在。
- EDINET 内の相対パス import も正常に解決:
  - `jpcrp_cor` → `../../common/2013-08-31/identificationAndOrdering_2013-08-31.xsd` (OK)
  - `jppfs_cor` → `jppfs_pe_2012.xsd` (OK, 同一ディレクトリ)

### H-1b.5: 固定プレフィックスルール

**結論: `http://disclosure.edinet-fsa.go.jp/taxonomy/` は固定プレフィックスとして安全に置換可能。例外は XBRL 国際標準スキーマのみ。**

- [F7] 提出者 XSD の import 8件中:
  - EDINET URL: 6件（全て `http://disclosure.edinet-fsa.go.jp/taxonomy/` で始まる）
  - 非EDINET URL: 2件（`http://www.xbrl.org/` で始まる）
- [F8] EDINET タクソノミ XSD 内部の import でも同じパターン:
  - EDINET 内部参照 → 相対パスまたは EDINET 絶対 URL
  - 外部参照 → `http://www.xbrl.org/` のみ
- **出典**: `H-1b.dts_resolve.py` 実行結果

### H-1b.6: XBRL 国際標準スキーマの所在

**結論: ALL_20251101 に XBRL 国際標準スキーマは一切含まれない。**

- [F9] 以下の全てが `ALL_20251101` 内に **NOT FOUND**:
  - `xbrl-instance-2003-12-31.xsd`
  - `xbrl-linkbase-2003-12-31.xsd`
  - `xl-2003-12-31.xsd`
  - `xbrldt-2005.xsd`
  - `nonNumeric-2009-12-16.xsd`
  - `numeric-2009-12-16.xsd`
  - `ref-2006-02-27.xsd`
  - `types.xsd`（`http://www.xbrl.org/dtr/type/2022-03-31/types.xsd`）
  - `xml.xsd`
  - `deprecated-2009-12-16.xsd`

- [F10] EDINET タクソノミ XSD が参照する外部 URL の完全一覧（6件）:
  1. `http://www.xbrl.org/2003/xbrl-instance-2003-12-31.xsd`
  2. `http://www.xbrl.org/2005/xbrldt-2005.xsd`
  3. `http://www.xbrl.org/2006/ref-2006-02-27.xsd`
  4. `http://www.xbrl.org/dtr/type/2022-03-31/types.xsd`
  5. `http://www.xbrl.org/dtr/type/nonNumeric-2009-12-16.xsd`
  6. `http://www.xbrl.org/dtr/type/numeric-2009-12-16.xsd`

- [R2] [F9]+[F10] → パーサーの DTS 解決は以下の2層で実装すべき:
  1. **EDINET URL** → `ALL_YYYYMMDD/taxonomy/` にプレフィックス置換（確実に解決）
  2. **XBRL.org URL** → ハードコード or バンドル or 無視（Q-1 で対処方針を決定）

### H-1b.7: Taxonomy Package 準拠性

**結論: ALL_20251101 は XBRL Taxonomy Package に準拠していない。**

- [F11] `META-INF/` ディレクトリ: **NOT FOUND**
- [F12] `catalog.xml`: **NOT FOUND**
- [F13] `taxonomyPackages.xml`: **NOT FOUND**
- [R3] [F11]+[F12]+[F13] → ALL_20251101 は単なるフラットなディレクトリ構成であり、OASIS XML Catalog による自動 URL 解決は使えない。**URL→ローカルパスの変換はパーサーが自前で実装する必要がある**。
- [R4] 変換ルールは [F2] の通り単純なプレフィックス置換で済むため、catalog.xml がなくても実装は容易。

## 設計への影響（まとめ）

パーサーの DTS 解決モジュールは以下のように実装すべき:

```python
def resolve_schema_url(url: str, taxonomy_root: Path) -> Path | None:
    """スキーマ URL をローカルパスに解決する。"""
    EDINET_PREFIX = "http://disclosure.edinet-fsa.go.jp/taxonomy/"
    if url.startswith(EDINET_PREFIX):
        relative = url[len(EDINET_PREFIX):]
        return taxonomy_root / "taxonomy" / relative
    # XBRL.org 等の外部URLは None（ハードコード対応 or 無視）
    return None
```

## 検証

- [x] スクリプト再実行で同一結果が得られることを確認（2026-02-23）
- [x] 2026サンプル XSD 3件の存在を確認
- [x] ALL_20251101 内の全マッピングファイルの存在を確認
- [x] P-3.a.md [F3] のトヨタ import 一覧との整合性を確認
- [x] 仕様書（提出者別タクソノミ作成ガイドライン L.1736-1768）の import ルールとの整合性を確認
