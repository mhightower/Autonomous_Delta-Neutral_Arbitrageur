# Architecture Documentation

## Overview

The Autonomous Delta-Neutral Arbitrageur is a multi-agent AI system designed to identify and execute cryptocurrency arbitrage opportunities across multiple exchanges. The system uses LangGraph to orchestrate a workflow of monitor, audit, and execute stages.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Main Application                          │
│                         (src/main.py)                           │
└────────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
      ┌──────────────────────────────────┐
      │      LangGraph Workflow          │
      │   (State-based Agent Graph)      │
      └──────────┬───────────────────────┘
                 │
        ┌────────┴────────┬──────────────┐
        ▼                 ▼              ▼
   ┌─────────┐      ┌──────────┐   ┌──────────┐
   │ Monitor │      │ Auditor  │   │ Executor │
   │  Agent  │─────▶│  Agent   │──▶│  Agent   │
   └────┬────┘      └────┬─────┘   └────┬─────┘
        │                │              │
        ▼                ▼              ▼
   ┌─────────────────────────────────────────┐
   │         Exchange APIs (CCXT)             │
   │  Binance US │ Coinbase │ Kraken         │
   └─────────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  SQLite DB     │
            │  (Event Log)   │
            └────────┬───────┘
                     │
                     ▼
            ┌────────────────┐
            │   Streamlit    │
            │   Dashboard    │
            └────────────────┘
```

## Core Components

### 1. Monitor Agent (`monitor_market`)

**Purpose:** Continuously scans multiple exchanges for price discrepancies.

**Responsibilities:**
- Fetch real-time ticker data from Binance US, Coinbase, and Kraken
- Calculate spread percentages across exchange pairs
- Identify the best buy/sell opportunity
- Determine if spread exceeds profitability threshold (0.5%)

**Input:** List of trading symbols (e.g., `["BTC/USDT", "ETH/USDT"]`)

**Output:** `AgentState` with:
- Latest prices from all exchanges
- Maximum spread percentage found
- Best buy/sell exchange pair
- Opportunity flag (true if spread > 0.5%)

**Implementation:**
```python
def monitor_market(state: AgentState) -> AgentState:
    # Fetch prices using get_crypto_prices tool
    prices = get_crypto_prices.invoke({"symbols": state["symbols"]})

    # Calculate max spread
    spread_pct, symbol, buy_ex, sell_ex, buy_price, sell_price = calculate_spread(
        prices
    )

    # Update state
    state["spread_pct"] = spread_pct
    state["opportunity_found"] = spread_pct > 0.5
    ...
    return state
```

### 2. Auditor Agent (`audit_trade`)

**Purpose:** Evaluates whether a detected opportunity is profitable after fees.

**Responsibilities:**
- Receive opportunity details from Monitor
- Calculate net profit after exchange fees (0.3% total)
- Use LLM (Anthropic Claude) to make GO/NO-GO decision
- Log audit decision and reasoning

**Input:** `AgentState` with opportunity details

**Output:** Updated `AgentState` with:
- Audit report (GO or NO-GO decision)
- Audit duration (latency tracking)
- Decision reasoning

**Fee Calculation:**
```python
TOTAL_FEE_RATE = 0.003  # 0.3% total (0.15% buy + 0.15% sell)
net_profit = spread_pct - (TOTAL_FEE_RATE * 100)
```

**LLM Integration:**
```python
auditor_llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
response = auditor_llm.invoke(
    [
        ("system", "You are an expert crypto arbitrage auditor..."),
        ("user", f"Spread: {spread_pct}%, Net profit: {net_profit}%..."),
    ]
)
```

### 3. Executor Agent (`execute_trade`)

**Purpose:** Executes approved trades in Kraken sandbox environment.

**Responsibilities:**
- Place market buy order on buy exchange
- Place market sell order on sell exchange
- Log execution results and estimated profit
- Handle API errors gracefully

**Input:** `AgentState` with GO decision from Auditor

**Output:** Updated `AgentState` with:
- Execution status (success/failure)
- Order IDs
- Estimated profit in USDT
- Execution duration

**Sandbox Mode:**
```python
kraken = ccxt.kraken(
    {
        "apiKey": os.getenv("KRAKEN_API_KEY"),
        "secret": os.getenv("KRAKEN_SECRET"),
        "options": {"sandbox": True},  # Safe testing environment
    }
)
```

### 4. State Management (`AgentState`)

The workflow uses a TypedDict to maintain state across agent transitions:

```python
class AgentState(TypedDict):
    # Input configuration
    symbols: List[str]

    # Monitor outputs
    latest_prices: dict
    spread_pct: float
    opportunity_found: bool
    best_symbol: Optional[str]
    best_buy_exchange: Optional[str]
    best_sell_exchange: Optional[str]
    best_buy_price: float
    best_sell_price: float

    # Auditor outputs
    audit_report: Optional[str]
    audit_duration_ms: float
    decision: str  # "WAIT", "AUDIT", or "EXECUTE"

    # Executor outputs
    execution_duration_ms: float

    # Tracking metadata
    run_id: str
    cycle_id: str
