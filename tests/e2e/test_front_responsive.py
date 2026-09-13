"""Régressions de reflow sur les ateliers d'interopérabilité prioritaires."""

import pytest


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/validation", "/messages", "/messages/by-dossier", "/scenarios", "/structure"])
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


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_command_palette_opens_with_keyboard_and_filters(page):
    response = await page.goto("/validation", wait_until="networkidle")

    assert response is not None
    assert response.status == 200
    await page.keyboard.press("Control+k")
    dialog = page.locator("#command-palette")
    assert await dialog.evaluate("element => element.open")
    search = page.locator("#command-palette-search")
    await search.fill("scénarios")
    assert await page.get_by_role("link", name="Catalogue des scénarios").is_visible()
    await page.keyboard.press("Escape")
    assert not await dialog.evaluate("element => element.open")


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_catalog_loads_the_shared_list_workspace(page):
    response = await page.goto("/scenarios", wait_until="networkidle")

    assert response is not None
    assert response.status == 200
    assert await page.locator('script[src*="js/list-workspace.js"]').count() == 1
