import streamlit as st
import pandas as pd
import time
import sqlite3
from db import DB_PATH

st.set_page_config(page_title="Arbitrage Agent Command Center", layout="wide")

st.title("🤖 Autonomous Arbitrage Dashboard")
st.sidebar.header("Agent Status: 🟢 RUNNING")


def load_events(limit=500) -> pd.DataFrame:
    try:
        con = sqlite3.connect(DB_PATH, check_same_thread=False)
        df = pd.read_sql_query(
            "SELECT * FROM trade_events ORDER BY timestamp DESC LIMIT ?",
            con, params=(limit,)
        )
        con.close()
        return df
    except Exception:
        return pd.DataFrame()


events = load_events()

# 1. Metric Row: Real-time P/L
col1, col2, col3 = st.columns(3)

if events.empty:
    col1.metric("Total Profit (USDT)", "$0.00")
    col2.metric("Active Spreads Found", "0")
    col3.metric("Win Rate", "N/A")
else:
    total_profit = events[events["event_type"] == "EXECUTED"]["profit_usdt"].sum()
    spreads_today = len(events[events["event_type"] == "OPPORTUNITY"])
    executed = len(events[events["event_type"] == "EXECUTED"])
    total_trades = len(events[events["event_type"].isin(["EXECUTED", "FAILED", "ABORTED"])])
    win_rate = f"{executed / total_trades * 100:.0f}%" if total_trades > 0 else "N/A"

    col1.metric("Total Profit (USDT)", f"${total_profit:.2f}")
    col2.metric("Active Spreads Found", str(spreads_today))
    col3.metric("Win Rate", win_rate)

# 2. The "Thought Stream" (Logs from DB)
st.subheader("🧠 Agent Reasoning Logs")
if events.empty:
    st.info("No events logged yet. Run main.py to start the trading agent.")
else:
    log_df = events[["timestamp", "model", "message"]].head(20).copy()
    log_df.columns = ["Timestamp", "Model", "Message"]
    st.table(log_df)

# 3. Live Price Spread Chart
st.subheader("📈 Live Spread Monitoring")
if not events.empty and events["spread_pct"].notna().any():
    spread_df = (
        events[events["spread_pct"].notna()][["timestamp", "spread_pct"]]
        .sort_values("timestamp")
        .rename(columns={"spread_pct": "Spread %"})
        .set_index("timestamp")
    )
    st.line_chart(spread_df)
else:
    st.info("No spread data yet.")

# Auto-refresh the page every 5 seconds
time.sleep(5)
st.rerun()
