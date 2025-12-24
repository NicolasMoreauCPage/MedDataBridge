#!/usr/bin/env python3
"""
Script de nettoyage des anciens types de namespace du vocabulaire

Ce script supprime les anciens types de namespace qui ont été supprimés
de l'enum IdentifierType mais qui pouvaient encore être présents dans
le système de vocabulaire.

Anciens types supprimés:
- NA (Numéro d'Archive) - remplacé par NDA
- PI (Patient Identifier) - remplacé par IPP
- PG (Patient Global) - remplacé par IPP
- NDP (Numéro de Dossier Patient) - remplacé par NDA
- SS (Séjour partiel) - type obsolète
- FINESS - code établissement, pas un type de namespace
"""

from app.db import session_factory
from sqlmodel import select, delete
from app.models_vocabulary import VocabularyValue


def clean_old_namespace_types():
    """Supprime les anciens types de namespace du vocabulaire."""
    session = session_factory()
    try:
        # Anciens types de namespace à supprimer
        old_types = ['NA', 'PI', 'PG', 'NDP', 'SS', 'FINESS']

        print('🧹 Nettoyage des anciens types de namespace du vocabulaire...')
        print('Types à supprimer:', ', '.join(old_types))

        deleted_count = 0
        for old_type in old_types:
            # Trouver et supprimer les valeurs
            values_to_delete = session.exec(
                select(VocabularyValue).where(VocabularyValue.code == old_type)
            ).all()

            for value in values_to_delete:
                print(f'  - Suppression: {value.code}: {value.display}')
                session.delete(value)
                deleted_count += 1

        session.commit()
        print(f'\n✅ Nettoyage terminé: {deleted_count} anciens types supprimés du vocabulaire.')

        # Vérification
        remaining = []
        for old_type in old_types:
            values = session.exec(
                select(VocabularyValue).where(VocabularyValue.code == old_type)
            ).all()
            remaining.extend(values)

        if remaining:
            print(f'⚠️  Attention: {len(remaining)} anciens types encore présents.')
        else:
            print('✅ Vérification: Aucun ancien type restant.')

    except Exception as e:
        print(f'❌ Erreur lors du nettoyage: {e}')
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    clean_old_namespace_types()