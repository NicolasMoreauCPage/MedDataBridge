"""Minimal, dependency-free sanitizer for server-rendered Markdown.

The documentation is maintained as Markdown in the repository and needs a
small amount of HTML (tables, code blocks and links) once rendered.  Templates
must never decide themselves that an arbitrary string is safe: this module is
the single explicit boundary that turns rendered Markdown into ``Markup``.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from markupsafe import Markup


_ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "div", "em",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "kbd", "li",
    "ol", "p", "pre", "s", "samp", "span", "strong", "sub", "sup", "table",
    "tbody", "td", "th", "thead", "tr", "ul",
}
_VOID_TAGS = {"br", "hr", "img"}
_GLOBAL_ATTRIBUTES = {"class", "id", "title"}
_TAG_ATTRIBUTES = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
_SAFE_SCHEMES = {"", "http", "https", "mailto"}


def _safe_url(value: str) -> bool:
    """Allow relative links and a deliberately short allow-list of schemes."""
    return urlparse(value).scheme.lower() in _SAFE_SCHEMES


class _DocumentationHtmlSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in _ALLOWED_TAGS:
            return
        permitted = _GLOBAL_ATTRIBUTES | _TAG_ATTRIBUTES.get(tag, set())
        rendered: list[str] = []
        for name, value in attrs:
            name = name.lower()
            value = "" if value is None else value
            if name not in permitted:
                continue
            if name in {"href", "src"} and not _safe_url(value):
                continue
            if name == "target" and value not in {"_blank", "_self"}:
                continue
            rendered.append(f' {name}="{escape(value, quote=True)}"')
        if tag == "a" and any(name.lower() == "target" and value == "_blank" for name, value in attrs):
            rendered.append(' rel="noopener noreferrer"')
        self.parts.append(f"<{tag}{''.join(rendered)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def sanitize_document_html(value: str) -> Markup:
    """Return an explicitly sanitized HTML fragment suitable for Jinja."""
    sanitizer = _DocumentationHtmlSanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return Markup("".join(sanitizer.parts))


class _IconSvgSanitizer(HTMLParser):
    """Keep only the static SVG vocabulary used by the icon macros."""

    _tags = {"svg", "path"}
    _attributes = {
        "svg": {"class", "fill", "stroke", "viewbox", "aria-hidden", "role"},
        "path": {"d", "fill", "stroke", "stroke-linecap", "stroke-linejoin", "stroke-width", "fill-rule", "clip-rule"},
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in self._tags:
            return
        permitted = self._attributes[tag]
        rendered = [
            f' {name.lower()}="{escape(value or "", quote=True)}"'
            for name, value in attrs if name.lower() in permitted
        ]
        self.parts.append(f"<{tag}{''.join(rendered)}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "svg":
            self.parts.append("</svg>")


def sanitize_icon_svg(value: str) -> Markup:
    """Return the internal SVG icon registry after strict structural filtering."""
    sanitizer = _IconSvgSanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return Markup("".join(sanitizer.parts))
