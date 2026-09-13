"""Conversions explicites pour les booléens issus des formats partenaires."""

from __future__ import annotations

from typing import Any


TRUE_VALUES = frozenset({"1", "true", "t", "yes", "y", "on", "oui"})


def as_bool(value: Any) -> bool:
    """Retourne un booléen sans traiter la chaîne ``\"non\"`` comme vraie.

    Les anciennes bases ont pu contenir des valeurs textuelles HPRIM. Cette
    conversion rend leur lecture compatible pendant la migration vers les
    colonnes booléennes, tout en gardant les représentations ``oui/non`` à la
    frontière XML seulement.
    """

    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().casefold() in TRUE_VALUES
