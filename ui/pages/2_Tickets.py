from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from _api import clear_data_cache, fetch_ticket_detail, run_processing
from _ui import apply_global_filters, load_base_dataframe, render_sidebar


def _safe_raw(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw", {})
    return raw if isinstance(raw, dict) else {}


def _render_attachment(attachment: str) -> None:
    if not attachment:
        return
    att = attachment.strip()
    if not att:
        return

    image_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    if att.lower().startswith(("http://", "https://")) and att.lower().endswith(image_ext):
        st.image(att, caption="Attachment preview", use_container_width=True)
        return
    if att.lower().startswith(("http://", "https://")):
        st.link_button("Open attachment", att)
        return
    st.code(att)


ctx = render_sidebar()
status = ctx["status"]
base_url = ctx["base_url"]

st.title("2) Tickets")
st.caption("Run processing, review enriched tickets, and inspect assignment details.")

actions_col1, actions_col2, actions_col3 = st.columns([1, 2, 1])
with actions_col1:
    st.page_link("pages/1_Upload.py", label="Ingest CSVs", use_container_width=True)
with actions_col2:
    if st.button("Run processing (AI + routing)", type="primary", use_container_width=True):
        result = run_processing(base_url=base_url)
        if result["ok"]:
            st.success(result["message"])
            st.toast("Processing completed.")
        else:
            st.warning(result["message"])
        if result.get("payload") is not None:
            st.json(result["payload"])
with actions_col3:
    if st.button("Refresh", use_container_width=True):
        clear_data_cache()
        st.toast("Data refreshed.")

window_col1, window_col2 = st.columns([1, 1])
with window_col1:
    limit = st.number_input("Limit", min_value=1, max_value=5000, value=500, step=50)
with window_col2:
    offset = st.number_input("Offset", min_value=0, value=0, step=50)

df_all = load_base_dataframe(base_url=base_url, schema=status.schema, limit=int(limit), offset=int(offset))
df_filtered = apply_global_filters(df_all)

left_col, right_col = st.columns([2, 1], gap="large")

selected_row: Optional[Dict[str, Any]] = None
table_cols = ["GUID", "ticket_id", "segment", "ai_type", "ai_sentiment", "ai_priority", "ai_lang", "office", "manager"]

with left_col:
    st.subheader("Filtered tickets")
    if df_filtered.empty:
        st.info("No tickets found with the current filters.")
    else:
        table_df = df_filtered[table_cols].copy()

        # Use interactive selection if available; fallback to selectbox otherwise.
        try:
            event = st.dataframe(
                table_df,
                use_container_width=True,
                hide_index=True,
                height=560,
                on_select="rerun",
                selection_mode="single-row",
            )
            rows = getattr(getattr(event, "selection", None), "rows", [])
            if rows:
                idx = int(rows[0])
                selected_row = df_filtered.iloc[idx].to_dict()
        except TypeError:
            st.dataframe(table_df, use_container_width=True, hide_index=True, height=560)

        if selected_row is None:
            ticket_options = [str(x) for x in df_filtered["ticket_id"].fillna("").tolist()]
            default_idx = 0 if ticket_options else None
            ticket_selected = st.selectbox("Select ticket", options=ticket_options, index=default_idx)
            if ticket_selected:
                row_match = df_filtered[df_filtered["ticket_id"].astype(str) == str(ticket_selected)]
                if not row_match.empty:
                    selected_row = row_match.iloc[0].to_dict()

with right_col:
    st.subheader("Ticket details")
    if not selected_row:
        st.info("Select a ticket row to view details.")
    else:
        ticket_id = str(selected_row.get("ticket_id", ""))
        raw = _safe_raw(selected_row)

        # For schema B, try detail endpoint and merge if available.
        detail = fetch_ticket_detail(base_url=base_url, schema=status.schema, ticket_id=ticket_id)
        if detail:
            raw = detail

        st.write(f"Ticket: `{ticket_id}`")
        st.write(f"GUID: `{selected_row.get('GUID', '')}`")
        st.write(f"Segment: `{selected_row.get('segment', '')}`")

        address_fields = {
            "country": raw.get("country", ""),
            "region": raw.get("region", ""),
            "city": raw.get("city", ""),
            "street": raw.get("street", ""),
            "house": raw.get("house", ""),
        }
        present_address = {k: v for k, v in address_fields.items() if str(v).strip()}
        if present_address:
            st.caption("Address fields")
            st.json(present_address)

        description = selected_row.get("description", "")
        if description:
            st.caption("Description")
            st.write(description)

        st.caption("AI summary")
        st.write(selected_row.get("summary", "") or "N/A")
        st.caption("Recommendation")
        st.write(selected_row.get("recommendation", "") or "N/A")

        reasons = selected_row.get("reasons", []) or []
        st.caption("Why assigned")
        if reasons:
            for reason in reasons:
                st.write(f"- {reason}")
        else:
            st.write("No explicit reason provided.")

        attachment = str(selected_row.get("attachment", "") or raw.get("attachment", ""))
        if attachment:
            st.caption("Attachment")
            _render_attachment(attachment)
