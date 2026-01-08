#!/usr/bin/env python3
"""
Test rapide de validation des scénarios HPRIM_COTATION
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.db import engine
from app.models_scenarios import InteropScenario, InteropScenarioStep
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload


def decode_hl7_payload(payload: str) -> str:
    """Décode un payload HL7 avec séquences d'échappement"""
    if not payload:
        return payload
    return payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')


def validate_hprim_scenario(scenario: InteropScenario) -> dict:
    """Valide un scénario HPRIM_COTATION"""
    validation = {
        'scenario_name': scenario.name,
        'total_steps': len(scenario.steps),
        'hl7_steps': 0,
        'identifiers': {'ipp': [], 'nda': [], 'venue': []},
        'parsing_errors': 0,
        'status': 'unknown'
    }

    for step in scenario.steps:
        if step.message_format == 'hl7' and step.payload:
            validation['hl7_steps'] += 1
            decoded_payload = decode_hl7_payload(step.payload)
            segments = decoded_payload.split('\r')

            for segment in segments:
                if segment.startswith('PID|'):
                    fields = segment.split('|')
                    if len(fields) > 3 and fields[3]:
                        ipp = fields[3].split('^')[0]
                        if ipp and ipp.isdigit() and len(ipp) >= 8:
                            validation['identifiers']['ipp'].append(ipp)
                    if len(fields) > 18 and fields[18]:
                        nda = fields[18].split('^')[0]
                        if nda and nda.isdigit() and len(nda) >= 8:
                            validation['identifiers']['nda'].append(nda)

                elif segment.startswith('PV1|'):
                    fields = segment.split('|')
                    if len(fields) > 3 and fields[3]:
                        venue = fields[3].split('^')[0]
                        if venue and len(venue) >= 3:
                            validation['identifiers']['venue'].append(venue)

    # Déterminer le statut
    has_identifiers = any(validation['identifiers'].values())
    has_errors = validation['parsing_errors'] > 0

    if has_identifiers and not has_errors:
        validation['status'] = 'valid'
    elif has_identifiers and has_errors:
        validation['status'] = 'partial'
    elif has_errors:
        validation['status'] = 'invalid'
    else:
        validation['status'] = 'empty'

    return validation


def main():
    """Test rapide des scénarios HPRIM_COTATION"""
    print('🚀 Test validation HPRIM_COTATION (60 scénarios)')
    print('=' * 60)

    with Session(engine) as session:
        hprim_scenarios = session.exec(
            select(InteropScenario).options(selectinload(InteropScenario.steps)).where(
                InteropScenario.category == 'HPRIM_COTATION'
            )
        ).all()

        print(f'📊 {len(hprim_scenarios)} scénarios à tester\n')

        results = {
            'valid': 0, 'partial': 0, 'invalid': 0, 'empty': 0,
            'total_identifiers': {'ipp': 0, 'nda': 0, 'venue': 0}
        }

        for i, scenario in enumerate(hprim_scenarios, 1):
            validation = validate_hprim_scenario(scenario)
            results[validation['status']] += 1

            for id_type, ids in validation['identifiers'].items():
                results['total_identifiers'][id_type] += len(ids)

            status_icon = {'valid': '✅', 'partial': '⚠️', 'invalid': '❌', 'empty': '🚫'}[validation['status']]
            print(f'[{i:2d}/60] {status_icon} {validation["status"]} - {validation["hl7_steps"]} HL7, {len(validation["identifiers"]["ipp"])} IPP')
        print()
        print('📊 RÉSULTATS HPRIM_COTATION:')
        print(f'   • Validés: {results["valid"]}')
        print(f'   • Partiels: {results["partial"]}')
        print(f'   • Invalides: {results["invalid"]}')
        print(f'   • Vides: {results["empty"]}')

        total_valid = results['valid'] + results['partial']
        success_rate = total_valid / len(hprim_scenarios) * 100
        print(f'   • Taux de succès: {success_rate:.1f}%')
        print()
        print('🆔 Identifiants trouvés:')
        print(f'   • IPP: {results["total_identifiers"]["ipp"]}')
        print(f'   • NDA: {results["total_identifiers"]["nda"]}')
        print(f'   • VENUE: {results["total_identifiers"]["venue"]}')

        # Résumé final
        if success_rate >= 95:
            print('\n🎉 EXCELLENT: Les scénarios HPRIM sont parfaitement intégrés!')
        elif success_rate >= 80:
            print('\n✅ BON: Intégration HPRIM réussie.')
        else:
            print('\n⚠️ MOYEN: Des améliorations nécessaires pour HPRIM.')


if __name__ == "__main__":
    main()