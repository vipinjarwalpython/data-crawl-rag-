"""
CrawlRAG — FastAPI application entry point.

Registers routers, CORS middleware, lifespan hooks, and global exception
handling.  The application description is kept up-to-date with the actual
live pipeline status.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Windows: Proactor event loop is required for Playwright subprocess compatibility.
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
from app.modules.rag.router import router as rag_router
from app.modules.scraping.router import router as scraping_router


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown tasks around the application's lifetime."""
    log_dir = settings.resolve_path(settings.LOG_DIR)
    log_file = log_dir / "crawlrag.log"

    logger.info(
        "Starting %s v0.2.0 (%s mode). Log file: %s.",
        settings.APP_NAME,
        settings.APP_ENV,
        log_file,
    )
    settings.ensure_directories()
    logger.info(
        "Storage directories verified: scraped='%s', vector_store='%s'.",
        settings.resolve_path(settings.SCRAPED_DIR),
        settings.resolve_path(settings.VECTOR_STORE_DIR),
    )
    yield
    logger.info("Shutting down %s.", settings.APP_NAME)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "**CrawlRAG** — High-performance web scraping, recursive BFS crawling, "
        "semantic chunking, dense embedding (BAAI/bge-small-en-v1.5), vector search, "
        "and grounded RAG answer generation with local Qwen2.5-1.5B-Instruct."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(scraping_router, prefix=settings.API_V1_PREFIX)
app.include_router(rag_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health & Info"])
async def root():
    """API metadata and module status overview."""
    return {
        "app_name": settings.APP_NAME,
        "version": "0.2.0",
        "status": "online",
        "docs_url": "/docs",
        "active_modules": {
            "scraping": "Web scraping, BFS recursive crawler, JSON document storage (Active)",
            "rag_pipeline": (
                "Text cleaning, recursive chunking, BAAI/bge-small-en-v1.5 embeddings, "
                "vector store search (Active)"
            ),
            "rag_answer": "Grounded RAG answer generation with Qwen2.5-1.5B-Instruct (Active)",
        },
        "key_endpoints": {
            "scrape": f"{settings.API_V1_PREFIX}/scraping/scrape",
            "embed_all": f"{settings.API_V1_PREFIX}/rag/embed-all",
            "search": f"{settings.API_V1_PREFIX}/rag/search",
            "answer": f"{settings.API_V1_PREFIX}/rag/answer",
            "status": f"{settings.API_V1_PREFIX}/rag/status",
        },
    }


@app.get("/health", tags=["Health & Info"])
async def health_check():
    """Health-check endpoint for container orchestrators and uptime monitors."""
    log_file_path = settings.resolve_path(settings.LOG_DIR) / "crawlrag.log"
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "debug_mode": settings.DEBUG,
        "log_file": str(log_file_path) if log_file_path.exists() else "not yet created",
        "scraped_dir": str(settings.resolve_path(settings.SCRAPED_DIR)),
        "vector_store_dir": str(settings.resolve_path(settings.VECTOR_STORE_DIR)),
    }


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled exceptions — logs and returns 500."""
    logger.error(
        "Unhandled server error at '%s': %s",
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Check server logs for details."
        },
    )


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
