"""
Generic click-crawler: a broad safety net that visits the main navigable pages and
exercises every visible link/button on them, asserting that nothing throws a browser
console error. This exists specifically to catch silent JS regressions (exceptions
swallowed by a try/catch, so nothing shows up in the DOM/response status) of the kind
that let the forms.js GET-submit bug through despite dozens of existing form-specific
tests.

Design choices, deliberately conservative:
- Runs against the UI test suite's own isolated `./medbridge.db` (via the shared
  `test_server`/`page` fixtures), never the shared `./data/medbridge.db` dev database.
- Only *navigates* same-origin links (read-only by construction) and only *clicks*
  buttons that pass a keyword blocklist (destructive/mutating actions are skipped
  outright rather than risk deleting/sending/merging real data in the test DB).
- Breadth-first crawl from a curated set of seed pages, capped by depth and by a
  global page/click budget — covers a large share of the app's clickable surface
  without an unbounded, potentially-runaway full-site crawl.
"""
import pytest
from collections import deque
from urllib.parse import urljoin, urlparse

from .ui_helpers import capture_console_errors, safe_navigate

# Seed pages to start the crawl from. Chosen to cover each top-level nav section
# (structure/activites/interop/ressources/administration) plus list pages that
# themselves link to many detail pages, so the BFS below fans out from a
# representative sample of the whole app rather than just the homepage.
SEED_PAGES = [
    "/",
    "/patients",
    "/dossiers",
    "/venues",
    # NB: /mouvements (bare) is intentionally scoped — it 400s without a
    # venue_id/dossier_id (like /patients/{id} needs an id), so it isn't a real
    # standalone page. Only its parametrized variant is seeded here; the BFS still
    # discovers real /mouvements?venue_id=... links from venue/dossier detail pages.
    "/mouvements/plan-lits",
    "/contacts",
    "/messages",
    "/messages/send",
    "/messages/by-dossier",
    "/messages/rejections",
    "/structure",
    "/structure/search",
    "/structure/poles",
    "/structure/eg",
    "/structure/services",
    "/structure/ufs",
    "/structure/uh",
    "/structure/chambres",
    "/structure/lits",
    "/scenarios",
    "/scenarios/dashboard",
    "/scenarios/templates",
    "/scenarios/runs",
    "/config/scenario-ej",
    "/documentation",
    "/guide",
    "/api-docs",
    "/conformity",
    "/endpoints",
    "/menu",
    "/admin/ght",
    "/vocabularies",
    "/cotation-modern",
    "/ccam",
    "/ngap",
    "/ucd",
    "/lpp",
    "/ihe",
    "/hprim/test-files",
    "/hprim/import",
    "/hprim/messages",
    "/hprim-cotation",
    "/hprim-cotation/dossiers-avec-cotations",
    "/examples/hl7v2",
    "/examples/mfn",
    "/examples/fhir-bundles",
    "/tools/mllp",
    "/tools/endpoints-test",
    "/docs/changelog",
    "/standards",
    "/standards-docs",
    "/dashboard",
    "/cache-dashboard",
    "/metrics/dashboard",
]

# Crawl bounds — kept generous but finite so a broken page that keeps generating new
# same-origin links (or a genuinely huge site) can't make this run indefinitely.
# MAX_TOTAL_PAGES/MAX_TOTAL_BUTTON_CLICKS were raised modestly alongside the SEED_PAGES
# expansion above (~26 -> ~52 seeds) so the BFS still has budget left to fan out into
# organically-discovered detail pages instead of exhausting the whole budget on seeds.
MAX_DEPTH = 2
MAX_TOTAL_PAGES = 150
MAX_LINKS_PER_PAGE = 6
MAX_BUTTONS_PER_PAGE = 4
MAX_TOTAL_BUTTON_CLICKS = 150

