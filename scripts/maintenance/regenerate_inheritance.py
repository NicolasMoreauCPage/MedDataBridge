#!/usr/bin/env python3
"""
Script pour régénérer complètement les propriétés d'héritage
dans models_structure.py de manière propre et complète.
"""

import re
from pathlib import Path

def regenerate_inheritance_properties():
    """Régénère toutes les propriétés d'héritage de manière propre"""

    models_file = Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/app/models_structure.py")

    with open(models_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Définition des hiérarchies d'héritage pour chaque modèle
    inheritance_hierarchies = {
        'Pole': 'entite_geo',
        'Service': 'pole.entite_geo',
        'UniteFonctionnelle': 'service.pole.entite_geo',
        'UniteHebergement': 'unite_fonctionnelle.service.pole.entite_geo',
        'Chambre': 'unite_hebergement.unite_fonctionnelle.service.pole.entite_geo',
        'Lit': 'chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo'
    }

    # Propriétés d'héritage à générer
    address_properties = [
        ('inherited_address_line1', 'address_line1'),
        ('inherited_address_line2', 'address_line2'),
        ('inherited_address_line3', 'address_line3'),
        ('inherited_address_city', 'address_city'),
        ('inherited_address_postalcode', 'address_postalcode'),
        ('inherited_address_country', 'address_country'),
    ]

    physical_properties = [
        ('inherited_etage', 'etage'),
        ('inherited_aile', 'aile'),
        ('inherited_type_chambre', 'type_chambre'),
    ]

    def generate_inheritance_properties(class_name):
        if class_name not in inheritance_hierarchies:
            return ""

        hierarchy_path = inheritance_hierarchies[class_name]
        path_parts = hierarchy_path.split('.')

        # Générer les vérifications de nullité
        null_checks = []
        for i in range(len(path_parts)):
            partial_path = '.'.join(path_parts[:i+1])
            null_checks.append(f"self.{partial_path}")

        null_check_str = ' and '.join(null_checks)

        properties = []

        # Propriétés d'adresse
        for prop_name, field_name in address_properties:
            if field_name == 'address_country':
                default_value = ' or "FR"'
            else:
                default_value = ''

            properties.append(f'''    @property
    def {prop_name}(self) -> Optional[str]:
        """{field_name.replace('_', ' ').title()} héritée de l'entité géographique parente"""
        if {null_check_str}:
            return self.{hierarchy_path}.{field_name}{default_value}
        return None''')

        # Propriétés physiques
        for prop_name, field_name in physical_properties:
            properties.append(f'''    @property
    def {prop_name}(self) -> Optional[str]:
        """{field_name.replace('_', ' ').title()} hérité de l'entité géographique parente"""
        if {null_check_str}:
            return self.{hierarchy_path}.{field_name}
        return None''')

        return '\n\n    # Propriétés d\'héritage de localisation physique depuis l\'entité géographique\n' + '\n'.join(properties)

    # Appliquer à chaque classe
    for class_name in inheritance_hierarchies.keys():
        # Trouver la classe dans le contenu
        class_pattern = rf'(class {class_name}\(SQLModel, table=True\):.*?(?=\n\nclass|\n\nfrom|\Z))'

        def replace_class(match):
            class_content = match.group(1)

            # Supprimer les anciennes propriétés d'héritage
            class_content = re.sub(
                r'\n    # Propriétés d\'héritage.*?(?=\n\n    |\n\nclass|\n\nfrom|\Z)',
                '',
                class_content,
                flags=re.DOTALL
            )

            # Ajouter les nouvelles propriétés avant la fin de la classe
            new_properties = generate_inheritance_properties(class_name)

            # Trouver où insérer (avant la dernière ligne de la classe)
            lines = class_content.split('\n')
            # Supprimer les lignes vides à la fin
            while lines and lines[-1].strip() == '':
                lines.pop()

            # Ajouter les propriétés
            if new_properties:
                lines.append('')
                lines.extend(new_properties.split('\n'))

            return '\n'.join(lines)

        content = re.sub(class_pattern, replace_class, content, flags=re.DOTALL)

    # Écrire le fichier
    with open(models_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Propriétés d'héritage régénérées avec succès !")

if __name__ == "__main__":
    regenerate_inheritance_properties()