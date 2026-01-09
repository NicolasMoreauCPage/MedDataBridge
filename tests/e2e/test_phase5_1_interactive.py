"""
Tests E2E pour Phase 5.1 : UX Interactive
Route testée : /structure/interactive

Fonctionnalités testées :
- Édition inline double-clic
- Drag & drop réorganisation
- Raccourcis clavier
- Actions de masse
- Navigation et interactions
"""

import pytest
import asyncio
from playwright.async_api import expect


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_interactive_page_loads(interactive_structure_page, e2e_helpers):
    """Test que la page Interactive Structure se charge correctement."""
    page = interactive_structure_page
    
    # Vérifier le titre de la page
    await expect(page).to_have_title("Structure Interactive")
    
    # Vérifier la présence des éléments principaux
    await e2e_helpers.assert_element_visible(page, ".structure-interactive-container")
    await e2e_helpers.assert_element_visible(page, ".structure-header")
    await e2e_helpers.assert_element_visible(page, ".structure-tree")
    
    # Vérifier la présence des boutons d'actions
    await e2e_helpers.assert_element_visible(page, ".action-buttons")
    
    # Screenshot pour debug
    await e2e_helpers.take_screenshot(page, "phase5_1_page_loaded")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_inline_editing_double_click(interactive_structure_page, e2e_helpers):
    """Test l'édition inline par double-clic."""
    page = interactive_structure_page
    
    # Attendre que les cartes soient chargées
    await page.wait_for_selector(".structure-card", state="visible", timeout=10000)
    
    # Trouver une carte de structure éditable
    structure_card = page.locator(".structure-card").first
    await structure_card.wait_for(state="visible")
    
    # Double-clic pour activer l'édition
    await structure_card.dblclick()
    
    # Vérifier que le mode édition est activé
    await e2e_helpers.assert_element_visible(page, ".inline-edit-mode")
    
    # Vérifier la présence des champs d'édition
    name_input = page.locator(".inline-edit-name")
    await name_input.wait_for(state="visible")
    
    # Modifier le nom
    original_value = await name_input.input_value()
    new_value = f"{original_value} - Édité E2E"
    
    await name_input.clear()
    await name_input.fill(new_value)
    
    # Sauvegarder avec Enter
    await name_input.press("Enter")
    
    # Attendre la fin de l'édition
    await e2e_helpers.wait_for_network_idle(page)
    
    # Vérifier que la modification est visible
    await expect(structure_card).to_contain_text("Édité E2E")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_inline_edit_success")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_keyboard_shortcuts(interactive_structure_page, e2e_helpers):
    """Test les raccourcis clavier."""
    page = interactive_structure_page
    
    # Attendre le chargement
    await page.wait_for_selector(".structure-card", state="visible")
    
    # Test Ctrl+A pour sélectionner tout
    await page.keyboard.press("Control+a")
    await asyncio.sleep(0.5)
    
    # Vérifier que des éléments sont sélectionnés
    selected_elements = await page.locator(".structure-card.selected").count()
    assert selected_elements > 0, "Aucun élément sélectionné avec Ctrl+A"
    
    # Test Escape pour désélectionner
    await page.keyboard.press("Escape")
    await asyncio.sleep(0.5)
    
    # Vérifier que la sélection est annulée
    selected_elements = await page.locator(".structure-card.selected").count()
    assert selected_elements == 0, "Éléments encore sélectionnés après Escape"
    
    # Test Ctrl+E pour mode édition rapide
    first_card = page.locator(".structure-card").first
    await first_card.click()  # Sélectionner d'abord
    await page.keyboard.press("Control+e")
    
    # Vérifier que le mode édition est activé
    await e2e_helpers.assert_element_visible(page, ".inline-edit-mode")
    
    # Annuler avec Escape
    await page.keyboard.press("Escape")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_keyboard_shortcuts")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_mass_actions(interactive_structure_page, e2e_helpers):
    """Test les actions de masse."""
    page = interactive_structure_page
    
    # Attendre le chargement
    await page.wait_for_selector(".structure-card", state="visible")
    
    # Sélectionner plusieurs cartes
    cards = page.locator(".structure-card")
    card_count = await cards.count()
    
    if card_count >= 2:
        # Sélectionner les 2 premières cartes avec Ctrl+clic
        await cards.nth(0).click()
        await cards.nth(1).click(modifiers=["Control"])
        
        # Vérifier que 2 cartes sont sélectionnées
        selected_count = await page.locator(".structure-card.selected").count()
        assert selected_count == 2, f"Expected 2 selected cards, got {selected_count}"
        
        # Vérifier que la barre d'actions de masse apparaît
        await e2e_helpers.assert_element_visible(page, ".mass-actions-bar")
        
        # Test action de masse : activer/désactiver
        toggle_button = page.locator(".mass-action-toggle")
        if await toggle_button.is_visible():
            await toggle_button.click()
            await e2e_helpers.wait_for_network_idle(page)
            
            # Vérifier que l'action a été appliquée
            await e2e_helpers.assert_text_content(page, ".notification", "Action appliquée")
        
        # Désélectionner tout
        await page.keyboard.press("Escape")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_mass_actions")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_drag_and_drop_reorganization(interactive_structure_page, e2e_helpers):
    """Test la réorganisation par drag & drop."""
    page = interactive_structure_page
    
    # Attendre le chargement
    await page.wait_for_selector(".structure-card", state="visible")
    
    cards = page.locator(".structure-card")
    card_count = await cards.count()
    
    if card_count >= 2:
        # Prendre les positions initiales
        source_card = cards.nth(0)
        target_card = cards.nth(1)
        
        # Obtenir les bounding boxes
        source_box = await source_card.bounding_box()
        target_box = await target_card.bounding_box()
        
        if source_box and target_box:
            # Effectuer le drag & drop
            await page.mouse.move(
                source_box["x"] + source_box["width"] / 2,
                source_box["y"] + source_box["height"] / 2
            )
            await page.mouse.down()
            
            # Déplacer vers la cible
            await page.mouse.move(
                target_box["x"] + target_box["width"] / 2,
                target_box["y"] + target_box["height"] / 2
            )
            await page.mouse.up()
            
            # Attendre la fin de l'animation
            await asyncio.sleep(1)
            await e2e_helpers.wait_for_network_idle(page)
            
            # Vérifier qu'une notification de succès apparaît
            notification = page.locator(".notification")
            if await notification.is_visible():
                await expect(notification).to_contain_text("déplacé", ignore_case=True)
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_drag_drop")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_responsive_design(interactive_structure_page, e2e_helpers):
    """Test le design responsive."""
    page = interactive_structure_page
    
    # Tester différentes résolutions
    resolutions = [
        {"width": 1280, "height": 720},  # Desktop
        {"width": 768, "height": 1024},  # Tablet
        {"width": 375, "height": 667}    # Mobile
    ]
    
    for i, resolution in enumerate(resolutions):
        await page.set_viewport_size(resolution)
        await asyncio.sleep(0.5)
        
        # Vérifier que la page s'adapte
        await e2e_helpers.assert_element_visible(page, ".structure-interactive-container")
        
        # Vérifier que les cartes sont visibles
        cards = page.locator(".structure-card")
        if await cards.count() > 0:
            await e2e_helpers.assert_element_visible(page, ".structure-card")
        
        # Screenshot pour chaque résolution
        await e2e_helpers.take_screenshot(page, f"phase5_1_responsive_{resolution['width']}x{resolution['height']}")
    
    # Remettre la résolution par défaut
    await page.set_viewport_size({"width": 1280, "height": 720})


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_navigation_and_links(interactive_structure_page, e2e_helpers):
    """Test la navigation et les liens."""
    page = interactive_structure_page
    
    # Vérifier la présence du menu de navigation
    nav_links = [
        ("Design System", "/design-system"),
        ("Recherche", "/structure/search"),
        ("Accueil", "/")
    ]
    
    for link_text, expected_url in nav_links:
        # Chercher le lien
        link = page.locator(f"a:has-text('{link_text}')")
        if await link.count() > 0:
            # Vérifier que le lien a la bonne URL
            href = await link.first.get_attribute("href")
            assert expected_url in href, f"Link '{link_text}' should point to '{expected_url}'"
    
    # Test navigation vers Design System
    design_link = page.locator("a[href*='/design-system']")
    if await design_link.count() > 0:
        await design_link.first.click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier qu'on est sur la bonne page
        await expect(page).to_have_url("*/design-system")
        
        # Retourner à la page interactive
        await page.go_back()
        await e2e_helpers.wait_for_network_idle(page)
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_navigation")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_error_handling(interactive_structure_page, e2e_helpers):
    """Test la gestion des erreurs."""
    page = interactive_structure_page
    
    # Test édition avec valeur invalide
    await page.wait_for_selector(".structure-card", state="visible")
    
    structure_card = page.locator(".structure-card").first
    if await structure_card.count() > 0:
        # Double-clic pour éditer
        await structure_card.dblclick()
        
        # Vérifier le mode édition
        name_input = page.locator(".inline-edit-name")
        if await name_input.count() > 0:
            # Entrer une valeur invalide (vide)
            await name_input.clear()
            await name_input.press("Enter")
            
            # Vérifier qu'un message d'erreur apparaît
            error_message = page.locator(".error-message, .notification.error")
            if await error_message.count() > 0:
                await expect(error_message).to_be_visible()
            
            # Annuler l'édition
            await page.keyboard.press("Escape")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_error_handling")


@pytest.mark.e2e_phase5_1
@pytest.mark.asyncio
async def test_performance_interactions(interactive_structure_page, e2e_helpers):
    """Test les performances des interactions."""
    page = interactive_structure_page
    
    # Mesurer le temps de chargement initial
    start_time = page.evaluate("performance.now()")
    await page.wait_for_selector(".structure-card", state="visible")
    end_time = page.evaluate("performance.now()")
    
    load_time = await end_time - await start_time
    assert load_time < 5000, f"Page load too slow: {load_time}ms"
    
    # Test performance des interactions
    cards = page.locator(".structure-card")
    card_count = await cards.count()
    
    if card_count > 0:
        # Mesurer le temps de response au clic
        start_time = page.evaluate("performance.now()")
        await cards.first.click()
        end_time = page.evaluate("performance.now()")
        
        click_time = await end_time - await start_time
        assert click_time < 1000, f"Click response too slow: {click_time}ms"
    
    print(f"Performance: Load time: {load_time}ms, Click time: {click_time if card_count > 0 else 'N/A'}ms")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_1_performance_test")