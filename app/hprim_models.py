"""Compatibilité historique des objets de messages HPRIM XML.

Ils sont désormais regroupés dans :mod:`app.protocols.hprim.models`.
"""

from app.protocols.hprim.models import *  # noqa: F403
from app.protocols.hprim.models import __all__ as _hprim_all

__all__ = _hprim_all
