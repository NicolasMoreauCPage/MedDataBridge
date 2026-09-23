"""Régressions navigateur complémentaires aux tests Axe."""

from __future__ import annotations

import pytest


PRIORITY_PATHS = ["/scenarios/new", "/structure/wizard", "/validation"]


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
@pytest.mark.parametrize("path", PRIORITY_PATHS)
async def test_priority_workspaces_do_not_raise_browser_errors(page, path: str) -> None:
    """A runtime error must never silently reach a user workspace."""

    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
    page.on(
        "console",
        lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None,
    )
    response = await page.goto(path, wait_until="networkidle")
    assert response is not None and response.status == 200
    await page.wait_for_timeout(250)
    assert not errors, "\n".join(errors)
