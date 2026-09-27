from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .services.agent_runner import cleanup_target_processes


@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    await cleanup_target_processes()


def create_app() -> FastAPI:
    application = FastAPI(title="Petasan Backend", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()