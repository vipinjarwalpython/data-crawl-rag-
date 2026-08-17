"""
One-time setup script: create the `crawlrag` PostgreSQL database and
seed the `cars` table with 20 sample records.

Credentials are read automatically from the .env file via
app.core.config.settings — no hardcoded values here.

Run this script from the backend directory:
    python scripts/setup_database.py
"""

import asyncio
import sys

import asyncpg

# ---------------------------------------------------------------------------
# Load all settings (including POSTGRES_*) from the project's .env file.
# This is the single source of truth — no credentials are hardcoded here.
# ---------------------------------------------------------------------------
import pathlib
import sys

# Ensure the backend package root is on the path so `app.core.config` is importable
# regardless of which directory the script is called from.
_BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402

POSTGRES_USER = settings.POSTGRES_USER
POSTGRES_PASSWORD = settings.POSTGRES_PASSWORD
POSTGRES_HOST = settings.POSTGRES_HOST
POSTGRES_PORT = settings.POSTGRES_PORT
TARGET_DB = settings.POSTGRES_DB


CREATE_CARS_TABLE_SQL = """
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

SAMPLE_CARS = [
    ("BMW", "E24 635CSi", 1984, "Germany", 189886, 18457.00, "Reserved", "Coupe", "Shark-nose grand tourer, factory colour, original interior."),
    ("BMW", "2002", 1978, "Italy", 181589, 336315.00, "Reserved", "Sedan", "Concours condition 2002, five-speed gearbox."),
    ("BMW", "E28 535i", 1970, "Japan", 73208, 126154.00, "Available", "Sedan", "Fully restored E28 535i, all matching numbers."),
    ("BMW", "E30 M3", 1975, "Italy", 186306, 347873.00, "Sold", "Coupe", "Homologation M3, Concours condition, documented history."),
    ("BMW", "E28 535i", 1968, "United Kingdom", 44686, 349488.00, "Available", "Sedan", "Driver condition E28 535i, recent service history."),
    ("BMW", "E28 535i", 1978, "Italy", 77472, 258187.00, "Available", "Sedan", "Project condition E28 535i, complete car."),
    ("BMW", "328i", 2002, "Germany", 120000, 12500.00, "Available", "Sedan", "Well-maintained 328i, one owner, full service history."),
    ("Ferrari", "308 GTB", 1979, "Italy", 42000, 98000.00, "Available", "Coupe", "Iconic Pininfarina body, Targa roof, dry-sump V8."),
    ("Ford", "Mustang Boss 302", 1970, "USA", 68000, 74500.00, "Reserved", "Coupe", "Numbers-matching Boss 302, high-downforce aero package."),
    ("Jaguar", "E-Type Series 1", 1962, "United Kingdom", 55300, 215000.00, "Available", "Convertible", "Flat-floor early Series 1, external bonnet latches."),
    ("Mercedes-Benz", "300SL Gullwing", 1956, "Germany", 38100, 1250000.00, "Sold", "Coupe", "Original gullwing doors, aluminium body, matching chassis."),
    ("Nissan", "Skyline GT-R R32", 1991, "Japan", 88400, 62000.00, "Available", "Coupe", "RB26 twin-turbo AWD, Godzilla legend, import compliant."),
    ("Porsche", "911 Carrera RS 2.7", 1973, "Germany", 61200, 950000.00, "Reserved", "Coupe", "Lightweight touring spec, duck-tail spoiler, matching engine."),
    ("Toyota", "2000GT", 1968, "Japan", 29700, 785000.00, "Sold", "Coupe", "Ultra-rare Toyota-Yamaha collaboration, DOHC inline-six."),
    ("BMW", "M1", 1980, "Germany", 47800, 520000.00, "Available", "Coupe", "Mid-engine BMW supercar, motorsport homologation road car."),
    ("Ford", "GT40 Mk I", 1966, "USA", 12400, 5400000.00, "Sold", "Coupe", "Le Mans race winner, fully documented racing provenance."),
    ("Porsche", "356 Speedster", 1958, "Germany", 74900, 310000.00, "Available", "Convertible", "Open two-seat roadster, pushrod flat-four, chrome bumpers."),
    ("Mercedes-Benz", "190E 2.3-16", 1985, "Germany", 109500, 45000.00, "Available", "Sedan", "Cosworth-developed 16-valve head, factory touring car."),
    ("Jaguar", "XJ-S HE", 1983, "United Kingdom", 93200, 22000.00, "Available", "Coupe", "V12 high-efficiency engine, factory burgundy with tan interior."),
    ("BMW", "E9 3.0 CSL", 1973, "Germany", 84600, 185000.00, "Reserved", "Coupe", "Batmobile aero kit, lightweight aluminium doors and bonnet."),
]


async def main() -> None:
    admin_dsn = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/postgres"
    target_dsn = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{TARGET_DB}"

    # ── Step 1: Create database if it doesn't exist ───────────────────
    print(f"Connecting to PostgreSQL as '{POSTGRES_USER}' on {POSTGRES_HOST}:{POSTGRES_PORT} …")
    try:
        admin_conn = await asyncpg.connect(admin_dsn)
    except Exception as exc:
        print(f"\n[ERROR] Cannot connect to PostgreSQL: {exc}")
        print("Make sure PostgreSQL is running and credentials in this script match your setup.")
        sys.exit(1)

    exists = await admin_conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = $1", TARGET_DB
    )
    if not exists:
        await admin_conn.execute(f'CREATE DATABASE "{TARGET_DB}"')
        print(f"[OK] Database '{TARGET_DB}' created.")
    else:
        print(f"[OK] Database '{TARGET_DB}' already exists.")

    await admin_conn.close()

    # ── Step 2: Create table ──────────────────────────────────────────
    print(f"\nConnecting to '{TARGET_DB}' database …")
    conn = await asyncpg.connect(target_dsn)

    await conn.execute(CREATE_CARS_TABLE_SQL)
    print("[OK] `cars` table is ready.")

    # Ensure constraint exists if table was created earlier without it
    has_constraint = await conn.fetchval("""
        SELECT 1 FROM pg_constraint
        WHERE conname IN ('cars_brand_model_year_key', 'cars_brand_model_year_unique')
    """)
    if not has_constraint:
        try:
            await conn.execute("ALTER TABLE cars ADD CONSTRAINT cars_brand_model_year_unique UNIQUE (brand, model, year)")
            print("[OK] Added UNIQUE constraint (brand, model, year).")
        except Exception:
            pass

    # ── Step 3: Seed data ─────────────────────────────────────────────
    print(f"\nInserting {len(SAMPLE_CARS)} sample car records …")
    inserted = 0
    for car in SAMPLE_CARS:
        result = await conn.execute(
            """
            INSERT INTO cars
                (brand, model, year, country_of_origin, mileage_km,
                 price_usd, status, category, description)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (brand, model, year) DO NOTHING
            """,
            *car
        )
        rows = int(result.split()[-1])
        inserted += rows

    print(f"[OK] Inserted {inserted} row(s) into `cars`.")

    # ── Step 4: Verify ────────────────────────────────────────────────
    count = await conn.fetchval("SELECT COUNT(*) FROM cars")
    print(f"\n[OK] Total rows in `cars` table: {count}")

    rows_sample = await conn.fetch(
        "SELECT brand, model, year, status, price_usd FROM cars ORDER BY brand LIMIT 5"
    )
    print("\nSample rows:")
    for row in rows_sample:
        print(f"  {row['brand']:<20} {row['model']:<25} {row['year']}  {row['status']:<10}  USD {row['price_usd']:>12,.0f}")

    await conn.close()
    print("\n[DONE] Database setup complete! You can now start the FastAPI server.")


if __name__ == "__main__":
    asyncio.run(main())
