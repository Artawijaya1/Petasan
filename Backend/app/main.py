from fastapi import FastAPI

from .api.routes import router


def create_app() -> FastAPI:
    application = FastAPI(title="Petasan Backend")
    application.include_router(router)
    return application


app = create_app()