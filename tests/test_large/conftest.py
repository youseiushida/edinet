"""Large テスト共通の fixture。

EDINET API へのネットワークアクセスを伴うテスト用。
EDINET_API_KEY 環境変数が未設定の場合は自動スキップする。
"""
import os

import pytest

import edinet

LARGE_TEST_DATE = "2025-01-15"  # 水曜日、安定データ


@pytest.fixture(autouse=True)
def _require_api_key():
    """EDINET_API_KEY が未設定なら全 Large テストをスキップする。"""
    api_key = os.environ.get("EDINET_API_KEY")
    if not api_key:
        pytest.skip("EDINET_API_KEY not set")
    edinet.configure(api_key=api_key)
