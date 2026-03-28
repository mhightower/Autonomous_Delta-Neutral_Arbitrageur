from main import monitor_market


def test_monitor_market_opportunity_found(
    state_factory, mock_get_crypto_prices_tool, mock_log_event, mock_prices
):
    """Test that monitor detects a gap > 0.5%."""
    sample_state = state_factory()

    high_gap_prices = {
        "binance": {"BTC/USDT": 65000.0},
        "coinbase": {"BTC/USDT": 66000.0},  # Gap ~1.5%
        "kraken": {"BTC/USDT": 65100.0},
    }

    mock_get_crypto_prices_tool.invoke.return_value = high_gap_prices

    result = monitor_market(sample_state)

    assert result["opportunity_found"] is True
    assert result["decision"] == "AUDIT"
    assert result["latest_prices"] == high_gap_prices
    assert result["spread_pct"] > 0.5
    mock_log_event.assert_called_once()
    assert mock_log_event.call_args[1]["event_type"] == "OPPORTUNITY"


def test_monitor_market_no_opportunity(
    state_factory,
    mock_get_crypto_prices_tool,
    mock_log_event,
    mock_prices_no_opportunity,
):
    """Test that monitor stays waiting if gap < 0.5%."""
    sample_state = state_factory()

    tight_prices = {"binance": {"BTC/USDT": 100.0}, "coinbase": {"BTC/USDT": 100.1}}
    mock_get_crypto_prices_tool.invoke.return_value = tight_prices

    result = monitor_market(sample_state)
    assert result["opportunity_found"] is False
    assert result["decision"] == "WAIT"
    assert result["spread_pct"] < 0.5
