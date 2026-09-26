"""Primitives sûres pour analyser les XML fournis à l'application."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET


_DOCTYPE_DECLARATION = re.compile(r"<!DOCTYPE\b", flags=re.IGNORECASE)


def parse_xml_without_dtd(payload: str) -> ET.Element:
    """Analyse du XML sans DTD, entités externes ni expansion d'entités."""
    if _DOCTYPE_DECLARATION.search(payload):
        raise ET.ParseError("DOCTYPE XML interdite")
    return ET.fromstring(payload)
