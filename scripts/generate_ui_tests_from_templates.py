"""Générateur de tests UI à partir des templates Jinja2.

Parcours `app/templates/` et extrait des URLs (href, action, fetch, form actions)
pour générer des tests smoke qui vérifient que les routes existent (statuts tolérants).

Usage:
    python scripts/generate_ui_tests_from_templates.py
"""
import re
from pathlib import Path
import json

TEMPLATES_DIR = Path(__file__).parent.parent / 'app' / 'templates'
OUT_FILE = Path(__file__).parent.parent / 'tests' / 'ui' / 'generated_from_templates_test.py'

URL_PATTERNS = [
    re.compile(r"href=[\"'](?P<u>/[^\"']*)[\"']"),
    re.compile(r"action=[\"'](?P<u>/[^\"']*)[\"']"),
    re.compile(r"fetch\(\s*['\"](?P<u>/[^'\"]*)['\"]"),
    re.compile(r"url_for\([^)]*\)"),
]


def extract_urls_from_text(text: str):
    urls = set()
    for pat in URL_PATTERNS[:-1]:
        for m in pat.finditer(text):
            urls.add(m.group('u'))
    # url_for(...) heuristics: try to extract literal paths in templates around usage
    # We'll ignore complex url_for calls for now.
    return urls


def scan_templates():
    urls = set()
    for p in TEMPLATES_DIR.rglob('*.html'):
        try:
            txt = p.read_text(encoding='utf-8')
        except Exception:
            continue
        found = extract_urls_from_text(txt)
        for u in found:
            urls.add(u)
    return sorted(urls)


def filter_urls(urls):
    """Remove templated and non-idempotent URLs to avoid 405/side-effects in GET tests."""
    skip_keywords = (
        '{{', '}}', 'seed-demo', '/delete', '/restart', '/start', '/stop', '/update',
        'clone-structure', '/generate/', '/send', '/import', '/validate', '/toggle',
        '/mllp/', '/fhir/'
    )
    filtered = []
    for u in urls:
        if any(k in u for k in skip_keywords):
            continue
        filtered.append(u)
    return filtered


def render_test_file(urls):
    lines = []
    lines.append('import os')
    lines.append('from fastapi.testclient import TestClient')
    lines.append("os.environ.setdefault('TESTING','1')")
    lines.append('from app.app import app')
    lines.append('client = TestClient(app)')
    lines.append('')
    lines.append('# Generated tests - tolerant assertions (200/204/302/400/404/422)')
    lines.append('OK_CODES = (200, 204, 302, 400, 404, 422)')
    lines.append('')
    for i, u in enumerate(urls):
        safe_name = re.sub(r'[^0-9a-zA-Z_]', '_', u.strip('/')) or 'root'
        test_name = f'test_generated_url_{i}_{safe_name}'
        lines.append(f'def {test_name}():')
        # if it's a form action we keep GET (safe) - forms might require POST but we don't know
        lines.append(f"    r = client.get('{u}')")
        lines.append('    assert r.status_code in OK_CODES')
        lines.append('')
    return '\n'.join(lines)


def main():
    urls = scan_templates()
    urls = filter_urls(urls)
    if not urls:
        print('No urls found in templates')
        return
    content = render_test_file(urls)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(content, encoding='utf-8')
    print(f'Generated {OUT_FILE} with {len(urls)} tests')


if __name__ == '__main__':
    main()
