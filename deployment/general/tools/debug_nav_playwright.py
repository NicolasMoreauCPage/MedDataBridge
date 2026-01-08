from playwright.sync_api import sync_playwright
import time
import sys
from pathlib import Path

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT_DIR = Path("test_reports")
OUT_DIR.mkdir(exist_ok=True)

console_messages = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))

    print(f"Navigating to {URL}")
    page.goto(URL, timeout=20000)
    # wait for nav
    try:
        page.wait_for_selector("nav", timeout=10000)
    except Exception as e:
        print("nav not found:", e)

    # dump nav html
    try:
        nav = page.locator("nav").nth(0)
        nav_html = nav.inner_html()
        (OUT_DIR / "nav_debug.html").write_text(nav_html, encoding="utf-8")
        print("Wrote test_reports/nav_debug.html")
    except Exception as e:
        print("Could not read nav inner_html:", e)

    # take full page screenshot
    screenshot_path = OUT_DIR / "nav_debug.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"Wrote {screenshot_path}")

    # write console logs
    (OUT_DIR / "nav_console.log").write_text("\n".join(console_messages), encoding="utf-8")
    print("Wrote test_reports/nav_console.log")

    browser.close()

print("Done")
