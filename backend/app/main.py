from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.market import UNIVERSE, all_ticks
from app.orchestrator import SCENARIOS, run_analysis
from app.profiles import USERS
from app.sessionlog import recent

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"

app = FastAPI(
    title="FinIntel PS-01",
    description="Multi-agent autonomous financial intelligence for retail investors",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeBody(BaseModel):
    symbol: str = "RELIANCE"
    user_id: str = "priya"
    scenario: str = "base"


@app.get("/api/health")
def health():
    return {"ok": True, "universe": list(UNIVERSE)}


@app.get("/api/market")
def market(feed_down: str | None = None):
    return [t.model_dump(mode="json") for t in all_ticks(feed_down)]


@app.get("/api/users")
def users():
    return [u.model_dump(mode="json") for u in USERS.values()]


@app.get("/api/scenarios")
def scenarios():
    return SCENARIOS


@app.post("/api/analyze")
def analyze(body: AnalyzeBody):
    if body.user_id not in USERS:
        raise HTTPException(404, "unknown user")
    if body.scenario not in SCENARIOS:
        raise HTTPException(400, "unknown scenario")
    try:
        return run_analysis(body.symbol, body.user_id, body.scenario).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/sessions")
def sessions():
    return recent(30)


if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        index = DIST / "index.html"
        file = DIST / full_path
        if full_path and file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(index)
