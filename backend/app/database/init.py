"""Command-line entry point for explicit database schema initialization.

Usage:

    python -m app.database.init

Runs ``init_schema`` against the configured ``DATABASE_URL`` and returns a non-
zero exit code (via an uncaught exception) if the database cannot be reached or
the schema cannot be created. No credentials or connection strings are printed.

This command must run as an explicit pre-deploy/release step BEFORE application
instances start; application startup performs no schema creation.
"""

import logging
import sys

from app.database.schema_init import init_schema, logger


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    tables = init_schema()
    logger.info("Schema initialization complete. %d tables present.", len(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())