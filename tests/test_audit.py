import pytest
from unittest.mock import patch, MagicMock
from main import audit_trade


@pytest.fixture
def audit_state():
    return {
        "symbols": ["BTC/USDT"],
        "latest_prices": {"binance": {"BTC/USDT": 65000}, "coinbase": {"BTC/USDT": 66000}},
        "opportunity_found": True,
        "audit_report": None,
        "decision": "AUDIT"
    }


@patch("main.log_event")
@patch("main.auditor_llm")
def test_audit_trade_go(mock_llm, mock_log, audit_state, mock_audit_go_response):
    """Test auditor giving a GO signal."""
    mock_response = MagicMock()
    mock_response.content = mock_audit_go_response
    mock_llm.invoke.return_value = mock_response

    result = audit_trade(audit_state)
    assert "GO" in result["audit_report"]
    assert result["decision"] == "EXECUTE"


@patch("main.log_event")
@patch("main.auditor_llm")
def test_audit_trade_nogo(mock_llm, mock_log, audit_state, mock_audit_nogo_response):
    """Test auditor giving a NO-GO signal."""
    mock_response = MagicMock()
    mock_response.content = mock_audit_nogo_response
    mock_llm.invoke.return_value = mock_response

    result = audit_trade(audit_state)
    assert result["decision"] == "WAIT"