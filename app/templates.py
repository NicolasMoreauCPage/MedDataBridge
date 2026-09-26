"""Environnement Jinja2 partagé par toutes les routes HTML.

Les filtres doivent être identiques quel que soit le routeur qui rend une
page. Créer un environnement par module rend les macros communes fragiles : un
nouveau filtre dans le layout peut alors casser une page sans relation directe.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.utils.safe_html import sanitize_icon_svg


def none_to_dash(value):
    """Affiche une valeur absente de façon cohérente dans les pages HTML."""
    return "—" if value is None or value == "None" else value


def _parse_display_date(value, formats: tuple[str, ...]):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return value
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return value


def fr_date(value):
    value = _parse_display_date(value, ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d"))
    if value is None:
        return "—"
    try:
        return value.strftime("%d/%m/%Y")
    except (AttributeError, ValueError):
        return value


def fr_datetime(value):
    value = _parse_display_date(
        value,
        ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d"),
    )
    if value is None:
        return "—"
    try:
        return value.strftime("%d/%m/%Y %H:%M")
    except (AttributeError, ValueError):
        return value


def format_hl7_payload(value):
    """Normalise les retours ligne HL7, préservés ensuite par le CSS."""
    if not isinstance(value, str):
        return value
    return value.replace("\r\n", "\n").replace("\r", "\n")


def create_templates() -> Jinja2Templates:
    """Construit l'unique environnement Jinja2 applicatif."""
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    templates.env.filters.update(
        {
            "none_to_dash": none_to_dash,
            "format_hl7_payload": format_hl7_payload,
            "fr_date": fr_date,
            "fr_datetime": fr_datetime,
            "sanitize_icon_svg": sanitize_icon_svg,
        }
    )
    templates.env.globals.update({"fr_date": fr_date, "fr_datetime": fr_datetime})
    return templates


templates = create_templates()
