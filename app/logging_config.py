"""Alias de compatibilité vers la configuration de journalisation."""

import sys

from app.infrastructure import logging as _logging

sys.modules[__name__] = _logging
