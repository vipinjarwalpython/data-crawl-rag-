import sys
from contextlib import asynccontextmanager

# Ensure Windows Proactor event loop policy for subprocess execution
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.modules.scraping.router import router as scraping_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown routines."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    settings.ensure_directories()
    logger.info(f"Storage directories initialized: {settings.SCRAPED_DIR}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "**CrawlRAG**: High-Performance Web Scraping, Recursive Crawling, "
        "and JSON Data Extraction Engine for RAG Pipelines and AI Chatbots."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(scraping_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health & Info"])
async def root():
    """Root metadata endpoint."""
    return {
        "app_name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "modules": {
            "module_1": "Web Scraping, Recursive Crawler & JSON Storage (Active)",
            "module_2": "Vector Embeddings & Indexing (Planned)",
            "module_3": "RAG Chatbot Pipeline (Planned)"
        }
    }


@app.get("/health", tags=["Health & Info"])
async def health_check():
    """Health check endpoint for container orchestrators and monitoring."""
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "scraped_directory": str(settings.SCRAPED_DIR)
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global unhandled exception catcher."""
    logger.error(f"Unhandled server error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Check logs for details."}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
