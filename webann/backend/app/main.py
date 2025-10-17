from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    health, classes, relations, texts, annotations, semantic, enums
)

def create_app() -> FastAPI:
    app = FastAPI(title="Annotation Backend")

    # CORS (same as before)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (keeps same HTTP paths as your monolith)
    app.include_router(health.router)
    app.include_router(classes.router, prefix="/api", tags=["classes"])
    app.include_router(relations.router, prefix="/api", tags=["relations"])
    app.include_router(texts.router, prefix="/api", tags=["texts"])
    app.include_router(annotations.router, prefix="/api", tags=["annotations"])
    app.include_router(semantic.router, prefix="/api", tags=["semantic"])
    app.include_router(enums.router, prefix="/api", tags=["enums & proposals"])

    return app

app = create_app()
