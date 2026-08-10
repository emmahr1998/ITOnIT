from fastapi import APIRouter

from app.api.routes import (
    attachments,
    auth,
    categories,
    companies,
    departments,
    health,
    inventory_categories,
    inventory_items,
    locations,
    priorities,
    tickets,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(categories.router)
api_router.include_router(departments.router)
api_router.include_router(locations.router)
api_router.include_router(priorities.router)
api_router.include_router(inventory_categories.router)
api_router.include_router(inventory_items.router)
api_router.include_router(users.router)
api_router.include_router(tickets.flat_router)
api_router.include_router(tickets.router)
api_router.include_router(attachments.router)
