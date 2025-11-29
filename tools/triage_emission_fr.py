#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Triage des échecs liés à l'émission (MFN / HL7 / FHIR) et génération d'un rapport en français.
Produit : test_reports/triage_emission_fr.md
"""
import json
import os
import textwrap

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT, 'test_reports')
SUMMARY_PATH = os.path.join(REPORT_DIR, 'summary.json')
OUT_PATH = os.path.join(REPORT_DIR, 'triage_emission_fr.md')

EMISSION_KEYS = ['mfn', 'hl7', 'fhir', 'emission', 'message', 'emit_', 'mfn_organization', 'mfn_structure', 'emission_crud', 'pam', 'pid']

if not os.path.exists(SUMMARY_PATH):
    print('summary.json introuvable. Exécuter d\'abord le runner.')
    raise SystemExit(1)

with open(SUMMARY_PATH, 'r', encoding='utf-8') as f:
    summary = json.load(f)

failures = summary.get('failures', [])

# Load per-test reports map
reports = {}
for fname in os.listdir(REPORT_DIR):
    if not fname.endswith('.json'):
        continue
    p = os.path.join(REPORT_DIR, fname)
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        continue
    nodeid = data.get('nodeid')
    if nodeid:
        reports[nodeid] = data

# Filter emission-related failures
emission_failures = []
for node in failures:
    low = node.lower()
    if any(k in low for k in EMISSION_KEYS):
        emission_failures.append(node)

# Build report
lines = []
lines.append('# Triage — échecs liés à l\'émission (MFN / HL7 / FHIR)')
lines.append('')
lines.append(f'- Généré à : {__import__("datetime").datetime.utcnow().isoformat()}Z')
lines.append(f'- Tests d\'émission échoués détectés : {len(emission_failures)}')
lines.append('')
lines.append('## Synthèse rapide')
if not emission_failures:
    lines.append('Aucun échec lié à l\'émission trouvé dans la liste des échecs.')
else:
    # group by file prefix
    by_file = {}
    for n in emission_failures:
        file = n.split('::')[0]
        by_file.setdefault(file, []).append(n)
    for f, lst in sorted(by_file.items()):
        lines.append(f'- {f} : {len(lst)} échec(s)')
lines.append('')
lines.append('## Détail et propositions par test')

for node in emission_failures:
    lines.append(f'### {node}')
    rep = reports.get(node)
    if not rep:
        lines.append('- Rapport individuel : non trouvé')
        lines.append('')
        continue
    exit_code = rep.get('exit_code')
    lines.append(f'- Code de sortie : {exit_code}')
    # extract snippets
    stdout = (rep.get('stdout') or '').splitlines()
    stderr = (rep.get('stderr') or '').splitlines()
    # find likely assertion or last traceback lines
    exc = None
    for l in reversed(stderr[-30:]):
        if 'Traceback' in l or 'Assertion' in l or 'Error' in l or 'Exception' in l:
            exc = l
            break
    if not exc and stderr:
        exc = stderr[-1]
    if exc:
        lines.append(f'- Ligne d\'exception détectée : {exc}')
    lines.append('- Extrait stdout (début) :')
    if stdout:
        for ln in stdout[:8]:
            lines.append('    ' + textwrap.fill(ln, width=200))
    else:
        lines.append('    (vide)')
    lines.append('- Extrait stderr (début) :')
    if stderr:
        for ln in stderr[:8]:
            lines.append('    ' + textwrap.fill(ln, width=200))
    else:
        lines.append('    (vide)')
    lines.append('- Extrait stderr (fin) :')
    if stderr:
        for ln in stderr[-8:]:
            lines.append('    ' + textwrap.fill(ln, width=200))
    else:
        lines.append('    (vide)')
    # Quick suggestion heuristics
    suggestions = []
    low = node.lower()
    if 'mfn' in low or 'hl7' in low:
        suggestions.append('Vérifier les générateurs MFN/HL7 (format des segments, terminaison CR/LF, champs MSH).')
        suggestions.append('S\'assurer que les fonctions acceptent des snapshots (dict) ou des instances SQLModel selon le flux d\'émission.')
    if 'fhir' in low:
        suggestions.append('Vérifier la conversion FHIR (identifiants, bundle, endpoint de transport).')
    if 'emission_crud' in low or 'message' in low:
        suggestions.append('Vérifier la persistance de MessageLog et que les endpoints configurés en TESTING sont accessibles.')
    if suggestions:
        lines.append('- Suggestions initiales :')
        for s in suggestions:
            lines.append('    - ' + s)
    lines.append('')

lines.append('## Étapes suivantes proposées')
lines.append('1. Corriger d\'abord les tests MFN/HL7 qui échouent sur la génération (MSH/MFI/MFE mal formés).')
lines.append('2. Pour chaque test listé, je peux: extraire la trace complète, ouvrir le fichier source du test, proposer un patch correctif et relancer le test individuel.')
lines.append('3. Si vous validez, je commence par les 5 premiers tests de cette liste et applique des correctifs incrémentaux.')

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('Rapport de triage écrit dans', OUT_PATH)
print('Nombre de tests d\'émission échoués :', len(emission_failures))
