#!/usr/bin/env python3
"""
Script de seed pour insérer les templates de structure hospitalière
dans la table StructureTemplate.

Usage:
    python scripts/seed_structure_templates.py
"""

import sys
import json
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine
from app.models_structure import StructureTemplate, StructureTemplateType


def get_chu_template_payload():
    """Payload JSON pour un CHU type avec 4 pôles."""
    return {
        "poles": [
            {
                "name": "Pôle Médecine",
                "short_name": "MED",
                "description": "Pôle des disciplines médicales",
                "services": [
                    {
                        "name": "Cardiologie",
                        "short_name": "CARDIO",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Cardiologie Hospitalisation", "um_code": "1010", "uf_type": "hospitalisation"},
                            {"name": "UF Cardiologie Consultation", "um_code": "1011", "uf_type": "consultation"},
                        ]
                    },
                    {
                        "name": "Gastro-entérologie",
                        "short_name": "GASTRO",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Gastro Hospitalisation", "um_code": "1020", "uf_type": "hospitalisation"},
                        ]
                    },
                    {
                        "name": "Pneumologie",
                        "short_name": "PNEUMO",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Pneumologie", "um_code": "1030", "uf_type": "hospitalisation"},
                        ]
                    },
                ]
            },
            {
                "name": "Pôle Chirurgie",
                "short_name": "CHIR",
                "description": "Pôle des disciplines chirurgicales",
                "services": [
                    {
                        "name": "Chirurgie Orthopédique",
                        "short_name": "ORTHO",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Orthopédie", "um_code": "2010", "uf_type": "hospitalisation"},
                            {"name": "UF Bloc Orthopédie", "um_code": "2011", "uf_type": "plateau_technique"},
                        ]
                    },
                    {
                        "name": "Chirurgie Viscérale",
                        "short_name": "VISC",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Chirurgie Viscérale", "um_code": "2020", "uf_type": "hospitalisation"},
                        ]
                    },
                ]
            },
            {
                "name": "Pôle Femme-Enfant",
                "short_name": "FE",
                "description": "Pôle Mère-Enfant",
                "services": [
                    {
                        "name": "Maternité",
                        "short_name": "MATER",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Maternité", "um_code": "3010", "uf_type": "hospitalisation"},
                            {"name": "UF Salle de Naissance", "um_code": "3011", "uf_type": "plateau_technique"},
                        ]
                    },
                    {
                        "name": "Pédiatrie",
                        "short_name": "PEDIA",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Pédiatrie", "um_code": "3020", "uf_type": "hospitalisation"},
                        ]
                    },
                ]
            },
            {
                "name": "Pôle Urgences-Réanimation",
                "short_name": "URG-REA",
                "description": "Pôle des urgences et soins critiques",
                "services": [
                    {
                        "name": "Urgences",
                        "short_name": "URG",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Urgences Adultes", "um_code": "4010", "uf_type": "urgences"},
                            {"name": "UF UHCD", "um_code": "4011", "uf_type": "hospitalisation"},
                        ]
                    },
                    {
                        "name": "Réanimation",
                        "short_name": "REA",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Réanimation Polyvalente", "um_code": "4020", "uf_type": "soins_intensifs"},
                        ]
                    },
                ]
            },
        ]
    }


def get_ch_template_payload():
    """Payload JSON pour un Centre Hospitalier type avec 2 pôles."""
    return {
        "poles": [
            {
                "name": "Pôle Médecine-Chirurgie",
                "short_name": "MED-CHIR",
                "description": "Pôle polyvalent médico-chirurgical",
                "services": [
                    {
                        "name": "Médecine Polyvalente",
                        "short_name": "MED",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Médecine Générale", "um_code": "1010", "uf_type": "hospitalisation"},
                        ]
                    },
                    {
                        "name": "Chirurgie Générale",
                        "short_name": "CHIR",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Chirurgie", "um_code": "2010", "uf_type": "hospitalisation"},
                            {"name": "UF Bloc Opératoire", "um_code": "2011", "uf_type": "plateau_technique"},
                        ]
                    },
                ]
            },
            {
                "name": "Pôle Gériatrie-SSR",
                "short_name": "GER-SSR",
                "description": "Pôle personnes âgées et rééducation",
                "services": [
                    {
                        "name": "Gériatrie",
                        "short_name": "GER",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Gériatrie Aiguë", "um_code": "3010", "uf_type": "hospitalisation"},
                        ]
                    },
                    {
                        "name": "SSR",
                        "short_name": "SSR",
                        "service_type": "SSR",
                        "ufs": [
                            {"name": "UF SSR Polyvalent", "um_code": "3020", "uf_type": "hospitalisation"},
                        ]
                    },
                ]
            },
        ]
    }


