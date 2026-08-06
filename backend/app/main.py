from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="IT Support Ticket Management System",
    version=settings.APP_VERSION,
)

# CORS: lets a browser-based frontend on a different origin (e.g. the React
# dev server) call this API. Allowed origins live in settings.CORS_ORIGINS
# (app/core/config.py / the CORS_ORIGINS env var) - update that list per
# environment; nothing here should need to change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to ITOnIT!"}
