from unittest.mock import MagicMock
from main import audit_trade


def test_audit_trade_go(
    state_factory, mock_auditor_llm, mock_log_event, mock_audit_go_response
):
    """Test auditor giving a GO signal."""
    audit_state = state_factory(
        latest_prices={
            "binance": {"BTC/USDT": 65000},
            "coinbase": {"BTC/USDT": 66000},
        },
        opportunity_found=True,
        decision="AUDIT",
    )
    mock_response = MagicMock()
    mock_response.content = mock_audit_go_response
    mock_auditor_llm.invoke.return_value = mock_response

    result = audit_trade(audit_state)
    assert "GO" in result["audit_report"]
    assert result["decision"] == "EXECUTE"
    mock_log_event.assert_called_once()


def test_audit_trade_nogo(
    state_factory, mock_auditor_llm, mock_log_event, mock_audit_nogo_response
):
    """Test auditor giving a NO-GO signal."""
    audit_state = state_factory(
        latest_prices={
            "binance": {"BTC/USDT": 65000},
            "coinbase": {"BTC/USDT": 66000},
        },
        opportunity_found=True,
        decision="AUDIT",
    )
    mock_response = MagicMock()
    mock_response.content = mock_audit_nogo_response
    mock_auditor_llm.invoke.return_value = mock_response

    result = audit_trade(audit_state)
    assert result["decision"] == "WAIT"
    mock_log_event.assert_called_once()
