import pytest
from unittest.mock import patch, MagicMock
from main import monitor_market, AgentState


@pytest.fixture
def sample_state():
    return {
        "symbols": ["BTC/USDT"],
        "latest_prices": {},
        "opportunity_found": False,
        "audit_report": None,
        "decision": "WAIT"
    }


@patch("main.log_event")
@patch("main.get_crypto_prices")
def test_monitor_market_opportunity_found(mock_get_prices, mock_log, sample_state, mock_prices):
    """Test that monitor detects a gap > 0.5%."""
    # binance: 65000, coinbase: 65200 (Diff 200. 200/65000 = ~0.3%)
    # Wait, let's use the fixture mock_prices which has:
    # BTC: 65000 vs 65200 (~0.3%) -> No op?
    # Let's force a larger gap for this test.
    
    high_gap_prices = {
        "binance": {"BTC/USDT": 65000.0},
        "coinbase": {"BTC/USDT": 66000.0}, # Gap ~1.5%
        "kraken": {"BTC/USDT": 65100.0},
    }
    
    # Mock the .invoke() method of the tool
    mock_get_prices.invoke.return_value = high_gap_prices

    result = monitor_market(sample_state)

    assert result["opportunity_found"] is True
    assert result["decision"] == "AUDIT"
    assert result["latest_prices"] == high_gap_prices
    mock_log.assert_called_once()
    assert mock_log.call_args[1]["event_type"] == "OPPORTUNITY"


@patch("main.log_event")
@patch("main.get_crypto_prices")
def test_monitor_market_no_opportunity(mock_get_prices, mock_log, sample_state, mock_prices_no_opportunity):
    """Test that monitor stays waiting if gap < 0.5%."""
    mock_get_prices.invoke.return_value = mock_prices_no_opportunity["BTC/USDT"]
    # Note: mock_prices_no_opportunity structure in conftest is nested by Symbol then Exchange
    # But main.py expects Exchange then Symbol. Let's manually construct correct input.
    
    # Using a tight spread
    tight_prices = {"binance": {"BTC/USDT": 100.0}, "coinbase": {"BTC/USDT": 100.1}}
    mock_get_prices.invoke.return_value = tight_prices

    result = monitor_market(sample_state)
    assert result["opportunity_found"] is False
    assert result["decision"] == "WAIT"