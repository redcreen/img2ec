from fastapi import APIRouter
from .lifecycle import router as lifecycle_router
from .images import router as images_router
from .process import router as process_router
from .masters import router as masters_router
from .detail import router as detail_router
from .dimensions import router as dimensions_router

# Create the parent router
router = APIRouter(prefix="/api/projects/{project_id}/skus", tags=["skus"])

# Manually add routes from all child routers using add_api_route
# This bypasses FastAPI's validation that prevents combining parent prefix with child empty-path routes
_child_routers = [
    lifecycle_router,
    images_router,
    process_router,
    masters_router,
    detail_router,
    dimensions_router,
]

for child_router in _child_routers:
    for route in child_router.routes:
        # Use add_api_route to properly apply the parent prefix
        router.add_api_route(
            path=route.path,
            endpoint=route.endpoint,
            methods=list(route.methods) if route.methods else ["GET"],
            name=route.name,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            openapi_extra=route.openapi_extra,
        )
