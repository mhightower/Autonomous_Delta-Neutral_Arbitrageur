import time
import os
import logging
import signal
import threading
import uuid
from collections import Counter
import ccxt
from ccxt.base.errors import BaseError, ExchangeError, NetworkError
from langchain_core.tools import tool
from typing import List, TypedDict, Optional, Dict
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

try:
    from .db import init_db, log_event
except ImportError:
    from db import init_db, log_event

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_LOOP_INTERVAL_SECONDS = 60.0
DEFAULT_METRICS_LOG_EVERY_CYCLES = 5


class AgentState(TypedDict):
    symbols: List[str]
    latest_prices: dict
    spread_pct: float
    opportunity_found: bool
    audit_report: Optional[str]
    run_id: str
    cycle_id: str
    audit_duration_ms: float
    execution_duration_ms: float
    decision: str  # "WAIT", "AUDIT", or "EXECUTE"


@tool
def get_crypto_prices(symbols: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Fetches real-time mid-market prices for a list of symbols
    from Binance, Coinbase, and Kraken. Use this to find arbitrage gaps.
    Example input: ["BTC/USDT", "ETH/USDT"]
    """
    exchanges = {
        "binance": ccxt.binanceus(),
        "coinbase": ccxt.coinbase(),
        "kraken": ccxt.kraken(),
    }

    results = {}

    for name, ex in exchanges.items():
        try:
            # Public APIs like fetch_tickers do NOT require API keys.
            tickers = ex.fetch_tickers(symbols)
            results[name] = {s: tickers[s]["close"] for s in symbols if s in tickers}
        except (NetworkError, ExchangeError, BaseError, KeyError, TypeError) as e:
            results[name] = f"Error: {str(e)}"

    return results


auditor_llm = None


def _get_auditor_llm():
    global auditor_llm
    if auditor_llm is None:
        auditor_llm = ChatAnthropic(
            model_name="claude-sonnet-4-6", timeout=10, stop=None
        )
    return auditor_llm


def get_trace_context(state: AgentState) -> str:
    return f"run_id={state.get('run_id', 'unknown')} cycle_id={state.get('cycle_id', 'unknown')}"


def with_trace_context(message: str, state: AgentState) -> str:
    return f"[{get_trace_context(state)}] {message}"


def monitor_market(state: AgentState):
    prices = get_crypto_prices.invoke({"symbols": state["symbols"]})

    # Compute the max price gap across exchanges for each symbol
    max_gap = 0.0
    best_symbol = None
    for sym in state["symbols"]:
        sym_prices = [
            v[sym] for v in prices.values() if isinstance(v, dict) and sym in v
        ]
        if len(sym_prices) >= 2:
            gap = (max(sym_prices) - min(sym_prices)) / min(sym_prices) * 100
            if gap > max_gap:
                max_gap, best_symbol = gap, sym
    gap_detected = max_gap > 0.5

    log_event(
        node="monitor",
        model="Gemini-Flash",
        event_type="OPPORTUNITY" if gap_detected else "WAIT",
        message=with_trace_context(
            f"Gap of {max_gap:.2f}% detected between exchanges for {best_symbol}",
            state,
        )
        if gap_detected
        else with_trace_context("No gap > 0.5% found", state),
        symbol=best_symbol,
        spread_pct=max_gap if max_gap > 0 else None,
    )

    return {
        "latest_prices": prices,
        "spread_pct": max_gap,
        "opportunity_found": gap_detected,
        "decision": "AUDIT" if gap_detected else "WAIT",
    }


def audit_trade(state: AgentState):
    audit_started_at = time.perf_counter()
    prompt = f"Audit this: {state['latest_prices']}. Is it profitable after 0.3% fees? Reply with GO if yes, NO if not."
    response = _get_auditor_llm().invoke(prompt)
    audit_duration_ms = round((time.perf_counter() - audit_started_at) * 1000, 2)

    log_event(
        node="auditor",
        model="Claude-4.6",
        event_type="AUDIT",
        message=with_trace_context(
            f"{response.content[:500]} | audit_duration_ms={audit_duration_ms:.2f}",
            state,
        ),
        symbol=state["symbols"][0] if state["symbols"] else None,
    )

    is_go_signal = response.content.strip().startswith("GO")

    return {
        "audit_report": response.content,
        "audit_duration_ms": audit_duration_ms,
        "decision": "EXECUTE" if is_go_signal else "WAIT",
    }


def execute_trade_node(state: AgentState):
    is_go_signal = state.get("audit_report") and state[
        "audit_report"
    ].strip().startswith("GO")
    execution_started_at = time.perf_counter()

    if not is_go_signal:
        logger.info(
            "event=trade_aborted reason=auditor_no_go %s", get_trace_context(state)
        )
        log_event(
            node="executor",
            model="System",
            event_type="ABORTED",
            message=with_trace_context("Auditor did not give GO signal.", state),
        )
        return {"decision": "ABORTED", "execution_duration_ms": 0.0}

    symbol = "BTC/USDT"
    amount = 0.01  # Small test amount

    try:
        api_key = os.environ["KRAKEN_API_KEY"]
        secret = os.environ["KRAKEN_SECRET"]

        # Initialize the exchange in Sandbox mode.
        exchange = ccxt.kraken({"apiKey": api_key, "secret": secret})
        exchange.set_sandbox_mode(True)  # Ensures we hit the Demo server

        logger.info(
            "event=trade_submit symbol=%s amount=%s %s",
            symbol,
            amount,
            get_trace_context(state),
        )
        order = exchange.create_market_buy_order(symbol, amount)
        # Estimate profit: spread % * trade notional * 70% (after fees)
        spread = float(state.get("spread_pct", 0.0) or 0.0)
        estimated_profit = round(spread * amount * 0.7, 4)
        execution_duration_ms = round(
            (time.perf_counter() - execution_started_at) * 1000, 2
        )
        log_event(
            node="executor",
            model="System",
            event_type="EXECUTED",
            message=with_trace_context(
                f"Order ID: {order['id']}. Estimated profit: ${estimated_profit:.4f} | execution_duration_ms={execution_duration_ms:.2f}",
                state,
            ),
            symbol=symbol,
            profit_usdt=estimated_profit,
        )
        return {
            "decision": "EXECUTED",
            "audit_report": f"Success! Order ID: {order['id']}",
            "execution_duration_ms": execution_duration_ms,
        }
    except KeyError as e:
        error_message = f"Missing required environment variable: {e}"
        logger.exception(
            "event=trade_execution_failed category=config_error %s",
            get_trace_context(state),
        )
        log_event(
            node="executor",
            model="System",
            event_type="FAILED",
            message=with_trace_context(error_message, state),
            symbol=symbol,
        )
        raise RuntimeError(error_message) from e
    except (NetworkError, ExchangeError, BaseError, ValueError) as e:
        execution_duration_ms = round(
            (time.perf_counter() - execution_started_at) * 1000, 2
        )
        logger.exception(
            "event=trade_execution_failed category=runtime_error %s",
            get_trace_context(state),
        )
        log_event(
            node="executor",
            model="System",
            event_type="FAILED",
            message=with_trace_context(
                f"{str(e)} | execution_duration_ms={execution_duration_ms:.2f}", state
            ),
            symbol=symbol,
        )
        return {
            "decision": "FAILED",
            "error": str(e),
            "execution_duration_ms": execution_duration_ms,
        }


def should_audit(state):
    return "auditor" if state["opportunity_found"] else END


def should_execute(state):
    is_go_signal = state.get("audit_report") and state[
        "audit_report"
    ].strip().startswith("GO")
    return "executor" if is_go_signal else END


def build_trading_bot():
    builder = StateGraph(AgentState)

    builder.add_node("monitor", monitor_market)  # Gemini Flash (Fast/Cheap)
    builder.add_node("auditor", audit_trade)  # Claude Sonnet 4.6 (High IQ)
    builder.add_node("executor", execute_trade_node)  # CCXT (The Action)

    builder.set_entry_point("monitor")
    builder.add_conditional_edges("monitor", should_audit)
    builder.add_conditional_edges("auditor", should_execute)
    builder.add_edge("executor", END)

    return builder.compile()


def get_loop_interval_seconds() -> float:
    raw_value = os.getenv("LOOP_INTERVAL_SECONDS", str(DEFAULT_LOOP_INTERVAL_SECONDS))

    try:
        interval = float(raw_value)
    except ValueError:
        logger.warning(
            "event=invalid_loop_interval raw_value=%s fallback=%s",
            raw_value,
            DEFAULT_LOOP_INTERVAL_SECONDS,
        )
        return DEFAULT_LOOP_INTERVAL_SECONDS

    if interval <= 0:
        logger.warning(
            "event=non_positive_loop_interval raw_value=%s fallback=%s",
            raw_value,
            DEFAULT_LOOP_INTERVAL_SECONDS,
        )
        return DEFAULT_LOOP_INTERVAL_SECONDS

    return interval


def get_metrics_log_every_cycles() -> int:
    raw_value = os.getenv(
        "METRICS_LOG_EVERY_CYCLES", str(DEFAULT_METRICS_LOG_EVERY_CYCLES)
    )

    try:
        value = int(raw_value)
    except ValueError:
        logger.warning(
            "event=invalid_metrics_log_every_cycles raw_value=%s fallback=%s",
            raw_value,
            DEFAULT_METRICS_LOG_EVERY_CYCLES,
        )
        return DEFAULT_METRICS_LOG_EVERY_CYCLES

    if value <= 0:
        logger.warning(
            "event=non_positive_metrics_log_every_cycles raw_value=%s fallback=%s",
            raw_value,
            DEFAULT_METRICS_LOG_EVERY_CYCLES,
        )
        return DEFAULT_METRICS_LOG_EVERY_CYCLES

    return value


def emit_metrics_summary(
    run_id: str,
    cycle_count: int,
    decision_counts: Counter,
    total_cycle_duration_ms: float,
    total_audit_duration_ms: float,
    audit_count: int,
    total_execution_duration_ms: float,
    execution_count: int,
    reason: str,
):
    average_cycle_ms = total_cycle_duration_ms / cycle_count if cycle_count else 0.0
    average_audit_ms = total_audit_duration_ms / audit_count if audit_count else 0.0
    average_execution_ms = (
        total_execution_duration_ms / execution_count if execution_count else 0.0
    )

    logger.info(
        "event=metrics_summary run_id=%s reason=%s cycles=%s wait=%s audited_cycles=%s executed=%s failed=%s aborted=%s avg_cycle_ms=%.2f avg_audit_ms=%.2f avg_execution_ms=%.2f",
        run_id,
        reason,
        cycle_count,
        decision_counts.get("WAIT", 0),
        audit_count,
        decision_counts.get("EXECUTED", 0),
        decision_counts.get("FAILED", 0),
        decision_counts.get("ABORTED", 0),
        average_cycle_ms,
        average_audit_ms,
        average_execution_ms,
    )


def register_signal_handlers(stop_event: threading.Event):
    previous_handlers = {}

    def _handle_signal(signum, _frame):
        signal_name = signal.Signals(signum).name
        logger.info("event=shutdown_requested reason=signal signal=%s", signal_name)
        stop_event.set()

    for handled_signal in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[handled_signal] = signal.signal(
            handled_signal, _handle_signal
        )

    return previous_handlers


def restore_signal_handlers(previous_handlers):
    for handled_signal, previous_handler in previous_handlers.items():
        signal.signal(handled_signal, previous_handler)


def run_trading_loop(stop_event: threading.Event, max_cycles: Optional[int] = None):
    init_db()
    run_id = uuid.uuid4().hex[:12]
    base_state: AgentState = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "latest_prices": {},
        "spread_pct": 0.0,
        "opportunity_found": False,
        "audit_report": None,
        "run_id": run_id,
        "cycle_id": "bootstrap",
        "audit_duration_ms": 0.0,
        "execution_duration_ms": 0.0,
        "decision": "WAIT",
    }
    graph = build_trading_bot()
    loop_interval_seconds = get_loop_interval_seconds()
    metrics_log_every_cycles = get_metrics_log_every_cycles()
    cycle_count = 0
    decision_counts = Counter()
    total_cycle_duration_ms = 0.0
    total_audit_duration_ms = 0.0
    total_execution_duration_ms = 0.0
    audit_count = 0
    execution_count = 0

    logger.info(
        "event=agent_started run_id=%s loop_interval_seconds=%s metrics_log_every_cycles=%s",
        run_id,
        loop_interval_seconds,
        metrics_log_every_cycles,
    )

    while not stop_event.is_set():
        cycle_count += 1
        cycle_id = f"cycle-{cycle_count:04d}-{uuid.uuid4().hex[:8]}"
        cycle_state = {**base_state, "cycle_id": cycle_id}
        cycle_started_at = time.perf_counter()

        logger.info(
            "event=cycle_started run_id=%s cycle=%s cycle_id=%s",
            run_id,
            cycle_count,
            cycle_id,
        )
        result = graph.invoke(cycle_state)
        cycle_duration_ms = round((time.perf_counter() - cycle_started_at) * 1000, 2)
        total_cycle_duration_ms += cycle_duration_ms
        decision_counts[result.get("decision", "UNKNOWN")] += 1

        audit_duration_ms = float(result.get("audit_duration_ms", 0.0) or 0.0)
        if audit_duration_ms > 0:
            total_audit_duration_ms += audit_duration_ms
            audit_count += 1

        execution_duration_ms = float(result.get("execution_duration_ms", 0.0) or 0.0)
        if execution_duration_ms > 0:
            total_execution_duration_ms += execution_duration_ms
            execution_count += 1

        logger.info(
            "event=state_update run_id=%s cycle=%s cycle_id=%s decision=%s cycle_duration_ms=%.2f audit_duration_ms=%.2f execution_duration_ms=%.2f",
            run_id,
            cycle_count,
            cycle_id,
            result.get("decision"),
            cycle_duration_ms,
            audit_duration_ms,
            execution_duration_ms,
        )

        if cycle_count % metrics_log_every_cycles == 0:
            emit_metrics_summary(
                run_id=run_id,
                cycle_count=cycle_count,
                decision_counts=decision_counts,
                total_cycle_duration_ms=total_cycle_duration_ms,
                total_audit_duration_ms=total_audit_duration_ms,
                audit_count=audit_count,
                total_execution_duration_ms=total_execution_duration_ms,
                execution_count=execution_count,
                reason="periodic",
            )

        if max_cycles is not None and cycle_count >= max_cycles:
            logger.info(
                "event=loop_stopped run_id=%s reason=max_cycles cycles=%s",
                run_id,
                cycle_count,
            )
            break

        if stop_event.wait(loop_interval_seconds):
            logger.info(
                "event=loop_stopped run_id=%s reason=shutdown_requested cycles=%s",
                run_id,
                cycle_count,
            )
            break

    emit_metrics_summary(
        run_id=run_id,
        cycle_count=cycle_count,
        decision_counts=decision_counts,
        total_cycle_duration_ms=total_cycle_duration_ms,
        total_audit_duration_ms=total_audit_duration_ms,
        audit_count=audit_count,
        total_execution_duration_ms=total_execution_duration_ms,
        execution_count=execution_count,
        reason="shutdown",
    )

    logger.info(
        "event=agent_stopped run_id=%s cycles=%s stop_requested=%s",
        run_id,
        cycle_count,
        stop_event.is_set(),
    )


def main():
    stop_event = threading.Event()
    previous_handlers = register_signal_handlers(stop_event)

    try:
        run_trading_loop(stop_event)
    except KeyboardInterrupt:
        logger.info("event=shutdown_requested reason=keyboard_interrupt")
        stop_event.set()
    except Exception:
        logger.exception("event=agent_crashed")
        raise
    finally:
        restore_signal_handlers(previous_handlers)
        logger.info("event=shutdown_complete")


if __name__ == "__main__":
    main()
