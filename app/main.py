import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.logging import configure_logging
from .database import Base, engine
from .routes import router

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("startup: creating database tables (db=%s)", settings.database_url)
    Base.metadata.create_all(bind=engine)
    logger.info("startup: complete — serving on http://%s:%d", settings.app_host, settings.app_port)
    yield
    logger.info("shutdown")


app = FastAPI(title="Structural Engineer AI Assistant", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        reload_dirs=["app"],
    )
