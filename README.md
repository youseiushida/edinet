# edinet

EDINET（金融庁の電子開示システム）の開示データを Python から簡単に扱うためのライブラリ。

XBRL のパース、財務諸表の組み立て、タクソノミの解析までをワンストップで提供します。

> **Status: Alpha** — API は安定していません。破壊的変更の可能性があります。

## Features

- **書類一覧の取得** — 日付・書類種別でフィルタして Filing 一覧を取得
- **XBRL パース** — Fact / Context / Unit を構造化オブジェクトとして抽出
- **DEI 抽出** — 会計基準（J-GAAP / IFRS / US-GAAP）、報告期間、企業属性を自動判別
- **財務諸表の組み立て** — PL / BS / CF を科目ラベル付きで取得（現在 J-GAAP のみ）
- **Linkbase 解析** — Presentation / Calculation / Definition の木構造をパース
- **タクソノミラベル解決** — 標準タクソノミ + 提出者タクソノミのラベルを自動解決
- **Async 対応** — 全 I/O 操作に sync / async ペアを提供

## Installation

```bash
pip install edinet
```

## Quick Start

```python
import edinet

# API キーの設定
edinet.configure(api_key="YOUR_API_KEY")

# 書類一覧の取得
filings = edinet.documents("2025-06-26", doc_type="120")  # 有価証券報告書

# XBRL から財務諸表を取得
for filing in filings:
    if filing.has_xbrl:
        stmts = filing.xbrl()
        pl = stmts.income_statement()
        bs = stmts.balance_sheet()
        for item in pl.items:
            print(f"{item.label_ja}: {item.value:,}")
        break
```

### 低レベル API

```python
from edinet.xbrl import parse_xbrl_facts, extract_dei
from edinet.xbrl.contexts import ContextCollection, structure_contexts
from edinet.xbrl.units import structure_units
from edinet.xbrl.linkbase import parse_presentation_linkbase

# XBRL インスタンスのパース
xbrl_path, xbrl_bytes = filing.fetch()
parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)

# DEI（企業属性）の抽出
dei = extract_dei(parsed.facts)
print(dei.filer_name_ja)          # 企業名
print(dei.accounting_standards)   # AccountingStandard.JAPAN_GAAP
print(dei.security_code)          # 証券コード

# Context / Unit の構造化
contexts = ContextCollection(structure_contexts(parsed.contexts))
units = structure_units(parsed.units)

# フィルタチェーン
consolidated = contexts.filter_consolidated().filter_no_extra_dimensions()
```

## Requirements

- Python >= 3.12
- EDINET API キー（[EDINET](https://disclosure.edinet-fsa.go.jp/) で取得）

## License

MIT
