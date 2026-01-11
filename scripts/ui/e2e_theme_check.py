#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time

BASE = 'http://127.0.0.1:8000'

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width':1280,'height':800})
    page = context.new_page()
    page.goto(BASE+'/', wait_until='networkidle')
    time.sleep(0.5)
    # ensure theme-toggle exists
    if not page.query_selector('#theme-toggle'):
        print('theme-toggle not found on /')
        browser.close()
        raise SystemExit(1)

    # read initial theme
    initial = page.evaluate('() => ({classList: Array.from(document.documentElement.classList), dataTheme: document.documentElement.getAttribute("data-theme")})')
    print('initial', initial)
    page.screenshot(path='e2e_theme_initial.png', full_page=True)

    # cycle once -> next theme
    page.click('#theme-toggle')
    time.sleep(0.2)
    after1 = page.evaluate('() => ({classList: Array.from(document.documentElement.classList), dataTheme: document.documentElement.getAttribute("data-theme")})')
    print('after1', after1)
    page.screenshot(path='e2e_theme_after1.png', full_page=True)

    # cycle again
    page.click('#theme-toggle')
    time.sleep(0.2)
    after2 = page.evaluate('() => ({classList: Array.from(document.documentElement.classList), dataTheme: document.documentElement.getAttribute("data-theme")})')
    print('after2', after2)
    page.screenshot(path='e2e_theme_after2.png', full_page=True)

    # cycle third time
    page.click('#theme-toggle')
    time.sleep(0.2)
    after3 = page.evaluate('() => ({classList: Array.from(document.documentElement.classList), dataTheme: document.documentElement.getAttribute("data-theme")})')
    print('after3', after3)
    page.screenshot(path='e2e_theme_after3.png', full_page=True)

    browser.close()
    print('screenshots saved: e2e_theme_initial.png, e2e_theme_after1.png, e2e_theme_after2.png, e2e_theme_after3.png')
