# FIRE (Freedom Intelligent Routing Engine) — Hackathon Starter

This repo contains a minimal, deadline-friendly implementation:
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- UI: Streamlit (simple demo panel)
- Pipeline: CSV ingest → AI enrichment (rules-first, optional LLM hook) → routing (business rules + dynamic top-2 round-robin) → DB → UI

## Quick start (Docker)
1) Copy env:
   - `cp .env.example .env`
2) Start:
   - `docker compose up --build`
3) Open:
   - UI: http://localhost:8501
   - API docs: http://localhost:8000/docs
   - PostgreSQL: `localhost:${POSTGRES_PORT:-15432}`

## API endpoints
- POST `/ingest`  (multipart): upload `tickets.csv`, `managers.csv`, `business_units.csv`
- POST `/process` : run enrichment + routing for all unassigned tickets
- GET  `/tickets`  : list tickets with AI + assignment
- GET  `/dashboard/summary` : simple aggregates

## Notes
- LLM is OFF by default. Set `USE_LLM=true` and `OPENAI_API_KEY=...` in `.env` to enable the hook.
- Geo routing is real geocoding first:
  - ticket address is geocoded via OpenStreetMap Nominatim (with DB cache)
  - if geocoded, the nearest business unit is selected by distance
  - if not geocoded, city mapping fallback is used
  - unknown address or non-KZ → Astana/Almaty 50/50

## Local backend without Docker
1) Make sure PostgreSQL is available and create DB `fire`.
2) Set env:
   - `DATABASE_URL=postgresql+psycopg://fire:fire@localhost:15432/fire` (adjust port/user/password)
3) Run backend:
   - `cd backend`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`
