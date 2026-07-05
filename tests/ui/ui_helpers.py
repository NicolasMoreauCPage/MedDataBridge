# Helpers communs pour les tests UI Playwright
import time, pytest, httpx

# Messages connus et sans rapport avec un bug applicatif (ex: avertissement du CDN
# Tailwind utilisé en dev), à ignorer lors de la capture d'erreurs console.
_KNOWN_BENIGN_CONSOLE_SNIPPETS = (
    "cdn.tailwindcss.com should not be used in production",
)


def capture_console_errors(page) -> list:
    """Attache des listeners console/pageerror à `page` et retourne la liste
    (mutée en direct) des messages d'erreur non bénins rencontrés.

    À utiliser pour détecter des régressions JS silencieuses (ex: une exception
    interceptée par un try/catch qui n'affiche qu'un toast, sans jamais faire
    échouer un test qui ne vérifie que le DOM/la navigation).
    """
    errors = []

    def _on_console(msg):
        if msg.type != "error":
            return
        text = msg.text
        if any(snippet in text for snippet in _KNOWN_BENIGN_CONSOLE_SNIPPETS):
            return
        errors.append(text)

    def _on_pageerror(exc):
        errors.append(str(exc))

    page.on("console", _on_console)
    page.on("pageerror", _on_pageerror)
    return errors

def wait_for_ready(url: str, max_retries: int = 30, delay: float = 0.5):
    for i in range(max_retries):
        try:
            response = httpx.get(url, follow_redirects=True, timeout=5.0)
            if response.status_code < 400:
                return True
        except Exception:
            pass
        if i < max_retries - 1:
            time.sleep(delay)
    return False

def safe_navigate(page, url: str, timeout_ms: int = 10000):
    max_retries = 3
    for i in range(max_retries):
        try:
            response = page.goto(url, timeout=timeout_ms)
            if response and response.ok:
                return True
        except Exception as e:
            if i == max_retries - 1:
                pytest.fail(f"Failed to navigate to {url}: {str(e)}")
            time.sleep(1)
    return False
