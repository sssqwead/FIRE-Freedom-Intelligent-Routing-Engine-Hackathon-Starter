from __future__ import annotations

from fastapi import APIRouter, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.ingest import ingest_csv_bundle
from app.services.processor import process_unassigned
from app.services.read_api import list_tickets_with_details, dashboard_summary

router = APIRouter()

@router.post("/ingest")
def ingest(
    tickets: UploadFile = File(None),
    managers: UploadFile = File(None),
    business_units: UploadFile = File(None),
):
    with SessionLocal() as db:
        return ingest_csv_bundle(db, tickets, managers, business_units)

@router.post("/process")
def process():
    with SessionLocal() as db:
        return process_unassigned(db)

@router.get("/tickets")
def tickets(limit: int = 200, offset: int = 0):
    with SessionLocal() as db:
        # Note: This endpoint is not paginated in the frontend, but we can still support pagination here for future use.
        return list_tickets_with_details(db, limit=limit, offset=offset)

@router.get("/dashboard/summary")
def dashboard():
    with SessionLocal() as db:
        return dashboard_summary(db)
