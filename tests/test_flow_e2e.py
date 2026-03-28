from unittest.mock import MagicMock, patch

import pytest

from main import build_trading_bot, execute_trade_node, main


def test_graph_end_to_end_executes_trade(monkeypatch, state_factory):
    initial_state = state_factory(symbols=["BTC/USDT"], decision="WAIT")

    high_gap_prices = {
        "binance": {"BTC/USDT": 65000.0},
        "coinbase": {"BTC/USDT": 66000.0},
        "kraken": {"BTC/USDT": 65100.0},
    }

    mock_audit_response = MagicMock()
    mock_audit_response.content = "GO - profitable after fees"

    mock_exchange = MagicMock()
    mock_exchange.create_market_buy_order.return_value = {"id": "order-123"}

    monkeypatch.setenv("KRAKEN_API_KEY", "fake_key")
    monkeypatch.setenv("KRAKEN_SECRET", "fake_secret")

    with (
        patch("main.get_crypto_prices") as mock_prices,
        patch("main._get_auditor_llm") as mock_auditor,
        patch("main.ccxt") as mock_ccxt,
        patch("main.log_event") as mock_log,
    ):
        mock_prices.invoke.return_value = high_gap_prices
        mock_auditor.return_value.invoke.return_value = mock_audit_response
        mock_ccxt.kraken.return_value = mock_exchange

        result = build_trading_bot().invoke(initial_state)

    assert result["decision"] == "EXECUTED"
    assert "Success!" in result["audit_report"]
    mock_log.assert_called()


def test_graph_degraded_market_data_waits(state_factory):
    initial_state = state_factory(symbols=["BTC/USDT"], decision="WAIT")

    degraded_prices = {
        "binance": "Error: exchange unavailable",
        "coinbase": "Error: timeout",
        "kraken": "Error: rate limit",
    }

    with (
        patch("main.get_crypto_prices") as mock_prices,
        patch("main._get_auditor_llm") as mock_auditor,
        patch("main.ccxt") as mock_ccxt,
        patch("main.log_event") as mock_log,
    ):
        mock_prices.invoke.return_value = degraded_prices

        result = build_trading_bot().invoke(initial_state)

    assert result["decision"] == "WAIT"
    mock_auditor.assert_not_called()
    mock_ccxt.kraken.assert_not_called()
    mock_log.assert_called_once()


def test_execute_trade_missing_env_vars_raises(state_factory, monkeypatch):
    execute_state = state_factory(
        opportunity_found=True,
        decision="EXECUTE",
        audit_report="GO - approved",
        spread_pct=1.0,
    )

    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_SECRET", raising=False)

    with patch("main.log_event") as mock_log:
        with pytest.raises(RuntimeError, match="Missing required environment variable"):
            execute_trade_node(execute_state)

    mock_log.assert_called_once()


def test_main_initializes_and_runs_single_iteration_before_interrupt():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"decision": "WAIT"}

    with (
        patch("main.init_db") as mock_init,
        patch("main.build_trading_bot", return_value=mock_graph),
        patch("main.time.sleep", side_effect=KeyboardInterrupt),
    ):
        with pytest.raises(KeyboardInterrupt):
            main()

    mock_init.assert_called_once()
    mock_graph.invoke.assert_called_once()