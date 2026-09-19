"""Skylark Drones BI Agent — Streamlit conversational interface."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.responder import BIAgent
from src.config import DATA_SOURCE, MONDAY_API_TOKEN
from src.data.repository import DataRepository

st.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="🛸",
    layout="wide",
)

st.title("🛸 Skylark Drones — Business Intelligence Agent")
st.caption("Founder-level insights across Deals pipeline & Work Orders")


@st.cache_data(ttl=300, show_spinner="Loading board data…")
def load_data(source: str):
    repo = DataRepository(source=source)
    deals, work_orders = repo.load_all()
    quality = repo.data_quality_summary(deals, work_orders)
    quality["effective_source"] = repo.effective_source
    quality["fallback_reason"] = repo.fallback_reason
    return deals, work_orders, quality


def render_charts(result: dict):
    charts = result.get("charts") or {}
    if "pipeline" in charts and charts["pipeline"] is not None and not charts["pipeline"].empty:
        df = charts["pipeline"]
        x_col = "sector" if "sector" in df.columns else "deal_stage"
        fig = px.bar(df, x=x_col, y="sum", title="Open Pipeline Value", labels={"sum": "Value (INR)"})
        st.plotly_chart(fig, use_container_width=True)
    if "execution" in charts and charts["execution"] is not None and not charts["execution"].empty:
        fig = px.pie(charts["execution"], names="execution_status", values="count", title="Work Orders by Execution Status")
        st.plotly_chart(fig, use_container_width=True)
    if "sectors" in charts and charts["sectors"] is not None and not charts["sectors"].empty:
        fig = px.bar(
            charts["sectors"].head(8),
            x="sector",
            y="pipeline_value",
            title="Open Pipeline by Sector",
            labels={"pipeline_value": "Pipeline (INR)"},
        )
        st.plotly_chart(fig, use_container_width=True)


with st.sidebar:
    st.header("Configuration")
    source_options = ["local"]
    if MONDAY_API_TOKEN:
        source_options.append("monday")
    default_source = "local" if DATA_SOURCE not in source_options else DATA_SOURCE
    source = st.selectbox(
        "Data source",
        options=source_options,
        index=source_options.index(default_source),
        help="Local reads Excel files in /data. Monday.com requires MONDAY_API_TOKEN in .env.",
    )
    if "monday" not in source_options:
        st.info("Monday.com mode disabled — add MONDAY_API_TOKEN to .env to enable.")

    st.divider()
    st.markdown("**Sample questions**")
    samples = [
        "How's our pipeline looking for Mining this quarter?",
        "What's our revenue and billing status?",
        "Show sector performance",
        "Prepare a leadership update",
        "How many work orders are ongoing?",
    ]
    for s in samples:
        if st.button(s, key=s, use_container_width=True):
            st.session_state["pending_question"] = s

try:
    deals, work_orders, quality = load_data(source)
except Exception as exc:
    st.error(f"Failed to load data: {exc}")
    st.stop()

if quality.get("fallback_reason"):
    st.warning(quality["fallback_reason"])

agent = BIAgent(deals, work_orders)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Deals", quality["deals_total"])
col2.metric("Open Deals", quality["deals_open"])
col3.metric("Work Orders", quality["work_orders_total"])
col4.metric("Ongoing WOs", quality["wo_ongoing"])

with st.expander("Data quality snapshot"):
    st.write(
        f"- {quality['deals_missing_value']} deals missing value\n"
        f"- {quality['wo_missing_billed']} work orders missing billed amount\n"
        f"- Source: **{quality.get('effective_source', source)}** (refreshes every 5 min)"
    )

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Ask me about pipeline, revenue, sectors, operations, or request a leadership brief.",
        }
    ]


def handle_question(question: str) -> None:
    result = agent.ask(question)
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "charts": result.get("charts")}
    )


if st.session_state.get("pending_question"):
    with st.spinner("Analyzing…"):
        handle_question(st.session_state.pop("pending_question"))
    st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("charts"):
            render_charts(msg)

question = st.chat_input("Ask a business question…")

if question:
    with st.spinner("Analyzing…"):
        handle_question(question)
    st.rerun()

with st.expander("Raw data preview"):
    tab1, tab2 = st.tabs(["Deals", "Work Orders"])
    with tab1:
        st.dataframe(deals, use_container_width=True)
    with tab2:
        st.dataframe(work_orders, use_container_width=True)
