from fastapi import APIRouter

from app.api.routes import auth, categories, health, tickets

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(categories.router)
api_router.include_router(tickets.router)
