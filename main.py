import os
import ccxt
from langchain_core.tools import tool
from pydantic import BaseModel
from typing import List, TypedDict, Optional, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    symbols: List[str]
    latest_prices: dict
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
        'binance': ccxt.binanceus(),
        'coinbase': ccxt.coinbase(),
        'kraken': ccxt.kraken()
    }

    results = {}

    for name, ex in exchanges.items():
        try:
            # Public APIs like fetch_tickers do NOT require API keys.
            tickers = ex.fetch_tickers(symbols)
            results[name] = {s: tickers[s]['close'] for s in symbols if s in tickers}
        except Exception as e:
            results[name] = f"Error: {str(e)}"

    return results


# Gemini 2.0 Flash: The fast, cheap monitor
monitor_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

# Claude Sonnet 4.6: The high-precision auditor
auditor_llm = ChatAnthropic(model_name="claude-sonnet-4-6", timeout=10, stop=None)  # Longer timeout for complex reasoning

def monitor_market(state: AgentState):
    prices = get_crypto_prices.invoke({"symbols": state["symbols"]})

    # Simple logic: If price gap > 0.5% between any two exchanges
    # For this example, let's assume the monitor logic finds a 0.8% gap
    gap_detected = True

    return {
        "latest_prices": prices,
        "opportunity_found": gap_detected,
        "decision": "AUDIT" if gap_detected else "WAIT"
    }

def audit_trade(state: AgentState):
    prompt = f"Audit this: {state['latest_prices']}. Is it profitable after 0.3% fees? Reply with GO if yes, NO if not."
    response = auditor_llm.invoke(prompt)

    return {
        "audit_report": response.content,
        "decision": "EXECUTE" if "GO" in response.content else "WAIT"
    }

def execute_trade_node(state: AgentState):
    # Initialize the exchange in Sandbox mode
    exchange = ccxt.kraken({
        'apiKey': os.environ['KRAKEN_API_KEY'],
        'secret': os.environ['KRAKEN_SECRET'],
    })
    exchange.set_sandbox_mode(True)  # Ensures we hit the Demo server

    if "GO" not in state["audit_report"]:
        print("🛑 Trade Aborted: Auditor did not give a GO signal.")
        return {"decision": "ABORTED"}

    symbol = "BTC/USDT"
    amount = 0.01  # Small test amount

    try:
        print(f"💸 Sending Market Buy Order for {amount} {symbol}...")
        order = exchange.create_market_buy_order(symbol, amount)
        return {
            "decision": "EXECUTED",
            "audit_report": f"Success! Order ID: {order['id']}"
        }
    except Exception as e:
        print(f"❌ Trade Execution Error: {e}")
        return {"decision": "FAILED"}


builder = StateGraph(AgentState)

builder.add_node("monitor", monitor_market)   # Gemini Flash (Fast/Cheap)
builder.add_node("auditor", audit_trade)      # Claude Sonnet 4.6 (High IQ)
builder.add_node("executor", execute_trade_node)  # CCXT (The Action)

builder.set_entry_point("monitor")

def should_audit(state):
    return "auditor" if state["opportunity_found"] else END

builder.add_conditional_edges("monitor", should_audit)

def should_execute(state):
    return "executor" if "GO" in state["audit_report"] else END

builder.add_conditional_edges("auditor", should_execute)
builder.add_edge("executor", END)

trading_bot = builder.compile()

def main():
    initial_state: AgentState = {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "latest_prices": {},
        "opportunity_found": False,
        "audit_report": None,
        "decision": "WAIT",
    }
    result = trading_bot.invoke(initial_state)
    print("Final state:", result)


if __name__ == "__main__":
    main()
