"""
Tests E2E pour Phase 5.3 : Interface de Recherche Avancée
Route testée : /structure/search

Fonctionnalités testées :
- Recherche multi-critères FHIR
- Filtres visuels et pagination
- Historique des recherches
- Export des résultats
- Intégration API FHIR Location
"""

import pytest
import asyncio
import json
from playwright.async_api import expect


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_search_page_loads(search_structure_page, e2e_helpers):
    """Test que la page de recherche se charge correctement."""
    page = search_structure_page
    
    # Vérifier le titre de la page
    await expect(page).to_have_title("Recherche Avancée Structure")
    
    # Vérifier la présence des éléments principaux
    await e2e_helpers.assert_element_visible(page, ".search-container")
    await e2e_helpers.assert_element_visible(page, ".search-header")
    await e2e_helpers.assert_element_visible(page, ".search-form")
    await e2e_helpers.assert_element_visible(page, ".results-container")
    
    # Vérifier les statistiques initiales
    await e2e_helpers.assert_element_visible(page, ".search-stats")
    
    # Screenshot pour debug
    await e2e_helpers.take_screenshot(page, "phase5_3_page_loaded")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_main_search_functionality(search_structure_page, e2e_helpers, test_structure_data):
    """Test la recherche principale."""
    page = search_structure_page
    
    # Trouver le champ de recherche principal
    search_input = page.locator(".search-input, input[name='search']")
    await search_input.wait_for(state="visible", timeout=10000)
    
    # Test recherche par nom
    for search_term in test_structure_data["search_terms"][:2]:  # Test 2 termes
        # Effacer et saisir le terme
        await search_input.clear()
        await search_input.fill(search_term)
        
        # Attendre la recherche automatique ou cliquer sur rechercher
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        # Attendre les résultats
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(1)  # Attendre l'affichage des résultats
        
        # Vérifier que les statistiques sont mises à jour
        stats_element = page.locator(".search-count, .results-count")
        if await stats_element.count() > 0:
            stats_text = await stats_element.text_content()
            print(f"Search '{search_term}' returned: {stats_text}")
        
        # Vérifier la présence de résultats ou message "aucun résultat"
        results_area = page.locator(".results-container")
        await expect(results_area).to_be_visible()
        
        # Screenshot pour chaque recherche
        await e2e_helpers.take_screenshot(page, f"phase5_3_search_{search_term.replace(' ', '_')}")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_advanced_filters(search_structure_page, e2e_helpers, test_structure_data):
    """Test les filtres avancés."""
    page = search_structure_page
    
    # Afficher les filtres avancés s'ils sont masqués
    filters_toggle = page.locator(".filters-toggle, .advanced-filters-toggle")
    if await filters_toggle.count() > 0:
        await filters_toggle.click()
        await asyncio.sleep(0.5)
    
    # Vérifier que la section de filtres est visible
    filters_section = page.locator(".search-filters, .filter-section")
    if await filters_section.count() > 0:
        await expect(filters_section).to_be_visible()
        
        # Test filtres par type
        type_filter = page.locator(".filter-type, select[name='type']")
        if await type_filter.count() > 0:
            # Sélectionner un type
            await type_filter.select_option("hospital")
            await e2e_helpers.wait_for_network_idle(page)
            
            # Vérifier que la recherche se lance automatiquement
            await asyncio.sleep(1)
        
        # Test filtres par statut
        status_filter = page.locator(".filter-status, select[name='status']")
        if await status_filter.count() > 0:
            await status_filter.select_option("active")
            await e2e_helpers.wait_for_network_idle(page)
            await asyncio.sleep(1)
        
        # Test filtre par identifiant
        identifier_filter = page.locator(".filter-identifier, input[name='identifier']")
        if await identifier_filter.count() > 0:
            await identifier_filter.fill("123456")
            await e2e_helpers.wait_for_network_idle(page)
            await asyncio.sleep(1)
    
    # Screenshot des filtres actifs
    await e2e_helpers.take_screenshot(page, "phase5_3_advanced_filters")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_search_results_display(search_structure_page, e2e_helpers):
    """Test l'affichage des résultats de recherche."""
    page = search_structure_page
    
    # Lancer une recherche générale
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        await search_input.fill("CHU")
        
        # Lancer la recherche
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(2)
        
        # Vérifier les cartes de résultats
        result_cards = page.locator(".structure-card")
        card_count = await result_cards.count()
        
        if card_count > 0:
            print(f"Found {card_count} result cards")
            
            # Vérifier les éléments de chaque carte
            first_card = result_cards.first
            
            # Vérifier le contenu de la carte
            card_content = await first_card.text_content()
            assert card_content and len(card_content.strip()) > 0, "Card should have content"
            
            # Test clic sur carte pour navigation
            card_link = first_card.locator("a")
            if await card_link.count() > 0:
                href = await card_link.get_attribute("href")
                assert href, "Card should have navigation link"
        else:
            # Vérifier le message "aucun résultat"
            no_results = page.locator(".no-results, .empty-results")
            if await no_results.count() > 0:
                await expect(no_results).to_be_visible()
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_search_results")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_pagination_functionality(search_structure_page, e2e_helpers):
    """Test la pagination des résultats."""
    page = search_structure_page
    
    # Lancer une recherche qui devrait retourner plusieurs pages
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        # Recherche générale pour avoir plus de résultats
        await search_input.fill("")  # Recherche vide pour tout afficher
        
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(2)
        
        # Vérifier la présence de la pagination
        pagination_section = page.locator(".pagination, .pagination-controls")
        if await pagination_section.count() > 0:
            await expect(pagination_section).to_be_visible()
            
            # Test bouton "Suivant"
            next_button = page.locator(".pagination-next, .btn-next")
            if await next_button.count() > 0:
                # Vérifier le nombre de résultats sur la page 1
                results_before = await page.locator(".structure-card").count()
                
                # Aller à la page suivante
                await next_button.click()
                await e2e_helpers.wait_for_network_idle(page)
                await asyncio.sleep(1)
                
                # Vérifier que nous sommes sur la page 2
                page_info = page.locator(".page-info")
                if await page_info.count() > 0:
                    page_text = await page_info.text_content()
                    assert "2" in (page_text or ""), "Should be on page 2"
                
                # Test bouton "Précédent"
                prev_button = page.locator(".pagination-prev, .btn-prev")
                if await prev_button.count() > 0:
                    await prev_button.click()
                    await e2e_helpers.wait_for_network_idle(page)
                    await asyncio.sleep(1)
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_pagination")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_search_history(search_structure_page, e2e_helpers):
    """Test l'historique des recherches."""
    page = search_structure_page
    
    # Effectuer plusieurs recherches pour créer un historique
    search_terms = ["cardio", "urgence", "chirurgie"]
    search_input = page.locator(".search-input, input[name='search']")
    
    if await search_input.count() > 0:
        for term in search_terms:
            await search_input.clear()
            await search_input.fill(term)
            
            # Lancer la recherche
            search_button = page.locator(".search-button, .btn-search")
            if await search_button.count() > 0:
                await search_button.click()
            
            await e2e_helpers.wait_for_network_idle(page)
            await asyncio.sleep(1)
        
        # Vérifier l'historique des recherches
        history_button = page.locator(".search-history-toggle, .history-toggle")
        if await history_button.count() > 0:
            await history_button.click()
            await asyncio.sleep(0.5)
            
            # Vérifier que l'historique est visible
            history_section = page.locator(".search-history, .history-section")
            if await history_section.count() > 0:
                await expect(history_section).to_be_visible()
                
                # Vérifier la présence des recherches précédentes
                history_items = page.locator(".history-item")
                history_count = await history_items.count()
                assert history_count > 0, "Should have history items"
                
                # Test clic sur un élément d'historique
                if history_count > 0:
                    first_history_item = history_items.first
                    await first_history_item.click()
                    await e2e_helpers.wait_for_network_idle(page)
                    
                    # Vérifier que la recherche est restaurée
                    current_search_value = await search_input.input_value()
                    assert len(current_search_value) > 0, "Search should be restored from history"
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_search_history")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_export_functionality(search_structure_page, e2e_helpers):
    """Test l'export des résultats."""
    page = search_structure_page
    
    # Lancer une recherche pour avoir des résultats à exporter
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        await search_input.fill("test")
        
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(2)
        
        # Vérifier le bouton d'export
        export_button = page.locator(".export-button, .btn-export")
        if await export_button.count() > 0:
            # Préparer le téléchargement
            async with page.expect_download() as download_info:
                await export_button.click()
            
            download = await download_info.value
            
            # Vérifier le nom du fichier téléchargé
            filename = download.suggested_filename
            assert filename.endswith(".json"), f"Export should be JSON file, got {filename}"
            assert "structure_search" in filename, f"Filename should contain 'structure_search', got {filename}"
            
            # Sauvegarder pour vérification
            await download.save_as(f"tests/artifacts/{filename}")
            print(f"Export saved as: tests/artifacts/{filename}")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_export")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_real_time_statistics(search_structure_page, e2e_helpers):
    """Test les statistiques en temps réel."""
    page = search_structure_page
    
    # Vérifier la présence des éléments de statistiques
    stats_elements = [
        ".search-count",
        ".search-time", 
        ".total-structures",
        ".results-count"
    ]
    
    visible_stats = []
    for stat_selector in stats_elements:
        if await page.locator(stat_selector).count() > 0:
            visible_stats.append(stat_selector)
    
    print(f"Found statistics elements: {visible_stats}")
    
    # Lancer une recherche et mesurer la mise à jour des stats
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        # Recherche initiale
        await search_input.fill("cardio")
        
        # Capturer les stats avant recherche
        stats_before = {}
        for stat_selector in visible_stats:
            element = page.locator(stat_selector)
            if await element.count() > 0:
                stats_before[stat_selector] = await element.text_content()
        
        # Lancer la recherche
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(2)
        
        # Capturer les stats après recherche
        stats_after = {}
        for stat_selector in visible_stats:
            element = page.locator(stat_selector)
            if await element.count() > 0:
                stats_after[stat_selector] = await element.text_content()
        
        # Vérifier que les statistiques ont été mises à jour
        print("Statistics before:", stats_before)
        print("Statistics after:", stats_after)
        
        # Au moins une statistique devrait avoir changé
        stats_changed = any(
            stats_before.get(key) != stats_after.get(key)
            for key in visible_stats
        )
        assert stats_changed, "At least one statistic should have changed"
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_statistics")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_fhir_api_integration(search_structure_page, e2e_helpers):
    """Test l'intégration avec l'API FHIR."""
    page = search_structure_page
    
    # Surveiller les requêtes réseau vers l'API FHIR
    fhir_requests = []
    
    def handle_request(request):
        if "/fhir/Location" in request.url:
            fhir_requests.append({
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers)
            })
    
    page.on("request", handle_request)
    
    # Lancer une recherche pour déclencher un appel API
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        await search_input.fill("test FHIR")
        
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(3)
    
    # Vérifier qu'des appels API FHIR ont été faits
    assert len(fhir_requests) > 0, "Should have made FHIR API calls"
    
    # Vérifier le format des requêtes FHIR
    for request in fhir_requests:
        assert "/fhir/Location" in request["url"], f"Should call FHIR Location API: {request['url']}"
        assert request["method"] in ["GET"], f"Should use GET method: {request['method']}"
        print(f"FHIR API call: {request['method']} {request['url']}")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_fhir_integration")


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_responsive_search_interface(search_structure_page, e2e_helpers):
    """Test le design responsive de l'interface de recherche."""
    page = search_structure_page
    
    # Test sur différentes résolutions
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
        
        # Vérifier que les éléments principaux restent accessibles
        await e2e_helpers.assert_element_visible(page, ".search-container")
        await e2e_helpers.assert_element_visible(page, ".search-form")
        
        # Tester une recherche sur cette résolution
        search_input = page.locator(".search-input, input[name='search']")
        if await search_input.count() > 0:
            await search_input.clear()
            await search_input.fill(f"test {resolution['name']}")
            
            search_button = page.locator(".search-button, .btn-search")
            if await search_button.count() > 0:
                await search_button.click()
            
            await e2e_helpers.wait_for_network_idle(page)
            await asyncio.sleep(1)
            
            # Vérifier que les résultats s'affichent correctement
            results_container = page.locator(".results-container")
            await expect(results_container).to_be_visible()
        
        # Screenshot pour chaque résolution
        await e2e_helpers.take_screenshot(page, f"phase5_3_responsive_{resolution['name']}")
    
    # Remettre la résolution par défaut
    await page.set_viewport_size({"width": 1280, "height": 720})


