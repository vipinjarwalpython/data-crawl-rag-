"""
Cars table repository for CrawlRAG's PostgreSQL fallback layer.

Provides all database interactions for the `cars` table:
  - DDL:  create_table()
  - DML:  seed_sample_data()
  - Query: fetch_all_cars(), execute_safe_select(), search_cars_by_keyword()

All methods are async and use the shared ``db_pool`` singleton so they
integrate naturally with FastAPI's async request lifecycle.
"""

import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.logging import get_module_logger
from app.modules.database.connection import db_pool

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# DDL — table definition
# ---------------------------------------------------------------------------

_CREATE_CARS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cars (
    id                SERIAL          PRIMARY KEY,
    brand             VARCHAR(100)    NOT NULL,
    model             VARCHAR(200)    NOT NULL,
    year              INTEGER,
    country_of_origin VARCHAR(100),
    mileage_km        INTEGER,
    price_usd         NUMERIC(12, 2),
    status            VARCHAR(50),
    category          VARCHAR(100),
    description       TEXT,
    created_at        TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (brand, model, year)
);
"""

# ---------------------------------------------------------------------------
# Seed data — 20 classic cars matching the BMW test-site theme
# ---------------------------------------------------------------------------

_SEED_CARS: List[Dict[str, Any]] = [
    # (brand, model, year, country_of_origin, mileage_km, price_usd, status, category, description)
    {"brand": "BMW", "model": "E24 635CSi", "year": 1984, "country_of_origin": "Germany",
     "mileage_km": 189_886, "price_usd": Decimal("18457.00"), "status": "Reserved",
     "category": "Coupe", "description": "Shark-nose grand tourer, factory colour, original interior."},

    {"brand": "BMW", "model": "2002", "year": 1978, "country_of_origin": "Italy",
     "mileage_km": 181_589, "price_usd": Decimal("336315.00"), "status": "Reserved",
     "category": "Sedan", "description": "Concours condition 2002, five-speed gearbox."},

    {"brand": "BMW", "model": "E28 535i", "year": 1970, "country_of_origin": "Japan",
     "mileage_km": 73_208, "price_usd": Decimal("126154.00"), "status": "Available",
     "category": "Sedan", "description": "Fully restored E28 535i, all matching numbers."},

    {"brand": "BMW", "model": "E30 M3", "year": 1975, "country_of_origin": "Italy",
     "mileage_km": 186_306, "price_usd": Decimal("347873.00"), "status": "Sold",
     "category": "Coupe", "description": "Homologation M3, Concours condition, documented history."},

    {"brand": "BMW", "model": "E28 535i", "year": 1968, "country_of_origin": "United Kingdom",
     "mileage_km": 44_686, "price_usd": Decimal("349488.00"), "status": "Available",
     "category": "Sedan", "description": "Driver condition E28 535i, recent service history."},

    {"brand": "BMW", "model": "E28 535i", "year": 1978, "country_of_origin": "Italy",
     "mileage_km": 77_472, "price_usd": Decimal("258187.00"), "status": "Available",
     "category": "Sedan", "description": "Project condition E28 535i, complete car."},

    {"brand": "BMW", "model": "328i", "year": 2002, "country_of_origin": "Germany",
     "mileage_km": 120_000, "price_usd": Decimal("12500.00"), "status": "Available",
     "category": "Sedan", "description": "Well-maintained 328i, one owner, full service history."},

    {"brand": "Ferrari", "model": "308 GTB", "year": 1979, "country_of_origin": "Italy",
     "mileage_km": 42_000, "price_usd": Decimal("98000.00"), "status": "Available",
     "category": "Coupe", "description": "Iconic Pininfarina body, Targa roof, dry-sump V8."},

    {"brand": "Ford", "model": "Mustang Boss 302", "year": 1970, "country_of_origin": "USA",
     "mileage_km": 68_000, "price_usd": Decimal("74500.00"), "status": "Reserved",
     "category": "Coupe", "description": "Numbers-matching Boss 302, high-downforce aero package."},

    {"brand": "Jaguar", "model": "E-Type Series 1", "year": 1962, "country_of_origin": "United Kingdom",
     "mileage_km": 55_300, "price_usd": Decimal("215000.00"), "status": "Available",
     "category": "Convertible", "description": "Flat-floor early Series 1, external bonnet latches."},

    {"brand": "Mercedes-Benz", "model": "300SL Gullwing", "year": 1956, "country_of_origin": "Germany",
     "mileage_km": 38_100, "price_usd": Decimal("1_250_000.00"), "status": "Sold",
     "category": "Coupe", "description": "Original gullwing doors, aluminium body, matching chassis."},

    {"brand": "Nissan", "model": "Skyline GT-R R32", "year": 1991, "country_of_origin": "Japan",
     "mileage_km": 88_400, "price_usd": Decimal("62000.00"), "status": "Available",
     "category": "Coupe", "description": "RB26 twin-turbo AWD, Godzilla legend, import compliant."},

    {"brand": "Porsche", "model": "911 Carrera RS 2.7", "year": 1973, "country_of_origin": "Germany",
     "mileage_km": 61_200, "price_usd": Decimal("950000.00"), "status": "Reserved",
     "category": "Coupe", "description": "Lightweight touring spec, duck-tail spoiler, matching engine."},

    {"brand": "Toyota", "model": "2000GT", "year": 1968, "country_of_origin": "Japan",
     "mileage_km": 29_700, "price_usd": Decimal("785000.00"), "status": "Sold",
     "category": "Coupe", "description": "Ultra-rare Toyota-Yamaha collaboration, DOHC inline-six."},

    {"brand": "BMW", "model": "M1", "year": 1980, "country_of_origin": "Germany",
     "mileage_km": 47_800, "price_usd": Decimal("520000.00"), "status": "Available",
     "category": "Coupe", "description": "Mid-engine BMW supercar, motorsport homologation road car."},

    {"brand": "Ford", "model": "GT40 Mk I", "year": 1966, "country_of_origin": "USA",
     "mileage_km": 12_400, "price_usd": Decimal("5_400_000.00"), "status": "Sold",
     "category": "Coupe", "description": "Le Mans race winner, fully documented racing provenance."},

    {"brand": "Porsche", "model": "356 Speedster", "year": 1958, "country_of_origin": "Germany",
     "mileage_km": 74_900, "price_usd": Decimal("310000.00"), "status": "Available",
     "category": "Convertible", "description": "Open two-seat roadster, pushrod flat-four, chrome bumpers."},

    {"brand": "Mercedes-Benz", "model": "190E 2.3-16", "year": 1985, "country_of_origin": "Germany",
     "mileage_km": 109_500, "price_usd": Decimal("45000.00"), "status": "Available",
     "category": "Sedan", "description": "Cosworth-developed 16-valve head, factory touring car."},

    {"brand": "Jaguar", "model": "XJ-S HE", "year": 1983, "country_of_origin": "United Kingdom",
     "mileage_km": 93_200, "price_usd": Decimal("22000.00"), "status": "Available",
     "category": "Coupe", "description": "V12 high-efficiency engine, factory burgundy with tan interior."},

    {"brand": "BMW", "model": "E9 3.0 CSL", "year": 1973, "country_of_origin": "Germany",
     "mileage_km": 84_600, "price_usd": Decimal("185000.00"), "status": "Reserved",
     "category": "Coupe", "description": "Batmobile aero kit, lightweight aluminium doors and bonnet."},
]

_INSERT_CAR_SQL = """
INSERT INTO cars
    (brand, model, year, country_of_origin, mileage_km, price_usd, status, category, description)
