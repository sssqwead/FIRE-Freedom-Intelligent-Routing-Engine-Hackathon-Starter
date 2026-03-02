from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Ticket, TicketAI, Assignment, Manager

def list_tickets_with_details(db: Session, limit: int = 200, offset: int = 0):
    rows = db.query(Ticket, TicketAI, Assignment, Manager)        .outerjoin(TicketAI, TicketAI.ticket_id == Ticket.id)        .outerjoin(Assignment, Assignment.ticket_id == Ticket.id)        .outerjoin(Manager, Manager.id == Assignment.manager_id)        .order_by(Ticket.id.asc())        .offset(offset)        .limit(limit)        .all()

    out = []
    for t, ai, a, m in rows:
        out.append({
            "ticket_id": t.id,
            "client_guid": t.client_guid,
            "segment": t.segment,
            "description": t.description,
            "attachment": t.attachment,
            "country": t.country,
            "region": t.region,
            "city": t.city,
            "street": t.street,
            "house": t.house,
            "ai": None if ai is None else {
                "language": ai.language,
                "type": ai.type,
                "sentiment": ai.sentiment,
                "priority": ai.priority,
                "summary": ai.summary,
                "recommendation": ai.recommendation,
                "geo_lat": ai.geo_lat,
                "geo_lon": ai.geo_lon,
                "source": ai.source,
                "confidence": ai.confidence,
                "reason": ai.reason,
            },
            "assignment": None if a is None else {
                "business_unit": a.business_unit,
                "manager_id": a.manager_id,
                "manager_name": None if m is None else m.full_name,
                "reason": a.reason,
            }
        })
    return out

def dashboard_summary(db: Session):
    total = db.query(func.count(Ticket.id)).scalar() or 0
    assigned = db.query(func.count(Assignment.id)).scalar() or 0

    by_type = db.query(TicketAI.type, func.count(TicketAI.id))        .group_by(TicketAI.type)        .all()

    by_office = db.query(Assignment.business_unit, func.count(Assignment.id))        .group_by(Assignment.business_unit)        .all()

    top_load = db.query(Manager.full_name, Manager.current_load)        .order_by(Manager.current_load.desc())        .limit(10)        .all()

    return {
        "total_tickets": total,
        "assigned_tickets": assigned,
        "by_type": [{"type": t, "count": int(c)} for t, c in by_type],
        "by_office": [{"office": o, "count": int(c)} for o, c in by_office],
        "top_manager_load": [{"manager": n, "load": int(l)} for n, l in top_load],
    }
