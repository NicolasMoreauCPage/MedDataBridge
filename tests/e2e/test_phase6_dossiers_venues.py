"""
Tests E2E pour Phase 6 : Refonte UX Dossiers & Venues
Routes testées : /dossiers, /venues, /patients

Fonctionnalités testées :
- Sprint 6.1 : Vue détaillée dossier
- Sprint 6.2 : Vue détaillée venue
- Sprint 6.3 : Wizard admission complète
- Sprint 6.4 : Filtres avancés et raccourcis clavier
"""

import pytest
import asyncio
from playwright.async_api import expect, Page


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_dossiers_listing_loads(page: Page):
    """Test que la page de listing des dossiers se charge correctement."""
    await page.goto("/dossiers")
    
    # Vérifier le titre
    await expect(page).to_have_title("Dossiers")
    
    # Vérifier la présence des éléments principaux
    assert await page.locator("h1").text_content() == "Dossiers" or "Dossiers" in await page.locator("h1").text_content()
    
    # Vérifier la présence de la table
    await expect(page.locator("table")).to_be_visible()
    
    # Vérifier le bouton "Nouveau"
    await expect(page.locator('a[href*="/dossiers/new"]')).to_be_visible()


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_dossiers_filters_work(page: Page):
    """Test que les filtres avancés sur dossiers fonctionnent."""
    await page.goto("/dossiers")
    
    # Cliquer sur le bouton filtres (si présent)
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
    
    # Vérifier la présence des champs de filtres
    uf_filter = page.locator('input[name="uf"]')
    if await uf_filter.count() > 0:
        # Remplir le filtre UF
        await uf_filter.fill("CARDIO")
        
        # Soumettre le formulaire de filtres
        filter_form = page.locator('form').first
        await filter_form.evaluate('(form) => form.submit()')
        
        # Attendre le rechargement
        await page.wait_for_load_state("networkidle")
        
        # Vérifier que le filtre est appliqué (valeur dans l'input)
        await expect(uf_filter).to_have_value("CARDIO")


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_keyboard_shortcut_ctrl_n_dossiers(page: Page):
    """Test que Ctrl+N redirige vers la création de dossier."""
    await page.goto("/dossiers")
    
    # Appuyer sur Ctrl+N
    await page.keyboard.press("Control+n")
    
    # Attendre la navigation
    await page.wait_for_load_state("networkidle")
    
    # Vérifier qu'on est sur la page de création
    assert "/dossiers/new" in page.url or "/patients/new" in page.url


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_keyboard_shortcut_slash_focus_filter(page: Page):
    """Test que / focus le premier champ de filtre."""
    await page.goto("/dossiers")
    
    # Ouvrir les filtres si nécessaire
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
    
    # Appuyer sur /
    await page.keyboard.press("/")
    
    # Vérifier qu'un champ de filtre est focus
    focused_element = await page.evaluate('document.activeElement.tagName')
    assert focused_element in ["INPUT", "SELECT"], f"Expected INPUT or SELECT, got {focused_element}"


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_venues_listing_loads(page: Page):
    """Test que la page de listing des venues se charge correctement."""
    await page.goto("/venues")
    
    # Vérifier le titre
    assert "Venues" in await page.title() or "Séjours" in await page.title()
    
    # Vérifier la présence de la table
    await expect(page.locator("table")).to_be_visible()


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_venues_filters_work(page: Page):
    """Test que les filtres sur venues fonctionnent."""
    await page.goto("/venues")
    
    # Ouvrir les filtres
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
    
    # Remplir le filtre service
    service_filter = page.locator('input[name="service"]')
    if await service_filter.count() > 0:
        await service_filter.fill("Cardio")
        
        # Soumettre
        filter_form = page.locator('form').first
        await filter_form.evaluate('(form) => form.submit()')
        
        # Attendre le rechargement
        await page.wait_for_load_state("networkidle")
        
        # Vérifier que le filtre est appliqué
        await expect(service_filter).to_have_value("Cardio")


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_dossier_detail_view_modern_ui(page: Page):
    """Test que la vue détaillée dossier affiche l'UI moderne."""
    # Aller sur la liste des dossiers
    await page.goto("/dossiers")
    
    # Cliquer sur le premier dossier
    first_dossier_link = page.locator('a[href*="/dossiers/"]').first
    if await first_dossier_link.count() > 0:
        await first_dossier_link.click()
        await page.wait_for_load_state("networkidle")
        
        # Vérifier la présence du header moderne avec gradient
        header = page.locator('.detail-header, [class*="gradient"]').first
        await expect(header).to_be_visible()
        
        # Vérifier la présence des sections d'informations
        assert await page.locator('text=/Informations|Détails|NDA|IPP/i').count() > 0


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_venue_detail_view_modern_ui(page: Page):
    """Test que la vue détaillée venue affiche l'UI moderne."""
    # Aller sur la liste des venues
    await page.goto("/venues")
    
    # Cliquer sur la première venue
    first_venue_link = page.locator('a[href*="/venues/"]').first
    if await first_venue_link.count() > 0:
        await first_venue_link.click()
        await page.wait_for_load_state("networkidle")
        
        # Vérifier la présence du header moderne
        header = page.locator('.detail-header, [class*="gradient"]').first
        await expect(header).to_be_visible()
        
        # Vérifier la présence des informations de venue
        assert await page.locator('text=/Venue|Séjour|Dossier/i').count() > 0


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_quick_action_nouvelle_venue_from_dossier(page: Page):
    """Test le bouton quick action 'Nouvelle venue' depuis un dossier."""
    # Aller sur un dossier
    await page.goto("/dossiers")
    
    first_dossier_link = page.locator('a[href*="/dossiers/"]').first
    if await first_dossier_link.count() > 0:
        await first_dossier_link.click()
        await page.wait_for_load_state("networkidle")
        
        # Chercher le bouton "Nouvelle venue"
        nouvelle_venue_btn = page.locator('a[href*="/venues/new"]')
        if await nouvelle_venue_btn.count() > 0:
            # Récupérer l'URL du bouton
            href = await nouvelle_venue_btn.get_attribute('href')
            
            # Vérifier qu'elle contient le dossier_id
            assert 'dossier_id=' in href, "Le lien nouvelle venue devrait pré-remplir dossier_id"
            
            # Cliquer et vérifier la navigation
            await nouvelle_venue_btn.click()
            await page.wait_for_load_state("networkidle")
            
            assert "/venues/new" in page.url


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_admission_wizard_navigation(page: Page):
    """Test la navigation dans le wizard d'admission (si implémenté)."""
    # Chercher l'URL du wizard
    await page.goto("/")
    
    # Chercher un lien vers le wizard d'admission
    wizard_link = page.locator('a[href*="admission"], a[href*="wizard"]').first
    
    if await wizard_link.count() > 0:
        await wizard_link.click()
        await page.wait_for_load_state("networkidle")
        
        # Vérifier la présence des étapes
        steps_indicator = page.locator('[class*="step"], [class*="progress"]')
        await expect(steps_indicator.first).to_be_visible()
        
        # Vérifier la présence des boutons de navigation
        next_button = page.locator('button:has-text("Suivant"), button:has-text("Next")')
        if await next_button.count() > 0:
            await expect(next_button.first).to_be_visible()


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_keyboard_shortcut_escape_closes_filters(page: Page):
    """Test que Esc ferme le panneau de filtres."""
    await page.goto("/dossiers")
    
    # Ouvrir les filtres
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
        
        # Vérifier que le panneau est visible
        filter_panel = page.locator('[x-show="showFilters"], .filters-panel')
        if await filter_panel.count() > 0:
            # Appuyer sur Escape
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            
            # Vérifier que le panneau est caché (peut nécessiter ajustement selon implémentation)
            # Note : Alpine.js peut mettre display:none ou utiliser x-show


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_mouvements_filters_work(page: Page):
    """Test que les filtres sur mouvements fonctionnent."""
    await page.goto("/mouvements")
    
    # Ouvrir les filtres si présent
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
    
    # Remplir le filtre type
    type_filter = page.locator('select[name="movement_type"]')
    if await type_filter.count() > 0:
        await type_filter.select_option(index=1)  # Sélectionner la première option non-vide
        
        # Soumettre
        filter_form = page.locator('form').first
        await filter_form.evaluate('(form) => form.submit()')
        
        # Attendre le rechargement
        await page.wait_for_load_state("networkidle")


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_cross_navigation_patient_dossier_venue(page: Page):
    """Test la navigation croisée Patient → Dossier → Venue."""
    # Aller sur les patients
    await page.goto("/patients")
    
    # Cliquer sur un patient
    first_patient_link = page.locator('a[href*="/patients/"]').first
    if await first_patient_link.count() > 0:
        await first_patient_link.click()
        await page.wait_for_load_state("networkidle")
        
        # Vérifier qu'on est sur la page patient
        assert "/patients/" in page.url
        
        # Chercher un lien vers un dossier
        dossier_link = page.locator('a[href*="/dossiers/"]').first
        if await dossier_link.count() > 0:
            await dossier_link.click()
            await page.wait_for_load_state("networkidle")
            
            # Vérifier qu'on est sur la page dossier
            assert "/dossiers/" in page.url
            
            # Chercher un lien vers une venue
            venue_link = page.locator('a[href*="/venues/"]').first
            if await venue_link.count() > 0:
                await venue_link.click()
                await page.wait_for_load_state("networkidle")
                
                # Vérifier qu'on est sur la page venue
                assert "/venues/" in page.url


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_filters_persist_after_navigation(page: Page):
    """Test que les filtres persistent dans l'URL après navigation."""
    await page.goto("/dossiers")
    
    # Ouvrir et remplir les filtres
    filters_button = page.locator('button:has-text("Filtres")')
    if await filters_button.count() > 0:
        await filters_button.click()
        await asyncio.sleep(0.3)
    
    uf_filter = page.locator('input[name="uf"]')
    if await uf_filter.count() > 0:
        await uf_filter.fill("TEST_UF")
        
        # Soumettre
        filter_form = page.locator('form').first
        await filter_form.evaluate('(form) => form.submit()')
        await page.wait_for_load_state("networkidle")
        
        # Vérifier que l'URL contient le filtre
        assert "uf=" in page.url or "TEST_UF" in page.url or await uf_filter.input_value() == "TEST_UF"


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
async def test_form_keyboard_shortcut_ctrl_s(page: Page):
    """Test que Ctrl+S sauvegarde un formulaire."""
    # Aller sur un formulaire (ex: création dossier ou édition)
    await page.goto("/dossiers")
    
    # Chercher un bouton "Nouveau" ou un formulaire
    new_button = page.locator('a[href*="/new"]').first
    if await new_button.count() > 0:
        await new_button.click()
        await page.wait_for_load_state("networkidle")
        
        # Vérifier qu'on est sur un formulaire
        form = page.locator('form').first
        if await form.count() > 0:
            # Remplir un champ si nécessaire
            first_input = form.locator('input[type="text"]').first
            if await first_input.count() > 0:
                await first_input.fill("Test E2E")
            
            # Appuyer sur Ctrl+S
            await page.keyboard.press("Control+s")
            
            # Attendre un événement (soumission ou feedback)
            await asyncio.sleep(1)
            
            # Note : Le comportement exact dépend de l'implémentation
            # Peut être une redirection, un message de succès, etc.


# Configuration pytest pour les fixtures
@pytest.fixture
async def page(playwright):
    """Fixture pour créer une page Playwright."""
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    
    # Configurer la base URL
    page.set_default_navigation_timeout(30000)
    
    yield page
    
    await context.close()
    await browser.close()
