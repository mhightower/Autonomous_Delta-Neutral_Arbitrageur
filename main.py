import ccxt
from langchain_core.tools import tool
from pydantic import BaseModel
from typing import List, TypedDict, List, Optional, TypedDict, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    symbols: List[str]
    latest_prices: dict
    opportunity_found: bool
    audit_report: Optional[dict]
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


# Gemini 3 Flash: The fast, cheap monitor
monitor_llm = ChatGoogleGenerativeAI(model="gemini-3-flash")

# Claude 4.6: The high-precision auditor
auditor_llm = ChatAnthropic(model="claude-4-6-sonnet")

def monitor_market(state: AgentState):
    # Imagine calling our CCXT tool here
    prices = get_crypto_prices.invoke({"symbols": state["symbols"]})
    
    # Simple logic: If price gap > 0.5% between any two exchanges
    # For this example, let's assume Gemini logic finds a 0.8% gap
    gap_detected = True 
    
    return {
        "latest_prices": prices,
        "opportunity_found": gap_detected,
        "decision": "AUDIT" if gap_detected else "WAIT"
    }

def audit_trade(state: AgentState):
    prompt = f"Audit this: {state['latest_prices']}. Is it profitable after 0.3% fees?"
    # Claude processes the high-stakes logic
    response = auditor_llm.invoke(prompt) 
    
    # We'll assume Claude returns a JSON decision
    return {
        "audit_report": response.content,
        "decision": "EXECUTE" if "GO" in response.content else "WAIT"
    }

def execute_trade(state: AgentState):
    # 1. Initialize the exchange in Sandbox mode
    exchange = ccxt.kraken({
        'apiKey': 'YOUR_DEMO_KEY',
        'secret': 'YOUR_DEMO_SECRET',
    })
    exchange.set_sandbox_mode(True) # CRITICAL: This ensures no real money is used

    # 2. Extract details from the state
    report = state["audit_report"]
    # We assume Claude's report confirmed the asset and side
    symbol = "BTC/USDT" 
    amount = 0.001 

    print(f"🚀 EXECUTING TRADE: {symbol} at market price...")

    try:
        # 3. Place the Market Order
        order = exchange.create_market_buy_order(symbol, amount)
        print(f"✅ Success! Order ID: {order['id']}")
        return {"decision": "COMPLETED"}
    except Exception as e:
        print(f"❌ Execution Failed: {e}")
        return {"decision": "FAILED"}


def execute_trade_node(state: AgentState):
    # 1. Initialize the exchange in Sandbox mode
    exchange = ccxt.kraken({
        'apiKey': 'YOUR_DEMO_API_KEY',
        'secret': 'YOUR_DEMO_SECRET_KEY',
    })
    exchange.set_sandbox_mode(True) # Ensures we hit the Demo server

    # 2. Extract the signal from the state
    # We assume Claude's audit_report contains a "decision": "GO"
    if "GO" not in state["audit_report"]:
        print("🛑 Trade Aborted: Auditor did not give a GO signal.")
        return {"decision": "ABORTED"}

    # 3. Perform the trade
    symbol = "BTC/USDT"
    amount = 0.01  # Small test amount
    
    try:
        print(f"💸 Sending Market Buy Order for {amount} {symbol}...")
        order = exchange.create_market_buy_order(symbol, amount)
        
        # 4. Update state with the result
        return {
            "decision": "EXECUTED",
            "audit_report": f"Success! Order ID: {order['id']}"
        }
    except Exception as e:
        print(f"❌ Trade Execution Error: {e}")
        return {"decision": "FAILED"}

workflow = StateGraph(AgentState)

# Add our nodes
workflow.add_node("monitor", monitor_market)
workflow.add_node("auditor", audit_trade)
workflow.add_node("executor", execute_trade)

# Define the flow
workflow.set_entry_point("monitor")

# Routing Logic
def route_after_audit(state: AgentState):
    if "GO" in state["audit_report"]:
        # In production, you might want to wait for a manual 'Y' here
        return "executor" 
    return END

# Conditional Logic: Where do we go after monitoring?
def route_after_monitor(state: AgentState):
    if state["decision"] == "AUDIT":
        return "auditor"
    return END

workflow.add_conditional_edges("monitor", route_after_monitor)
workflow.add_conditional_edges("auditor", route_after_audit)
workflow.add_edge("executor", END)

# Compile the graph
app = workflow.compile()

# Define the workflow
builder = StateGraph(AgentState)

# Add our specialized nodes
builder.add_node("monitor", monitor_market) # Gemini Flash (Fast/Cheap)
builder.add_node("auditor", audit_trade)    # Claude 4.6 (High IQ)
builder.add_node("executor", execute_trade_node) # CCXT (The Action)

# Define the logic flow
builder.set_entry_point("monitor")

# Transition logic: If Gemini finds a gap, go to Claude.
def should_audit(state):
    return "auditor" if state["opportunity_found"] else END

builder.add_conditional_edges("monitor", should_audit)

# Transition logic: If Claude says GO, go to Executor.
def should_execute(state):
    return "executor" if "GO" in state["audit_report"] else END

builder.add_conditional_edges("auditor", should_execute)
builder.add_edge("executor", END)

# Compile the agent
trading_bot = builder.compile()

def main():
    result = get_crypto_prices.invoke({"symbols": ["BTC/USDT", "ETH/USDT"]})
    print(result)


if __name__ == "__main__":
    main()
