from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.game import router as game_router
from app.api.config import router as config_router
from app.api.ws import router as ws_router
from app.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LyingLLM",
        description="LLM-powered Werewolf Game API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(game_router)
    app.include_router(config_router)
    app.include_router(ws_router)

    @app.get("/")
    async def root() -> dict:
        return {"name": "LyingLLM", "version": "0.1.0", "status": "running"}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.app.host,
        port=s.app.port,
        reload=s.app.debug,
    )