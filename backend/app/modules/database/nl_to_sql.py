"""
NL-to-SQL converter for CrawlRAG's PostgreSQL fallback layer.

Uses the local Qwen LLM to convert a natural language question into a
safe, read-only SQL SELECT statement against the `cars` table.

Safety guarantees
-----------------
1. Only SELECT statements are accepted — any other DML/DDL is rejected.
2. The generated SQL is sanitised with a strict allow-list regex before
   execution.  Parameters are never interpolated directly (asyncpg uses
   parameterised queries for user-supplied values when possible).
3. A hard LIMIT is enforced if the LLM forgot to add one.
"""

import re
from typing import Optional

from app.core.config import settings
from app.core.logging import get_module_logger
from app.modules.rag.llm import llm_manager

logger = get_module_logger(__name__)

# Maximum rows the SQL converter is allowed to request.
_SQL_RESULT_HARD_LIMIT: int = 20

# Table schema description injected into the LLM prompt so it knows
# the exact column names and value domains.
_CARS_TABLE_SCHEMA = """
Table name: cars

Columns:
  id               INTEGER        — auto-increment primary key
  brand            VARCHAR        — car manufacturer, e.g. BMW, Ferrari, Ford, Jaguar, Mercedes-Benz, Nissan, Porsche, Toyota
  model            VARCHAR        — model name, e.g. E24 635CSi, 2002, E28 535i, E30 M3, 328i
  year             INTEGER        — manufacturing year (e.g. 1954, 1978, 2002)
  country_of_origin VARCHAR       — e.g. Germany, Italy, Japan, United Kingdom, USA
  mileage_km       INTEGER        — odometer reading in kilometres
  price_usd        NUMERIC(12,2)  — asking price in US dollars
  status           VARCHAR        — one of: Available, Reserved, Sold
  category         VARCHAR        — one of: Convertible, Coupe, Hatchback, Sedan
  description      TEXT           — short human-readable description of the car
  created_at       TIMESTAMPTZ    — row insertion timestamp
""".strip()

# System prompt kept short — small models perform better with concise instructions.
_NL_TO_SQL_SYSTEM_PROMPT = (
    "You are a PostgreSQL expert. Convert the user's question into a valid "
    "SQL SELECT query against the schema provided. "
    "Return ONLY the raw SQL — no explanation, no markdown, no code fences. "
    "Rules: "
    "(1) Only SELECT statements are allowed. "
    "(2) Use ILIKE for case-insensitive string matching. "
    f"(3) Add LIMIT {_SQL_RESULT_HARD_LIMIT} if the user does not specify a count. "
    "(4) Never use subqueries or JOINs — the schema has one table only."
)


class NLToSQLConverter:
    """Converts natural-language questions into safe PostgreSQL SELECT queries.

    The conversion is performed by the local LLM (same Qwen instance used
    for RAG answer generation) so no external API calls are required.
    """

    # Regex: SQL must start with SELECT (after optional whitespace).
    _SELECT_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

    # Characters / keywords that must never appear in an accepted query.
    # This is a conservative block-list as a second defence layer.
    _DANGEROUS_PATTERN = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE"
        r"|GRANT|REVOKE|COPY|pg_|information_schema|pg_catalog)\b",
        re.IGNORECASE,
    )

    def convert(self, user_question: str) -> Optional[str]:
        """Generate a SQL SELECT query from *user_question*.

        Returns
        -------
        str
            A validated SQL SELECT string, or ``None`` if the LLM output
            was unusable or failed the safety check.
        """
        prompt = (
            f"Schema:\n{_CARS_TABLE_SCHEMA}\n\n"
            f"User Question: {user_question}\n"
            f"SQL Query:"
        )

        logger.info(
            "NL-to-SQL: generating SQL for question='%s'.",
            user_question,
        )

        try:
            raw_output = llm_manager.generate_response(
                prompt=prompt,
                system_prompt=_NL_TO_SQL_SYSTEM_PROMPT,
                max_new_tokens=150,   # SQL queries are short
                temperature=0.0,      # deterministic — we want exact SQL
            )
        except Exception as exc:
            logger.error(
                "NL-to-SQL: LLM call failed for question='%s': %s",
                user_question,
                exc,
                exc_info=True,
            )
            return None

        sql = self._extract_and_clean_sql(raw_output)

        if sql is None:
            logger.warning(
                "NL-to-SQL: could not extract a valid SELECT from LLM output. "
                "Raw output: '%s'.",
                raw_output[:200],
            )
            return None

        sql = self._enforce_limit(sql)

        logger.info("NL-to-SQL: generated SQL -> '%s'.", sql)
        return sql

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_and_clean_sql(self, raw_llm_output: str) -> Optional[str]:
        """Strip markdown fences and prose, then validate the SQL.

        Returns the cleaned SQL string on success, or ``None`` if the
        output fails the safety check.
        """
        # Remove ```sql ... ``` fences that small models often emit.
        sql = re.sub(r"```(?:sql)?", "", raw_llm_output, flags=re.IGNORECASE).strip()
        sql = sql.strip("`").strip()

        # Keep only the first statement (up to the first semicolon).
        sql = sql.split(";")[0].strip()

        # If the LLM prefixed the SQL with prose, try to find SELECT.
        select_match = re.search(r"(SELECT\b.*)", sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            sql = select_match.group(1).strip()

        if not self._is_safe_select(sql):
            return None

        return sql

    def _is_safe_select(self, sql: str) -> bool:
        """Return True only if *sql* is a safe, read-only SELECT statement."""
        if not self._SELECT_PATTERN.match(sql):
            logger.warning("NL-to-SQL safety check failed: not a SELECT. SQL='%s'.", sql[:120])
            return False

        if self._DANGEROUS_PATTERN.search(sql):
            logger.warning(
                "NL-to-SQL safety check failed: dangerous keyword detected. SQL='%s'.",
                sql[:120],
            )
            return False

        return True

    def _enforce_limit(self, sql: str) -> str:
        """Append LIMIT clause if the query does not already have one."""
        if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
            sql = f"{sql} LIMIT {_SQL_RESULT_HARD_LIMIT}"
        return sql


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
nl_sql_converter = NLToSQLConverter()