```

### 5. Database Layer (`src/db.py`)

**Schema:**
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'monitor', 'audit', 'execute'
    run_id TEXT,
    cycle_id TEXT,
    payload TEXT NOT NULL      -- JSON-serialized event data
)
```

**Event Types:**
- `monitor_cycle`: Price fetching and spread calculation
- `audit_decision`: LLM audit results
- `trade_execution`: Order placement and results
- `metrics_summary`: Periodic aggregated stats

**Usage:**
```python
log_event(
    "monitor_cycle",
    {
        "spread_pct": 0.75,
        "best_symbol": "BTC/USDT",
        "buy_exchange": "binance",
        "sell_exchange": "coinbase",
    },
    run_id,
    cycle_id,
)
```

### 6. Dashboard (`src/dashboard.py`)

**Technology:** Streamlit web framework

**Features:**
- **Metrics Cards:** Total profit, active spreads, win rate
- **Live Logs:** Real-time agent reasoning and decisions
- **Spread Chart:** Time-series visualization of opportunities
- **Auto-refresh:** Updates every 5 seconds

**Data Flow:**
```
SQLite DB → Query events → Aggregate metrics → Render UI
```

## LangGraph Workflow

The system uses LangGraph to define a state machine with conditional routing:

```python
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("monitor", monitor_market)
workflow.add_node("audit", audit_trade)
workflow.add_node("execute", execute_trade)

# Define edges
workflow.set_entry_point("monitor")

workflow.add_conditional_edges(
    "monitor",
    decide_after_monitor,  # Routes to "audit" or END
    {"audit": "audit", "wait": END},
)

workflow.add_conditional_edges(
    "audit",
    decide_after_audit,  # Routes to "execute" or END
    {"execute": "execute", "wait": END},
)

workflow.add_edge("execute", END)
```

**Routing Logic:**
- **Monitor → Audit:** If spread > 0.5%
- **Monitor → END:** If no opportunity found
- **Audit → Execute:** If LLM returns "GO"
- **Audit → END:** If LLM returns "NO-GO"
- **Execute → END:** Always (after order placement)

## Data Flow

### Typical Execution Cycle

1. **Monitor Phase:**
   ```
   Fetch prices → Calculate spreads → Find best opportunity
   → If spread > 0.5%, proceed to Audit; else END
   ```

2. **Audit Phase:**
   ```
   Calculate net profit after fees → Query LLM auditor
   → If GO decision, proceed to Execute; else END
   ```

3. **Execute Phase:**
   ```
   Place buy order → Place sell order → Log results → END
   ```

4. **Logging:**
   ```
   Each phase logs events to SQLite with metadata
   (run_id, cycle_id, timestamps, durations)
   ```

