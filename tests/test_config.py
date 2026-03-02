"""_config.py のテスト。"""
from edinet._config import _Config, configure, get_config
from edinet.exceptions import EdinetConfigError
import pytest


def test_default_config_has_no_api_key():
    """初期状態では API キーが未設定であること。"""
    config = _Config()
    assert config.api_key is None


def test_ensure_api_key_raises_when_not_set():
    """API キー未設定で ensure_api_key() を呼ぶと EdinetConfigError。"""
    config = _Config()
    with pytest.raises(EdinetConfigError):
        config.ensure_api_key()


def test_api_key_not_in_repr():
    """API キーが repr() に含まれないこと（漏洩防止）。"""
    config = _Config(api_key="secret-key-12345")
    assert "secret-key-12345" not in repr(config)


def test_configure_sets_api_key():
    """configure() で API キーが設定されること。"""
    configure(api_key="test-key")
    config = get_config()
    assert config.api_key == "test-key"
    # クリーンアップは conftest.py の autouse fixture が行う


def test_configure_clears_api_key_with_none():
    """configure(api_key=None) で API キーをクリアできること。"""
    configure(api_key="test-key")
    assert get_config().api_key == "test-key"
    configure(api_key=None)
    assert get_config().api_key is None


def test_configure_no_args_changes_nothing():
    """configure() を引数なしで呼んでも設定が変わらないこと。"""
    configure(api_key="test-key", rate_limit=0.5)
    configure()  # 引数なし → 何も変わらない
    config = get_config()
    assert config.api_key == "test-key"
    assert config.rate_limit == 0.5


def test_configure_sets_rate_limit():
    """configure() でレート制限が変更できること。"""
    configure(rate_limit=0.5)
    config = get_config()
    assert config.rate_limit == 0.5


# --- ランタイムバリデーション ---

def test_configure_rejects_none_for_base_url():
    """base_url に None を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(base_url=None)


def test_configure_rejects_none_for_timeout():
    """timeout に None を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(timeout=None)


def test_configure_rejects_negative_timeout():
    """timeout に負の値を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(timeout=-1)


def test_configure_rejects_zero_max_retries():
    """max_retries に 0 を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(max_retries=0)


def test_configure_rejects_negative_rate_limit():
    """rate_limit に負の値を渡すと EdinetConfigError。"""
    with pytest.raises(EdinetConfigError):
        configure(rate_limit=-1)


# --- クライアント無効化 ---

def test_configure_invalidates_client_on_base_url_change():
    """base_url 変更時に httpx.Client が破棄されること。"""
    from edinet import _http

    # クライアントを生成させる（内部状態を作る）
    configure(api_key="dummy")
    _http._get_client()
    assert _http._client is not None

    # base_url を変更 → クライアントが破棄される
    configure(base_url="https://example.com")
    assert _http._client is None


# --- トップレベルエクスポート ---


def test_top_level_exports_statements():
    """Statements が edinet パッケージからインポートできること。"""
    from edinet import Statements
    assert Statements is not None


def test_top_level_exports_financial_statement():
    """FinancialStatement が edinet パッケージからインポートできること。"""
    from edinet import FinancialStatement
    assert FinancialStatement is not None


def test_top_level_exports_line_item():
    """LineItem が edinet パッケージからインポートできること。"""
    from edinet import LineItem
    assert LineItem is not None