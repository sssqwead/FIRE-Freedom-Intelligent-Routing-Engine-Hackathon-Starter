from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Ticket, TicketAI, Assignment
from app.services.geo import choose_office, geocode_ticket
from app.services.ai_rules import run_hybrid

from app.services.routing import route_ticket


def _ensure_ai(db: Session, ticket: Ticket) -> TicketAI:
    ai = db.query(TicketAI).filter(TicketAI.ticket_id == ticket.id).one_or_none()
    if ai is not None:
        return ai

    r = run_hybrid(ticket.description or "", ticket.segment or "Mass")
    ai = TicketAI(
        ticket_id=ticket.id,
        language=r.language,
        type=r.type,
        sentiment=r.sentiment,
        priority=r.priority,
        summary=r.summary,
        recommendation=r.recommendation,
        source="rules",
        confidence=r.confidence,
        reason=r.reason,
    )
    db.add(ai)
    db.commit()
    return ai


def process_unassigned(db: Session):
    
    tickets = (
        db.query(Ticket)
        .outerjoin(Assignment, Assignment.ticket_id == Ticket.id)
        .filter(Assignment.id.is_(None))
        .order_by(Ticket.id.asc())
        .limit(settings.PROCESS_BATCH_LIMIT)
        .all()
    )

    processed = 0
    assigned = 0
    errors: list[dict] = []

    for t in tickets:
        processed += 1
        try:
            ai = _ensure_ai(db, t)

            
            lat, lon, geo_reason = geocode_ticket(db, t)
            ai.geo_lat = "" if lat is None else f"{lat:.6f}"
            ai.geo_lon = "" if lon is None else f"{lon:.6f}"
            db.add(ai)

            
            office, office_reason = choose_office(
                db,
                t.country or "",
                t.city or "",
                lat=lat,
                lon=lon,
            )

            
            manager, route_reason = route_ticket(db, t, ai, office)

            
            reason = (
                f"office_preferred={office}({office_reason}); geocode={geo_reason}; "
                f"route={route_reason}; filters=hard_skills; priority={ai.priority}"
            )
            db.add(
                Assignment(
                    ticket_id=t.id,
                    manager_id=manager.id,
                    business_unit=manager.business_unit,
                    reason=reason,
                )
            )

            
            manager.current_load += 1
            db.add(manager)

            db.commit()
            assigned += 1

        except Exception as e:
            db.rollback()
            errors.append({"ticket_id": t.id, "error": str(e)})

    return {"status": "ok", "processed": processed, "assigned": assigned, "errors": errors}