def get_clinique_template_payload():
    """Payload JSON pour une Clinique type avec forte composante ambulatoire."""
    return {
        "poles": [
            {
                "name": "Pôle Chirurgie Ambulatoire",
                "short_name": "CHIR-AMB",
                "description": "Chirurgie ambulatoire et hospitalisation courte durée",
                "services": [
                    {
                        "name": "Chirurgie Ambulatoire",
                        "short_name": "AMB",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Chirurgie Ambulatoire", "um_code": "1010", "uf_type": "ambulatoire"},
                            {"name": "UF Bloc Ambulatoire", "um_code": "1011", "uf_type": "plateau_technique"},
                        ]
                    },
                    {
                        "name": "Hospitalisation Complète",
                        "short_name": "HC",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Hospitalisation Chirurgie", "um_code": "1020", "uf_type": "hospitalisation"},
                        ]
                    },
                ]
            },
            {
                "name": "Pôle Imagerie et Consultations",
                "short_name": "IMG-CONSULT",
                "description": "Plateau technique et consultations spécialisées",
                "services": [
                    {
                        "name": "Imagerie Médicale",
                        "short_name": "RADIO",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Radiologie", "um_code": "2010", "uf_type": "plateau_technique"},
                            {"name": "UF Scanner", "um_code": "2011", "uf_type": "plateau_technique"},
                        ]
                    },
                    {
                        "name": "Consultations Externes",
                        "short_name": "CONSULT",
                        "service_type": "MCO",
                        "ufs": [
                            {"name": "UF Consultations", "um_code": "2020", "uf_type": "consultation"},
                        ]
                    },
                ]
            },
        ]
    }


def seed_templates():
    """Insère ou met à jour les templates de structure dans la base."""
    templates_data = [
        {
            "key": "chu",
            "name": "CHU",
            "template_type": StructureTemplateType.CHU,
            "description": "Centre Hospitalier Universitaire avec 4 pôles spécialisés (Médecine, Chirurgie, Femme-Enfant, Urgences-Réanimation)",
            "is_default": True,
            "payload": json.dumps(get_chu_template_payload(), ensure_ascii=False, indent=2),
        },
        {
            "key": "ch",
            "name": "Centre Hospitalier",
            "template_type": StructureTemplateType.CH,
            "description": "Établissement général polyvalent avec 2 pôles (Médecine-Chirurgie, Gériatrie-SSR)",
            "is_default": False,
            "payload": json.dumps(get_ch_template_payload(), ensure_ascii=False, indent=2),
        },
        {
            "key": "clinique",
            "name": "Clinique",
            "template_type": StructureTemplateType.CLINIQUE,
            "description": "Structure privée avec forte composante ambulatoire (Chirurgie ambulatoire, Imagerie)",
            "is_default": False,
            "payload": json.dumps(get_clinique_template_payload(), ensure_ascii=False, indent=2),
        },
    ]

    with Session(engine) as session:
        for data in templates_data:
            # Vérifier si le template existe déjà
            existing = session.exec(
                select(StructureTemplate).where(StructureTemplate.key == data["key"])
            ).first()

            if existing:
                # Mise à jour
                for key, value in data.items():
                    setattr(existing, key, value)
                session.add(existing)
                print(f"✓ Template '{data['key']}' mis à jour")
            else:
                # Création
                template = StructureTemplate(**data)
                session.add(template)
                print(f"✓ Template '{data['key']}' créé")

        session.commit()
        print(f"\n✅ {len(templates_data)} templates insérés/mis à jour avec succès")


if __name__ == "__main__":
    print("🚀 Seed des templates de structure hospitalière\n")
    seed_templates()
