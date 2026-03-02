from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


DEFAULT_COLUMNS = [
    "ticket_id",
    "GUID",
    "segment",
    "description",
    "ai_type",
    "ai_sentiment",
    "ai_priority",
    "ai_lang",
    "summary",
    "recommendation",
    "office",
    "manager",
    "reasons",
]


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _first_non_empty(values: Iterable[Any], default: Any = "") -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return default


def _to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _norm_lang(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in ("EN", "ENG", "ENGLISH"):
        return "ENG"
    if raw in ("RU", "RUS", "RUSSIAN"):
        return "RU"
    if raw in ("KZ", "KAZ", "KAZAKH"):
        return "KZ"
    return raw


def _collect_reasons(ticket: Dict[str, Any], ai: Dict[str, Any], assignment: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    for candidate in (
        assignment.get("reason"),
        ticket.get("assignment_reason"),
        ticket.get("reason"),
        ai.get("reason"),
    ):
        for item in _as_list(candidate):
            text = str(item or "").strip()
            if text and text not in reasons:
                reasons.append(text)
    return reasons


def _extract_identifier(ticket: Dict[str, Any]) -> Tuple[str, str]:
    ticket_id = _first_non_empty(
        [
            ticket.get("ticket_id"),
            ticket.get("id"),
            ticket.get("GUID"),
            ticket.get("guid"),
            ticket.get("client_guid"),
        ],
        default="",
    )
    guid = _first_non_empty(
        [
            ticket.get("GUID"),
            ticket.get("guid"),
            ticket.get("client_guid"),
            ticket.get("client_id"),
            ticket_id,
        ],
        default="",
    )
    return str(ticket_id), str(guid)


def normalize_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    ai = _as_dict(ticket.get("ai"))
    assignment = _as_dict(ticket.get("assignment"))

    ticket_id, guid = _extract_identifier(ticket)

    ai_priority = _to_int(
        _first_non_empty(
            [
                ai.get("priority"),
                ticket.get("ai_priority"),
                ticket.get("priority"),
            ],
            default=None,
        ),
        default=None,
    )

    normalized = {
        "ticket_id": ticket_id,
        "GUID": guid,
        "segment": str(_first_non_empty([ticket.get("segment")], default="")),
        "description": str(_first_non_empty([ticket.get("description"), ticket.get("text")], default="")),
        "ai_type": str(
            _first_non_empty(
                [
                    ai.get("type"),
                    ticket.get("ai_type"),
                    ticket.get("type"),
                ],
                default="",
            )
        ),
        "ai_sentiment": str(
            _first_non_empty(
                [
                    ai.get("sentiment"),
                    ticket.get("ai_sentiment"),
                    ticket.get("sentiment"),
                ],
                default="",
            )
        ),
        "ai_priority": ai_priority,
        "ai_lang": _norm_lang(
            _first_non_empty(
                [
                    ai.get("language"),
                    ai.get("lang"),
                    ticket.get("ai_lang"),
                    ticket.get("language"),
                    ticket.get("lang"),
                ],
                default="",
            )
        ),
        "summary": str(
            _first_non_empty(
                [
                    ai.get("summary"),
                    ticket.get("summary"),
                    ticket.get("ai_summary"),
                ],
                default="",
            )
        ),
        "recommendation": str(
            _first_non_empty(
                [
                    ai.get("recommendation"),
                    ticket.get("recommendation"),
                    ticket.get("ai_recommendation"),
                ],
                default="",
            )
        ),
        "office": str(
            _first_non_empty(
                [
                    assignment.get("business_unit"),
                    assignment.get("office"),
                    ticket.get("office"),
                    ticket.get("business_unit"),
                ],
                default="",
            )
        ),
        "manager": str(
            _first_non_empty(
                [
                    assignment.get("manager_name"),
                    assignment.get("manager"),
                    ticket.get("manager"),
                    ticket.get("manager_name"),
                ],
                default="",
            )
        ),
        "reasons": _collect_reasons(ticket=ticket, ai=ai, assignment=assignment),
        "attachment": str(_first_non_empty([ticket.get("attachment"), ticket.get("attachment_url")], default="")),
        "country": str(_first_non_empty([ticket.get("country")], default="")),
        "region": str(_first_non_empty([ticket.get("region")], default="")),
        "city": str(_first_non_empty([ticket.get("city")], default="")),
        "street": str(_first_non_empty([ticket.get("street")], default="")),
        "house": str(_first_non_empty([ticket.get("house")], default="")),
        "raw": ticket,
    }
    return normalized


def normalize_tickets(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return []
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(normalize_ticket(row))
    return normalized


def to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=DEFAULT_COLUMNS)

    df = pd.DataFrame(rows)
    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col != "ai_priority" else pd.NA

    # Guarantee numeric priority for filtering/aggregations.
    df["ai_priority"] = pd.to_numeric(df["ai_priority"], errors="coerce")
    return df


def filter_dataframe(
    df: pd.DataFrame,
    selected_types: List[str],
    selected_langs: List[str],
    selected_offices: List[str],
    priority_range: Tuple[int, int],
    search_text: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else DEFAULT_COLUMNS)

    out = df.copy()

    if selected_types:
        out = out[out["ai_type"].isin(selected_types)]
    if selected_langs:
        out = out[out["ai_lang"].isin(selected_langs)]
    if selected_offices:
        out = out[out["office"].isin(selected_offices)]

    if isinstance(priority_range, (list, tuple)) and len(priority_range) == 2:
        p_min = _to_int(priority_range[0], default=1) or 1
        p_max = _to_int(priority_range[1], default=10) or 10
    else:
        one = _to_int(priority_range, default=10) or 10
        p_min, p_max = one, one
    if p_min > p_max:
        p_min, p_max = p_max, p_min

    out = out[(out["ai_priority"].isna()) | ((out["ai_priority"] >= p_min) & (out["ai_priority"] <= p_max))]

    q = (search_text or "").strip().lower()
    if q:
        search_cols = ["ticket_id", "GUID", "segment", "description", "summary"]
        search_blob = out[search_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        out = out[search_blob.str.contains(q, na=False)]

    return out.reset_index(drop=True)


def has_active_filters(
    selected_types: List[str],
    selected_langs: List[str],
    selected_offices: List[str],
    priority_range: Tuple[int, int],
    full_priority_range: Tuple[int, int],
    search_text: str,
) -> bool:
    if isinstance(priority_range, (list, tuple)) and len(priority_range) == 2:
        pr = (int(priority_range[0]), int(priority_range[1]))
    else:
        one = int(_to_int(priority_range, default=10) or 10)
        pr = (one, one)
    if isinstance(full_priority_range, (list, tuple)) and len(full_priority_range) == 2:
        fr = (int(full_priority_range[0]), int(full_priority_range[1]))
    else:
        one = int(_to_int(full_priority_range, default=10) or 10)
        fr = (one, one)

    return bool(
        selected_types
        or selected_langs
        or selected_offices
        or (pr != fr)
        or (search_text or "").strip()
    )
