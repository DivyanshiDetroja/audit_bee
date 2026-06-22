import secrets
import subprocess
import threading

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.router import router as auth_router
from app.clients.router import router as clients_router
from app.config import settings
from app.database import get_db
from app.documents.router import router as documents_router
from app.integrations.router import router as integrations_router

app = FastAPI(title="Audit Bee API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(clients_router)
app.include_router(integrations_router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}


_seed_status: dict = {"state": "idle", "detail": ""}


def _run_seed_demo():
    _seed_status["state"] = "running"
    result = subprocess.run(
        ["python", "scripts/seed_demo.py"],
        capture_output=True, text=True, cwd="/app"
    )
    if result.returncode == 0:
        _seed_status["state"] = "done"
        _seed_status["detail"] = result.stdout[-500:]
    else:
        _seed_status["state"] = "error"
        _seed_status["detail"] = result.stderr[-500:] or result.stdout[-500:]


def _auth(x_seed_secret: str):
    if not settings.seed_secret or not secrets.compare_digest(x_seed_secret, settings.seed_secret):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/admin/seed-base")
def seed_base(x_seed_secret: str = Header(...)):
    _auth(x_seed_secret)
    result = subprocess.run(
        ["python", "scripts/seed.py"],
        capture_output=True, text=True, cwd="/app"
    )
    return {"returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-500:]}


@app.post("/admin/seed-demo")
def seed_demo(x_seed_secret: str = Header(...)):
    _auth(x_seed_secret)
    if _seed_status["state"] == "running":
        return {"state": "already_running"}
    _seed_status["state"] = "idle"
    t = threading.Thread(target=_run_seed_demo, daemon=True)
    t.start()
    return {"state": "started", "poll": "/admin/seed-status"}


@app.get("/admin/seed-status")
def seed_status(x_seed_secret: str = Header(...)):
    _auth(x_seed_secret)
    return _seed_status