# Case-insensitive keywords that mark a button/link as mutating/destructive — skipped
# outright rather than risk state changes (delete, send a real HL7/FHIR message,
# merge patients, confirm a destructive dialog, etc.).
DANGEROUS_KEYWORDS = (
    "supprim", "delete", "désactiv", "desactiv", "envoy", "fusion", "merge",
    "confirm", "réinitialiser", "reinitialiser", "annuler le", "purge",
    "archiv", "valider", "rejeter", "reject",
    # Added when SEED_PAGES was expanded to scenario/HPRIM/cotation pages: these run a
    # scenario against a dossier, transmit/persist a real message, or import HPRIM acts
    # into cotations (e.g. "Lancer l'exécution", "Rejouer maintenant", "Transmettre",
    # "Importer") — most are also guarded by the closest('form') skip already, but the
    # keyword blocklist is kept as defense-in-depth in case a future template moves one
    # of these outside a <form>.
    "lancer", "exécut", "execut", "rejou", "transmet", "import", "traiter",
)

# Link path substrings that are known destructive/mutating actions or leave the app
# (logout, external redirects, fragments) rather than plain page views.
SKIP_LINK_PATTERNS = (
    "/logout", "/delete", "mailto:", "javascript:", "#",
)


def _is_dangerous(text: str) -> bool:
    lowered = (text or "").lower()
    return any(kw in lowered for kw in DANGEROUS_KEYWORDS)


def _collect_internal_links(page, base_url: str) -> list:
    links = []
    seen = set()
    for a in page.locator("a[href]").all():
        try:
            if not a.is_visible():
                continue
            href = a.get_attribute("href")
        except Exception:
            continue
        if not href or any(p in href for p in SKIP_LINK_PATTERNS):
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != urlparse(base_url).netloc:
            continue  # external link
        if not href.startswith("/"):
            continue  # relative/anchor fragments etc.
        try:
            text = a.inner_text()
        except Exception:
            text = ""
        if _is_dangerous(text):
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        links.append(full)
        if len(links) >= MAX_LINKS_PER_PAGE:
            break
    return links


def _collect_safe_buttons(page):
    buttons = []
    for btn in page.locator("button").all():
        try:
            if not btn.is_visible() or not btn.is_enabled():
                continue
            # Skip submit buttons inside forms — form submission flows are already
            # covered by dedicated tests (test_forms.py) and are far more likely to
            # mutate state than a standalone UI toggle/button.
            if btn.evaluate("el => !!el.closest('form')"):
                continue
            text = btn.inner_text()
        except Exception:
            continue
        if _is_dangerous(text):
            continue
        buttons.append(btn)
        if len(buttons) >= MAX_BUTTONS_PER_PAGE:
            break
    return buttons


def _click_safe_buttons_on_current_page(page, page_url, findings, click_budget):
    """Click up to MAX_BUTTONS_PER_PAGE safe buttons on whatever page is currently
    loaded, restoring `page_url` after each click. Mutates `click_budget[0]`
    (a 1-item list used as a mutable counter) and stops once it hits zero."""
    if click_budget[0] <= 0:
        return
    buttons = _collect_safe_buttons(page)
    for btn in buttons:
        if click_budget[0] <= 0:
            break
        try:
            label = btn.inner_text()
        except Exception:
            label = "<button>"
        errors = capture_console_errors(page)
        try:
            btn.click(timeout=3000)
            page.wait_for_timeout(200)
        except Exception:
            continue  # element became stale/covered — not a console error, skip
        click_budget[0] -= 1
        if errors:
            findings.append((f"click '{label}' on {page_url}", "; ".join(errors)))
        # Reset to the original page before the next button, in case the click
        # navigated away or changed visible state.
        if not safe_navigate(page, page_url):
            break
        page.wait_for_load_state("networkidle")


