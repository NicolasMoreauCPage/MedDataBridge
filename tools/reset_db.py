#!/usr/bin/env python3
"""Reset database for development: drop all tables and recreate from SQLModel models.

Usage:
    python tools/reset_db.py [--init-vocab]

Options:
    --init-vocab    Also initialize vocabulary systems after schema creation

This script is intended for development only. It will:
1. Drop all existing tables in medbridge.db
2. Recreate schema from SQLModel models (via create_all)
3. Optionally initialize vocabulary systems if --init-vocab is passed

For production databases, use proper migration tools (Alembic).
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import SQLModel
from app.db import engine, session_factory


def reset_database(init_vocab: bool = False):
    """Drop all tables and recreate schema from models."""
    print("⚠️  WARNING: This will DROP all tables in medbridge.db")
    print("    All data will be lost!")
    
    response = input("\nContinue? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return
    
    print("\n🗑️  Dropping all tables...")
    SQLModel.metadata.drop_all(engine)
    
    print("📦 Creating tables from SQLModel definitions...")
    SQLModel.metadata.create_all(engine)
    
    print("✅ Database schema recreated successfully")
    
    if init_vocab:
        print("\n📚 Initializing vocabulary systems...")
        from app.vocabulary_init import init_vocabularies
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
