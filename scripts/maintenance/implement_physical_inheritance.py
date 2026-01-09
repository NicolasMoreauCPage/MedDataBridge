#!/usr/bin/env python3
"""
Implémentation de l'héritage pour les champs de localisation physique
(etage, aile, type_chambre) dans tous les modèles de la hiérarchie.
"""

import re
from pathlib import Path

def add_physical_location_inheritance():
    """Ajoute les propriétés d'héritage pour etage, aile, type_chambre"""

    models_file = Path("/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/app/models_structure.py")

    with open(models_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern pour trouver les classes de modèles
    model_pattern = r'(class (\w+)\(SQLModel, table=True\):.*?(?=\n\nclass|\n\nfrom|\Z))'

    def add_inheritance_properties(match):
        class_name = match.group(2)
        class_content = match.group(1)

        # Ne pas modifier EntiteGeographique (source de l'héritage)
        if class_name == 'EntiteGeographique':
            return class_content

        # Déterminer le chemin d'héritage selon la hiérarchie
        inheritance_paths = {
            'Pole': 'entite_geo',
            'Service': 'pole.entite_geo',
            'UniteFonctionnelle': 'service.pole.entite_geo',
            'UniteHebergement': 'unite_fonctionnelle.service.pole.entite_geo',
            'Chambre': 'unite_hebergement.unite_fonctionnelle.service.pole.entite_geo',
            'Lit': 'chambre.unite_hebergement.unite_fonctionnelle.service.pole.entite_geo'
        }

        if class_name not in inheritance_paths:
            return class_content

        inheritance_path = inheritance_paths[class_name]

        # Propriétés d'héritage pour les champs de localisation physique
        inheritance_properties = f'''

    # Propriétés d'héritage de localisation physique depuis l'entité géographique
    @property
    def inherited_etage(self) -> Optional[str]:
        """Étage hérité de l'entité géographique parente"""
        if self.{inheritance_path}:
            return self.{inheritance_path}.etage
        return None

    @property
    def inherited_aile(self) -> Optional[str]:
        """Aile héritée de l'entité géographique parente"""
        if self.{inheritance_path}:
            return self.{inheritance_path}.aile
        return None

    @property
    def inherited_type_chambre(self) -> Optional[str]:
        """Type de chambre hérité de l'entité géographique parente"""
        if self.{inheritance_path}:
            return self.{inheritance_path}.type_chambre
        return None'''

        # Vérifier si les propriétés existent déjà
        if 'inherited_etage' in class_content:
            print(f"Propriétés d'héritage déjà présentes dans {class_name}")
            return class_content

        # Trouver où insérer les propriétés (après les propriétés d'adresse existantes)
        # Chercher le pattern des propriétés d'héritage d'adresse
        address_inheritance_pattern = r'(\s+@property\s+def inherited_address_country.*?return "FR"\s*\n)'

        if re.search(address_inheritance_pattern, class_content, re.DOTALL):
            # Insérer après les propriétés d'adresse
            class_content = re.sub(
                address_inheritance_pattern,
                r'\1' + inheritance_properties,
                class_content,
                flags=re.DOTALL
            )
        else:
            # Si pas de propriétés d'adresse, chercher la fin de la classe
            # Trouver le dernier @property ou la fin des champs
            lines = class_content.split('\n')
            insert_index = -1

            for i, line in enumerate(lines):
                if line.strip().startswith('@property') or line.strip().startswith('def ') and 'self' in line:
                    insert_index = i
                elif line.strip() == '' and insert_index != -1:
                    # Trouver la fin des propriétés/methodes
                    break

            if insert_index != -1:
                # Insérer après la dernière propriété
                lines.insert(insert_index + 1, inheritance_properties.strip())
                class_content = '\n'.join(lines)

        print(f"Ajout des propriétés d'héritage dans {class_name}")
        return class_content

    # Appliquer les modifications à toutes les classes
    modified_content = re.sub(model_pattern, add_inheritance_properties, content, flags=re.DOTALL)

    # Écrire le fichier modifié
    with open(models_file, 'w', encoding='utf-8') as f:
        f.write(modified_content)

    print("Héritage des champs de localisation physique ajouté avec succès !")

if __name__ == "__main__":
    add_physical_location_inheritance()