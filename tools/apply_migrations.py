#!/usr/bin/env python3
"""Apply numbered and timestamped SQL migrations idempotently (SQLite).

Strategy:
1. Collect files in migrations/ matching: ^(\d{3}_.*|\d{8}_\d{6}_.*)\.sql
2. Sort: numeric prefix first (001..999) by number, then timestamped by datetime.
3. Track applied migrations in table migration_log (id INTEGER PK, filename TEXT UNIQUE, applied_at TEXT).
4. For each migration not yet logged, read and execute statements separated by semicolons.
   - Skip empty statements and pure comments.
   - Basic error handling: on failure, print and stop.

NOTE: This is a lightweight mechanism suitable for dev/prototyping. For production
      Alembic remains recommended. Keep legacy numbered migrations intact.
"""
from __future__ import annotations
import sqlite3, re, pathlib, datetime, sys

MIGRATIONS_DIR = pathlib.Path("migrations")
NUMERIC_RE = re.compile(r"^(\d{3})_.*\.sql$")
TS_RE = re.compile(r"^(\d{8}_\d{6})_.*\.sql$")

LOG_TABLE = "migration_log"

def list_migration_files():
    if not MIGRATIONS_DIR.exists():
        return []
    files = []
    for f in MIGRATIONS_DIR.iterdir():
        if not f.is_file():
            continue
        if NUMERIC_RE.match(f.name) or TS_RE.match(f.name):
            files.append(f)
    # Separate numeric and timestamped
    numeric = []
    ts = []
    for f in files:
        m_num = NUMERIC_RE.match(f.name)
        m_ts = TS_RE.match(f.name)
        if m_num:
            numeric.append((int(m_num.group(1)), f))
        elif m_ts:
            # Convert timestamp to sortable key
            ts.append((m_ts.group(1), f))
    numeric.sort(key=lambda x: x[0])
    ts.sort(key=lambda x: x[0])
    ordered = [f for _, f in numeric] + [f for _, f in ts]
    return ordered

def ensure_log_table(conn: sqlite3.Connection):
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {LOG_TABLE} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        applied_at TEXT NOT NULL
    )
    """)

def already_applied(conn: sqlite3.Connection, filename: str) -> bool:
    cur = conn.execute(f"SELECT 1 FROM {LOG_TABLE} WHERE filename=?", (filename,))
    return cur.fetchone() is not None

def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.Error:
        return set()

ALTER_RE = re.compile(r"^ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)", re.IGNORECASE)
ALTER_IF_NOT_EXISTS_RE = re.compile(r"^ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)", re.IGNORECASE)

def apply_migration(conn: sqlite3.Connection, path: pathlib.Path):
    sql_text = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql_text.split(";")]
    executed_any = False
    for stmt in statements:
        if not stmt:
            continue
        # Remove pure comment lines within a statement so mixed comment+SQL executes
        comment_stripped_lines = []
        for line in stmt.splitlines():
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            # naive skip single-line /* */ comments
            if stripped.startswith("/*") and stripped.endswith("*/"):
                continue
            # skip start of block comment (assuming it doesn't contain code on same line)
            if stripped.startswith("/*"):
                continue
            comment_stripped_lines.append(line)
        stmt = "\n".join(comment_stripped_lines).strip()
        if not stmt:
            continue
        # Skip COMMENT statements for SQLite compatibility
        if stmt.upper().startswith("COMMENT "):
            print(f"• Skip COMMENT in {path.name}")
            continue
        # Skip explicit transaction control statements (handled implicitly by connection)
        up = stmt.upper()
        if up.startswith("BEGIN") or up.startswith("COMMIT") or up.startswith("ROLLBACK"):
            print(f"• Skip TX control in {path.name}: {stmt.split()[0]}")
            continue
        # Normalize ALTER ... ADD COLUMN IF NOT EXISTS (not supported in older SQLite) -> without clause
        m_alt_if = ALTER_IF_NOT_EXISTS_RE.match(stmt)
        if m_alt_if:
            tbl, col = m_alt_if.group(1), m_alt_if.group(2)
            # rewrite by removing IF NOT EXISTS portion
            stmt = ALTER_RE.sub(f"ALTER TABLE {tbl} ADD COLUMN {col}", stmt)
        m_alt = ALTER_RE.match(stmt)
        if m_alt:
            tbl, col = m_alt.group(1), m_alt.group(2)
            cols = table_columns(conn, tbl)
            if col in cols:
                print(f"• Skip (exists) {tbl}.{col} in {path.name}")
                continue
        try:
            conn.execute(stmt)
            executed_any = True
        except sqlite3.Error as e:
            up_stmt = stmt.upper()
            # Allow graceful skip of CREATE INDEX statements referencing columns not yet present
            if (up_stmt.startswith("CREATE INDEX") or up_stmt.startswith("CREATE UNIQUE INDEX")):
                if "no such column" in str(e):
                    print(f"• Skip (missing column) index in {path.name}: {stmt.split()[2]}")
                    continue
                if "already exists" in str(e):
                    print(f"• Skip (exists) index in {path.name}: {stmt.split()[2]}")
                    continue
            print(f"✗ Migration {path.name} failed on statement: {stmt[:80]}...", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            raise
    conn.execute(f"INSERT INTO {LOG_TABLE} (filename, applied_at) VALUES (?, ?)", (path.name, datetime.datetime.utcnow().isoformat()))
    if executed_any:
        print(f"✓ Applied {path.name}")
    else:
        print(f"✓ Marked {path.name} as applied (no executable statements or all skipped)")

def main():
    db_path = "poc.db"
    conn = sqlite3.connect(db_path)
    try:
        ensure_log_table(conn)
        files = list_migration_files()
        if not files:
            print("No migration files found.")
            return 0
        for f in files:
            if already_applied(conn, f.name):
                print(f"• Skipping {f.name} (already applied)")
                continue
            apply_migration(conn, f)
        conn.commit()
        print("\nAll pending migrations applied.")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
