# GEMINI.md - Autonomous Delta-Neutral Arbitrageur

## Project Overview
This project, **Autonomous Delta-Neutral Arbitrageur**, is a sophisticated trading bot or platform designed for delta-neutral arbitrage. Delta-neutral strategies aim to profit from price discrepancies (arbitrage) while maintaining a neutral exposure to the underlying asset's price movements, typically by hedging positions in spot and derivative markets.

The project uses **uv** for efficient Python project management, including environment creation and dependency resolution.

### Core Technologies
- **Language:** Python 3.12+
- **Project Manager:** `uv`
- **Domain:** Quantitative Finance / Crypto Arbitrage

## Building and Running
The project is managed with `uv`.

### Environment Setup
1.  **Create and activate the virtual environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    ```
2.  **Install dependencies:**
    ```bash
    uv sync
    ```
3.  **Add new dependencies:**
    ```bash
    uv add <package-name>
    ```

### Execution
- **Run the main application:**
    ```bash
    uv run main.py
    ```
- **Run tests:**
    ```bash
    uv run pytest
    ```

## Development Conventions
To ensure consistency and quality as this project grows, the following conventions are recommended:

- **Modular Architecture:** Separate exchange connectors, strategy logic, risk management, and order execution into distinct modules.
- **Type Safety:** Utilize Python's type hinting for robust code, especially for financial calculations.
- **Comprehensive Logging:** Implement detailed logging for all trading activities, errors, and state changes.
- **Testing-First:** Prioritize unit tests for strategy logic and integration tests for exchange APIs.
- **Security:** Rigorously protect API keys and sensitive configuration (e.g., using `.env` files and never committing them).

## Key Files & Directories
- `pyproject.toml`: Project metadata and dependencies managed by `uv`.
- `main.py`: Entry point for the application.
- `src/`: Core source code (TODO: Create this directory).
- `tests/`: Automated test suite (TODO: Create this directory).
- `config/`: Configuration files (e.g., `.yaml`, `.json`).
- `.env.example`: Template for environment variables.
