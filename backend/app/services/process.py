from sqlalchemy.orm import Session
from app.db.models import Ticket
from app.services.routing import route_ticket

def run_processing(db: Session):
    tickets = db.query(Ticket).all()
    processed = 0
    assigned = 0
    errors = []

    for ticket in tickets:
        try:
            result = route_ticket(db, ticket)
            processed += 1
            if result:
                assigned += 1
            else:
                errors.append({"ticket_id": ticket.id, "reason": "no eligible"})
        except Exception as e:
            errors.append({"ticket_id": ticket.id, "reason": str(e)})

    return {
        "processed": processed,
        "assigned": assigned,
        "errors": errors,
    }