from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from img2ec.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="img2ec", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from img2ec.api import projects, scenes, skus, outputs, fs, copy
    app.include_router(projects.router)
    app.include_router(scenes.router)
    app.include_router(skus.router)
    app.include_router(outputs.router)
    app.include_router(fs.router)
    app.include_router(copy.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Mount static files for detail-page templates and other project assets.
    # /static/projects/<project_name>/<sku_name>/... maps to <root_path>/<project_name>/<sku_name>/...
    # check_dir=False so the app starts even if root_path doesn't exist yet (created on first project)
    settings.root_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static/projects", StaticFiles(directory=str(settings.root_path), check_dir=False), name="projects")

    return app


app = create_app()
