"""Alias de compatibilité vers l'initialisation des vocabulaires."""

import sys

from app.vocabularies import init as _init

sys.modules[__name__] = _init
