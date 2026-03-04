"""V030 等価性検証スクリプト。

旧ロジック（extract.py.bak）と新ロジック（extract.py）が同一入力に対して
同一の結果を返すことを検証する。

使用方法::

    uv run python tools/v030_equivalence_check.py
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# 旧 extract.py.bak を動的インポート
# ---------------------------------------------------------------------------

_BAK_PATH = Path(__file__).resolve().parent.parent / "src" / "edinet" / "financial" / "extract.py.bak"

if not _BAK_PATH.exists():
    print(f"ERROR: {_BAK_PATH} が見つかりません。")
    sys.exit(1)

spec = importlib.util.spec_from_file_location(
    "extract_bak", _BAK_PATH,
    submodule_search_locations=[],
)
if spec is None or spec.loader is None:
    # .bak 拡張子対策: SourceFileLoader を直接使用
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("extract_bak", str(_BAK_PATH))
    spec = importlib.util.spec_from_loader("extract_bak", loader)
    assert spec is not None and spec.loader is not None

extract_bak = importlib.util.module_from_spec(spec)
sys.modules["extract_bak"] = extract_bak  # dataclass が __module__ 参照で必要
spec.loader.exec_module(extract_bak)

old_extract_values = extract_bak.extract_values
OldExtractedValue = extract_bak.ExtractedValue

# 新しいモジュール
from edinet.financial.extract import extract_values as new_extract_values  # noqa: E402
from edinet.financial.standards.canonical_keys import CK  # noqa: E402
from edinet.financial.statements import Statements  # noqa: E402
from edinet.models.financial import LineItem  # noqa: E402
from edinet.xbrl.contexts import DurationPeriod, InstantPeriod  # noqa: E402
from edinet.xbrl.taxonomy import LabelInfo, LabelSource  # noqa: E402

# ---------------------------------------------------------------------------
# テストデータ構築
# ---------------------------------------------------------------------------

_NS = "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2025-11-01/jpcrp_cor"
_DUR = DurationPeriod(start_date=date(2024, 4, 1), end_date=date(2025, 3, 31))
_INST = InstantPeriod(instant=date(2025, 3, 31))


def _label(text: str, lang: str = "ja") -> LabelInfo:
    return LabelInfo(text=text, role="http://www.xbrl.org/2003/role/label",
                     lang=lang, source=LabelSource.STANDARD)


def _item(local_name: str, value: Decimal | None = Decimal("100"),
          period: DurationPeriod | InstantPeriod | None = None,
          order: int = 0) -> LineItem:
    if period is None:
        period = _DUR
    return LineItem(
        concept=f"{{{_NS}}}{local_name}",
        namespace_uri=_NS, local_name=local_name,
        label_ja=_label("テスト"), label_en=_label("test", "en"),
        value=value, unit_ref="JPY",
        decimals=-6 if value else None,
        context_id="CurrentYearDuration", period=period,
        entity_id="E00001", dimensions=(), is_nil=False,
        source_line=1, order=order,
    )


# ---------------------------------------------------------------------------
# テストケース
# ---------------------------------------------------------------------------

TESTS: list[tuple[str, Statements, list[str] | None]] = [
    (
        "Summary のみ",
        Statements(_items=(
            _item("NetSalesSummaryOfBusinessResults", Decimal("1000000")),
            _item("OrdinaryIncomeLossSummaryOfBusinessResults", Decimal("200000"), order=1),
        )),
        [CK.REVENUE, CK.ORDINARY_INCOME],
    ),
    (
        "Statement のみ（PL 本体）",
        Statements(_items=(
            _item("OperatingIncome", Decimal("500000")),
            _item("Goodwill", Decimal("300000"), period=_INST, order=1),
        )),
        [CK.OPERATING_INCOME, CK.GOODWILL],
    ),
    (
        "Summary + Statement 混在",
        Statements(_items=(
            _item("NetSalesSummaryOfBusinessResults", Decimal("1000000")),
            _item("OperatingIncome", Decimal("500000"), order=1),
        )),
        [CK.REVENUE, CK.OPERATING_INCOME],
    ),
    (
        "Summary 優先（同一 CK）",
        Statements(_items=(
            _item("NetSales", Decimal("999999")),
            _item("NetSalesSummaryOfBusinessResults", Decimal("1000000"), order=1),
        )),
        [CK.REVENUE],
    ),
    (
        "keys=None（全科目走査）",
        Statements(_items=(
            _item("NetSalesSummaryOfBusinessResults", Decimal("1000000")),
            _item("TotalAssetsSummaryOfBusinessResults", Decimal("5000000"), period=_INST, order=1),
            _item("CustomFilerItem", Decimal("50000"), order=2),
        )),
        None,
    ),
    (
        "空 Statements",
        Statements(_items=()),
        [CK.REVENUE],
    ),
    (
        "空 Statements + keys=None",
        Statements(_items=()),
        None,
    ),
    (
        "R&D（注記セクション）",
        Statements(_items=(
            _item("ResearchAndDevelopmentExpensesSGA", Decimal("160246000")),
        )),
        [CK.RD_EXPENSES],
    ),
]


# ---------------------------------------------------------------------------
# 検証
# ---------------------------------------------------------------------------

def _compare(test_name: str, stmts: Statements, keys: list[str] | None) -> bool:
    """旧新の出力を比較し、等価であれば True を返す。"""
    old_result = old_extract_values(stmts, keys)
    new_result = new_extract_values(stmts, keys)

    if set(old_result.keys()) != set(new_result.keys()):
        print(f"  FAIL [{test_name}]: キー集合が異なる")
        print(f"    old: {set(old_result.keys())}")
        print(f"    new: {set(new_result.keys())}")
        return False

    ok = True
    for ck in old_result:
        old_ev = old_result[ck]
        new_ev = new_result[ck]

        if old_ev is None and new_ev is None:
            continue
        if (old_ev is None) != (new_ev is None):
            print(f"  FAIL [{test_name}]: {ck} — old={old_ev}, new={new_ev}")
            ok = False
            continue

        assert old_ev is not None and new_ev is not None
        if old_ev.canonical_key != new_ev.canonical_key:
            print(f"  FAIL [{test_name}]: {ck} canonical_key — old={old_ev.canonical_key}, new={new_ev.canonical_key}")
            ok = False
        if old_ev.value != new_ev.value:
            print(f"  FAIL [{test_name}]: {ck} value — old={old_ev.value}, new={new_ev.value}")
            ok = False
        if old_ev.item is not new_ev.item:
            print(f"  FAIL [{test_name}]: {ck} item — 異なるオブジェクト")
            ok = False

    return ok


def main() -> None:
    print("V030 等価性検証")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_name, stmts, keys in TESTS:
        try:
            if _compare(test_name, stmts, keys):
                print(f"  PASS: {test_name}")
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR [{test_name}]: {e}")
            failed += 1

    print("=" * 60)
    print(f"結果: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
