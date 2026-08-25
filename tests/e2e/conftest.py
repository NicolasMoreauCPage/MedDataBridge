# Configuration des Tests E2E pour Phase 5

import pytest
import pytest_asyncio
import asyncio
from playwright.async_api import async_playwright
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any
from urllib.request import urlopen


# Ensure app runs in testing mode
os.environ.setdefault("TESTING", "1")

# Delay importing the FastAPI app to fixture runtime to avoid heavy
# initialization during pytest collection. Import `app` inside fixtures
# that actually require it.





# The installed pytest-playwright plugin exposes synchronous fixtures.  The E2E
# suite itself is asynchronous, therefore it owns an async ``page`` fixture.

# Keep `test_server` fixture to point to local server under test.


@pytest.fixture(scope="session")
def test_server():
    """Start an isolated application server for browser-based tests.

    Playwright drives a real browser and cannot use FastAPI's in-process
    ``TestClient``.  The former fixture returned ``localhost:8000`` without
    starting anything, making E2E results depend on a manually launched server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    project_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.update({"TESTING": "1", "E2E_TESTING": "1"})
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Le serveur E2E s'est arrêté avant son démarrage")
            try:
                with urlopen(f"{url}/health/live", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Délai dépassé lors du démarrage du serveur E2E")

        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest_asyncio.fixture
async def page(test_server):
    """Create an asynchronous Chromium page bound to the isolated server."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(base_url=test_server)
        browser_page = await context.new_page()
        browser_page.set_default_timeout(30_000)
        browser_page.set_default_navigation_timeout(30_000)
        try:
            yield browser_page
        finally:
            await context.close()
            await browser.close()


@pytest_asyncio.fixture
async def authenticated_page(page, test_server):
    """Prime a browser session for routes that may use it."""
    # Ensure timeout/console behavior matches previous expectations
    page.set_default_timeout(30000)

    # Navigate to root to prime any server-side session/cookies
    await page.goto(f"{test_server}/")

    # If server redirects to /login or /auth, tests may need to provide credentials.
    # For now assume public access or that TEST_AUTH_TOKEN is set and server accepts it.
    current_url = page.url
    if "/login" in current_url or "/auth" in current_url:
        # No-op: leave it to tests or environment to provide auth flow.
        pass

    yield page


class E2ETestHelpers:
    """Helper methods for E2E tests."""
    
    @staticmethod
    async def wait_for_network_idle(page, timeout: int = 10000):
        """Wait for network to be idle (no requests for 500ms)."""
        await page.wait_for_load_state("networkidle", timeout=timeout)
    
    @staticmethod
    async def take_screenshot(page, name: str):
        """Take screenshot for debugging."""
        screenshot_dir = "tests/artifacts/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        await page.screenshot(path=f"{screenshot_dir}/{name}.png", full_page=True)
    
    @staticmethod
    async def wait_for_element_visible(page, selector: str, timeout: int = 10000):
        """Wait for element to be visible."""
        await page.wait_for_selector(selector, state="visible", timeout=timeout)
    
    @staticmethod
    async def click_and_wait(page, selector: str, wait_for_selector: str = None):
        """Click element and wait for response."""
        await page.click(selector)
        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, state="visible")
        else:
            await E2ETestHelpers.wait_for_network_idle(page)
    
    @staticmethod
    async def fill_and_wait(page, selector: str, value: str, wait_for_selector: str = None):
        """Fill input and wait for response."""
        await page.fill(selector, value)
        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, state="visible")
        else:
            await asyncio.sleep(0.5)  # Wait for input processing
    
    @staticmethod
    async def assert_text_content(page, selector: str, expected_text: str):
        """Assert element contains expected text."""
        element = await page.wait_for_selector(selector)
        text_content = await element.text_content()
        assert expected_text in text_content, f"Expected '{expected_text}' not found in '{text_content}'"
    
    @staticmethod
    async def assert_element_visible(page, selector: str):
        """Assert element is visible."""
        element = await page.wait_for_selector(selector, state="visible")
        assert await element.is_visible(), f"Element '{selector}' is not visible"
    
    @staticmethod
    async def assert_element_hidden(page, selector: str):
        """Assert element is hidden or doesn't exist."""
        try:
            element = await page.query_selector(selector)
            if element:
                assert not await element.is_visible(), f"Element '{selector}' should be hidden"
        except:
            pass  # Element doesn't exist, which is expected


@pytest.fixture
def e2e_helpers():
    """Provide E2E test helpers."""
    return E2ETestHelpers


# Custom markers for Phase 5 E2E tests
def pytest_configure(config):
    """Register Phase 5 E2E test markers."""
    config.addinivalue_line("markers", "e2e_phase5_1: Phase 5.1 UX Interactive E2E tests")
    config.addinivalue_line("markers", "e2e_phase5_2: Phase 5.2 Design System E2E tests")
    config.addinivalue_line("markers", "e2e_phase5_3: Phase 5.3 Search Interface E2E tests")
    config.addinivalue_line("markers", "e2e_integration: Cross-phase integration E2E tests")


# Fixtures for specific Phase 5 routes
@pytest_asyncio.fixture
async def design_system_page(authenticated_page, test_server):
    """Navigate to Design System page."""
    await authenticated_page.goto(f"{test_server}/design-system")
    await authenticated_page.wait_for_load_state("networkidle")
    return authenticated_page


@pytest_asyncio.fixture
async def interactive_structure_page(authenticated_page, test_server):
    """Navigate to Interactive Structure page."""
    await authenticated_page.goto(f"{test_server}/structure/interactive")
    await authenticated_page.wait_for_load_state("networkidle")
    return authenticated_page


@pytest_asyncio.fixture
async def search_structure_page(authenticated_page, test_server):
    """Navigate to Search Structure page."""
    await authenticated_page.goto(f"{test_server}/structure/search")
    await authenticated_page.wait_for_load_state("networkidle")
    return authenticated_page


# Data fixtures for tests
@pytest.fixture
def test_structure_data():
    """Provide test structure data."""
    return {
        "search_terms": [
            "cardio",
            "123456789",  # Test FINESS
            "urgence",
            "CHU"
        ],
        "filter_values": {
            "type": ["hospital", "department", "ward"],
            "status": ["active", "inactive"],
            "operational_status": ["operational", "closed"]
        },
        "sample_structure": {
            "nom": "Service Test E2E",
            "code": "TEST_E2E_001",
            "type": "Service",
            "description": "Service créé pour les tests E2E"
        }
    }
