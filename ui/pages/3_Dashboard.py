from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd
import streamlit as st

from _api import fetch_summary_cached
from _normalize import has_active_filters
from _ui import apply_global_filters, load_base_dataframe, render_sidebar


def _from_summary(summary: Dict[str, object]) -> Tuple[int, int, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    total = int(summary.get("total_tickets", 0) or 0)
    assigned = int(summary.get("assigned_tickets", 0) or 0)

    by_type = pd.DataFrame(summary.get("by_type", []))
    by_type = by_type.rename(columns={"type": "ai_type"})
    if "count" not in by_type.columns:
        by_type["count"] = 0
    if "ai_type" not in by_type.columns:
        by_type["ai_type"] = ""

    by_office = pd.DataFrame(summary.get("by_office", []))
    by_office = by_office.rename(columns={"office": "office"})
    if "count" not in by_office.columns:
        by_office["count"] = 0
    if "office" not in by_office.columns:
        by_office["office"] = ""

    manager_load = pd.DataFrame(summary.get("top_manager_load", []))
    if "manager" not in manager_load.columns:
        manager_load["manager"] = ""
    if "load" not in manager_load.columns:
        manager_load["load"] = 0

    return total, assigned, by_type[["ai_type", "count"]], by_office[["office", "count"]], manager_load[["manager", "load"]]


def _from_df(df: pd.DataFrame) -> Tuple[int, int, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if df.empty:
        empty = pd.DataFrame(columns=["label", "count"])
        mgr = pd.DataFrame(columns=["manager", "load"])
        return 0, 0, empty.rename(columns={"label": "ai_type"}), empty.rename(columns={"label": "office"}), mgr

    total = len(df)
    assigned = int(((df["office"].fillna("").astype(str).str.strip() != "") | (df["manager"].fillna("").astype(str).str.strip() != "")).sum())

    by_type = (
        df["ai_type"]
        .fillna("")
        .astype(str)
        .replace("", "Unknown")
        .value_counts()
        .rename_axis("ai_type")
        .reset_index(name="count")
    )
    by_office = (
        df["office"]
        .fillna("")
        .astype(str)
        .replace("", "Unassigned")
        .value_counts()
        .rename_axis("office")
        .reset_index(name="count")
    )
    manager_load = (
        df["manager"]
        .fillna("")
        .astype(str)
        .replace("", "Unassigned")
        .value_counts()
        .rename_axis("manager")
        .reset_index(name="load")
    )

    return total, assigned, by_type, by_office, manager_load


def _type_office_matrix(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    matrix = pd.pivot_table(
        df.assign(
            ai_type=df["ai_type"].fillna("").replace("", "Unknown"),
            office=df["office"].fillna("").replace("", "Unassigned"),
            __count__=1,
        ),
        index="ai_type",
        columns="office",
        values="__count__",
        aggfunc="sum",
        fill_value=0,
    )
    return matrix


ctx = render_sidebar()
status = ctx["status"]
base_url = ctx["base_url"]
priority_bounds = ctx["priority_bounds"]

st.title("3) Dashboard")
st.caption("Aggregates for ticket volume, office distribution, manager load, and routing matrix.")

df_all = load_base_dataframe(base_url=base_url, schema=status.schema, limit=500, offset=0)
df_filtered = apply_global_filters(df_all)

active_filters = has_active_filters(
    selected_types=st.session_state.get("global_filter_types", []),
    selected_langs=st.session_state.get("global_filter_langs", []),
    selected_offices=st.session_state.get("global_filter_offices", []),
    priority_range=st.session_state.get("global_filter_priority", priority_bounds),
    full_priority_range=priority_bounds,
    search_text=st.session_state.get("global_filter_search", ""),
)

summary = fetch_summary_cached(base_url) if status.schema == "A" else None
if summary and not active_filters:
    total_tickets, assigned_tickets, by_type_df, by_office_df, manager_df = _from_summary(summary)
else:
    total_tickets, assigned_tickets, by_type_df, by_office_df, manager_df = _from_df(df_filtered)
    if not summary:
        st.info("`/dashboard/summary` not available. Metrics are computed from fetched tickets.")

kpi1, kpi2 = st.columns(2)
with kpi1:
    st.metric("Total tickets", value=int(total_tickets))
with kpi2:
    st.metric("Assigned tickets", value=int(assigned_tickets))

charts_col1, charts_col2 = st.columns(2)
with charts_col1:
    st.subheader("Counts by type")
    if by_type_df.empty:
        st.info("No type data.")
    else:
        st.bar_chart(by_type_df.set_index("ai_type")["count"])
        st.dataframe(by_type_df, use_container_width=True, hide_index=True)
with charts_col2:
    st.subheader("Counts by office")
    if by_office_df.empty:
        st.info("No office data.")
    else:
        st.bar_chart(by_office_df.set_index("office")["count"])
        st.dataframe(by_office_df, use_container_width=True, hide_index=True)

st.subheader("Top manager load")
if manager_df.empty:
    st.info("No manager load data.")
else:
    top_manager_df = manager_df.sort_values("load", ascending=False).head(15)
    st.bar_chart(top_manager_df.set_index("manager")["load"])
    st.dataframe(top_manager_df, use_container_width=True, hide_index=True)

st.subheader("Type x Office matrix")
matrix_df = _type_office_matrix(df_filtered if active_filters else df_all)
if matrix_df.empty:
    st.info("No matrix data.")
else:
    st.dataframe(matrix_df, use_container_width=True)
