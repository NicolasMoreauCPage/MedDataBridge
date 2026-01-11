# app/db_session_factory.py
from app.db import session_factory as session_factory_impl, get_session as get_session_impl


# Re-export the session_factory from app.db for callers that import this module
def session_factory():
    return session_factory_impl()


# Backwards-compatible generator function matching the previous get_session()
def get_session():
    # app.db.get_session is a generator-based dependency; re-expose it here
    yield from get_session_impl()
