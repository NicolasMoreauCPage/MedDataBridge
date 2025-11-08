#!/usr/bin/env python3
"""Generate a timestamped SQL migration skeleton.

Usage:
    python tools/generate_migration.py "add new field to patient"

Creates migrations/YYYYMMDD_HHMMSS_<slug>.sql with a template body.
Slug is derived from the description: lowercase, hyphens, alphanumerics only.

Safety:
- Does not overwrite existing file.
- Prints path created.
"""
from __future__ import annotations
import sys, re, datetime, pathlib

MIGRATIONS_DIR = pathlib.Path("migrations")

TEMPLATE = """-- Migration: {description}\n-- Created: {created}\n-- Safe to re-run: EDIT AS NEEDED (add idempotent checks)\n-- Down migration: (optional) provide manual revert instructions here\n\n/* Example idempotent pattern (SQLite doesn't support IF NOT EXISTS on ALTER):\n   -- Check existence in Python script or accept duplicate column for dev only.\n*/\n\n-- TODO: add SQL statements below\n-- e.g. ALTER TABLE patient ADD COLUMN new_field TEXT;\n"""

def slugify(desc: str) -> str:
    s = desc.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "migration"

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Description required. Usage: python tools/generate_migration.py 'add xyz'", file=sys.stderr)
        return 1
    description = argv[1].strip()
    slug = slugify(description)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{slug}.sql"
    MIGRATIONS_DIR.mkdir(exist_ok=True)
    path = MIGRATIONS_DIR / filename
    if path.exists():
        print(f"File already exists: {path}", file=sys.stderr)
        return 2
    created = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(TEMPLATE.format(description=description, created=created), encoding="utf-8")
    print(f"Created migration: {path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
