from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from _api import BackendStatus, clear_data_cache, detect_backend, fetch_tickets_cached
from _normalize import filter_dataframe, normalize_tickets, to_dataframe


def _get_list_options(df: pd.DataFrame, column: str) -> List[str]:
    if df.empty or column not in df.columns:
        return []
    values = sorted([str(v) for v in df[column].dropna().unique() if str(v).strip()])
    return values


def _compute_priority_bounds(df: pd.DataFrame) -> Tuple[int, int]:
    if df.empty or "ai_priority" not in df.columns:
        return (1, 10)
    series = pd.to_numeric(df["ai_priority"], errors="coerce").dropna()
    if series.empty:
        return (1, 10)
    p_min = int(max(1, min(10, series.min())))
    p_max = int(max(1, min(10, series.max())))
    if p_min > p_max:
        return (1, 10)
    return (p_min, p_max)


def load_base_dataframe(base_url: str, schema: str | None, limit: int = 500, offset: int = 0) -> pd.DataFrame:
    tickets = fetch_tickets_cached(base_url=base_url, schema=schema, limit=limit, offset=offset)
    return to_dataframe(normalize_tickets(tickets))


def apply_global_filters(df: pd.DataFrame) -> pd.DataFrame:
    selected_types = st.session_state.get("global_filter_types", [])
    selected_langs = st.session_state.get("global_filter_langs", [])
    selected_offices = st.session_state.get("global_filter_offices", [])
    priority_range = st.session_state.get("global_filter_priority", (1, 10))
    search_text = st.session_state.get("global_filter_search", "")
    return filter_dataframe(
        df=df,
        selected_types=selected_types,
        selected_langs=selected_langs,
        selected_offices=selected_offices,
        priority_range=priority_range,
        search_text=search_text,
    )


def render_sidebar() -> Dict[str, object]:
    st.sidebar.header("FIRE Config")
    if "base_url" not in st.session_state:
        st.session_state["base_url"] = "http://backend:8000"
    base_url = st.sidebar.text_input("BASE_URL", key="base_url")

    status: BackendStatus = detect_backend(base_url)
    if st.sidebar.button("Check backend", use_container_width=True):
        detect_backend.clear()
        status = detect_backend(base_url)

    if status.health_ok:
        st.sidebar.success("Backend health: OK")
    else:
        st.sidebar.warning("Backend health: unavailable")
    if status.schema:
        st.sidebar.caption(f"Detected schema: {status.schema}")
    else:
        st.sidebar.caption("Detected schema: unknown")
    st.sidebar.caption(status.message)

    # Base data for global filter options.
    df_base = load_base_dataframe(base_url=base_url, schema=status.schema, limit=500, offset=0)
    types = _get_list_options(df_base, "ai_type")
    langs = _get_list_options(df_base, "ai_lang")
    offices = _get_list_options(df_base, "office")
    priority_bounds = _compute_priority_bounds(df_base)
    priority_value = st.session_state.get("global_filter_priority", priority_bounds)

    if priority_value[0] < priority_bounds[0] or priority_value[1] > priority_bounds[1]:
        priority_value = priority_bounds

    st.sidebar.divider()
    st.sidebar.subheader("Global filters")
    st.sidebar.multiselect("Type", options=types, key="global_filter_types")
    st.sidebar.multiselect("Language", options=langs, key="global_filter_langs")
    st.sidebar.multiselect("Office", options=offices, key="global_filter_offices")
    if priority_bounds[0] == priority_bounds[1]:
        st.sidebar.slider(
            "Priority range",
            min_value=priority_bounds[0],
            max_value=priority_bounds[1],
            value=priority_bounds[0],
            key="global_filter_priority_single",
            disabled=True,
        )
        st.session_state["global_filter_priority"] = priority_bounds
    else:
        st.sidebar.slider(
            "Priority range",
            min_value=priority_bounds[0],
            max_value=priority_bounds[1],
            value=priority_value,
            key="global_filter_priority",
        )
    st.sidebar.text_input(
        "Search",
        key="global_filter_search",
        placeholder="GUID / id / ticket_id / segment / description / summary",
    )

    if st.sidebar.button("Clear cache", use_container_width=True):
        clear_data_cache()
        st.toast("Cache cleared.")

    return {
        "base_url": base_url,
        "status": status,
        "df_base": df_base,
        "priority_bounds": priority_bounds,
    }
