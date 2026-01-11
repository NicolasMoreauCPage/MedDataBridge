import pytest
import json
import secrets
import os


@pytest.fixture
def ght_context(page, test_server):
    """Ensure a selectable GHT context exists and is selected in the browser session.

    Returns the selected ght id.
    """
    # Use the database approach to get the GHT ID
    try:
        from sqlmodel import Session as SQLSession, select
        from sqlalchemy import create_engine
        from app.models_structure import GHTContext

        file_engine = create_engine("sqlite:///./medbridge.db")
        with SQLSession(file_engine) as s:
            existing = s.exec(select(GHTContext).where(GHTContext.code == "TEST")).first()
            if existing:
                gid = existing.id
                try:
                    page.goto(f"{test_server}/context/ght/{gid}", timeout=10000)
                    page.wait_for_load_state("networkidle")
                except Exception:
                    return gid
                return gid
    except Exception:
        return None

    # Fallback: try the token approach if DB fails
    test_token = os.environ.get("TEST_AUTH_TOKEN")
    if test_token:
        try:
            page.goto(f"{test_server}/admin/ght/_test/session/set?token={test_token}&ght_code=TEST", timeout=10000)
            page.wait_for_load_state("networkidle")
            # For now, assume it worked and return a dummy ID - the test will fail if it's wrong
            return 1
        except Exception:
            pass

    return None


@pytest.fixture
def patient_context(page, test_server):
    """Create a minimal patient via API and set the browser patient context cookie and session.

    Returns the created patient id.
    """
    try:
        resp = page.request.post(
            f"{test_server}/patients/api/patients",
            data=json.dumps({"family": "Test", "given": "Patient"}),
            headers={"Content-Type": "application/json"},
            timeout=10000,
        )
        if resp.ok:
            pdata = resp.json()
            pid = pdata.get("id")
            if pid:
                # Navigate to context setter so cookie is set
                page.goto(f"{test_server}/context/patient/{pid}", timeout=10000)
                page.wait_for_load_state("networkidle")
                # Force sessionStorage and cookie for patient_id (for FastAPI/Starlette session)
                try:
                    page.evaluate(f"window.sessionStorage.setItem('patient_id', '{pid}')")
                except Exception:
                    pass
                # Set cookie for patient_id if possible (for fallback in middleware)
                try:
                    page.context.add_cookies([
                        {"name": "patient_id", "value": str(pid), "url": test_server}
                    ])
                except Exception:
                    pass
                return pid
    except Exception:
        return None
    return None
# Temporary file to fix conftest.py
import pytest
import os
import uvicorn
from multiprocessing import Process
from playwright.sync_api import Page, sync_playwright


def run_app(host, port):
    """Function to run the application in a separate process"""
    # Ensure the server process uses the on-disk DB so the test process
    # and the browser-driven server share the same database files.
    import os
    # Keep server child TESTING=0 so the application runs in its normal
    # mode (some code paths assume TESTING is not enabled). The test
    # fixture uses browser navigation to set session where possible.
    os.environ["TESTING"] = "0"

    # Import create_app inside the server process to avoid initializing the
    # full FastAPI app during pytest collection in the parent process.
    from app.app import create_app
    app = create_app()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        timeout_keep_alive=0,
    )
    server = uvicorn.Server(config)
    server.run()


@pytest.fixture(scope="session")
def server():
    """Fixture that starts a FastAPI server for UI tests"""
    import socket
    import time
    import httpx

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]

    host = "127.0.0.1"

    # Start server in a separate process
    # Ensure the DB schema exists on disk so the server process can access it
    try:
        from sqlmodel import SQLModel
        from sqlalchemy import create_engine
        # Create a file-based SQLite engine and ensure tables exist on disk
        file_engine = create_engine("sqlite:///./medbridge.db")
        SQLModel.metadata.create_all(file_engine)
        # Create a deterministic TEST_GHT so the server has a selectable
        # context at startup. This avoids timing issues where the test
        # process creates the GHT after the server has already rendered
        # pages and the id isn't available yet.
        try:
            from sqlmodel import Session as SQLSession, select
            from app.models_structure import GHTContext

            with SQLSession(file_engine) as s:
                existing = s.exec(select(GHTContext).where(GHTContext.code == "TEST_GHT")).first()
                if not existing:
                    ght = GHTContext(name="Test GHT", code="TEST_GHT", is_active=True)
                    s.add(ght)
                    s.commit()
        except Exception:
            # Non-fatal: if model import fails, tests may create contexts later
            pass
    except Exception:
        pass

    proc = Process(target=run_app, args=(host, port))
    # Ensure a test auth token is present in the environment so the server
    # child (which inherits os.environ) will accept browser-originated calls
    # to the test-only endpoints without enabling full TESTING mode.
    token = os.environ.get("TEST_AUTH_TOKEN") or secrets.token_urlsafe(24)
    os.environ["TEST_AUTH_TOKEN"] = token
    proc.start()

    # Wait for server to be ready by checking root URL (more robust)
    url = f"http://{host}:{port}"
    max_retries = 60

    for i in range(max_retries):
        try:
            response = httpx.get(url, follow_redirects=True)
            if response.status_code < 400:
                break
        except Exception as e:
            if i == max_retries - 1:
                raise Exception(f"Server failed to start (timeout): {str(e)}")
            time.sleep(0.5)

    yield url

    # Cleanup: stop the server
    proc.terminate()
    proc.join(timeout=5)
    if proc.is_alive():
        proc.kill()
        proc.join()


