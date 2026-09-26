from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router


def create_app() -> FastAPI:
    application = FastAPI(title="Petasan Backend")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()