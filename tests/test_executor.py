from unittest.mock import MagicMock
from main import DEFAULT_ORDER_AMOUNT, execute_trade_node


def test_execute_trade_success(
    state_factory, fake_kraken_env, mock_ccxt_module, mock_log_event
):
    """Test successful trade execution using the detected opportunity symbol."""
    execute_state = state_factory(
        symbols=["BTC/USDT", "ETH/USDT"],
        opportunity_found=True,
        audit_report="GO for trade",
        decision="EXECUTE",
        spread_pct=1.5,
        best_symbol="ETH/USDT",
        best_buy_exchange="binance",
        best_sell_exchange="coinbase",
        best_buy_price=3500.0,
        best_sell_price=3552.5,
    )
    mock_exchange = MagicMock()
    mock_ccxt_module.kraken.return_value = mock_exchange

    mock_order = {"id": "12345", "status": "closed"}
    mock_exchange.create_market_buy_order.return_value = mock_order

    result = execute_trade_node(execute_state)

    mock_exchange.set_sandbox_mode.assert_called_with(True)
    mock_exchange.create_market_buy_order.assert_called_with(
        "ETH/USDT", DEFAULT_ORDER_AMOUNT
    )

    assert result["decision"] == "EXECUTED"
    assert "Success" in result["audit_report"]
    assert mock_log_event.call_args.kwargs["profit_usdt"] == 0.42
    mock_log_event.assert_called()


def test_execute_trade_aborted(
    state_factory, fake_kraken_env, mock_ccxt_module, mock_log_event
):
    """Test execution aborts if audit report is missing GO."""
    execute_state = state_factory(
        opportunity_found=True,
        audit_report="NO-GO, too risky",
        decision="EXECUTE",
        spread_pct=1.5,
    )
    execute_state["audit_report"] = "NO-GO, too risky"
    result = execute_trade_node(execute_state)
    assert result["decision"] == "ABORTED"
    mock_ccxt_module.kraken.assert_not_called()
