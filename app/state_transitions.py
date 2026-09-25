"""Alias de compatibilité vers les transitions de workflow."""

import sys

from app.workflows import transitions as _transitions

sys.modules[__name__] = _transitions
