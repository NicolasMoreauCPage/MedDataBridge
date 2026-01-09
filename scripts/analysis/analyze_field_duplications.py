#!/usr/bin/env python3
"""
Analyse complète des duplications dans les modèles de structure
pour identifier les opportunités d'héritage et d'optimisation.
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass

@dataclass
class FieldInfo:
    """Informations sur un champ dans un modèle"""
    name: str
    model: str
    is_optional: bool = True
    has_default: bool = False
    description: Optional[str] = None

@dataclass
class DuplicationAnalysis:
    """Analyse d'une duplication de champs"""
    field_name: str
    models: List[str]
    can_inherit: bool
    inheritance_path: Optional[str] = None
    notes: Optional[str] = None

def analyze_field_duplications():
    """Analyse les duplications de champs dans tous les modèles"""

    # Définition de la hiérarchie
    hierarchy = {
        'EntiteJuridique': [],
        'EntiteGeographique': ['EntiteJuridique'],
        'Pole': ['EntiteGeographique'],
        'Service': ['Pole'],
        'UniteFonctionnelle': ['Service'],
        'UniteHebergement': ['UniteFonctionnelle'],
        'Chambre': ['UniteHebergement'],
        'Lit': ['Chambre']
    }

    # Champs présents dans chaque modèle (analyse basée sur le code lu)
    model_fields = {
        'EntiteJuridique': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode',
            'category_code', 'is_active', 'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'EntiteGeographique': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'responsible_id', 'responsible_name', 'responsible_firstname', 'responsible_email', 'responsible_phone',
            'responsible_rpps', 'responsible_adeli', 'responsible_specialty',
            'category_code', 'category_name', 'category_sae',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'Pole': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'responsible_id', 'responsible_name', 'responsible_firstname', 'responsible_email', 'responsible_phone',
            'responsible_rpps', 'responsible_adeli', 'responsible_specialty',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'Service': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'responsible_id', 'responsible_name', 'responsible_firstname', 'responsible_email', 'responsible_phone',
            'responsible_rpps', 'responsible_adeli', 'responsible_specialty',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'UniteFonctionnelle': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'responsible_id', 'responsible_name', 'responsible_firstname', 'responsible_email', 'responsible_phone',
            'responsible_rpps', 'responsible_adeli', 'responsible_specialty',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'UniteHebergement': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'Chambre': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ],
        'Lit': [
            'address_line1', 'address_line2', 'address_line3', 'address_city', 'address_postalcode', 'address_country',
            'etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
            'typology', 'uf_type', 'gender_usage',
            'opening_date', 'activation_date', 'closing_date', 'deactivation_date'
        ]
    }

    # Identifier les champs dupliqués
    all_fields = set()
    for fields in model_fields.values():
        all_fields.update(fields)

    duplications = []
    for field in all_fields:
        models_with_field = [model for model, fields in model_fields.items() if field in fields]
        if len(models_with_field) > 1:
            # Déterminer si l'héritage est possible
            can_inherit = False
            inheritance_path = None

            if field.startswith('address_'):
                # Les adresses peuvent être héritées de EntiteGeographique
                if 'EntiteGeographique' in models_with_field:
                    can_inherit = True
                    inheritance_path = "EntiteGeographique"
            elif field in ['etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode', 'physical_type',
                          'typology', 'uf_type', 'gender_usage']:
                # Ces champs peuvent être hérités selon la hiérarchie
                # Pour les entités de bas niveau, hériter des parents
                can_inherit = True
                inheritance_path = "hiérarchie parent"
            elif field.startswith('responsible_'):
                # Les responsables peuvent être hérités
                can_inherit = True
                inheritance_path = "hiérarchie parent"
            elif field in ['opening_date', 'activation_date', 'closing_date', 'deactivation_date']:
                # Les dates peuvent être héritées
                can_inherit = True
                inheritance_path = "hiérarchie parent"

            duplications.append(DuplicationAnalysis(
                field_name=field,
                models=models_with_field,
                can_inherit=can_inherit,
                inheritance_path=inheritance_path
            ))

    return sorted(duplications, key=lambda x: (not x.can_inherit, len(x.models), x.field_name))

