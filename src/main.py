import time
import os
import ccxt
from langchain_core.tools import tool
from pydantic import BaseModel
from typing import List, TypedDict, Optional, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from db import init_db, log_event

load_dotenv()


class AgentState(TypedDict):
    symbols: List[str]
    latest_prices: dict
    spread_pct: float
    opportunity_found: bool
    audit_report: Optional[str]
    decision: str  # "WAIT", "AUDIT", or "EXECUTE"


class TradeState(BaseModel):
    asset: str
    prices: Dict[str, float]  # e.g., {"coinbase": 65002, "kraken": 65110}
    fees: float
    risk_approval: bool = False
    execution_status: str = "pending"


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
        except Exception as e:
            results[name] = f"Error: {str(e)}"

    return results


monitor_llm = None
auditor_llm = None


def _get_monitor_llm():
    global monitor_llm
    if monitor_llm is None:
        monitor_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    return monitor_llm


def _get_auditor_llm():
    global auditor_llm
    if auditor_llm is None:
        auditor_llm = ChatAnthropic(
            model_name="claude-sonnet-4-6", timeout=10, stop=None
        )
    return auditor_llm


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
        message=f"Gap of {max_gap:.2f}% detected between exchanges for {best_symbol}"
        if gap_detected
        else "No gap > 0.5% found",
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
    prompt = f"Audit this: {state['latest_prices']}. Is it profitable after 0.3% fees? Reply with GO if yes, NO if not."
    response = _get_auditor_llm().invoke(prompt)

    log_event(
        node="auditor",
        model="Claude-4.6",
        event_type="AUDIT",
        message=response.content[:500],
        symbol=state["symbols"][0] if state["symbols"] else None,
    )

    is_go_signal = response.content.strip().startswith("GO")

    return {
        "audit_report": response.content,
        "decision": "EXECUTE" if is_go_signal else "WAIT",
    }


def execute_trade_node(state: AgentState):
    # Initialize the exchange in Sandbox mode
    exchange = ccxt.kraken(
        {
            "apiKey": os.environ["KRAKEN_API_KEY"],
            "secret": os.environ["KRAKEN_SECRET"],
        }
    )
    exchange.set_sandbox_mode(True)  # Ensures we hit the Demo server

    is_go_signal = state.get("audit_report") and state[
        "audit_report"
    ].strip().startswith("GO")

    if not is_go_signal:
        print("🛑 Trade Aborted: Auditor did not give a GO signal.")
        log_event(
            node="executor",
            model="System",
            event_type="ABORTED",
            message="Auditor did not give GO signal.",
        )
        return {"decision": "ABORTED"}

    symbol = "BTC/USDT"
    amount = 0.01  # Small test amount

    try:
        print(f"💸 Sending Market Buy Order for {amount} {symbol}...")
        order = exchange.create_market_buy_order(symbol, amount)
        # Estimate profit: spread % * trade notional * 70% (after fees)
        spread = float(state.get("spread_pct", 0.0) or 0.0)
        estimated_profit = round(spread * amount * 0.7, 4)
        log_event(
            node="executor",
            model="System",
            event_type="EXECUTED",
            message=f"Order ID: {order['id']}. Estimated profit: ${estimated_profit:.4f}",
            symbol=symbol,
            profit_usdt=estimated_profit,
        )
        return {
            "decision": "EXECUTED",
            "audit_report": f"Success! Order ID: {order['id']}",
        }
    except Exception as e:
        print(f"❌ Trade Execution Error: {e}")
        log_event(
            node="executor",
            model="System",
            event_type="FAILED",
            message=str(e),
            symbol=symbol,
        )
        return {"decision": "FAILED"}


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


def main():
    init_db()
    initial_state: AgentState = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "latest_prices": {},
        "spread_pct": 0.0,
        "opportunity_found": False,
        "audit_report": None,
        "decision": "WAIT",
    }

    while True:
        result = build_trading_bot().invoke(initial_state)
        print("State:", result)
        time.sleep(60)


if __name__ == "__main__":
    main()
