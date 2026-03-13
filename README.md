# Autonomous Delta-Neutral Arbitrageur

This project is a sophisticated trading bot designed for delta-neutral arbitrage strategies in the cryptocurrency markets. It aims to profit from price discrepancies between spot and derivatives markets while maintaining a neutral exposure to the underlying asset's price movements.

## 🚀 Core Technologies

- **Language:** Python 3.12+
- **Project Manager:** `uv`
- **Domain:** Quantitative Finance / Crypto Arbitrage

## ✨ Features

- **Delta-Neutral Strategy:** Implements a core arbitrage strategy to minimize market risk.
- **Modular Architecture:** Separates concerns for exchange connectors, strategy logic, risk management, and order execution.
- **Test-Driven Development:** Emphasizes a robust testing culture to ensure reliability.
- **Extensible:** Designed to be extended with new exchange integrations and trading strategies.

## 🏁 Getting Started

### Prerequisites

- Python 3.12+
- `uv` package manager

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/Autonomous_Delta-Neutral_Arbitrageur.git
    cd Autonomous_Delta-Neutral_Arbitrageur
    ```

2.  **Create and activate the virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    uv sync
    ```

### Configuration

1.  Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
2.  Add your exchange API keys and any other required environment variables to the `.env` file.

### Running the Bot

- **Run the main application:**
    ```bash
    uv run main.py
    ```

## 🧪 Testing

This project follows Test-Driven Development (TDD).

- **Run all tests:**

    ```bash
    uv run pytest
    ```

- **Run a specific test file:**

    ```bash
    uv run pytest tests/test_prices.py
    ```

- **Run tests with verbose output:**

    ```bash
    uv run pytest -v
    ```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE.md` file for details.
