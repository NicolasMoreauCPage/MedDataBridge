"""Compatibilité : configuration des formulaires déplacée vers ``app.forms``.

Les imports internes doivent utiliser :mod:`app.forms.config`. Ce module reste
volontairement mince pour les scripts ou extensions qui importent encore
``app.form_config``.
"""

from app.forms.config import *  # noqa: F403
from app.forms.config import __all__ as _FORM_CONFIG_PUBLIC

__all__ = _FORM_CONFIG_PUBLIC
