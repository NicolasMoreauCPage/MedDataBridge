#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

BASE = 'http://127.0.0.1:8000'
PAGES = [
    "/",
    "/mouvements/plan-lits",
    "/patients/new/",
    "/dossiers/new/",
    "/admin/ght/",
    "/structure",
    "/structure/chambres",
    "/structure/lits",
    "/mouvements",
    "/cotation-modern/select",
    "/messages",
    "/api-docs",
]

results = []
for p in PAGES:
    url = BASE + p
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
    except Exception as e:
        results.append((p, 'ERROR', str(e)))
        continue
    status = r.status_code
    if status != 200:
        results.append((p, f'HTTP {status}', ''))
        continue
    soup = BeautifulSoup(r.text, 'html.parser')
    # Check for preflight script by looking for the inline script content hint
    preflight = any('Pré-flight theme' in (s.get_text() or '') for s in soup.find_all('script'))
    toggle = bool(soup.find(id='theme-toggle'))
    data_theme = soup.find('html') and soup.find('html').get('data-theme')
    has_dark_class = 'dark' in (soup.find('html').get('class') or [])
    results.append((p, 'OK', {'preflight': preflight, 'toggle': toggle, 'data-theme': data_theme, 'dark-class': has_dark_class}))

if __name__ == '__main__':
    for r in results:
        print(r)
