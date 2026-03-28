from unittest.mock import MagicMock, patch
import signal
import threading

import pytest

from main import (
    build_trading_bot,
    execute_trade_node,
    get_loop_interval_seconds,
    main,
    register_signal_handlers,
    run_trading_loop,
)


def test_graph_end_to_end_executes_trade(monkeypatch, state_factory):
    initial_state = state_factory(
        symbols=["BTC/USDT"],
        decision="WAIT",
        run_id="run-e2e",
        cycle_id="cycle-e2e",
    )

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
    assert all(
        "run_id=run-e2e" in call.kwargs["message"] for call in mock_log.call_args_list
    )
    assert all(
        "cycle_id=cycle-e2e" in call.kwargs["message"]
        for call in mock_log.call_args_list
    )


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
    assert "run_id=test-run" in mock_log.call_args.kwargs["message"]


def test_get_metrics_log_every_cycles_invalid_value_falls_back(monkeypatch):
    from main import get_metrics_log_every_cycles

    monkeypatch.setenv("METRICS_LOG_EVERY_CYCLES", "invalid")

    assert get_metrics_log_every_cycles() == 5


def test_get_loop_interval_seconds_invalid_value_falls_back(monkeypatch):
    monkeypatch.setenv("LOOP_INTERVAL_SECONDS", "invalid")

    assert get_loop_interval_seconds() == 60.0


def test_register_signal_handlers_sets_stop_event_on_signal():
    stop_event = threading.Event()
    registered_handlers = {}

    def fake_signal(sig, handler):
        registered_handlers[sig] = handler
        return signal.SIG_DFL

    with patch("main.signal.signal", side_effect=fake_signal):
        previous_handlers = register_signal_handlers(stop_event)

    assert signal.SIGTERM in previous_handlers
    assert signal.SIGTERM in registered_handlers

    registered_handlers[signal.SIGTERM](signal.SIGTERM, None)
    assert stop_event.is_set() is True


def test_run_trading_loop_initializes_and_runs_single_iteration():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "decision": "WAIT",
        "audit_duration_ms": 0.0,
        "execution_duration_ms": 0.0,
    }
    stop_event = threading.Event()

    with (
        patch("main.init_db") as mock_init,
        patch("main.build_trading_bot", return_value=mock_graph),
        patch("main.get_loop_interval_seconds", return_value=0.01),
        patch("main.get_metrics_log_every_cycles", return_value=1),
        patch("main.logger.info") as mock_logger,
    ):
        run_trading_loop(stop_event, max_cycles=1)

    mock_init.assert_called_once()
    mock_graph.invoke.assert_called_once()
    assert any(
        "event=metrics_summary" in call.args[0] for call in mock_logger.call_args_list
    )


def test_main_handles_keyboard_interrupt_gracefully():
    with (
        patch("main.register_signal_handlers", return_value={}) as mock_register,
        patch("main.restore_signal_handlers") as mock_restore,
        patch("main.run_trading_loop", side_effect=KeyboardInterrupt),
    ):
        main()

    mock_register.assert_called_once()
    mock_restore.assert_called_once_with({})
