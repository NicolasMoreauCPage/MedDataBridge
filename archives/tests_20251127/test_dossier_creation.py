#!/usr/bin/env python3
import requests

# Créer une session pour maintenir les cookies
session = requests.Session()

try:
    print('=== Test création dossier après correction ===')
    
    # 1. Définir les contextes
    session.get('http://127.0.0.1:8000/admin/ght/1', timeout=5, allow_redirects=True)
    session.get('http://127.0.0.1:8000/context/patient/1', timeout=5, allow_redirects=True)
    
    # 2. Tester la soumission du formulaire (avec patient_id_display pour compatibilité template)
    form_data = {
        'patient_id_display': 'Martin Jean (ID: 1)',  # Inclus pour le template
        'dossier_type': 'hospitalise',
        'admission_source': 'RD',
        'attending_provider': 'Dr. Test',
        'admit_time': '2025-11-12T10:00',
        'uf_responsabilite': '',
    }
    
    response_post = session.post('http://127.0.0.1:8000/dossiers/new', data=form_data, timeout=10, allow_redirects=True)
    print(f'✓ Soumission formulaire (status: {response_post.status_code})')
    
    if 'dossiers' in response_post.url and response_post.status_code == 200:
        print('✓ Redirection vers la liste des dossiers après création')
        
        # Vérifier que le dossier a été créé
        if 'Martin Jean' in response_post.text:
            print('✓ Patient visible dans la liste des dossiers')
        else:
            print('✗ Patient non trouvé dans la liste')
            
    else:
        print(f'✗ Problème avec la redirection: {response_post.url}')
        print(f'Contenu: {response_post.text[:500]}...')
    
    print('\n=== Test terminé ===')
        
except Exception as e:
    print(f'Error: {e}')