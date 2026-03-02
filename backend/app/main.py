from fastapi import FastAPI
from app.api.routes import router
from app.db.session import init_db

app = FastAPI(title="FIRE API", version="0.1.0")

@app.on_event("startup")
def _startup() -> None:
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router)
