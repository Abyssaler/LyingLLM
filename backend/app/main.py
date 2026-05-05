"""FastAPI application factory.

Only assembles routers and middleware — all business logic lives in
``lyingllm``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lyingllm.config.loader import load_providers_catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    # lazy: catalog is loaded on first access so we don't block import
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LyingLLM",
        description="12-player standard Werewolf LLM simulation backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    from lyingllm.api import games, providers, setup, ws
    app.include_router(games.router, prefix="/api")
    app.include_router(providers.router, prefix="/api")
    app.include_router(setup.router, prefix="/api")
    app.include_router(ws.router, prefix="/api")

    return app


app = create_app()
