from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.core.logging import get_module_logger
from app.modules.scraping.schemas import (
    DocumentListResponse,
    ScrapedDocument,
    UnifiedScrapeRequest,
    UnifiedScrapeResponse
)
from app.modules.scraping.service import scraping_service

logger = get_module_logger(__name__)

router = APIRouter(prefix="/scraping", tags=["Web Scraping & Crawler Engine"])



@router.post(
    "/scrape",
    response_model=UnifiedScrapeResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified Web Scraper & Nested Crawler",
    description=(
        "**One Single Endpoint for Everything**:\n"
        "1. Takes 1 seed URL.\n"
        "2. Renders dynamic JavaScript / React / Next.js SPAs.\n"
        "3. Extracts all words, hierarchical sections (`h1`-`h6`), and clean markdown.\n"
        "4. Automatically discovers all internal links and crawls each subpage one-by-one.\n"
        "5. Saves each page into its own individual JSON file in `data/scraped/`.\n"
        "6. Returns the full structured data of all scraped pages in the response."
    )
)
async def scrape_endpoint(request: UnifiedScrapeRequest):
    """Primary unified scraping endpoint."""
    logger.info("[POST /scraping/scrape] url='%s', max_depth=%d.", request.url, request.max_depth)
    try:
        response = await scraping_service.scrape_website(request)
        logger.info(
            "[POST /scraping/scrape] scraped=%d pages from '%s'.",
            response.total_scraped,
            request.url,
        )
        return response
    except Exception as exc:
        logger.error("[POST /scraping/scrape] failed for '%s': %s", request.url, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed for '{request.url}': {exc}"
        )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Stored JSON Documents",
    description="Returns metadata summaries of all saved JSON files on disk with pagination and search filter."
)
async def list_stored_documents(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Number of items to return"),
    query: Optional[str] = Query(None, description="Optional search filter matching title or URL")
):
    return await scraping_service.list_all_documents(skip=skip, limit=limit, query=query)


@router.get(
    "/documents/{doc_id}",
    response_model=ScrapedDocument,
    status_code=status.HTTP_200_OK,
    summary="Get Scraped Document by ID",
    description="Retrieves the complete JSON payload of a previously scraped document."
)
async def get_stored_document(doc_id: str):
    document = await scraping_service.get_document(doc_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found."
        )
    return document


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Stored Document",
    description="Deletes a scraped JSON document from disk by its document ID."
)
async def delete_stored_document(doc_id: str):
    success = await scraping_service.delete_document(doc_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found or could not be deleted."
        )
    return {"status": "success", "message": f"Document '{doc_id}' successfully deleted."}
