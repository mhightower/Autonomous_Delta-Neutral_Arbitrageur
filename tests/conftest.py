import pytest


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
