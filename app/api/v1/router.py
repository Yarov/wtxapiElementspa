from fastapi import APIRouter

from app.api.v1.endpoints import health, messages, webhooks

api_router = APIRouter()
api_router.include_router(webhooks.router, prefix="/webhook", tags=["webhooks"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
