"""Alias de compatibilité vers l'infrastructure de cache.

L'alias de module conserve notamment le comportement des outils qui remplacent
``app.cache.redis_client`` pendant leurs tests.
"""

import sys

from app.infrastructure import cache as _cache

sys.modules[__name__] = _cache
