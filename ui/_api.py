from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


REQUEST_TIMEOUT = 20
PROCESS_TIMEOUT = 300


@dataclass
class BackendStatus:
    base_url: str
    health_ok: bool
    schema: Optional[str]
    message: str


def _clean_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/")


def _safe_get_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _get(base_url: str, path: str, timeout: int = REQUEST_TIMEOUT, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    url = f"{_clean_base_url(base_url)}{path}"
    return requests.get(url, timeout=timeout, params=params)


def _post(
    base_url: str,
    path: str,
    timeout: int = REQUEST_TIMEOUT,
    files: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    url = f"{_clean_base_url(base_url)}{path}"
    return requests.post(url, timeout=timeout, files=files)


@st.cache_data(ttl=15, show_spinner=False)
def detect_backend(base_url: str) -> BackendStatus:
    base_url = _clean_base_url(base_url)
    if not base_url:
        return BackendStatus(base_url=base_url, health_ok=False, schema=None, message="BASE_URL is empty.")

    health_ok = False
    health_msg = ""
    try:
        health_resp = _get(base_url, "/health")
        if health_resp.status_code == 200:
            health_ok = True
            health_msg = "Health check passed."
        else:
            health_msg = f"/health returned {health_resp.status_code}."
    except requests.RequestException as exc:
        health_msg = f"/health unavailable: {exc}"

    # Schema A probe
    try:
        summary_resp = _get(base_url, "/dashboard/summary")
        if summary_resp.status_code == 200:
            return BackendStatus(
                base_url=base_url,
                health_ok=health_ok,
                schema="A",
                message=f"{health_msg} Detected schema A.",
            )
    except requests.RequestException:
        pass

    # Schema B probe
    try:
        results_resp = _get(base_url, "/results")
        if results_resp.status_code == 200:
            return BackendStatus(
                base_url=base_url,
                health_ok=health_ok,
                schema="B",
                message=f"{health_msg} Detected schema B.",
            )
    except requests.RequestException:
        pass

    # Safety fallback: if /tickets works, treat as A-like read API.
    try:
        tickets_resp = _get(base_url, "/tickets")
        if tickets_resp.status_code == 200:
            return BackendStatus(
                base_url=base_url,
                health_ok=health_ok,
                schema="A",
                message=f"{health_msg} Detected A-like read endpoints via /tickets.",
            )
    except requests.RequestException:
        pass

    return BackendStatus(
        base_url=base_url,
        health_ok=health_ok,
        schema=None,
        message=f"{health_msg} Could not detect API schema.",
    )


def clear_data_cache() -> None:
    detect_backend.clear()
    fetch_tickets_cached.clear()
    fetch_summary_cached.clear()


def _list_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "tickets"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def fetch_tickets_uncached(base_url: str, schema: Optional[str], limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
    base_url = _clean_base_url(base_url)
    schema = (schema or "").upper() or None

    paths: List[str]
    if schema == "A":
        paths = ["/tickets"]
    elif schema == "B":
        paths = ["/results", "/tickets"]
    else:
        paths = ["/tickets", "/results"]

    for path in paths:
        try:
            params = {"limit": limit, "offset": offset} if path == "/tickets" else None
            resp = _get(base_url, path, params=params)
            if resp.status_code != 200:
                continue
            data = _list_from_payload(_safe_get_json(resp))
            if path == "/results":
                start = max(offset, 0)
                end = start + max(limit, 0) if limit is not None else None
                return data[start:end]
            return data
        except requests.RequestException:
            continue
    return []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_tickets_cached(base_url: str, schema: Optional[str], limit: int = 500, offset: int = 0) -> List[Dict[str, Any]]:
    return fetch_tickets_uncached(base_url=base_url, schema=schema, limit=limit, offset=offset)


def fetch_ticket_detail(base_url: str, schema: Optional[str], ticket_id: str) -> Optional[Dict[str, Any]]:
    if not ticket_id:
        return None

    if (schema or "").upper() == "B":
        try:
            resp = _get(base_url, f"/results/{ticket_id}")
            if resp.status_code == 200:
                payload = _safe_get_json(resp)
                if isinstance(payload, dict):
                    return payload
        except requests.RequestException:
            pass
    return None


@st.cache_data(ttl=30, show_spinner=False)
def fetch_summary_cached(base_url: str) -> Optional[Dict[str, Any]]:
    try:
        resp = _get(base_url, "/dashboard/summary")
        if resp.status_code == 200:
            payload = _safe_get_json(resp)
            if isinstance(payload, dict):
                return payload
    except requests.RequestException:
        pass
    return None


def _build_upload_files(
    tickets: Any,
    managers: Any,
    business_units: Any,
) -> Dict[str, Any]:
    files: Dict[str, Any] = {}
    if tickets is not None:
        files["tickets"] = (getattr(tickets, "name", "tickets.csv"), tickets.getvalue(), "text/csv")
    if managers is not None:
        files["managers"] = (getattr(managers, "name", "managers.csv"), managers.getvalue(), "text/csv")
    if business_units is not None:
        files["business_units"] = (
            getattr(business_units, "name", "business_units.csv"),
            business_units.getvalue(),
            "text/csv",
        )
    return files


def ingest_csvs(
    base_url: str,
    schema: Optional[str],
    tickets: Any,
    managers: Any,
    business_units: Any,
) -> Dict[str, Any]:
    files = _build_upload_files(tickets=tickets, managers=managers, business_units=business_units)
    if not files:
        return {"ok": False, "status_code": None, "message": "Please select at least one CSV file.", "payload": None}

    schema = (schema or "").upper()
    if schema == "A":
        paths = ["/ingest", "/import"]
    elif schema == "B":
        paths = ["/import", "/ingest"]
    else:
        paths = ["/ingest", "/import"]

    for path in paths:
        try:
            resp = _post(base_url, path, files=files, timeout=REQUEST_TIMEOUT)
            if 200 <= resp.status_code < 300:
                clear_data_cache()
                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "message": f"Upload successful via {path}.",
                    "payload": _safe_get_json(resp),
                }
            payload = _safe_get_json(resp)
            if resp.status_code not in (404, 405):
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "message": f"Upload failed via {path}.",
                    "payload": payload,
                }
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            last_error = ""

    return {
        "ok": False,
        "status_code": None,
        "message": f"Upload endpoint not found or unavailable. Last error: {last_error}" if "last_error" in locals() else "Upload endpoint not found.",
        "payload": None,
    }


def run_processing(base_url: str) -> Dict[str, Any]:
    try:
        resp = _post(base_url, "/process", timeout=PROCESS_TIMEOUT)
        payload = _safe_get_json(resp)
        if 200 <= resp.status_code < 300:
            clear_data_cache()
            return {
                "ok": True,
                "status_code": resp.status_code,
                "message": "Processing completed.",
                "payload": payload,
            }
        return {
            "ok": False,
            "status_code": resp.status_code,
            "message": "Processing request failed.",
            "payload": payload,
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "message": f"Processing request failed: {exc}",
            "payload": None,
        }
