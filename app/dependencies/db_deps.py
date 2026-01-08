"""Compatibilité des dépendances DB.

Ce module fournit la fonction `get_session` attendue par d'anciens imports
(`from app.dependencies.db_deps import get_session`) en la réexportant depuis
`app.db`. Cela évite de casser le code existant tout en centralisant la logique
DB dans `app.db`.
"""

from app.db import get_session  # noqa: F401
