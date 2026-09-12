"""Différences fonctionnelles lisibles entre template et payload compilé."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any


def _add(result: list[dict[str, str]], path: str, before: Any, after: Any) -> None:
    if before != after and len(result) < 100:
        result.append({"path": path, "before": "" if before is None else str(before), "after": "" if after is None else str(after)})


def _hl7_diff(source: str, compiled: str) -> list[dict[str, str]]:
    def fields(payload: str) -> dict[str, list[str]]:
        output: dict[str, list[str]] = {}
        occurrences: dict[str, int] = {}
        for line in payload.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
            if not line:
                continue
            segment, *values = line.split("|")
            occurrences[segment] = occurrences.get(segment, 0) + 1
            output[f"{segment}[{occurrences[segment]}]"] = values
        return output

    before, after, result = fields(source), fields(compiled), []
    for segment in sorted(set(before) | set(after)):
        first, second = before.get(segment, []), after.get(segment, [])
        for index in range(max(len(first), len(second))):
            _add(result, f"{segment}-{index + 1}", first[index] if index < len(first) else None, second[index] if index < len(second) else None)
    return result


def _walk_json(value: Any, path: str, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_json(child, f"{path}.{key}" if path else key, output)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_json(child, f"{path}[{index}]", output)
    else:
        output[path] = value


def _json_diff(source: str, compiled: str) -> list[dict[str, str]]:
    try:
        before_value, after_value = json.loads(source), json.loads(compiled)
    except (json.JSONDecodeError, TypeError):
        return [{"path": "payload", "before": source, "after": compiled}] if source != compiled else []
    before, after, result = {}, {}, []
    _walk_json(before_value, "", before)
    _walk_json(after_value, "", after)
    for path in sorted(set(before) | set(after)):
        _add(result, path, before.get(path), after.get(path))
    return result


def _xml_map(payload: str) -> dict[str, str]:
    root = ET.fromstring(payload)
    output: dict[str, str] = {}

    def visit(node: ET.Element, path: str) -> None:
        output[path] = (node.text or "").strip()
        counts: dict[str, int] = {}
        for child in node:
            tag = child.tag.rsplit("}", 1)[-1]
            counts[tag] = counts.get(tag, 0) + 1
            visit(child, f"{path}/{tag}[{counts[tag]}]")

    visit(root, root.tag.rsplit("}", 1)[-1])
    return output


def _xml_diff(source: str, compiled: str) -> list[dict[str, str]]:
    try:
        before, after = _xml_map(source), _xml_map(compiled)
    except ET.ParseError:
        return [{"path": "payload", "before": source, "after": compiled}] if source != compiled else []
    result: list[dict[str, str]] = []
    for path in sorted(set(before) | set(after)):
        _add(result, path, before.get(path), after.get(path))
    return result


def semantic_diff(source: str, compiled: str, message_format: str | None) -> list[dict[str, str]]:
    """Retourne au plus 100 changements, sans modifier le payload."""
    fmt = (message_format or "hl7").lower()
    if fmt == "hl7":
        return _hl7_diff(source, compiled)
    if fmt in {"json", "fhir"}:
        return _json_diff(source, compiled)
    if fmt in {"xml", "hprim", "hprimxml"}:
        return _xml_diff(source, compiled)
    return [{"path": "payload", "before": source, "after": compiled}] if source != compiled else []