def print_analysis():
    """Affiche l'analyse des duplications"""
    duplications = analyze_field_duplications()

    print("=== ANALYSE DES DUPLICATIONS DE CHAMPS ===\n")

    # Grouper par catégorie
    categories = {
        'Adresses': [d for d in duplications if d.field_name.startswith('address_')],
        'Localisation physique': [d for d in duplications if d.field_name in ['etage', 'aile', 'type_chambre']],
        'Statuts opérationnels': [d for d in duplications if d.field_name in ['operational_status', 'status', 'mode', 'physical_type']],
        'Typologie': [d for d in duplications if d.field_name in ['typology', 'uf_type', 'gender_usage']],
        'Dates': [d for d in duplications if d.field_name in ['opening_date', 'activation_date', 'closing_date', 'deactivation_date']],
        'Responsables': [d for d in duplications if d.field_name.startswith('responsible_')],
        'Catégorisation': [d for d in duplications if d.field_name.startswith('category_')],
        'Autres': [d for d in duplications if not any(d.field_name.startswith(prefix) for prefix in
                                                     ['address_', 'responsible_', 'category_']) and
                  d.field_name not in ['etage', 'aile', 'type_chambre', 'operational_status', 'status', 'mode',
                                     'physical_type', 'typology', 'uf_type', 'gender_usage', 'opening_date',
                                     'activation_date', 'closing_date', 'deactivation_date']]
    }

    for category, dupes in categories.items():
        if not dupes:
            continue

        print(f"## {category}")
        print()

        for dup in dupes:
            status = "✅ Héritable" if dup.can_inherit else "❌ Non héritable"
            print(f"### {dup.field_name}")
            print(f"- **Statut**: {status}")
            if dup.inheritance_path:
                print(f"- **Héritage possible**: {dup.inheritance_path}")
            print(f"- **Présent dans**: {', '.join(dup.models)}")
            print(f"- **Nombre de modèles**: {len(dup.models)}")
            print()

        # Statistiques de la catégorie
        total_fields = len(dupes)
        inheritable = sum(1 for d in dupes if d.can_inherit)
        total_duplications = sum(len(d.models) for d in dupes)
        potential_savings = sum(len(d.models) - 1 for d in dupes if d.can_inherit)

        print(f"**Statistiques {category}**:")
        print(f"- Champs dupliqués: {total_fields}")
        print(f"- Champs héritables: {inheritable}")
        print(f"- Total duplications: {total_duplications}")
        print(f"- Économies potentielles: {potential_savings} champs")
        print()

    # Statistiques globales
    total_duplications = len(duplications)
    inheritable_total = sum(1 for d in duplications if d.can_inherit)
    total_instances = sum(len(d.models) for d in duplications)
    potential_savings_total = sum(len(d.models) - 1 for d in duplications if d.can_inherit)

    print("## STATISTIQUES GLOBALES")
    print()
    print(f"- **Total champs dupliqués**: {total_duplications}")
    print(f"- **Champs héritables**: {inheritable_total} ({inheritable_total/total_duplications*100:.1f}%)")
    print(f"- **Total instances de duplication**: {total_instances}")
    print(f"- **Économies potentielles**: {potential_savings_total} champs ({potential_savings_total/total_instances*100:.1f}%)")
    print()

    print("## PROCHAINES ÉTAPES RECOMMANDÉES")
    print()
    print("1. **Implémenter l'héritage pour les champs de localisation physique** (etage, aile, type_chambre)")
    print("2. **Implémenter l'héritage pour les statuts opérationnels** (operational_status, status, mode, physical_type)")
    print("3. **Implémenter l'héritage pour la typologie** (typology, uf_type, gender_usage)")
    print("4. **Implémenter l'héritage pour les dates** (opening_date, activation_date, closing_date, deactivation_date)")
    print("5. **Implémenter l'héritage pour les responsables** (responsible_* fields)")
    print("6. **Nettoyer les duplications internes** (champs définis 2x dans EntiteGeographique et EntiteJuridique)")
    print("7. **Migrer les templates** pour utiliser les propriétés d'héritage")
    print("8. **Supprimer les champs dupliqués** après validation")
    print()

if __name__ == "__main__":
    print_analysis()