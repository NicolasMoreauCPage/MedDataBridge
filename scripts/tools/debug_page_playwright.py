from playwright.sync_api import sync_playwright
import sys
from pathlib import Path

OUT_DIR = Path("test_reports")
OUT_DIR.mkdir(exist_ok=True)

if len(sys.argv) < 2:
    print('Usage: debug_page_playwright.py <URL>')
    sys.exit(2)
URL = sys.argv[1]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()

    console_msgs = []
    page.on('console', lambda msg: console_msgs.append(f"{msg.type}: {msg.text}"))

    print('Navigating to', URL)
    page.goto(URL, timeout=20000)
    page.wait_for_load_state('networkidle')

    try:
        form = page.locator('form').nth(0)
        form_html = form.inner_html()
        (OUT_DIR / 'dossier_form.html').write_text(form_html, encoding='utf-8')
        print('Wrote dossier_form.html')
    except Exception as e:
        print('No form found or error reading form:', e)

    # capture select current_state if present
    try:
        sel = page.locator("select[name=current_state]").first
        if sel.count() > 0:
            outer = page.evaluate("el => el.outerHTML", sel)
            (OUT_DIR / 'dossier_select_current_state.html').write_text(outer, encoding='utf-8')
            print('Wrote dossier_select_current_state.html')
        else:
            print('select[name=current_state] not found')
    except Exception as e:
        print('Error locating select:', e)

    # full page screenshot
    (OUT_DIR / 'dossier_page.png').write_bytes(page.screenshot(full_page=True))
    print('Wrote dossier_page.png')

    (OUT_DIR / 'dossier_console.log').write_text('\n'.join(console_msgs), encoding='utf-8')
    print('Wrote dossier_console.log')

    browser.close()
    print('Done')