5. **Dashboard Updates:**
   ```
   Query events table → Aggregate metrics → Render UI
   (auto-refreshes every 5 seconds)
   ```

## Design Decisions

### Why LangGraph?

1. **State Management:** Clean separation of agent state
2. **Conditional Routing:** Easy to express decision logic
3. **Extensibility:** Simple to add new agents or workflows
4. **Observability:** Built-in support for logging and tracing

### Why CCXT?

1. **Multi-exchange support:** 100+ exchanges with unified API
2. **Sandbox mode:** Safe testing without real money
3. **Error handling:** Robust exception hierarchy
4. **Active development:** Well-maintained library

### Why SQLite?

1. **Simplicity:** No separate database server needed
2. **Portability:** Single file database
3. **Performance:** Sufficient for local logging
4. **ACID compliance:** Reliable event persistence

### Why Streamlit?

1. **Rapid development:** Python-native UI framework
2. **Auto-refresh:** Built-in reactivity
3. **Charting:** Easy integration with Plotly/Altair
4. **Deployment:** Simple to host and share

## Error Handling

### Exchange API Errors

```python
try:
    tickers = exchange.fetch_tickers(symbols)
except (NetworkError, ExchangeError) as e:
    logger.error(f"Exchange error: {e}")
    # Continue with other exchanges
```

### LLM Timeouts

```python
try:
    response = auditor_llm.invoke(messages, config={"timeout": 10})
except Exception as e:
    logger.error(f"LLM timeout: {e}")
    state["decision"] = "WAIT"  # Conservative fallback
```

### Graceful Shutdown

```python
def signal_handler(sig, frame):
    global shutdown_flag
    shutdown_flag = True
    logger.info("Shutting down gracefully...")


signal.signal(signal.SIGINT, signal_handler)
```

## Performance Considerations

### Latency Tracking

- **Monitor Duration:** Time to fetch prices from all exchanges
- **Audit Duration:** LLM response time
- **Execution Duration:** Order placement latency

Logged for each cycle to identify bottlenecks.

### Optimization Strategies

1. **Parallel price fetching:** Query exchanges concurrently
2. **Connection pooling:** Reuse exchange connections
3. **Caching:** Store recent prices for quick reference
4. **Rate limiting:** Respect exchange API limits

## Security Measures

1. **Environment Variables:** API keys stored in `.env`
2. **Sandbox Mode:** Test with fake money first
3. **Input Validation:** Sanitize user inputs
4. **Dependency Scanning:** Automated with `pip-audit`
5. **Code Scanning:** Security checks with `bandit`

## Testing Strategy

### Unit Tests

- `test_prices.py`: Price fetching and parsing
- `test_monitor.py`: Spread calculation logic
- `test_audit.py`: Audit decision routing
- `test_executor.py`: Order placement mocking
- `test_db.py`: Database operations

### Integration Tests

- `test_flow_e2e.py`: End-to-end workflow execution

### Test Coverage

Current: **74%** (target: 90%+)

**Coverage Breakdown:**
- `main.py`: 89%
- `db.py`: 86%
- `dashboard.py`: 0% (Streamlit testing complex)

## Future Enhancements

### Planned Features

1. **Multi-symbol parallel monitoring**
2. **Advanced risk management** (position sizing, stop-loss)
3. **Historical backtesting** framework
4. **REST API** for external integrations
5. **Real-money trading** mode (post-validation)
6. **Advanced dashboard** with P&L analytics
7. **Notification system** (email/SMS/Slack)

### Scalability Considerations

For production deployment:

1. **PostgreSQL** instead of SQLite
2. **Redis** for caching and rate limiting
3. **Kubernetes** for container orchestration
4. **Prometheus/Grafana** for metrics
5. **Message queue** (RabbitMQ/Kafka) for async processing

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CCXT Library](https://github.com/ccxt/ccxt)
- [Streamlit Framework](https://streamlit.io/)
- [Kraken API Docs](https://docs.kraken.com/rest/)

---

**Last Updated:** September 18, 2026