def test_click_crawler_no_console_errors(page, test_server, ght_context):
    """Breadth-first crawl (depth <= MAX_DEPTH) from SEED_PAGES: follow safe links,
    click safe buttons on every page visited, and fail with a consolidated report if
    any browser console error is observed anywhere during the crawl."""
    findings = []  # list of (context, error_text)
    visited = set()
    click_budget = [MAX_TOTAL_BUTTON_CLICKS]

    queue = deque((urljoin(test_server, p), 0) for p in SEED_PAGES)

    while queue and len(visited) < MAX_TOTAL_PAGES:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        errors = capture_console_errors(page)
        if not safe_navigate(page, url):
            findings.append((url, "failed to load page"))
            continue
        page.wait_for_load_state("networkidle")
        if errors:
            findings.append((f"load {url}", "; ".join(errors)))

        # Exercise buttons on this page before following its links onward, so a
        # button that navigates away doesn't cost us the chance to click others.
        _click_safe_buttons_on_current_page(page, url, findings, click_budget)

        if depth >= MAX_DEPTH:
            continue

        # Re-navigate in case a button click above left the page in a different state.
        if not safe_navigate(page, url):
            continue
        page.wait_for_load_state("networkidle")

        for link in _collect_internal_links(page, test_server):
            if link not in visited and len(visited) + len(queue) < MAX_TOTAL_PAGES:
                queue.append((link, depth + 1))

    if findings:
        report = "\n".join(f"  - {ctx}: {err}" for ctx, err in findings)
        pytest.fail(
            f"Console errors found during click crawl "
            f"({len(visited)} pages visited, {MAX_TOTAL_BUTTON_CLICKS - click_budget[0]} buttons clicked):\n{report}"
        )


# A handful of representative pages (one per major nav section) re-checked with dark
# mode forced on. Deliberately not the full SEED_PAGES/BFS list — that would roughly
# double this file's runtime for marginal value, since the dark-mode Tailwind pass
# applies the same `[data-theme="dark"]` CSS rules (see app/templates/base.html) across
# nearly every template rather than page-specific styling.
DARK_MODE_SMOKE_PAGES = ["/", "/patients", "/dossiers", "/structure"]


def test_click_crawler_dark_mode_no_console_errors(page, test_server, ght_context):
    """Force dark mode the same way the header toggle does and re-visit a small
    representative subset of pages, asserting no console error appears.

    base.html's theme toggle (see the `themeToggle` object and the pre-flight script
    near the top of the file) reads/writes a `theme` key in localStorage
    ('light' | 'dark' | 'auto') and applies it as `data-theme` on <html>. We reproduce
    that by setting localStorage directly (equivalent to clicking the toggle until it
    lands on 'dark') and reloading, rather than clicking the toggle button itself,
    so this doesn't depend on how many clicks it takes to cycle to 'dark'.
    """
    findings = []  # list of (context, error_text)

    for path in DARK_MODE_SMOKE_PAGES:
        url = urljoin(test_server, path)
        errors = capture_console_errors(page)
        if not safe_navigate(page, url):
            findings.append((url, "failed to load page"))
            continue
        page.wait_for_load_state("networkidle")
        if errors:
            findings.append((f"load (light) {url}", "; ".join(errors)))

        # Check errors accumulated *before* switching to dark mode, then start a fresh
        # capture for the dark reload so the two don't get conflated (console listeners
        # attached via capture_console_errors stay live across page.reload()).
        errors_after_dark = capture_console_errors(page)
        page.evaluate("localStorage.setItem('theme', 'dark')")
        page.reload()
        page.wait_for_load_state("networkidle")

        applied_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        if applied_theme != "dark":
            findings.append((url, f"dark theme did not apply (data-theme={applied_theme!r})"))
        if errors_after_dark:
            findings.append((f"load (dark) {url}", "; ".join(errors_after_dark)))

        # Exercise the same safe-button pass as the main crawl, but under dark mode,
        # to catch JS that only misbehaves once `[data-theme="dark"]` styles are live
        # (e.g. a script reading computed styles/colors).
        _click_safe_buttons_on_current_page(page, url, findings, [MAX_BUTTONS_PER_PAGE])

    # Reset to light so this test doesn't leak dark-mode state into whichever test
    # (in this file or elsewhere) shares the same `page`/localStorage next.
    page.evaluate("localStorage.setItem('theme', 'light')")

    if findings:
        report = "\n".join(f"  - {ctx}: {err}" for ctx, err in findings)
        pytest.fail(f"Dark-mode smoke check failed on {len(DARK_MODE_SMOKE_PAGES)} pages:\n{report}")
