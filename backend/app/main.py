import secrets
import subprocess

from fastapi import Depends, FastAPI, Header, HTTPException
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


@app.post("/admin/seed")
def seed(x_seed_secret: str = Header(...)):
    if not settings.seed_secret or not secrets.compare_digest(x_seed_secret, settings.seed_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    out = []
    for script in ["scripts/seed.py", "scripts/seed_demo.py"]:
        result = subprocess.run(
            ["python", script],
            capture_output=True, text=True, cwd="/app"
        )
        out.append({"script": script, "returncode": result.returncode,
                    "stdout": result.stdout[-3000:], "stderr": result.stderr[-1000:]})
        if result.returncode != 0:
            break
    return out
