#!/bin/sh
set -eu

# Alembic reads DATABASE_URL when it is explicitly supplied; otherwise its
# local SQLite URL from alembic.ini remains the development default.
python -m alembic upgrade head
exec "$@"
