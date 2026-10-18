"""Production entry point: one server for the API and the built frontend.

Run with `uvicorn app.prod:root`. The browser calls /api/..., which the dev proxy normally strips, so
the API app is mounted at /api and the Vite build is served for everything else."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT
from .main import app

root = FastAPI(title="Reeta")
root.mount("/api", app)

dist = REPO_ROOT / "frontend" / "dist"
if dist.is_dir():
    root.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
