"""
CrawlRAG — PostgreSQL database module.

Provides a structured fallback retrieval layer for the RAG pipeline.
When the vector store cannot find relevant context for a query, this
module converts the natural language question into a safe SQL SELECT
statement, executes it against the PostgreSQL knowledge base, and
returns formatted results for the LLM (or directly to the caller).

Public singletons (import-ready):
    db_pool           — asyncpg connection pool manager
    cars_repository   — CRUD layer for the `cars` table
    nl_sql_converter  — LLM-based natural-language → SQL converter
"""

from app.modules.database.connection import db_pool
from app.modules.database.nl_to_sql import nl_sql_converter
from app.modules.database.repository import cars_repository

__all__ = [
    "db_pool",
    "cars_repository",
    "nl_sql_converter",
]
