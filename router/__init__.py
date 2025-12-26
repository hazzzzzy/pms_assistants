from fastapi import APIRouter

from router.agent import agent_router
from router.user import user_router


def register_routers(app):
    api_router = APIRouter(prefix="/api")

    api_router.include_router(user_router)
    api_router.include_router(agent_router)

    app.include_router(api_router)