@pytest.fixture(scope="session")
def test_server(server):
    """Returns the test server URL"""
    return server


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Browser context configuration with improved defaults"""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        "accept_downloads": False,
        "java_script_enabled": True,
        "ignore_https_errors": True,
        "bypass_csp": True,
    }


@pytest.fixture(scope="session")
def browser(playwright):
    """Session-scoped browser with error handling"""
    browser = playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage'],
    )
    try:
        yield browser
    finally:
        try:
            browser.close()
        except Exception:
            pass


@pytest.fixture
def page(browser, test_server):
    """Fixture that creates a new page with timeout configuration"""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
        bypass_csp=True,
        accept_downloads=False,
    )
    page = context.new_page()
    page.set_default_timeout(10000)  # 10s default for most operations

    # Ensure a GHT context is selected in the browser session to bypass guards
    # and make UI routes like /patients/new/ directly accessible in tests.
    try:
        # Create or retrieve a GHT context via the server API so the server
        # process and the browser share the same session-backed context.
        # Deterministically create a GHT in the on-disk DB so the server
        # process and the browser see the same data, then set session via
        # the test-only endpoint. This avoids form encoding issues when
        # posting to the HTML form endpoint.
        try:
            from sqlmodel import Session as SQLSession, select
            from sqlalchemy import create_engine
            from app.models_structure import GHTContext

            file_engine = create_engine("sqlite:///./medbridge.db")
            with SQLSession(file_engine) as s:
                existing = s.exec(select(GHTContext).where(GHTContext.code == "TEST_GHT")).first()
                if existing:
                    gid = existing.id
                else:
                    ght = GHTContext(name="Test GHT", code="TEST_GHT", is_active=True)
                    s.add(ght)
                    s.commit()
                    s.refresh(ght)
                    gid = ght.id

                # Ensure the Playwright browser context has a plain Solution de repli cookie
                # so middleware can immediately detect the GHT even if the signed
                # session cookie hasn't propagated yet.
                try:
                    import json as _json
                    cookies_to_set = [
                        {"name": "medbridge_test", "value": "1", "url": test_server, "path": "/"},
                        {"name": "medbridge_test_data", "value": _json.dumps({"ght_id": gid}), "url": test_server, "path": "/"},
                    ]
                    try:
                        context.add_cookies(cookies_to_set)
                    except Exception:
                        # older Playwright API might require different signature; best-effort
                        for c in cookies_to_set:
                            context.add_cookies([c])
                except Exception:
                    pass

                # Try to set the session by calling the test-only endpoint from
                # the browser origin. This ensures Set-Cookie is applied to the
                # Playwright browser context. The server child accepts the call
                # when it sees the X-TEST-AUTH header matching TEST_AUTH_TOKEN.
                try:
                    test_token = os.environ.get("TEST_AUTH_TOKEN")
                    if test_token:
                        js = f"""
                        async () => {{
                            const resp = await fetch('{test_server}/admin/ght/_test/session', {{
                                method: 'POST',
                                credentials: 'include',
                                headers: {{ 'Content-Type': 'application/json', 'x-test-auth': '{test_token}' }},
                                body: JSON.stringify({{ ght_code: 'TEST_GHT' }})
                            }});
                            try {{ return await resp.json(); }} catch(e) {{ return {{ok:false}} }}
                        }}
                        """
                        try:
                            # page.evaluate supports async arrow functions
                            res = page.evaluate(js)
                        except Exception:
                            res = None
                    else:
                        res = None

                    # If fetch didn't result in a visible cookie, fall back to
                    # the server-side context setter navigation.
                    try:
                        cookies = context.cookies()
                    except Exception:
                        cookies = []
                    if not cookies:
                        # Try navigating to the GET token helper to avoid CORS/preflight.
                        # Use ght_code so the server resolves its own DB id and sets
                        # the session cookie correctly even if numeric ids differ.
                        test_token = os.environ.get("TEST_AUTH_TOKEN")
                        if test_token:
                            try:
                                page.goto(f"{test_server}/admin/ght/_test/session/set?token={test_token}&ght_code=TEST_GHT", wait_until="domcontentloaded")
                                # After navigation, assert debug-html shows the session
                                try:
                                    page.goto(f"{test_server}/admin/ght/_test/session/debug-html?token={test_token}", timeout=5000)
                                    page.wait_for_selector("ul", timeout=3000)
                                except Exception:
                                    pass
                                # Poll for the signed session cookie to appear in the browser context
                                try:
                                        import time
                                        found = False
                                        for _ in range(12):
                                            cookies = context.cookies()
                                            names = [c.get('name') for c in cookies]
                                            # Playwright SessionMiddleware uses cookie name 'session' by default in this app
                                            if 'session' in names or 'medbridge_test_data' in names:
                                                found = True
                                                break
                                            time.sleep(0.25)
                                        # If cookie not found after polling, continue gracefully.
                                        # Avoid saving artifacts during normal test runs to reduce noise.
                                except Exception:
                                    pass
                            except Exception:
                                page.goto(f"{test_server}/context/ght/{gid}", wait_until="domcontentloaded")
                        else:
                            page.goto(f"{test_server}/context/ght/{gid}", wait_until="domcontentloaded")
                except Exception:
                    page.goto(f"{test_server}/admin/ght/", wait_until="domcontentloaded")
        except Exception:
            # If DB access or test endpoint fails, fall back to visiting the admin page
            page.goto(f"{test_server}/admin/ght/", wait_until="domcontentloaded")
    except Exception:
        # If anything fails here, tests may redirect to /admin/ght and time out;
        # leave it best-effort to not mask other errors.
        pass

    try:
        yield page
    finally:
        try:
            # Ensure main navigation has loaded (best-effort) before closing the context
            page.wait_for_selector("a[href='/patients']", timeout=2000)
        except Exception:
            pass
        context.close()
