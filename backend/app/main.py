from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="IT Support Ticket Management System",
    version=settings.APP_VERSION,
)

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to ITOnIT!"}
