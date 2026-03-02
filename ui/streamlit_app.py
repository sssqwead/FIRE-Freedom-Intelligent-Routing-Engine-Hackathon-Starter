from __future__ import annotations
import streamlit as st

from _ui import render_sidebar


st.set_page_config(page_title="FIRE — Tickets UI", layout="wide")

ctx = render_sidebar()
status = ctx["status"]

st.title("FIRE — Freedom Intelligent Routing Engine")
st.caption("Hackathon UI for ingest, processing, routing visibility, dashboarding, and command assistant.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Pipeline")
    st.markdown(
        """
1. Open `Upload` and send `tickets.csv`, `managers.csv`, `business_units.csv`.
2. Open `Tickets` and run **processing (AI + routing)**.
3. Review enriched tickets, assignments, and reasons.
        """
    )
with col2:
    st.subheader("Backend")
    st.write(f"BASE_URL: `{ctx['base_url']}`")
    st.write(f"Schema: `{status.schema or 'unknown'}`")
    if status.health_ok:
        st.success("Health is OK.")
    else:
        st.warning("Health check is not available.")

st.divider()
st.subheader("Pages")
st.page_link("pages/1_Upload.py", label="1) Upload")
st.page_link("pages/2_Tickets.py", label="2) Tickets")
st.page_link("pages/3_Dashboard.py", label="3) Dashboard")
st.page_link("pages/4_Assistant.py", label="4) Assistant")
