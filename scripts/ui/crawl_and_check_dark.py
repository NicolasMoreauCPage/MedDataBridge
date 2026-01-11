#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE = 'http://127.0.0.1:8000'
MAX_PAGES = 200

visited = set()
queue = ['/']
results = []

while queue and len(visited) < MAX_PAGES:
    path = queue.pop(0)
    if path in visited:
        continue
    visited.add(path)
    url = urljoin(BASE, path)
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
    except Exception as e:
        results.append((path, 'ERROR', str(e)))
        continue
    status = r.status_code
    if 'text/html' not in r.headers.get('Content-Type', ''):
        results.append((path, f'NON_HTML {status}', ''))
        continue
    if status >= 400:
        results.append((path, f'HTTP {status}', ''))
        continue
    soup = BeautifulSoup(r.text, 'html.parser')
    preflight = any('Pré-flight theme' in (s.get_text() or '') for s in soup.find_all('script'))
    toggle = bool(soup.find(id='theme-toggle'))
    data_theme = soup.find('html') and soup.find('html').get('data-theme')
    has_dark_class = 'dark' in (soup.find('html').get('class') or [])
    results.append((path, 'OK', {'preflight': preflight, 'toggle': toggle, 'data-theme': data_theme, 'dark-class': has_dark_class}))
    # enqueue internal links
    for a in soup.find_all('a', href=True):
        href = a['href']
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != '127.0.0.1:8000' and parsed.netloc != 'localhost:8000':
            continue
        if href.startswith('mailto:') or href.startswith('tel:'):
            continue
        # normalize
        if href.startswith('http'):
            p = urlparse(href).path
        else:
            p = href
        if p.startswith('#') or p.startswith('javascript:'):
            continue
        if p not in visited and p not in queue:
            queue.append(p)

if __name__ == '__main__':
    for r in results:
        print(r)
