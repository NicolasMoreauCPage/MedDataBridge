"""Alias de compatibilité vers les métriques d'infrastructure."""

import sys

from app.infrastructure import metrics as _metrics

sys.modules[__name__] = _metrics
