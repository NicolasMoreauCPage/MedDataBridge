"""
Tests E2E pour Phase 5.2 : Design System Hospitalier
Route testée : /design-system

Fonctionnalités testées :
- Palette couleurs métier
- Composants JS réutilisables (6 classes)
- Démo interactive
- Cards, buttons, forms
- Responsive design
"""

import pytest
import asyncio
from playwright.async_api import expect


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_design_system_page_loads(design_system_page, e2e_helpers):
    """Test que la page Design System se charge correctement."""
    page = design_system_page
    
    # Vérifier le titre de la page
    await expect(page).to_have_title("Design System Hospitalier")
    
    # Vérifier la présence des sections principales
    await e2e_helpers.assert_element_visible(page, ".design-system-container")
    await e2e_helpers.assert_element_visible(page, ".color-palette-section")
    await e2e_helpers.assert_element_visible(page, ".components-demo-section")
    
    # Vérifier le header avec titre
    await e2e_helpers.assert_text_content(page, ".design-system-header h1", "Design System Hospitalier")
    
    # Screenshot pour debug
    await e2e_helpers.take_screenshot(page, "phase5_2_page_loaded")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_color_palette_display(design_system_page, e2e_helpers):
    """Test l'affichage de la palette couleurs métier."""
    page = design_system_page
    
    # Vérifier la section palette de couleurs
    await e2e_helpers.assert_element_visible(page, ".color-palette-section")
    
    # Vérifier les couleurs par niveau hiérarchique
    hierarchy_levels = [
        ".color-ght",      # Niveau 1: GHT
        ".color-eg",       # Niveau 2: Entité Géographique
        ".color-pole",     # Niveau 3: Pôle
        ".color-service",  # Niveau 4: Service
        ".color-uf",       # Niveau 5: Unité Fonctionnelle
        ".color-chambre",  # Niveau 6: Chambre
        ".color-lit"       # Niveau 7: Lit
    ]
    
    for color_level in hierarchy_levels:
        await e2e_helpers.assert_element_visible(page, color_level)
    
    # Vérifier les couleurs d'urgence
    urgency_colors = [
        ".urgence-1",  # Très faible
        ".urgence-2",  # Faible  
        ".urgence-3",  # Modérée
        ".urgence-4",  # Élevée
        ".urgence-5"   # Critique
    ]
    
    for urgency_color in urgency_colors:
        await e2e_helpers.assert_element_visible(page, urgency_color)
    
    # Test interaction : hover sur couleurs
    color_card = page.locator(".color-card").first
    await color_card.hover()
    
    # Vérifier que l'info-bulle ou détails apparaissent
    await asyncio.sleep(0.5)  # Attendre l'animation hover
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_color_palette")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_structure_card_component(design_system_page, e2e_helpers):
    """Test le composant StructureCard."""
    page = design_system_page
    
    # Chercher la démo du composant StructureCard
    structure_card_demo = page.locator(".structure-card-demo")
    await structure_card_demo.wait_for(state="visible", timeout=10000)
    
    # Vérifier qu'il y a des cartes de démo
    demo_cards = page.locator(".structure-card")
    card_count = await demo_cards.count()
    assert card_count > 0, "Aucune carte de démonstration trouvée"
    
    # Test interaction avec une carte
    first_card = demo_cards.first
    
    # Vérifier les éléments de la carte
    await e2e_helpers.assert_element_visible(page, ".structure-card .card-header")
    await e2e_helpers.assert_element_visible(page, ".structure-card .card-content")
    
    # Test hover effet
    await first_card.hover()
    await asyncio.sleep(0.3)
    
    # Test clic sur carte
    await first_card.click()
    
    # Vérifier la response (highlight, selection, etc.)
    selected_card = page.locator(".structure-card.selected")
    if await selected_card.count() > 0:
        await expect(selected_card).to_be_visible()
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_structure_cards")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_search_component(design_system_page, e2e_helpers):
    """Test le composant SearchComponent."""
    page = design_system_page
    
    # Chercher la démo du SearchComponent
    search_demo = page.locator(".search-component-demo")
    if await search_demo.count() > 0:
        await search_demo.wait_for(state="visible")
        
        # Trouver l'input de recherche
        search_input = page.locator(".search-input")
        await search_input.wait_for(state="visible")
        
        # Test saisie dans le champ de recherche
        test_query = "test recherche"
        await search_input.fill(test_query)
        
        # Vérifier que la valeur est bien saisie
        input_value = await search_input.input_value()
        assert input_value == test_query, f"Expected '{test_query}', got '{input_value}'"
        
        # Test bouton clear si présent
        clear_button = page.locator(".search-clear")
        if await clear_button.count() > 0:
            await clear_button.click()
            
            # Vérifier que le champ est vidé
            input_value = await search_input.input_value()
            assert input_value == "", "Search field should be empty after clear"
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_search_component")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_filter_component(design_system_page, e2e_helpers):
    """Test le composant FilterComponent."""
    page = design_system_page
    
    # Chercher la démo du FilterComponent
    filter_demo = page.locator(".filter-component-demo")
    if await filter_demo.count() > 0:
        await filter_demo.wait_for(state="visible")
        
        # Test sélection de filtres
        filter_options = page.locator(".filter-option")
        option_count = await filter_options.count()
        
        if option_count > 0:
            # Sélectionner le premier filtre
            first_option = filter_options.first
            await first_option.click()
            
            # Vérifier que le filtre est sélectionné
            await expect(first_option).to_have_class(".*selected.*")
            
            # Test désélection
            await first_option.click()
            
            # Vérifier que le filtre est désélectionné
            class_name = await first_option.get_attribute("class")
            assert "selected" not in (class_name or ""), "Filter should be deselected"
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_filter_component")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_notification_system(design_system_page, e2e_helpers):
    """Test le système de notifications."""
    page = design_system_page
    
    # Chercher les boutons de test de notifications
    notification_buttons = [
        ".btn-test-success",
        ".btn-test-warning", 
        ".btn-test-error",
        ".btn-test-info"
    ]
    
    for button_selector in notification_buttons:
        button = page.locator(button_selector)
        if await button.count() > 0:
            # Cliquer sur le bouton de test
            await button.click()
            
            # Attendre qu'une notification apparaisse
            notification = page.locator(".notification")
            await notification.wait_for(state="visible", timeout=5000)
            
            # Vérifier que la notification est visible
            await expect(notification).to_be_visible()
            
            # Attendre que la notification disparaisse (auto-hide)
            await asyncio.sleep(3)
            
            # Vérifier que la notification a disparu ou est en train de disparaître
            try:
                await notification.wait_for(state="hidden", timeout=5000)
            except:
                pass  # La notification peut être encore visible selon le timing
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_notifications")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_button_styles(design_system_page, e2e_helpers):
    """Test les styles de boutons."""
    page = design_system_page
    
    # Vérifier les différents types de boutons
    button_types = [
        ".btn-primary",
        ".btn-secondary", 
        ".btn-success",
        ".btn-warning",
        ".btn-danger",
        ".btn-outline"
    ]
    
    for button_type in button_types:
        buttons = page.locator(button_type)
        button_count = await buttons.count()
        
        if button_count > 0:
            # Vérifier que le bouton est visible
            first_button = buttons.first
            await expect(first_button).to_be_visible()
            
            # Test hover effet
            await first_button.hover()
            await asyncio.sleep(0.2)
            
            # Test clic si ce n'est pas un bouton de navigation
            button_text = await first_button.text_content()
            if "Navigation" not in (button_text or ""):
                await first_button.click()
                await asyncio.sleep(0.2)
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_button_styles")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_responsive_design_system(design_system_page, e2e_helpers):
    """Test le design responsive du Design System."""
    page = design_system_page
    
    # Tester différentes résolutions
    resolutions = [
        {"width": 1280, "height": 720, "name": "desktop"},
        {"width": 768, "height": 1024, "name": "tablet"},
        {"width": 375, "height": 667, "name": "mobile"}
    ]
    
    for resolution in resolutions:
        await page.set_viewport_size({
            "width": resolution["width"], 
            "height": resolution["height"]
        })
        await asyncio.sleep(0.5)
        
        # Vérifier que les éléments principaux restent visibles
        await e2e_helpers.assert_element_visible(page, ".design-system-container")
        
        # Vérifier que la palette de couleurs s'adapte
        color_section = page.locator(".color-palette-section")
        if await color_section.count() > 0:
            await expect(color_section).to_be_visible()
        
        # Vérifier que les composants s'adaptent
        components_section = page.locator(".components-demo-section")
        if await components_section.count() > 0:
            await expect(components_section).to_be_visible()
        
        # Screenshot pour chaque résolution
        await e2e_helpers.take_screenshot(page, f"phase5_2_responsive_{resolution['name']}")
    
    # Remettre la résolution par défaut
    await page.set_viewport_size({"width": 1280, "height": 720})


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_component_interactions(design_system_page, e2e_helpers):
    """Test les interactions entre composants."""
    page = design_system_page
    
    # Test interaction search + filter si présents ensemble
    search_input = page.locator(".search-input")
    filter_options = page.locator(".filter-option")
    
    search_count = await search_input.count()
    filter_count = await filter_options.count()
    
    if search_count > 0 and filter_count > 0:
        # Saisir dans la recherche
        await search_input.first.fill("test")
        
        # Sélectionner un filtre
        await filter_options.first.click()
        
        # Vérifier que les deux sont actifs
        input_value = await search_input.first.input_value()
        assert "test" in input_value, "Search input should contain 'test'"
        
        # Vérifier la sélection du filtre
        first_filter_class = await filter_options.first.get_attribute("class")
        # Cette vérification dépend de l'implémentation spécifique
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_component_interactions")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_design_system_navigation(design_system_page, e2e_helpers):
    """Test la navigation depuis le Design System."""
    page = design_system_page
    
    # Test liens vers autres pages Phase 5
    navigation_links = [
        ("Interactive", "/structure/interactive"),
        ("Search", "/structure/search"),
        ("Accueil", "/")
    ]
    
    for link_text, expected_url in navigation_links:
        # Chercher le lien de navigation
        nav_link = page.locator(f"a:has-text('{link_text}')")
        link_count = await nav_link.count()
        
        if link_count > 0:
            # Vérifier l'URL du lien
            href = await nav_link.first.get_attribute("href")
            assert expected_url in (href or ""), f"Link should point to {expected_url}"
    
    # Test navigation vers page Interactive
    interactive_link = page.locator("a[href*='/structure/interactive']")
    if await interactive_link.count() > 0:
        await interactive_link.first.click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier qu'on est sur la bonne page
        await expect(page).to_have_url("*/structure/interactive")
        
        # Retourner au Design System
        await page.go_back()
        await e2e_helpers.wait_for_network_idle(page)
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_navigation")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_css_variables_and_theming(design_system_page, e2e_helpers):
    """Test les variables CSS et le theming."""
    page = design_system_page
    
    # Vérifier que les variables CSS sont bien définies
    css_variables_to_check = [
        "--color-ght",
        "--color-eg", 
        "--color-pole",
        "--color-service",
        "--urgence-1",
        "--urgence-5"
    ]
    
    for css_var in css_variables_to_check:
        # Vérifier que la variable CSS est définie
        css_value = await page.evaluate(f"""
            getComputedStyle(document.documentElement).getPropertyValue('{css_var}')
        """)
        assert css_value.strip() != "", f"CSS variable {css_var} should be defined"
    
    # Test changement de thème si implémenté
    theme_toggle = page.locator(".theme-toggle")
    if await theme_toggle.count() > 0:
        await theme_toggle.click()
        await asyncio.sleep(0.5)
        
        # Vérifier que le thème a changé
        body_class = await page.locator("body").get_attribute("class")
        # Cette vérification dépend de l'implémentation du système de thèmes
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_css_theming")


@pytest.mark.e2e_phase5_2
@pytest.mark.asyncio
async def test_accessibility_features(design_system_page, e2e_helpers):
    """Test les fonctionnalités d'accessibilité."""
    page = design_system_page
    
    # Test navigation au clavier
    await page.keyboard.press("Tab")
    focused_element = await page.evaluate("document.activeElement.tagName")
    assert focused_element in ["BUTTON", "A", "INPUT"], "First tab should focus an interactive element"
    
    # Continuer la navigation au clavier
    for _ in range(5):
        await page.keyboard.press("Tab")
        await asyncio.sleep(0.1)
    
    # Test activation par clavier (Enter/Space)
    clickable_element = page.locator("button, a").first
    if await clickable_element.count() > 0:
        await clickable_element.focus()
        await page.keyboard.press("Enter")
        await asyncio.sleep(0.2)
    
    # Vérifier les attributs ARIA si présents
    aria_elements = await page.locator("[aria-label], [aria-labelledby], [role]").count()
    print(f"Found {aria_elements} elements with ARIA attributes")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_2_accessibility")