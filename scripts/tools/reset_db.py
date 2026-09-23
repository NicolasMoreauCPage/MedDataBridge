#!/usr/bin/env python3
"""Reset database for development: drop all tables and recreate via Alembic.

Usage:
    python tools/reset_db.py [--init-vocab]

Options:
    --init-vocab    Also initialize vocabulary systems after schema creation

This script is intended for development only. It will:
1. Drop all existing tables in medbridge.db
2. Recreate schema through Alembic migrations
3. Optionally initialize vocabulary systems if --init-vocab is passed

For production databases, use proper migration tools (Alembic).
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
from app.db import engine, migrate_database, session_factory  # noqa: E402


def reset_database(init_vocab: bool = False):
    """Drop all tables and recreate the schema through migrations."""
    print("⚠️  WARNING: This will DROP all tables in medbridge.db")
    print("    All data will be lost!")
    
    response = input("\nContinue? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return
    
    print("\n🗑️  Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    print("📦 Applying Alembic migrations...")
    migrate_database(str(engine.url))
    
    print("✅ Database schema recreated successfully")
    
    if init_vocab:
        print("\n📚 Initializing vocabulary systems...")
        from app.vocabularies.init import init_vocabularies
        session = session_factory()
        try:
            init_vocabularies(session)
            session.commit()
            print("✅ Vocabularies initialized")
        except Exception as e:
            session.rollback()
            print(f"❌ Error initializing vocabularies: {e}")
            raise
        finally:
            session.close()
    
    print("\n🎉 Database reset complete!")
    print("\nNext steps:")
    print("  - Start the server: .venv/bin/uvicorn app.app:app --reload")
    print("  - Or run tests: .venv/bin/pytest")


if __name__ == "__main__":
    init_vocab = "--init-vocab" in sys.argv
    reset_database(init_vocab=init_vocab)
