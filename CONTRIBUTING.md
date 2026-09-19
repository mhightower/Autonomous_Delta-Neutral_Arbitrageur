# Contributing to Autonomous Delta-Neutral Arbitrageur

First off, thank you for considering contributing to this project! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the issue
- **Expected vs. actual behavior**
- **Environment details** (OS, Python version, etc.)
- **Relevant logs or error messages**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear use case** and problem being solved
- **Proposed solution** with examples if possible
- **Alternatives considered**
- **Impact on existing functionality**

### Pull Requests

1. **Fork** the repository and create your branch from `master`
2. **Follow TDD**: Write tests before implementing features
3. **Ensure tests pass**: Run `uv run pytest` locally
4. **Follow code style**: Run `uv run ruff check .` and `uv run ruff format .`
5. **Update documentation**: Modify README.md if needed
6. **Write clear commit messages**: Use conventional commit format (e.g., `feat:`, `fix:`, `chore:`)

## Development Setup

1. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/Autonomous_Delta-Neutral_Arbitrageur.git
   cd Autonomous_Delta-Neutral_Arbitrageur
   ```

2. **Create virtual environment:**
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

4. **Copy environment template:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Testing Guidelines

This project follows **Test-Driven Development (TDD)**:

1. **Write failing tests first** that define expected behavior
2. **Implement minimal code** to make tests pass
3. **Refactor** while keeping tests green
4. **Maintain coverage**: Target 75%+ overall

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_prices.py

# Run with verbose output
uv run pytest -v
```

## Code Style

- Follow **PEP 8** Python style guide
- Use **type hints** for function parameters and returns
- Write **docstrings** for public functions and classes
- Keep functions **small and focused**
- Use **meaningful variable names**

### Formatting and Linting

```bash
# Format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Run security scan
uv run bandit -r src

# Check for vulnerable dependencies
uv run pip-audit
```

## Commit Message Guidelines

Use conventional commit format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `chore:` Maintenance tasks
- `test:` Adding or updating tests
- `refactor:` Code refactoring

Examples:
```
feat: Add Binance futures exchange support
fix: Resolve race condition in order execution
docs: Update README with Docker deployment guide
chore: Upgrade dependencies to resolve CVEs
test: Add integration tests for audit workflow
```

## Project Structure

```
├── src/                    # Source code
│   ├── main.py            # Main application entry point
│   ├── db.py              # Database operations
│   └── dashboard.py       # Streamlit dashboard
├── tests/                 # Test suite
│   ├── conftest.py        # Shared test fixtures
│   ├── test_*.py          # Individual test modules
├── .github/
│   └── workflows/         # CI/CD pipelines
├── assets/                # Images and media
├── docs/                  # Additional documentation
└── pyproject.toml         # Project configuration
```

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions. We're here to build something great together! 🚀

---

Thank you for contributing! 🙏
