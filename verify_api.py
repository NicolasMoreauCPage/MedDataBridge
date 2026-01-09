#!/usr/bin/env python3
"""Vérifier via l'API si les données sont accessibles."""
import sys
import os

# Ajouter le répertoire courant au path si on est en prod
if os.path.exists('/opt/meddata-bridge'):
    sys.path.insert(0, '/opt/meddata-bridge')

# Simple test avec SQLite direct
import sqlite3

db_path = './data/medbridge.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('=== VERIFICATION SQLITE DIRECT ===\n')

# Compter les GHT contexts
cursor.execute('SELECT COUNT(*) FROM ghtcontext')
ght_count = cursor.fetchone()[0]
print(f'GHT Contexts: {ght_count}')

if ght_count > 0:
    cursor.execute('SELECT id, name, code FROM ghtcontext')
    for row in cursor.fetchall():
        print(f'  - ID={row[0]}, Name={row[1]}, Code={row[2]}')

# Compter les entités juridiques
cursor.execute('SELECT COUNT(*) FROM entitejuridique')
ej_count = cursor.fetchone()[0]
print(f'\nEntites Juridiques: {ej_count}')

if ej_count > 0:
    cursor.execute('SELECT id, name FROM entitejuridique LIMIT 3')
    for row in cursor.fetchall():
        print(f'  - ID={row[0]}, Name={row[1]}')

# Compter les services
cursor.execute('SELECT COUNT(*) FROM service')
svc_count = cursor.fetchone()[0]
print(f'\nServices: {svc_count}')

if svc_count > 0:
    cursor.execute('SELECT id, name FROM service LIMIT 3')
    for row in cursor.fetchall():
        print(f'  - ID={row[0]}, Name={row[1]}')

conn.close()

print('\n=== TEST API LOCALE ===\n')
import requests
try:
    response = requests.get('http://localhost:8000/admin/', timeout=5)
    print(f'Status: {response.status_code}')
    if 'CHU' in response.text or 'Demo' in response.text:
        print('✓ Page admin contient les données du seed')
    else:
        print('✗ Page admin ne contient pas les données attendues')
except Exception as e:
    print(f'Erreur API: {e}')
