"""
FastAPI router for the PostgreSQL database management endpoints.

Endpoints:
    POST /db/setup           — Create table and seed sample car data
    GET  /db/cars            — List all cars in the database
    POST /db/search          — Natural-language search (NL → SQL → results)
    GET  /db/health          — Connection pool status
"""

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_module_logger
from app.modules.database.connection import db_pool
from app.modules.database.nl_to_sql import nl_sql_converter
from app.modules.database.repository import cars_repository
from app.modules.database.schemas import (
    CarListResponse,
    CarRecord,
    DatabaseSearchResponse,
    DatabaseSetupResponse,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/db", tags=["PostgreSQL Database"])


# ---------------------------------------------------------------------------
# Request schemas (local — only used by this router)
# ---------------------------------------------------------------------------

class NLSearchRequest(BaseModel):
    """Request body for the natural-language database search endpoint."""

    query: str = Field(
        ...,
        min_length=2,
        description="Natural-language question to search the cars database.",
        examples=["Show me all available BMW cars", "Which Porsche models cost more than 300000?"],
    )
    fallback_keyword_search: bool = Field(
        default=True,
        description=(
            "If True and NL-to-SQL conversion fails, fall back to a simple "
            "ILIKE keyword search across all text columns."
        ),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/setup",
    response_model=DatabaseSetupResponse,
    summary="Create Cars Table and Seed Sample Data",
)
async def setup_database() -> DatabaseSetupResponse:
    """Create the `cars` table and insert 20 sample classic car records.

    Safe to call multiple times — DDL uses ``CREATE TABLE IF NOT EXISTS``
    and inserts use ``ON CONFLICT DO NOTHING``.
    """
    logger.info("[POST /db/setup] Starting database table creation and seed.")
    start_time = time.perf_counter()

    # Step 1: Create table
    table_created = await cars_repository.create_table()
    if not table_created:
        raise HTTPException(
            status_code=503,
            detail=(
                "Failed to create the `cars` table. "
                "Check that PostgreSQL is running and connection settings are correct."
            ),
        )

    # Step 2: Seed data
    rows_inserted = await cars_repository.seed_sample_data()
    elapsed = round(time.perf_counter() - start_time, 3)

    logger.info(
        "[POST /db/setup] Setup complete: table_created=%s, rows_inserted=%d, elapsed=%.3fs.",
        table_created,
        rows_inserted,
        elapsed,
    )
    return DatabaseSetupResponse(
        status="success",
        message=(
            f"Table `cars` is ready. "
            f"{rows_inserted} new row(s) inserted (existing rows skipped)."
        ),
        table_created=table_created,
        rows_inserted=rows_inserted,
        elapsed_seconds=elapsed,
    )


@router.get(
    "/cars",
    response_model=CarListResponse,
    summary="List All Cars in the Database",
)
async def list_all_cars() -> CarListResponse:
    """Return every row from the `cars` table, ordered by brand and model."""
    logger.info("[GET /db/cars] Fetching all car records.")
    start_time = time.perf_counter()

    raw_rows = await cars_repository.fetch_all_cars()
    elapsed = round(time.perf_counter() - start_time, 3)

    logger.info("[GET /db/cars] Returned %d car(s) in %.3fs.", len(raw_rows), elapsed)
    return CarListResponse(
        total_count=len(raw_rows),
        cars=[CarRecord(**row) for row in raw_rows],
    )


@router.post(
    "/search",
    response_model=DatabaseSearchResponse,
    summary="Natural-Language Search Against the Cars Database",
)
async def natural_language_search(request: NLSearchRequest) -> DatabaseSearchResponse:
    """Convert a natural-language question into SQL and search the `cars` table.

    1. The LLM generates a safe SELECT query from the user's question.
    2. The query is validated and executed against PostgreSQL.
    3. If NL-to-SQL fails and ``fallback_keyword_search`` is True, a simple
       ILIKE search is run as a fallback.
    4. If no rows are found in either path, an informative "no results"
       message is returned.
    """
    logger.info(
        "[POST /db/search] NL search — query='%s', fallback=%s.",
        request.query,
        request.fallback_keyword_search,
    )
    start_time = time.perf_counter()

    generated_sql: str | None = None
    rows: list[Dict[str, Any]] = []

    # Attempt 1: NL-to-SQL via LLM
    sql = nl_sql_converter.convert(request.query)
    if sql:
        generated_sql = sql
        result = await cars_repository.execute_safe_select(sql)
        if result is not None:
            rows = result

    # Attempt 2: keyword fallback
    if not rows and request.fallback_keyword_search:
        logger.info(
            "[POST /db/search] NL-to-SQL returned no rows — trying keyword fallback.",
        )
        # Use the longest meaningful word in the query as the keyword.
        keywords = sorted(
            [w for w in request.query.split() if len(w) > 3],
            key=len,
            reverse=True,
        )
        if keywords:
            rows = await cars_repository.search_cars_by_keyword(keywords[0])

    elapsed = round(time.perf_counter() - start_time, 3)

    if rows:
        answer = _format_rows_as_answer(rows)
    else:
        answer = "I don't have information about that in the available data."

    logger.info(
        "[POST /db/search] Found %d row(s) in %.3fs for query='%s'.",
        len(rows),
        elapsed,
        request.query,
    )
    return DatabaseSearchResponse(
        query=request.query,
        generated_sql=generated_sql,
        rows_found=len(rows),
        results=rows,
        answer=answer,
    )


@router.get(
    "/health",
    summary="PostgreSQL Connection Pool Health",
)
async def database_health() -> Dict[str, Any]:
    """Return the connection pool status and total row count of the `cars` table."""
    logger.debug("[GET /db/health] Checking database health.")
    pool_stats = db_pool.get_pool_stats()
    row_count = await cars_repository.get_table_row_count() if db_pool.is_connected else -1

    return {
        "status": "connected" if db_pool.is_connected else "disconnected",
        "pool": pool_stats,
        "cars_table_row_count": row_count,
        "postgres_host": settings.POSTGRES_HOST,
        "postgres_db": settings.POSTGRES_DB,
    }


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------

def _format_rows_as_answer(rows: list[Dict[str, Any]]) -> str:
    """Convert a list of car row dicts into a readable summary string.

    This string is what the RAG service will include in the API ``answer``
    field when results come from the database fallback.
    """
    if not rows:
        return "No matching cars found in the database."

    if len(rows) == 1:
        car = rows[0]
        parts = [
            f"{car.get('brand', 'Unknown')} {car.get('model', '')} ({car.get('year', 'N/A')})",
            f"Status: {car.get('status', 'N/A')}",
            f"Category: {car.get('category', 'N/A')}",
            f"Country of Origin: {car.get('country_of_origin', 'N/A')}",
            f"Mileage: {car.get('mileage_km', 'N/A'):,} km" if car.get("mileage_km") else "Mileage: N/A",
            f"Price: USD {car.get('price_usd', 'N/A'):,.2f}" if car.get("price_usd") else "Price: N/A",
        ]
        if car.get("description"):
            parts.append(f"Description: {car['description']}")
        return "\n".join(parts)

    # Multiple rows — bullet list
    summary_lines = [f"Found {len(rows)} matching car(s):\n"]
    for car in rows:
        price = f"USD {car['price_usd']:,.0f}" if car.get("price_usd") else "price N/A"
        line = (
            f"• {car.get('brand', '?')} {car.get('model', '?')} "
            f"({car.get('year', '?')}) — {car.get('status', '?')} — {price}"
        )
        summary_lines.append(line)
    return "\n".join(summary_lines)
