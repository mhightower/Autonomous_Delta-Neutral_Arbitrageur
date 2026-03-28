import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Exchange price fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_prices():
    """Sample price data across three exchanges for BTC/USDT and ETH/USDT."""
    return {
        "BTC/USDT": {
            "binance": 65000.0,
            "coinbase": 65200.0,
            "kraken": 65100.0,
        },
        "ETH/USDT": {
            "binance": 3500.0,
            "coinbase": 3510.0,
            "kraken": 3505.0,
        },
    }


@pytest.fixture
def mock_prices_no_opportunity():
    """Price data where spread is below the 0.5% threshold."""
    return {
        "BTC/USDT": {
            "binance": 65000.0,
            "coinbase": 65010.0,  # ~0.015% spread
            "kraken": 65005.0,
        },
    }


# ---------------------------------------------------------------------------
# LLM / agent fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_monitor_go_response():
    """Simulates the monitor agent returning an opportunity found."""
    return "OPPORTUNITY FOUND: BTC/USDT spread of 0.31% between binance and coinbase."


@pytest.fixture
def mock_audit_go_response():
    """Simulates the audit agent approving a trade."""
    return "GO — net profit after 0.3% fees: 0.01%."


@pytest.fixture
def mock_audit_nogo_response():
    """Simulates the audit agent rejecting a trade."""
    return "NO-GO — spread insufficient after fees."


# ---------------------------------------------------------------------------
# Shared state and patch fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def state_factory():
    """Builds a default AgentState and allows per-test overrides."""

    def _factory(**overrides):
        state = {
            "symbols": ["BTC/USDT"],
            "latest_prices": {},
            "spread_pct": 0.0,
            "opportunity_found": False,
            "audit_report": None,
            "run_id": "test-run",
            "cycle_id": "test-cycle",
            "audit_duration_ms": 0.0,
            "execution_duration_ms": 0.0,
            "decision": "WAIT",
        }
        state.update(overrides)
        return state

    return _factory


@pytest.fixture
def fake_kraken_env(monkeypatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "fake_key")
    monkeypatch.setenv("KRAKEN_SECRET", "fake_secret")


@pytest.fixture
def mock_log_event():
    with patch("main.log_event") as mock:
        yield mock


@pytest.fixture
def mock_ccxt_module():
    with patch("main.ccxt") as mock:
        yield mock


@pytest.fixture
def mock_get_crypto_prices_tool():
    with patch("main.get_crypto_prices") as mock:
        yield mock


@pytest.fixture
def mock_auditor_llm():
    with patch("main.auditor_llm") as mock:
        yield mock
