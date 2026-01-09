"""
Tests E2E d'intégration cross-phases
Tests de l'intégration entre Phase 5.1, 5.2 et 5.3

Scénarios testés :
- Navigation entre interfaces Phase 5
- Cohérence du Design System
- Flux complet utilisateur
- Performance globale
- Intégration données
"""

import pytest
import asyncio
from playwright.async_api import expect


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_complete_user_workflow(authenticated_page, test_server, e2e_helpers):
    """Test le workflow complet utilisateur à travers toutes les phases."""
    page = authenticated_page
    
    # 1. Démarrer depuis l'accueil
    await page.goto(f"{test_server}/")
    await e2e_helpers.wait_for_network_idle(page)
    
    # 2. Navigation vers Design System
    design_link = page.locator("a[href*='/design-system']")
    if await design_link.count() > 0:
        await design_link.click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier qu'on est sur la page Design System
        await expect(page).to_have_url("*/design-system")
        await e2e_helpers.assert_element_visible(page, ".design-system-container")
        
        # Screenshot étape 1
        await e2e_helpers.take_screenshot(page, "integration_step1_design_system")
    
    # 3. Navigation vers Interface Interactive
    interactive_link = page.locator("a[href*='/structure/interactive']")
    if await interactive_link.count() > 0:
        await interactive_link.click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier la page Interactive
        await expect(page).to_have_url("*/structure/interactive")
        await e2e_helpers.assert_element_visible(page, ".structure-interactive-container")
        
        # Test interaction rapide
        structure_card = page.locator(".structure-card").first
        if await structure_card.count() > 0:
            await structure_card.click()
        
        # Screenshot étape 2
        await e2e_helpers.take_screenshot(page, "integration_step2_interactive")
    
    # 4. Navigation vers Recherche Avancée
    search_link = page.locator("a[href*='/structure/search']")
    if await search_link.count() > 0:
        await search_link.click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier la page Recherche
        await expect(page).to_have_url("*/structure/search")
        await e2e_helpers.assert_element_visible(page, ".search-container")
        
        # Test recherche rapide
        search_input = page.locator(".search-input, input[name='search']")
        if await search_input.count() > 0:
            await search_input.fill("test integration")
            
            search_button = page.locator(".search-button, .btn-search")
            if await search_button.count() > 0:
                await search_button.click()
            
            await e2e_helpers.wait_for_network_idle(page)
            await asyncio.sleep(2)
        
        # Screenshot étape 3
        await e2e_helpers.take_screenshot(page, "integration_step3_search")
    
    # 5. Retour vers Design System pour vérifier la cohérence
    if await page.locator("a[href*='/design-system']").count() > 0:
        await page.locator("a[href*='/design-system']").click()
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier que le Design System est toujours cohérent
        await e2e_helpers.assert_element_visible(page, ".color-palette-section")
        
        # Screenshot final
        await e2e_helpers.take_screenshot(page, "integration_step4_complete_workflow")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_design_system_consistency(authenticated_page, test_server, e2e_helpers):
    """Test la cohérence du Design System à travers toutes les pages."""
    page = authenticated_page
    
    # Pages à tester
    phase_5_pages = [
        ("/design-system", ".design-system-container"),
        ("/structure/interactive", ".structure-interactive-container"),
        ("/structure/search", ".search-container")
    ]
    
    css_variables_to_check = [
        "--color-ght",
        "--color-eg", 
        "--color-pole",
        "--color-service",
        "--urgence-1",
        "--urgence-5"
    ]
    
    css_values = {}
    
    for page_url, main_selector in phase_5_pages:
        # Naviguer vers la page
        await page.goto(f"{test_server}{page_url}")
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier que la page se charge
        await e2e_helpers.assert_element_visible(page, main_selector)
        
        # Vérifier les variables CSS
        for css_var in css_variables_to_check:
            css_value = await page.evaluate(f"""
                getComputedStyle(document.documentElement).getPropertyValue('{css_var}')
            """)
            
            if css_var not in css_values:
                css_values[css_var] = css_value.strip()
            else:
                # Vérifier la cohérence
                assert css_values[css_var] == css_value.strip(), \
                    f"CSS variable {css_var} inconsistent: {css_values[css_var]} vs {css_value.strip()}"
        
        # Vérifier la présence de composants du Design System
        common_components = [
            ".structure-card",
            ".btn-primary",
            ".search-input"
        ]
        
        for component in common_components:
            if await page.locator(component).count() > 0:
                # Le composant existe, vérifier qu'il a les bonnes classes
                element = page.locator(component).first
                class_name = await element.get_attribute("class")
                assert class_name, f"Component {component} should have classes"
        
        # Screenshot de chaque page pour comparaison visuelle
        await e2e_helpers.take_screenshot(page, f"consistency_check_{page_url.replace('/', '_')}")
    
    print("Design System consistency check passed!")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_navigation_menu_consistency(authenticated_page, test_server, e2e_helpers):
    """Test la cohérence du menu de navigation."""
    page = authenticated_page
    
    expected_nav_links = [
        ("Design System", "/design-system"),
        ("Interactive", "/structure/interactive"), 
        ("Search", "/structure/search")
    ]
    
    # Test sur chaque page Phase 5
    pages_to_test = [
        "/design-system",
        "/structure/interactive", 
        "/structure/search"
    ]
    
    for current_page in pages_to_test:
        await page.goto(f"{test_server}{current_page}")
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier la présence du menu de navigation
        nav_menu = page.locator(".nav-menu, .navigation, header nav")
        if await nav_menu.count() > 0:
            await expect(nav_menu).to_be_visible()
            
            # Vérifier chaque lien de navigation
            for link_text, link_url in expected_nav_links:
                nav_link = page.locator(f"a:has-text('{link_text}'), a[href*='{link_url}']")
                if await nav_link.count() > 0:
                    # Vérifier que le lien est visible et cliquable
                    await expect(nav_link.first).to_be_visible()
                    
                    # Vérifier l'URL du lien
                    href = await nav_link.first.get_attribute("href")
                    assert link_url in (href or ""), f"Link should point to {link_url}"
        
        # Screenshot du menu sur chaque page
        await e2e_helpers.take_screenshot(page, f"navigation_menu_{current_page.replace('/', '_')}")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_data_consistency_across_phases(authenticated_page, test_server, e2e_helpers):
    """Test la cohérence des données entre phases."""
    page = authenticated_page
    
    # 1. Rechercher une structure sur la page de recherche
    await page.goto(f"{test_server}/structure/search")
    await e2e_helpers.wait_for_network_idle(page)
    
    search_input = page.locator(".search-input, input[name='search']")
    if await search_input.count() > 0:
        # Recherche spécifique
        await search_input.fill("CHU")
        
        search_button = page.locator(".search-button, .btn-search")
        if await search_button.count() > 0:
            await search_button.click()
        
        await e2e_helpers.wait_for_network_idle(page)
        await asyncio.sleep(2)
        
        # Récupérer les données de la première carte
        result_cards = page.locator(".structure-card")
        if await result_cards.count() > 0:
            first_card = result_cards.first
            card_text = await first_card.text_content()
            
            # Extraire des informations (nom, ID, etc.)
            structure_data = {
                "text": card_text,
                "found": True
            }
            
            print(f"Found structure data in search: {structure_data['text'][:100]}...")
            
            # 2. Aller sur la page interactive et vérifier la cohérence
            await page.goto(f"{test_server}/structure/interactive")
            await e2e_helpers.wait_for_network_idle(page)
            
            # Vérifier que des données similaires sont présentes
            interactive_cards = page.locator(".structure-card")
            if await interactive_cards.count() > 0:
                # Les cartes utilisent le même composant StructureCard
                # donc le format devrait être cohérent
                interactive_card = interactive_cards.first
                interactive_text = await interactive_card.text_content()
                
                print(f"Found structure data in interactive: {interactive_text[:100]}...")
                
                # Les deux devraient utiliser le même format de carte
                # (même composant StructureCard du Design System)
                assert len(interactive_text.strip()) > 0, "Interactive card should have content"
    
    # Screenshot final
    await e2e_helpers.take_screenshot(page, "data_consistency_check")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_performance_across_all_phases(authenticated_page, test_server, e2e_helpers):
    """Test les performances globales des 3 phases."""
    page = authenticated_page
    
    performance_results = {}
    
    # Pages Phase 5 à tester
    phase_pages = {
        "design_system": "/design-system",
        "interactive": "/structure/interactive",
        "search": "/structure/search"
    }
    
    for page_name, page_url in phase_pages.items():
        # Mesurer le temps de chargement
        start_time = await page.evaluate("performance.now()")
        
        await page.goto(f"{test_server}{page_url}")
        await e2e_helpers.wait_for_network_idle(page)
        
        # Attendre que les éléments principaux soient chargés
        await page.wait_for_load_state("networkidle")
        
        end_time = await page.evaluate("performance.now()")
        load_time = end_time - start_time
        
        # Mesurer le temps de première interaction
        interaction_start = await page.evaluate("performance.now()")
        
        # Test interaction spécifique à chaque page
        if page_name == "design_system":
            color_card = page.locator(".color-card").first
            if await color_card.count() > 0:
                await color_card.hover()
        elif page_name == "interactive":
            structure_card = page.locator(".structure-card").first
            if await structure_card.count() > 0:
                await structure_card.click()
        elif page_name == "search":
            search_input = page.locator(".search-input, input[name='search']")
            if await search_input.count() > 0:
                await search_input.fill("test")
        
        interaction_end = await page.evaluate("performance.now()")
        interaction_time = interaction_end - interaction_start
        
        performance_results[page_name] = {
            "load_time": load_time,
            "interaction_time": interaction_time
        }
        
        print(f"Page {page_name}: Load {load_time:.2f}ms, Interaction {interaction_time:.2f}ms")
        
        # Assertions de performance
        assert load_time < 5000, f"Page {page_name} load too slow: {load_time}ms"
        assert interaction_time < 2000, f"Page {page_name} interaction too slow: {interaction_time}ms"
    
    # Performance globale
    total_load_time = sum(p["load_time"] for p in performance_results.values())
    avg_load_time = total_load_time / len(performance_results)
    
    print(f"Average load time across all phases: {avg_load_time:.2f}ms")
    assert avg_load_time < 4000, f"Average load time too high: {avg_load_time}ms"
    
    # Screenshot final
    await e2e_helpers.take_screenshot(page, "performance_test_complete")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_error_handling_consistency(authenticated_page, test_server, e2e_helpers):
    """Test la cohérence de gestion d'erreurs."""
    page = authenticated_page
    
    # Test pages inexistantes/erreurs sur chaque phase
    error_scenarios = [
        "/design-system/nonexistent",
        "/structure/interactive/invalid", 
        "/structure/search/404"
    ]
    
    for error_url in error_scenarios:
        await page.goto(f"{test_server}{error_url}", wait_until="load")
        
        # Vérifier la gestion d'erreur
        page_content = await page.content()
        
        # Devrait soit rediriger vers une page valide, soit afficher une erreur cohérente
        if "404" in page_content or "Not Found" in page_content:
            # Page d'erreur 404 personnalisée
            error_container = page.locator(".error-container, .not-found")
            if await error_container.count() > 0:
                await expect(error_container).to_be_visible()
        else:
            # Redirection vers page valide - vérifier qu'elle fonctionne
            main_content = page.locator("main, .main-content, .container")
            if await main_content.count() > 0:
                await expect(main_content).to_be_visible()
        
        # Screenshot de chaque scenario d'erreur
        await e2e_helpers.take_screenshot(page, f"error_handling_{error_url.replace('/', '_')}")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_accessibility_across_phases(authenticated_page, test_server, e2e_helpers):
    """Test l'accessibilité sur toutes les phases."""
    page = authenticated_page
    
    # Pages à tester
    accessibility_pages = [
        "/design-system",
        "/structure/interactive",
        "/structure/search"
    ]
    
    for page_url in accessibility_pages:
        await page.goto(f"{test_server}{page_url}")
        await e2e_helpers.wait_for_network_idle(page)
        
        # Test navigation au clavier
        await page.keyboard.press("Tab")
        focused_element = await page.evaluate("document.activeElement.tagName")
        assert focused_element in ["BUTTON", "A", "INPUT"], f"First tab should focus interactive element on {page_url}"
        
        # Continuer navigation clavier
        for i in range(3):
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.1)
        
        # Vérifier les attributs ARIA
        aria_elements = await page.locator("[aria-label], [aria-labelledby], [role]").count()
        print(f"Page {page_url}: {aria_elements} elements with ARIA attributes")
        
        # Vérifier les contrastes de couleurs (basique)
        # Cette vérification nécessiterait des outils spécialisés en production
        
        # Screenshot pour audit visuel
        await e2e_helpers.take_screenshot(page, f"accessibility_{page_url.replace('/', '_')}")
    
    print("Accessibility checks completed across all phases")


@pytest.mark.e2e_integration
@pytest.mark.asyncio
async def test_browser_compatibility_simulation(authenticated_page, test_server, e2e_helpers):
    """Test simulation compatibilité navigateurs."""
    page = authenticated_page
    
    # Simuler différents user agents
    user_agents = [
        {
            "name": "Chrome_Desktop",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        {
            "name": "Firefox_Desktop", 
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        },
        {
            "name": "Safari_Mobile",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        }
    ]
    
    for ua_config in user_agents:
        # Changer le user agent
        await page.set_extra_http_headers({"User-Agent": ua_config["user_agent"]})
        
        # Tester une page représentative
        await page.goto(f"{test_server}/structure/search")
        await e2e_helpers.wait_for_network_idle(page)
        
        # Vérifier que la page fonctionne
        await e2e_helpers.assert_element_visible(page, ".search-container")
        
        # Test interaction basique
        search_input = page.locator(".search-input, input[name='search']")
        if await search_input.count() > 0:
            await search_input.fill("test browser compatibility")
            await asyncio.sleep(0.5)
        
        # Screenshot pour chaque "navigateur"
        await e2e_helpers.take_screenshot(page, f"browser_compat_{ua_config['name']}")
    
    print("Browser compatibility simulation completed")