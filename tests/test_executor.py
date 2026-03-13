import pytest
import os
from unittest.mock import patch, MagicMock
from main import execute_trade_node


@pytest.fixture
def execute_state():
    return {
        "symbols": ["BTC/USDT"],
        "latest_prices": {},
        "opportunity_found": True,
        "audit_report": "GO for trade",
        "decision": "EXECUTE",
        # spread_pct might be missing in TypedDict but main.py tries to read it from list of dicts?
        # main.py logic: spread = next((e["spread_pct"] ...), 0.0). 
        # We pass it here to see if it picks it up if we treat state as dict.
        "spread_pct": 1.5 
    }


@patch.dict(os.environ, {"KRAKEN_API_KEY": "fake_key", "KRAKEN_SECRET": "fake_secret"})
@patch("main.log_event")
@patch("main.ccxt")
def test_execute_trade_success(mock_ccxt, mock_log, execute_state):
    """Test successful trade execution."""
    mock_exchange = MagicMock()
    mock_ccxt.kraken.return_value = mock_exchange
    
    mock_order = {"id": "12345", "status": "closed"}
    mock_exchange.create_market_buy_order.return_value = mock_order

    result = execute_trade_node(execute_state)

    mock_exchange.set_sandbox_mode.assert_called_with(True)
    mock_exchange.create_market_buy_order.assert_called_with("BTC/USDT", 0.01)
    
    assert result["decision"] == "EXECUTED"
    assert "Success" in result["audit_report"]
    mock_log.assert_called()


@patch.dict(os.environ, {"KRAKEN_API_KEY": "fake_key", "KRAKEN_SECRET": "fake_secret"})
@patch("main.log_event")
@patch("main.ccxt")
def test_execute_trade_aborted(mock_ccxt, mock_log, execute_state):
    """Test execution aborts if audit report is missing GO."""
    execute_state["audit_report"] = "NO-GO, too risky"
    result = execute_trade_node(execute_state)
    assert result["decision"] == "ABORTED"