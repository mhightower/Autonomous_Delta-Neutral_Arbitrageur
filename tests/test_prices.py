import pytest
from unittest.mock import MagicMock, patch
from main import get_crypto_prices


@patch("main.ccxt")
def test_get_crypto_prices_success(mock_ccxt):
    """Test fetching prices successfully from multiple exchanges."""
    # Setup mocks for each exchange
    mock_binance = MagicMock()
    mock_coinbase = MagicMock()
    mock_kraken = MagicMock()

    mock_ccxt.binanceus.return_value = mock_binance
    mock_ccxt.coinbase.return_value = mock_coinbase
    mock_ccxt.kraken.return_value = mock_kraken

    # Mock fetch_tickers behavior
    mock_binance.fetch_tickers.return_value = {"BTC/USDT": {"close": 65000.0}}
    mock_coinbase.fetch_tickers.return_value = {"BTC/USDT": {"close": 65100.0}}
    mock_kraken.fetch_tickers.return_value = {"BTC/USDT": {"close": 65050.0}}

    symbols = ["BTC/USDT"]
    result = get_crypto_prices.invoke({"symbols": symbols})

    assert "binance" in result
    assert "coinbase" in result
    assert "kraken" in result
    assert result["binance"]["BTC/USDT"] == 65000.0
    assert result["coinbase"]["BTC/USDT"] == 65100.0


@patch("main.ccxt")
def test_get_crypto_prices_error_handling(mock_ccxt):
    """Test that individual exchange errors are caught and reported."""
    mock_binance = MagicMock()
    mock_ccxt.binanceus.return_value = mock_binance
    mock_binance.fetch_tickers.side_effect = Exception("Network Error")

    result = get_crypto_prices.invoke({"symbols": ["BTC/USDT"]})
    assert "Error: Network Error" in str(result["binance"])