VALUES
    ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT DO NOTHING;
"""


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class CarsRepository:
    """All database operations for the `cars` table.

    Methods are intentionally fine-grained so that the RAG service and
    the HTTP router can each use exactly what they need.
    """

    # ------------------------------------------------------------------
    # DDL / seed
    # ------------------------------------------------------------------

    async def create_table(self) -> bool:
        """Create the `cars` table if it does not already exist.

        Returns True on success, False if the pool is unavailable.
        """
        logger.info("CarsRepository: ensuring `cars` table exists …")
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(_CREATE_CARS_TABLE_SQL)
            logger.info("CarsRepository: `cars` table is ready.")
            return True
        except Exception as exc:
            logger.error(
                "CarsRepository: failed to create `cars` table: %s",
                exc,
                exc_info=True,
            )
            return False

    async def seed_sample_data(self) -> int:
        """Insert the built-in sample cars into the table.

        Skips rows that already exist (ON CONFLICT DO NOTHING).

        Returns
        -------
        int
            Number of rows actually inserted (0 if already seeded).
        """
        logger.info("CarsRepository: seeding %d sample car records …", len(_SEED_CARS))
        inserted_count = 0

        try:
            async with db_pool.acquire() as conn:
                for car in _SEED_CARS:
                    result = await conn.execute(
                        _INSERT_CAR_SQL,
                        car["brand"],
                        car["model"],
                        car["year"],
                        car["country_of_origin"],
                        car["mileage_km"],
                        car["price_usd"],
                        car["status"],
                        car["category"],
                        car["description"],
                    )
                    # asyncpg returns "INSERT 0 N" — extract N.
                    rows_affected = int(result.split()[-1])
                    inserted_count += rows_affected

            logger.info(
                "CarsRepository: seeding complete — %d/%d rows inserted.",
                inserted_count,
                len(_SEED_CARS),
            )
            return inserted_count

        except Exception as exc:
            logger.error(
                "CarsRepository: seed_sample_data failed: %s",
                exc,
                exc_info=True,
            )
            return 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def fetch_all_cars(self) -> List[Dict[str, Any]]:
        """Return all rows from the `cars` table as plain dicts."""
        logger.debug("CarsRepository: fetching all cars …")
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM cars ORDER BY brand, model, year;")
            result = [dict(row) for row in rows]
            logger.info("CarsRepository: fetched %d car records.", len(result))
            return result
        except Exception as exc:
            logger.error("CarsRepository: fetch_all_cars failed: %s", exc, exc_info=True)
            return []

    async def execute_safe_select(
        self,
        sql: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a pre-validated SELECT statement and return rows as dicts.

        This method trusts that the caller (``NLToSQLConverter``) has already
        validated the SQL.  It adds a final guard to reject non-SELECT queries.

        Returns
        -------
        List[dict]  — results (may be empty list if query returned no rows)
        None        — if execution failed or query was rejected
        """
        if not sql.strip().upper().startswith("SELECT"):
            logger.error(
                "CarsRepository.execute_safe_select: rejected non-SELECT SQL='%s'.",
                sql[:120],
            )
            return None

        start_time = time.perf_counter()
        logger.info("CarsRepository: executing SQL -> '%s'.", sql)

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(sql)

            elapsed = round(time.perf_counter() - start_time, 4)
            result = [dict(row) for row in rows]

            logger.info(
                "CarsRepository: query returned %d row(s) in %.4fs.",
                len(result),
                elapsed,
            )
            return result

        except Exception as exc:
            logger.error(
                "CarsRepository: SQL execution failed for query='%s': %s",
                sql[:120],
                exc,
                exc_info=True,
            )
            return None

    async def search_cars_by_keyword(
        self,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fallback keyword search when NL-to-SQL conversion fails.

        Searches brand, model, category, status, and description columns
        using a case-insensitive ILIKE match.
        """
        pattern = f"%{keyword}%"
        sql = """
            SELECT * FROM cars
            WHERE  brand            ILIKE $1
                OR model            ILIKE $1
                OR category         ILIKE $1
                OR status           ILIKE $1
                OR description      ILIKE $1
                OR country_of_origin ILIKE $1
            ORDER BY brand, model
            LIMIT $2;
        """
        logger.info(
            "CarsRepository: keyword search for '%s' (limit=%d).",
            keyword,
            limit,
        )
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(sql, pattern, limit)
            result = [dict(row) for row in rows]
            logger.info(
                "CarsRepository: keyword search returned %d row(s).",
                len(result),
            )
            return result
        except Exception as exc:
            logger.error(
                "CarsRepository: keyword search failed for keyword='%s': %s",
                keyword,
                exc,
                exc_info=True,
            )
            return []

    async def get_table_row_count(self) -> int:
        """Return the total number of rows in the `cars` table."""
        try:
            async with db_pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM cars;")
            return int(count or 0)
        except Exception as exc:
            logger.error("CarsRepository: get_table_row_count failed: %s", exc)
            return -1


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
cars_repository = CarsRepository()
