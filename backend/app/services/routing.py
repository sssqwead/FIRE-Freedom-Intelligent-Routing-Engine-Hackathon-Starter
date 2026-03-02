from __future__ import annotations

from sqlalchemy.orm import Session
from app.db.models import Manager, RRState, Ticket, TicketAI


def _skills_set(skills: str) -> set[str]:
    return {s.strip().upper() for s in (skills or "").split(",") if s.strip()}


def eligible_managers(db: Session, office: str, ticket: Ticket, ai: TicketAI) -> list[Manager]:
    q = db.query(Manager).filter(Manager.business_unit == office)
    managers = q.all()

    out: list[Manager] = []
    for m in managers:
        skills = _skills_set(m.skills)

        if (ticket.segment or "").upper() in ["VIP", "PRIORITY"] and "VIP" not in skills:
            continue

        if ai.type == "DataChange" and ("глав" not in (m.position or "").lower() and "chief" not in (m.position or "").lower()):
            continue

        if ai.language == "KZ" and "KZ" not in skills:
            continue

        if ai.language == "ENG" and "ENG" not in skills:
            continue

        out.append(m)
    return out


def pick_by_dynamic_top2_round_robin(db: Session, office: str, candidates: list[Manager]) -> tuple[Manager, str]:
    if not candidates:
        raise ValueError("no eligible managers")

    candidates = sorted(candidates, key=lambda m: (m.current_load, m.id))
    if len(candidates) == 1:
        return candidates[0], "only_one_candidate"

    top2 = candidates[:2]
    pair = f"{top2[0].id},{top2[1].id}"

    key = f"bu:{office}"
    st = db.query(RRState).filter(RRState.key == key).one_or_none()
    if st is None:
        st = RRState(key=key, last_pair=pair, toggle=0)
        db.add(st)
        db.commit()

    if st.last_pair != pair:
        st.last_pair = pair
        st.toggle = 0

    chosen = top2[0] if st.toggle == 0 else top2[1]
    st.toggle = 1 - st.toggle
    db.add(st)
    db.commit()

    return chosen, f"dynamic_top2_rr(pair={pair}, chosen={chosen.id})"


def route_ticket(db: Session, ticket: Ticket, ai: TicketAI, preferred_office: str):
    # 1) GEO-FIRST
    candidates = eligible_managers(db, preferred_office, ticket, ai)
    if candidates:
        manager, reason = pick_by_dynamic_top2_round_robin(db, preferred_office, candidates)
        return manager, f"{reason}, office={preferred_office}, geo_first"

    # 2) OTHER OFFICES CASCADE (deterministic order)
    offices = sorted([o[0] for o in db.query(Manager.business_unit).distinct().all()])

    for office in offices:
        if office == preferred_office:
            continue

        candidates = eligible_managers(db, office, ticket, ai)
        if candidates:
            manager, reason = pick_by_dynamic_top2_round_robin(db, office, candidates)
            return manager, f"{reason}, office={office}, cascade"

    # 3) GLOBAL STRICT (ignore geo, keep hard rules)
    all_managers = db.query(Manager).all()
    strict_global: list[Manager] = []

    for m in all_managers:
        skills = _skills_set(m.skills)

        if (ticket.segment or "").upper() in ["VIP", "PRIORITY"] and "VIP" not in skills:
            continue

        if ai.type == "DataChange" and ("глав" not in (m.position or "").lower() and "chief" not in (m.position or "").lower()):
            continue

        if ai.language == "KZ" and "KZ" not in skills:
            continue

        if ai.language == "ENG" and "ENG" not in skills:
            continue

        strict_global.append(m)

    if strict_global:
        strict_global = sorted(strict_global, key=lambda m: (m.current_load, m.id))
        chosen = strict_global[0]
        return chosen, "global_strict_min_load"

    # 4) ABSOLUTE FALLBACK (guarantee 150/150)
    if not all_managers:
        raise ValueError("no managers in system")

    all_managers = sorted(all_managers, key=lambda m: (m.current_load, m.id))
    chosen = all_managers[0]
    return chosen, "absolute_global_min_load"