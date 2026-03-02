from __future__ import annotations

import streamlit as st

from _api import ingest_csvs
from _ui import render_sidebar

API = "http://backend:8000"
ctx = render_sidebar()
status = ctx["status"]
base_url = ctx["base_url"]

st.title("1) Upload CSVs")
st.caption("Upload source files and ingest them into the backend.")

tickets_file = st.file_uploader("tickets.csv", type=["csv"])
managers_file = st.file_uploader("managers.csv", type=["csv"])
business_units_file = st.file_uploader("business_units.csv", type=["csv"])

if st.button("Ingest CSVs", use_container_width=True, type="primary"):
    result = ingest_csvs(
        base_url=base_url,
        schema=status.schema,
        tickets=tickets_file,
        managers=managers_file,
        business_units=business_units_file,
    )
    if result["ok"]:
        st.success(result["message"])
        st.toast("CSV upload finished.")
    else:
        st.warning(result["message"])
    if result.get("payload") is not None:
        st.json(result["payload"])
