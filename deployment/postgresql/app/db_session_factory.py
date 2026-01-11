# app/db_session_factory.py
from app.db import session_factory as session_factory_impl

# Re-export the session_factory from the main app.db module for deployment
def session_factory():
    return session_factory_impl()
