"""
Auteur Backend — FastAPI Application Entry Point
AI Video Editing Platform
"""

import re
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_router
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Auteur API",
    description="AI Video Editing Platform — Content Creation Operating System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# In dev mode, allow all localhost ports to avoid CORS issues with random vite ports
DEV_MODE = settings.dev_mode

if DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[re.compile(r"^https?://localhost:\d+$")],
        allow_origin_regex=r"https?://localhost:\d+",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Range"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Range"],
    )

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "app": "Auteur API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