@pytest.mark.e2e_phase5_3
@pytest.mark.asyncio
async def test_search_performance(search_structure_page, e2e_helpers):
    """Test les performances de la recherche."""
    page = search_structure_page
    
    search_input = page.locator(".search-input, input[name='search']")
    search_button = page.locator(".search-button, .btn-search")
    
    if await search_input.count() > 0 and await search_button.count() > 0:
        # Test multiple recherches pour mesurer la performance
        search_terms = ["cardio", "urgence", "CHU", "service"]
        
        for term in search_terms:
            # Mesurer le temps de recherche
            start_time = await page.evaluate("performance.now()")
            
            await search_input.clear()
            await search_input.fill(term)
            await search_button.click()
            
            # Attendre les résultats
            await e2e_helpers.wait_for_network_idle(page)
            
            end_time = await page.evaluate("performance.now()")
            search_time = end_time - start_time
            
            print(f"Search '{term}' took {search_time:.2f}ms")
            
            # Vérifier que la recherche n'est pas trop lente
            assert search_time < 10000, f"Search for '{term}' too slow: {search_time}ms"
            
            await asyncio.sleep(0.5)  # Pause entre recherches
        
        # Test recherche instantanée (si implémentée)
        await search_input.clear()
        start_time = await page.evaluate("performance.now()")
        
        # Saisie caractère par caractère
        for char in "test":
            await search_input.type(char)
            await asyncio.sleep(0.1)  # Délai de frappe réaliste
        
        # Attendre la recherche instantanée
        await asyncio.sleep(1)
        end_time = await page.evaluate("performance.now()")
        
        instant_search_time = end_time - start_time
        print(f"Instant search took {instant_search_time:.2f}ms")
    
    # Screenshot
    await e2e_helpers.take_screenshot(page, "phase5_3_performance_test")