"""EDINET コードデータ品質監査テスト（data_audit）。"""
from __future__ import annotations

import pytest

from edinet.models.edinet_code import all_edinet_codes


@pytest.mark.data_audit
def test_listed_company_has_sec_code() -> None:
    listed = [entry for entry in all_edinet_codes() if entry.listing_status == "上場"]
    assert listed, "No listed entries found in EDINET code table."

    missing_count = sum(1 for entry in listed if not entry.sec_code)
    threshold = max(10, int(len(listed) * 0.01))
    assert missing_count <= threshold, (
        f"listed entries with missing sec_code: {missing_count} "
        f"(threshold={threshold}, listed={len(listed)})"
    )
