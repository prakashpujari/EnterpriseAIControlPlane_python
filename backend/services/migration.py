#!/usr/bin/env python3
"""
Database migration script for Enterprise AI Customer Support Assistant.
Run this script to initialize the database schema.
"""

import asyncio
import sys
from sqlalchemy import text

from app.config.database import engine, Base
from app.config.settings import settings


async def run_migrations():
    """Run database migrations."""
    print("Running database migrations...")

    async with engine.begin() as conn:
        # Create all tables
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

    print("Migrations completed successfully!")


async def drop_migrations():
    """Drop all tables (for testing only!)."""
    print("WARNING: This will drop all tables!")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("Tables dropped successfully!")


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        asyncio.run(drop_migrations())
    else:
        asyncio.run(run_migrations())


if __name__ == "__main__":
    main()