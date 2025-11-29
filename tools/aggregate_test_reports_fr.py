#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agrégation des rapports de tests et génération d'un rapport en français.

Génère : test_reports/failure_report_fr.md
"""
import json
import os
import textwrap

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT, "test_reports")
SUMMARY_PATH = os.path.join(REPORT_DIR, "summary.json")
OUT_PATH = os.path.join(REPORT_DIR, "failure_report_fr.md")

KEYWORD_GROUPS = {
    'Emission / MFN / HL7 / FHIR': ['mfn', 'hl7', 'fhir', 'emission', 'message', 'mfn_organization', 'mfn_structure', 'emission_crud'],
    'Structure / Loc / Venue': ['structure', 'location', 'loc', 'eg', 'ej', 'venue'],
    'Identité / PAM / Patient': ['pam', 'patient', 'dossier', 'pid', 'mouvement'],
    'UI / Templates / Pages': ['ui', 'generated', 'template', 'forms', 'pages', 'ui_pages'],
    'IHM / Workflows / Scenarios': ['scenario', 'scenarios', 'workflow'],
    'IHE / PIX / PDQ / Integration': ['ihe', 'pix', 'pdq', 'integration'],
}

# Load summary
if not os.path.exists(SUMMARY_PATH):
    print('summary.json introuvable dans test_reports/. Exécuter d\'abord le runner.')
    raise SystemExit(1)

with open(SUMMARY_PATH, 'r', encoding='utf-8') as f:
    summary = json.load(f)

failures = summary.get('failures', [])

# Build map of nodeid -> report file
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

# Helper to extract concise error info
def extract_snippet(data):
    out = data.get('stdout', '') or ''
    err = data.get('stderr', '') or ''
    exit_code = data.get('exit_code')
    # Get first lines of stdout
    out_lines = [l for l in out.splitlines() if l.strip()]
    err_lines = [l for l in err.splitlines() if l.strip()]
    head_out = out_lines[:8]
    head_err = err_lines[:8]
    tail_err = err_lines[-8:]
    # Detect exception message: look for last line containing 'Error' or 'Assertion' in stderr
    exc = None
    for l in reversed(err_lines[-20:]):
        if 'Assertion' in l or 'Error' in l or 'Exception' in l or 'Traceback' in l:
            exc = l
            break
    if not exc and tail_err:
        exc = tail_err[-1]
    return {
        'exit_code': exit_code,
        'stdout_head': head_out,
        'stderr_head': head_err,
        'stderr_tail': tail_err,
        'exception_line': exc,
    }

# Group failures by keyword
grouped = {k: [] for k in KEYWORD_GROUPS}
grouped['Autres'] = []

entries = []
for node in failures:
    data = reports.get(node)
    if not data:
        entries.append({'nodeid': node, 'missing_report': True})
        grouped['Autres'].append(node)
        continue
    info = extract_snippet(data)
    entry = {'nodeid': node, 'info': info}
    entries.append(entry)
    lowered = node.lower()
    placed = False
    for g, keys in KEYWORD_GROUPS.items():
        for k in keys:
            if k in lowered:
                grouped[g].append(node)
                placed = True
                break
        if placed:
            break
    if not placed:
        grouped['Autres'].append(node)

# Compose French report
lines = []
lines.append('# Rapport d\'échecs des tests (généré automatiquement)')
lines.append('')
lines.append(f'- Date : {__import__("datetime").datetime.utcnow().isoformat()}Z')
lines.append(f'- Total tests collectés : {summary.get("total")}')
lines.append(f'- Passés : {summary.get("passed")}')
lines.append(f'- Échoués : {summary.get("failed")}')
lines.append(f'- Ignorés / Skipped : {summary.get("skipped", 0)}')
lines.append('')
lines.append('## Résumé par catégorie (basé sur heuristique de mots-clés)')
for g, lst in grouped.items():
    lines.append(f'- **{g}** : {len(lst)} échec(s)')
lines.append('')
lines.append('## Détail des échecs')
for e in entries:
    node = e['nodeid'] if isinstance(e, dict) else e
    if isinstance(e, dict) and e.get('missing_report'):
        lines.append(f"### {node}")
        lines.append("- Rapport individuel : non trouvé")
        lines.append("")
        continue
    info = e['info']
    lines.append(f'### {node}')
    lines.append(f'- Code de sortie pytest : {info["exit_code"]}')
    if info['exception_line']:
        lines.append(f'- Exception / message détecté : {info["exception_line"]}')
    lines.append('- Extrait stdout (début) :')
    if info['stdout_head']:
        lines.extend(['\n'.join([f'    {textwrap.fill(l, width=200)}' for l in info['stdout_head']])])
    else:
        lines.append('    (vide)')
    lines.append('- Extrait stderr (début) :')
    if info['stderr_head']:
        lines.extend(['\n'.join([f'    {textwrap.fill(l, width=200)}' for l in info['stderr_head']])])
    else:
        lines.append('    (vide)')
    lines.append('- Extrait stderr (fin) :')
    if info['stderr_tail']:
        lines.extend(['\n'.join([f'    {textwrap.fill(l, width=200)}' for l in info['stderr_tail']])])
    else:
        lines.append('    (vide)')
    lines.append('')

lines.append('## Recommandations initiales')
lines.append('1. Prioriser les échecs liés à l\'émission (MFN/HL7/FHIR) et aux MessageLog : corriger les générateurs qui produisent des segments mal formés ou l\'usage des snapshots. (Voir catégorie "Emission / MFN / HL7 / FHIR")')
lines.append('2. Pour les échecs UI/Pages, vérifier les fixtures et le client TestClient (problèmes d\'auth/session).')
lines.append('3. Pour les tests d\'intégration IHE/PAM, exécuter localement les tests individuels listés et lire les traces complètes (fichiers JSON) pour identifier les assertions exactes.')
lines.append('4. Si vous voulez, je peux commencer à triager les N tests d\'émission priorisés (où N = nombre d\'échecs dans la catégorie) et proposer des correctifs ciblés.')

# Write output
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('Rapport écrit dans', OUT_PATH)
print('Résumé :', { 'total': summary.get('total'), 'passed': summary.get('passed'), 'failed': summary.get('failed') })
