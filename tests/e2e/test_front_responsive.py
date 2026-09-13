"""Régressions de reflow sur les ateliers d'interopérabilité prioritaires."""

import pytest


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/validation", "/messages", "/scenarios", "/structure"])
async def test_core_workspace_has_no_document_horizontal_overflow(page, path):
    """À 390 px, une table peut défiler, jamais le document entier."""
    await page.set_viewport_size({"width": 390, "height": 844})
    response = await page.goto(path, wait_until="networkidle")

    assert response is not None
    assert response.status == 200
    dimensions = await page.evaluate(
        """() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth
        })"""
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"]


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_validation_workspace_tabs_are_keyboard_accessible(page):
    await page.set_viewport_size({"width": 390, "height": 844})
    response = await page.goto("/validation", wait_until="networkidle")

    assert response is not None
    assert response.status == 200
    single = page.locator("#tab-single")
    scenario = page.locator("#tab-scenario")
    await single.focus()
    await single.press("ArrowRight")

    assert await scenario.get_attribute("aria-selected") == "true"
    assert not await page.locator("#form-scenario").evaluate(
        "element => element.classList.contains('hidden')"
    )


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_validation_workspace_keeps_reflow_in_dark_theme(page):
    await page.add_init_script("localStorage.setItem('theme', 'dark')")
    await page.set_viewport_size({"width": 390, "height": 844})
    response = await page.goto("/validation", wait_until="networkidle")

    assert response is not None
    assert response.status == 200
    assert await page.locator("html").evaluate(
        "element => element.classList.contains('dark')"
    )
    dimensions = await page.evaluate(
        "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert dimensions[0] <= dimensions[1]
