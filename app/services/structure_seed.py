"""Service de génération de données de démonstration pour la structure hospitalière.

Ce module fournit un dataset complet (DEMO_STRUCTURE) représentant un établissement 
hospitalier fictif (CHU Demo) avec :
- Entité juridique et sites géographiques (FINESS, adresses)
- Pôles, services, unités fonctionnelles (UF) avec activités multiples
- Unités d'hébergement, chambres, lits avec statuts opérationnels
- Intégration avec les scénarios IHE (ADT, PAM) pour tests d'interopérabilité

Fonctions principales :
- ensure_demo_structure() : crée ou met à jour la structure complète (upsert idempotent)
- _ensure_* : fonctions privées pour chaque niveau hiérarchique (EJ, EG, Pole, Service, UF, UH, Chambre, Lit)
- _sync_uf_activities() : synchronise les activités d'une UF (relation N-N avec UFActivity)

Usage typique :
    from app.services.structure_seed import ensure_demo_structure
    ensure_demo_structure(session, ght_context_id=1, force_recreate=False)

Le dataset DEMO_STRUCTURE est utilisé par :
- tools/init_complete_demo.py : initialisation base de données complète
- tests/test_ihe_integration.py : scénarios IHE PAM avec structure réaliste
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

from sqlmodel import Session, select

from app.models_structure import (
    Pole,
    Service,
    UniteFonctionnelle,
    UniteHebergement,
    Chambre,
    Lit,
    UFActivity,
    LocationMode,
    LocationPhysicalType,
    LocationServiceType,
    LocationStatus,
)
from app.models_structure_fhir import EntiteGeographique, EntiteJuridique, GHTContext


def _enum_value(value: Any) -> Any:
    """Extrait la valeur brute d'une enum (value), ou retourne l'objet tel quel si ce n'est pas une enum.
    
    Utilisé pour préparer les valeurs de configuration avant insertion en base.
    
    Args:
        value: Valeur potentiellement enum
    
    Returns:
        Valeur .value si enum, sinon l'objet original
    """
    return value.value if hasattr(value, "value") else value


DEMO_STRUCTURE: Dict[str, Any] = {
    # Dataset historique mono-EJ (CHU) conservé pour compatibilité des outils/tests existants.
    # Utiliser EXTENDED_GHT_DATA pour un seed multi-EJ réaliste.
    "entite_juridique": {
        "name": "GHT Demo - Centre Hospitalier Universitaire",
        "short_name": "CHU Demo",
        "description": (
            "Structure hospitalière complète servant de référentiel pour les tests "
            "d'interopérabilité et les démonstrations IHE PAM / FHIR."
        ),
        "finess_ej": "010000000",
        "siren": "123456789",
        "siret": "12345678900011",
        "address_line": "10 Rue de la République",
        "postal_code": "69000",
        "city": "Lyon",
        "country": "FR",
        "is_active": True,
    },
    "sites": [
        {
            "identifier": "CHU-DEMO-SITE-CENTRAL",
            "name": "CHU Demo - Site Central",
            "short_name": "Site Central",
            "description": "Plateau principal de soins aigus et maternité.",
            "finess": "010000001",
            "status": LocationStatus.ACTIVE,
            "mode": LocationMode.INSTANCE,
            "physical_type": LocationPhysicalType.SI,
            "type": "MCO",
            "address_line1": "1 Place de l'Hôpital",
            "address_postalcode": "69002",
            "address_city": "Lyon",
            "poles": [
                {
                    "identifier": "CHU-DEMO-POLE-MED",
                    "name": "Pôle Médecine Aiguë",
                    "short_name": "Médecine",
                    "description": "Urgences, cardiologie et médecine interne.",
                    "physical_type": LocationPhysicalType.AREA,
                    "services": [
                        {
                            "identifier": "CHU-DEMO-SRV-URG",
                            "name": "Service des Urgences Adultes",
                            "short_name": "Urgences",
                            "service_type": LocationServiceType.MCO,
                            "physical_type": LocationPhysicalType.BU,
                            "typology": "Urgences",
                            "ufs": [
                                {
                                    "identifier": "CHU-DEMO-UF-URG-ACC",
                                    "name": "UF Accueil Urgences",
                                    "short_name": "UF Accueil",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "URGA",
                                    "uf_type": "urgences",
                                    "uf_activities": ["urgences", "consultations"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-URG-ZO",
                                            "name": "UH Urgences - Zone Orange",
                                            "short_name": "Zone Orange",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "RDC",
                                            "aile": "Orange",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-URG-01",
                                                    "name": "Box Urgences 1",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Box de soins",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-URG-0101",
                                                            "name": "Lit Urgences 1",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-URG-0102",
                                                            "name": "Lit Urgences 2",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                                {
                                                    "identifier": "CHU-DEMO-CH-URG-02",
                                                    "name": "Box Urgences 2",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Box de soins",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-URG-0201",
                                                            "name": "Lit Urgences 3",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "occupied",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-URG-0202",
                                                            "name": "Lit Urgences 4",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "maintenance",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                        {
                            "identifier": "CHU-DEMO-SRV-CARD",
                            "name": "Service de Cardiologie",
                            "short_name": "Cardiologie",
                            "service_type": LocationServiceType.MCO,
                            "physical_type": LocationPhysicalType.BU,
                            "typology": "Cardiologie",
                            "ufs": [
                                {
                                    "identifier": "CHU-DEMO-UF-CARD-HOSP",
                                    "name": "UF Hospitalisation Cardiologique",
                                    "short_name": "UF Cardio HC",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "CARD-HC",
                                    "uf_type": "hospitalisation",
                                    "uf_activities": ["hospitalisation", "consultations"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-CARD-AE",
                                            "name": "UH Cardiologie – Aile Est",
                                            "short_name": "Cardio Est",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "3",
                                            "aile": "Est",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-CARD-301",
                                                    "name": "Chambre 301",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Double",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-CARD-301A",
                                                            "name": "Lit 301A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-CARD-301B",
                                                            "name": "Lit 301B",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                                {
                                                    "identifier": "CHU-DEMO-CH-CARD-302",
                                                    "name": "Chambre 302",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Simple",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-CARD-302A",
                                                            "name": "Lit 302A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "occupied",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "identifier": "CHU-DEMO-UF-CARD-SI",
                                    "name": "UF Soins Intensifs Cardiaques",
                                    "short_name": "UF SIC",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "CARD-SI",
                                    "uf_type": "soins intensifs",
                                    "uf_activities": ["hospitalisation"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-CARD-USI",
                                            "name": "Unité de Soins Intensifs Cardiaques",
                                            "short_name": "USIC",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "2",
                                            "aile": "Nord",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-CARD-USI-01",
                                                    "name": "Box USIC 1",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Box monitoré",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-CARD-USI-01A",
                                                            "name": "Lit USIC 1",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-CARD-USI-01B",
                                                            "name": "Lit USIC 2",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
                {
                    "identifier": "CHU-DEMO-POLE-FEM",
                    "name": "Pôle Femme-Enfant",
                    "short_name": "Femme-Enfant",
                    "description": "Maternité, néonatologie et obstétrique.",
                    "physical_type": LocationPhysicalType.AREA,
                    "services": [
                        {
                            "identifier": "CHU-DEMO-SRV-MAT",
                            "name": "Service Maternité & Obstétrique",
                            "short_name": "Maternité",
                            "service_type": LocationServiceType.MCO,
                            "physical_type": LocationPhysicalType.BU,
                            "typology": "Obstétrique",
                            "ufs": [
                                {
                                    "identifier": "CHU-DEMO-UF-MAT-SC",
                                    "name": "UF Suites de couches",
                                    "short_name": "Suites de couches",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "MAT-SC",
                                    "uf_type": "maternite",
                                    "uf_activities": ["hospitalisation"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-MAT-ET2",
                                            "name": "Maternité – 2e étage",
                                            "short_name": "Mat 2e",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "2",
                                            "aile": "Sud",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-MAT-201",
                                                    "name": "Chambre 201",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Mère-enfant",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-MAT-201A",
                                                            "name": "Lit Mère 201",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-MAT-201B",
                                                            "name": "Lit Bébé 201",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                                {
                                                    "identifier": "CHU-DEMO-CH-MAT-202",
                                                    "name": "Chambre 202",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Mère-enfant",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-MAT-202A",
                                                            "name": "Lit Mère 202",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-MAT-202B",
                                                            "name": "Lit Bébé 202",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                                {
                                    "identifier": "CHU-DEMO-UF-MAT-BO",
                                    "name": "UF Bloc Obstétrical",
                                    "short_name": "Bloc obstétrical",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "MAT-BO",
                                    "uf_type": "bloc",
                                    "uf_activities": ["bloc"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-MAT-BLOC",
                                            "name": "Bloc Obstétrical",
                                            "short_name": "Bloc mat",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "1",
                                            "aile": "Bloc",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-MAT-BLOC-01",
                                                    "name": "Salle de naissance 1",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Salle de naissance",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-MAT-BLOC-01",
                                                            "name": "Lit de naissance 1",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        {
            "identifier": "CHU-DEMO-SITE-NORD",
            "name": "CHU Demo - Site Nord",
            "short_name": "Site Nord",
            "description": "Site spécialisé en SSR et rééducation.",
            "finess": "010000002",
            "status": LocationStatus.ACTIVE,
            "mode": LocationMode.INSTANCE,
            "physical_type": LocationPhysicalType.SI,
            "type": "SSR",
            "address_line1": "50 Avenue des Alpes",
            "address_postalcode": "69100",
            "address_city": "Villeurbanne",
            "poles": [
                {
                    "identifier": "CHU-DEMO-POLE-SSR",
                    "name": "Pôle Soins de Suite et Réadaptation",
                    "short_name": "Pôle SSR",
                    "physical_type": LocationPhysicalType.AREA,
                    "services": [
                        {
                            "identifier": "CHU-DEMO-SRV-SSR",
                            "name": "Service Rééducation Fonctionnelle",
                            "short_name": "Rééducation",
                            "service_type": LocationServiceType.SSR,
                            "physical_type": LocationPhysicalType.BU,
                            "typology": "Rééducation",
                            "ufs": [
                                {
                                    "identifier": "CHU-DEMO-UF-SSR-READ",
                                    "name": "UF Réadaptation Neurologique",
                                    "short_name": "UF Réadaptation",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "SSR-NEURO",
                                    "uf_type": "readaptation",
                                    "uf_activities": ["hospitalisation"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-SSR-PAV",
                                            "name": "Pavillon SSR Nord",
                                            "short_name": "Pavillon Nord",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "1",
                                            "aile": "Nord",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-SSR-101",
                                                    "name": "Chambre 101",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Double",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-SSR-101A",
                                                            "name": "Lit 101A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-SSR-101B",
                                                            "name": "Lit 101B",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                                {
                                                    "identifier": "CHU-DEMO-CH-SSR-102",
                                                    "name": "Chambre 102",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Double",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-SSR-102A",
                                                            "name": "Lit 102A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "occupied",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-SSR-102B",
                                                            "name": "Lit 102B",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        },
        {
            "identifier": "CHU-DEMO-SITE-PSY",
            "name": "CHU Demo - Site Psychiatrie",
            "short_name": "Site Psy",
            "description": "Site dédié aux prises en charge psychiatriques adultes.",
            "finess": "010000003",
            "status": LocationStatus.ACTIVE,
            "mode": LocationMode.INSTANCE,
            "physical_type": LocationPhysicalType.SI,
            "type": "PSY",
            "address_line1": "20 Rue des Cèdres",
            "address_postalcode": "69008",
            "address_city": "Lyon",
            "poles": [
                {
                    "identifier": "CHU-DEMO-POLE-PSY",
                    "name": "Pôle Psychiatrie",
                    "short_name": "Psychiatrie",
                    "description": "Prise en charge psychiatrique – hospitalisation et consultations.",
                    "physical_type": LocationPhysicalType.AREA,
                    "services": [
                        {
                            "identifier": "CHU-DEMO-SRV-PSY-ADU",
                            "name": "Service Psychiatrie Adulte",
                            "short_name": "Psy Adulte",
                            "service_type": LocationServiceType.PSY,
                            "physical_type": LocationPhysicalType.BU,
                            "typology": "Psychiatrie générale",
                            "ufs": [
                                {
                                    "identifier": "CHU-DEMO-UF-PSY-HOSP",
                                    "name": "UF Hospitalisation Psychiatrie",
                                    "short_name": "UF Psy Hosp",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "PSY-HOSP",
                                    "uf_type": "hospitalisation",
                                    "uf_activities": ["hospitalisation", "consultations"],
                                    "uhs": [
                                        {
                                            "identifier": "CHU-DEMO-UH-PSY-A",
                                            "name": "UH Psychiatrie – Secteur A",
                                            "short_name": "Psy Secteur A",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "1",
                                            "aile": "A",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-PSY-A101",
                                                    "name": "Chambre A101",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Simple sécurisée",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-PSY-A101A",
                                                            "name": "Lit A101A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        }
                                                    ],
                                                },
                                                {
                                                    "identifier": "CHU-DEMO-CH-PSY-A102",
                                                    "name": "Chambre A102",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Double",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-PSY-A102A",
                                                            "name": "Lit A102A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        },
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-PSY-A102B",
                                                            "name": "Lit A102B",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "occupied",
                                                        }
                                                    ],
                                                }
                                            ],
                                        },
                                        {
                                            "identifier": "CHU-DEMO-UH-PSY-B",
                                            "name": "UH Psychiatrie – Secteur B",
                                            "short_name": "Psy Secteur B",
                                            "physical_type": LocationPhysicalType.WI,
                                            "etage": "2",
                                            "aile": "B",
                                            "chambres": [
                                                {
                                                    "identifier": "CHU-DEMO-CH-PSY-B201",
                                                    "name": "Chambre B201",
                                                    "physical_type": LocationPhysicalType.RO,
                                                    "type_chambre": "Simple",
                                                    "lits": [
                                                        {
                                                            "identifier": "CHU-DEMO-LIT-PSY-B201A",
                                                            "name": "Lit B201A",
                                                            "physical_type": LocationPhysicalType.BD,
                                                            "operational_status": "available",
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "identifier": "CHU-DEMO-UF-PSY-CMP",
                                    "name": "UF Consultations (CMP)",
                                    "short_name": "CMP",
                                    "physical_type": LocationPhysicalType.FL,
                                    "um_code": "PSY-CMP",
                                    "uf_type": "consultations",
                                    "uf_activities": ["consultations"],
                                    "uhs": []
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# EXTENDED_GHT_DATA : Jeu de données multi-EJ réaliste
# ---------------------------------------------------------------------------
# Objectif : Fournir un GHT avec plusieurs entités juridiques distinctes simulant
# un territoire complet :
#   - CHU universitaire multi-sites (MCO + Maternité + Urgences + SSR partiel)
#   - Centre Hospitalier Local (hôpital général avec médecine, chirurgie légère)
#   - EHPAD (structure d'hébergement personnes âgées dépendantes)
#   - Établissement Psychiatrique (PSY)
# Chaque EJ a ses sites (EG), pôles, services, UF, UH, chambres, lits.
# Les identifiants sont conçus pour être uniques et idempotents (identifier).
# ---------------------------------------------------------------------------
EXTENDED_GHT_DATA: Dict[str, Any] = {
    "juridical_entities": [
        {
            "entite_juridique": {
                "name": "CHU Universitaire Lyon",
                "short_name": "CHU Lyon",
                "description": "Centre Hospitalier Universitaire de référence régional (multi-sites).",
                "finess_ej": "020000000",
                "siren": "145678321",
                "siret": "14567832100011",
                "address_line": "1 Place de l'Hôpital",
                "postal_code": "69002",
                "city": "Lyon",
                "country": "FR",
                "is_active": True,
            },
            "sites": [
                {
                    "identifier": "CHU-LYON-SITE-CENTRAL",
                    "name": "CHU Lyon - Site Central",
                    "short_name": "Site Central",
                    "description": "Plateau technique principal, urgences et blocs.",
                    "finess": "020000001",
                    "status": LocationStatus.ACTIVE,
                    "mode": LocationMode.INSTANCE,
                    "physical_type": LocationPhysicalType.SI,
                    "type": "MCO",
                    "address_line1": "1 Place de l'Hôpital",
                    "address_postalcode": "69002",
                    "address_city": "Lyon",
                    "poles": [
                        {
                            "identifier": "CHU-LYON-POLE-URG",
                            "name": "Pôle Urgences / SAMU",
                            "short_name": "Urgences",
                            "description": "Urgences adultes + UH médecine aiguë.",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "CHU-LYON-SRV-URG-ADU",
                                    "name": "Service Urgences Adultes",
                                    "short_name": "Urgences",
                                    "service_type": LocationServiceType.MCO,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Urgences",
                                    "ufs": [
                                        {
                                            "identifier": "CHU-LYON-UF-URG-ACC",
                                            "name": "UF Accueil-Tria ge",
                                            "short_name": "Accueil",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "URG-ACC",
                                            "uf_type": "urgences",
                                            "uf_activities": ["urgences", "consultations"],
                                            "uhs": [
                                                {
                                                    "identifier": "CHU-LYON-UH-URG-ZA",
                                                    "name": "UH Zone Accueil",
                                                    "short_name": "Zone A",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "RDC",
                                                    "aile": "A",
                                                    "chambres": [
                                                        {
                                                            "identifier": "CHU-LYON-CH-URG-A01",
                                                            "name": "Box A01",
                                                            "physical_type": LocationPhysicalType.RO,
                                                            "type_chambre": "Box",
                                                            "lits": [
                                                                {"identifier": "CHU-LYON-LIT-URG-A0101", "name": "Lit A01", "physical_type": LocationPhysicalType.BD, "operational_status": "available"},
                                                                {"identifier": "CHU-LYON-LIT-URG-A0102", "name": "Lit A02", "physical_type": LocationPhysicalType.BD, "operational_status": "available"},
                                                            ],
                                                        },
                                                    ],
                                                }
                                            ],
                                        },
                                        {
                                            "identifier": "CHU-LYON-UF-URG-SHORT",
                                            "name": "UF UHCD / courte durée",
                                            "short_name": "UHCD",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "URG-UHCD",
                                            "uf_type": "hospitalisation",
                                            "uf_activities": ["hospitalisation"],
                                            "uhs": [
                                                {
                                                    "identifier": "CHU-LYON-UH-UHCD-1",
                                                    "name": "UHCD Niveau 1",
                                                    "short_name": "UHCD 1",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "1",
                                                    "aile": "UHCD",
                                                    "chambres": [
                                                        {
                                                            "identifier": "CHU-LYON-CH-UHCD-101",
                                                            "name": "Chambre UHCD 101",
                                                            "physical_type": LocationPhysicalType.RO,
                                                            "type_chambre": "Simple",
                                                            "lits": [
                                                                {"identifier": "CHU-LYON-LIT-UHCD-101A", "name": "Lit UHCD 101A", "physical_type": LocationPhysicalType.BD, "operational_status": "occupied"},
                                                            ],
                                                        }
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "identifier": "CHU-LYON-POLE-MAT",
                            "name": "Pôle Mère-Enfant",
                            "short_name": "Mère-Enfant",
                            "description": "Maternité et néonatologie",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "CHU-LYON-SRV-MAT",
                                    "name": "Service Maternité",
                                    "short_name": "Maternité",
                                    "service_type": LocationServiceType.MCO,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Obstétrique",
                                    "ufs": [
                                        {
                                            "identifier": "CHU-LYON-UF-MAT-SC",
                                            "name": "UF Suites de couches",
                                            "short_name": "Suites",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "MAT-SC",
                                            "uf_type": "maternite",
                                            "uf_activities": ["hospitalisation"],
                                            "uhs": [
                                                {
                                                    "identifier": "CHU-LYON-UH-MAT-ET2",
                                                    "name": "UH Maternité 2e",
                                                    "short_name": "Mat2",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "2",
                                                    "aile": "Sud",
                                                    "chambres": [
                                                        {"identifier": "CHU-LYON-CH-MAT-201", "name": "Chambre 201", "physical_type": LocationPhysicalType.RO, "type_chambre": "Mère-enfant", "lits": [{"identifier": "CHU-LYON-LIT-MAT-201A", "name": "Lit Mère 201", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}, {"identifier": "CHU-LYON-LIT-MAT-201B", "name": "Lit Bébé 201", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
                {
                    "identifier": "CHU-LYON-SITE-SSR",
                    "name": "CHU Lyon - Site SSR",
                    "short_name": "Site SSR",
                    "description": "Site de rééducation et soins de suite.",
                    "finess": "020000002",
                    "status": LocationStatus.ACTIVE,
                    "mode": LocationMode.INSTANCE,
                    "physical_type": LocationPhysicalType.SI,
                    "type": "SSR",
                    "address_line1": "50 Avenue des Alpes",
                    "address_postalcode": "69100",
                    "address_city": "Villeurbanne",
                    "poles": [
                        {
                            "identifier": "CHU-LYON-POLE-READ",
                            "name": "Pôle Réadaptation",
                            "short_name": "Réadaptation",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "CHU-LYON-SRV-READ-FONC",
                                    "name": "Service Rééducation Fonctionnelle",
                                    "short_name": "Rééducation",
                                    "service_type": LocationServiceType.SSR,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Rééducation",
                                    "ufs": [
                                        {
                                            "identifier": "CHU-LYON-UF-READ-NEURO",
                                            "name": "UF Réadaptation Neuro",
                                            "short_name": "Neuro",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "READ-NEURO",
                                            "uf_type": "readaptation",
                                            "uf_activities": ["hospitalisation"],
                                            "uhs": [
                                                {
                                                    "identifier": "CHU-LYON-UH-READ-PAV1",
                                                    "name": "Pavillon Réadaptation 1",
                                                    "short_name": "Pav1",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "1",
                                                    "aile": "Nord",
                                                    "chambres": [
                                                        {"identifier": "CHU-LYON-CH-READ-101", "name": "Chambre 101", "physical_type": LocationPhysicalType.RO, "type_chambre": "Double", "lits": [{"identifier": "CHU-LYON-LIT-READ-101A", "name": "Lit 101A", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}, {"identifier": "CHU-LYON-LIT-READ-101B", "name": "Lit 101B", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "entite_juridique": {
                "name": "Centre Hospitalier Local de Vienne",
                "short_name": "CH Vienne",
                "description": "Hôpital local : médecine générale, chirurgie ambulatoire.",
                "finess_ej": "030000000",
                "siren": "998877665",
                "siret": "99887766500022",
                "address_line": "12 Rue Pasteur",
                "postal_code": "38200",
                "city": "Vienne",
                "country": "FR",
                "is_active": True,
            },
            "sites": [
                {
                    "identifier": "CH-VIENNE-SITE-UNIQUE",
                    "name": "CH Vienne - Site Principal",
                    "short_name": "Site Vienne",
                    "description": "Site unique médecine/chirurgie ambulatoire.",
                    "finess": "030000001",
                    "status": LocationStatus.ACTIVE,
                    "mode": LocationMode.INSTANCE,
                    "physical_type": LocationPhysicalType.SI,
                    "type": "MCO",
                    "address_line1": "12 Rue Pasteur",
                    "address_postalcode": "38200",
                    "address_city": "Vienne",
                    "poles": [
                        {
                            "identifier": "CH-VIENNE-POLE-MED",
                            "name": "Pôle Médecine",
                            "short_name": "Médecine",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "CH-VIENNE-SRV-MED-GEN",
                                    "name": "Service Médecine Générale",
                                    "short_name": "Med Générale",
                                    "service_type": LocationServiceType.MCO,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Médecine",
                                    "ufs": [
                                        {
                                            "identifier": "CH-VIENNE-UF-MED-HOSP",
                                            "name": "UF Hospitalisation Médecine",
                                            "short_name": "UF Med Hosp",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "MED-HOSP",
                                            "uf_type": "hospitalisation",
                                            "uf_activities": ["hospitalisation"],
                                            "uhs": [
                                                {
                                                    "identifier": "CH-VIENNE-UH-MED-1",
                                                    "name": "UH Médecine Niveau 1",
                                                    "short_name": "Med1",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "1",
                                                    "aile": "A",
                                                    "chambres": [
                                                        {"identifier": "CH-VIENNE-CH-MED-101", "name": "Chambre 101", "physical_type": LocationPhysicalType.RO, "type_chambre": "Double", "lits": [{"identifier": "CH-VIENNE-LIT-MED-101A", "name": "Lit 101A", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}, {"identifier": "CH-VIENNE-LIT-MED-101B", "name": "Lit 101B", "physical_type": LocationPhysicalType.BD, "operational_status": "occupied"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "identifier": "CH-VIENNE-POLE-CHIR",
                            "name": "Pôle Chirurgie Ambulatoire",
                            "short_name": "Chir Ambu",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "CH-VIENNE-SRV-CHIR-AMB",
                                    "name": "Service Chirurgie Ambulatoire",
                                    "short_name": "Chir Ambu",
                                    "service_type": LocationServiceType.MCO,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Chirurgie ambulatoire",
                                    "ufs": [
                                        {
                                            "identifier": "CH-VIENNE-UF-CHIR-BLOC",
                                            "name": "UF Bloc Ambulatoire",
                                            "short_name": "Bloc Ambu",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "CHIR-BLOC",
                                            "uf_type": "bloc",
                                            "uf_activities": ["bloc"],
                                            "uhs": [
                                                {
                                                    "identifier": "CH-VIENNE-UH-BLOC-AMB",
                                                    "name": "Zone Chirurgie Ambu",
                                                    "short_name": "Zone Bloc",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "RDC",
                                                    "aile": "Bloc",
                                                    "chambres": [
                                                        {"identifier": "CH-VIENNE-CH-BLOC-PRE", "name": "Salle Pré-op 1", "physical_type": LocationPhysicalType.RO, "type_chambre": "Salle pré-op", "lits": [{"identifier": "CH-VIENNE-LIT-BLOC-PRE1", "name": "Lit Pré1", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "entite_juridique": {
                "name": "EHPAD Les Jardins du Rhône",
                "short_name": "EHPAD Jardins",
                "description": "Établissement d'hébergement personnes âgées dépendantes.",
                "finess_ej": "040000000",
                "siren": "776655443",
                "siret": "77665544300033",
                "address_line": "5 Chemin des Tilleuls",
                "postal_code": "69340",
                "city": "Francheville",
                "country": "FR",
                "is_active": True,
            },
            "sites": [
                {
                    "identifier": "EHPAD-JARDINS-SITE-UNIQUE",
                    "name": "EHPAD Jardins - Site Unique",
                    "short_name": "EHPAD",
                    "description": "Site résidentiel personnes âgées.",
                    "finess": "040000001",
                    "status": LocationStatus.ACTIVE,
                    "mode": LocationMode.INSTANCE,
                    "physical_type": LocationPhysicalType.SI,
                    "type": "EHPAD",
                    "address_line1": "5 Chemin des Tilleuls",
                    "address_postalcode": "69340",
                    "address_city": "Francheville",
                    "poles": [
                        {
                            "identifier": "EHPAD-JARDINS-POLE-SOINS",
                            "name": "Pôle Soins et Vie",
                            "short_name": "Soins",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "EHPAD-JARDINS-SRV-GER",
                                    "name": "Service Gériatrie Résidentielle",
                                    "short_name": "Gériatrie",
                                    "service_type": LocationServiceType.EHPAD,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Hébergement",
                                    "ufs": [
                                        {
                                            "identifier": "EHPAD-JARDINS-UF-HEB-A",
                                            "name": "UF Hébergement Aile A",
                                            "short_name": "Aile A",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "EHPAD-A",
                                            "uf_type": "hebergement",
                                            "uf_activities": ["hospitalisation"],
                                            "uhs": [
                                                {
                                                    "identifier": "EHPAD-JARDINS-UH-AILE-A1",
                                                    "name": "UH Aile A Niveau 1",
                                                    "short_name": "A1",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "1",
                                                    "aile": "A",
                                                    "chambres": [
                                                        {"identifier": "EHPAD-JARDINS-CH-A101", "name": "Chambre A101", "physical_type": LocationPhysicalType.RO, "type_chambre": "Simple", "lits": [{"identifier": "EHPAD-JARDINS-LIT-A101A", "name": "Lit A101", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "entite_juridique": {
                "name": "Établissement Spécialisé Psychiatrie Rhône",
                "short_name": "Psy Rhône",
                "description": "Prise en charge psychiatrique adulte régionale.",
                "finess_ej": "050000000",
                "siren": "665544332",
                "siret": "66554433200044",
                "address_line": "20 Rue des Cèdres",
                "postal_code": "69008",
                "city": "Lyon",
                "country": "FR",
                "is_active": True,
            },
            "sites": [
                {
                    "identifier": "PSY-RHONE-SITE-UNIQUE",
                    "name": "Psy Rhône - Site Unique",
                    "short_name": "Psy Rhône",
                    "description": "Hospitalisation psychiatrique et CMP.",
                    "finess": "050000001",
                    "status": LocationStatus.ACTIVE,
                    "mode": LocationMode.INSTANCE,
                    "physical_type": LocationPhysicalType.SI,
                    "type": "PSY",
                    "address_line1": "20 Rue des Cèdres",
                    "address_postalcode": "69008",
                    "address_city": "Lyon",
                    "poles": [
                        {
                            "identifier": "PSY-RHONE-POLE-ADULT",
                            "name": "Pôle Psychiatrie Adulte",
                            "short_name": "Psy Adulte",
                            "physical_type": LocationPhysicalType.AREA,
                            "services": [
                                {
                                    "identifier": "PSY-RHONE-SRV-ADU",
                                    "name": "Service Hospitalisation Adulte",
                                    "short_name": "Hosp",
                                    "service_type": LocationServiceType.PSY,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Psychiatrie",
                                    "ufs": [
                                        {
                                            "identifier": "PSY-RHONE-UF-HOSP-A",
                                            "name": "UF Hospitalisation Secteur A",
                                            "short_name": "Secteur A",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "PSY-A",
                                            "uf_type": "hospitalisation",
                                            "uf_activities": ["hospitalisation", "consultations"],
                                            "uhs": [
                                                {
                                                    "identifier": "PSY-RHONE-UH-A1",
                                                    "name": "UH Secteur A Niveau 1",
                                                    "short_name": "A1",
                                                    "physical_type": LocationPhysicalType.WI,
                                                    "etage": "1",
                                                    "aile": "A",
                                                    "chambres": [
                                                        {"identifier": "PSY-RHONE-CH-A101", "name": "Chambre A101", "physical_type": LocationPhysicalType.RO, "type_chambre": "Simple sécurisée", "lits": [{"identifier": "PSY-RHONE-LIT-A101A", "name": "Lit A101", "physical_type": LocationPhysicalType.BD, "operational_status": "available"}]},
                                                    ],
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "identifier": "PSY-RHONE-SRV-CMP",
                                    "name": "Service CMP Consultations",
                                    "short_name": "CMP",
                                    "service_type": LocationServiceType.PSY,
                                    "physical_type": LocationPhysicalType.BU,
                                    "typology": "Consultations",
                                    "ufs": [
                                        {
                                            "identifier": "PSY-RHONE-UF-CMP",
                                            "name": "UF Centre Médico-Psychologique",
                                            "short_name": "UF CMP",
                                            "physical_type": LocationPhysicalType.FL,
                                            "um_code": "PSY-CMP",
                                            "uf_type": "consultations",
                                            "uf_activities": ["consultations"],
                                            "uhs": [],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    ]
}



def ensure_demo_structure(
    session: Session,
    context: GHTContext,
    structure: Dict[str, Any] | None = None,
) -> Dict[str, Counter]:
    """Crée ou met à jour la structure hospitalière complète pour le contexte GHT donné.
    
    Cette fonction est idempotente : les identifiants métier (identifier) sont utilisés 
    pour rechercher les entités existantes et les mettre à jour, ou créer de nouvelles 
    entités si elles n'existent pas.
    
    Pipeline :
    1. Entité juridique (EJ) avec FINESS EJ, SIREN, SIRET
    2. Sites géographiques (EG) avec FINESS, adresse
    3. Pôles (Pole) sous chaque EG
    4. Services sous chaque Pole avec typologie
    5. Unités fonctionnelles (UF) avec activités multiples (relation N-N UFActivity)
    6. Unités d'hébergement (UH) avec étage/aile
    7. Chambres avec type
    8. Lits avec statut opérationnel
    
    Args:
        session: Session SQLModel pour les opérations DB
        context: GHTContext auquel rattacher la structure
        structure: Dictionnaire de configuration (défaut=DEMO_STRUCTURE global)
    
    Returns:
        Dictionnaire de compteurs par type d'entité (created/updated/unchanged)
        Ex: {"entite_juridique": Counter({"created": 1}), "pole": Counter({"updated": 2})}
    """
    data = structure or DEMO_STRUCTURE
    stats = {"created": Counter(), "updated": Counter()}

    entite_juridique = _ensure_entite_juridique(session, context, data["entite_juridique"], stats)

    for site in data.get("sites", []):
        entite_geo = _ensure_entite_geographique(session, entite_juridique, site, stats)
        for pole_data in site.get("poles", []):
            pole = _ensure_pole(session, entite_geo, pole_data, stats)
            for service_data in pole_data.get("services", []):
                service = _ensure_service(session, pole, service_data, stats)
                for uf_data in service_data.get("ufs", []):
                    uf = _ensure_unite_fonctionnelle(session, service, uf_data, stats)
                    for uh_data in uf_data.get("uhs", []):
                        uh = _ensure_unite_hebergement(session, uf, uh_data, stats)
                        for chambre_data in uh_data.get("chambres", []):
                            chambre = _ensure_chambre(session, uh, chambre_data, stats)
                            for lit_data in chambre_data.get("lits", []):
                                _ensure_lit(session, chambre, lit_data, stats)

    context.updated_at = datetime.utcnow()
    session.add(context)
    session.commit()
    return stats


def ensure_extended_demo_ght(
    session: Session,
    context: GHTContext,
    dataset: Dict[str, Any] | None = None,
    commit: bool = True,
) -> Dict[str, Dict[str, Counter]]:
    """Crée ou met à jour une structure multi-EJ réaliste pour un GHT.

    Cette fonction utilise EXTENDED_GHT_DATA (multi entités juridiques) pour
    provisionner un territoire hospitalier complet.

    Idempotence : s'appuie sur les identifiants métier (finess_ej pour EJ,
    identifier pour EG/Pole/Service/UF/UH/Chambre/Lit).

    Args:
        session: Session SQLModel
        context: Contexte GHT cible
        dataset: Dataset optionnel (défaut EXTENDED_GHT_DATA)
        commit: Commit explicite en fin (True par défaut)

    Returns:
        Dictionnaire des statistiques par EJ (clé = finess_ej) avec compteurs
        created/updated.
    """
    data = dataset or EXTENDED_GHT_DATA
    results: Dict[str, Dict[str, Counter]] = {}

    for ej_block in data.get("juridical_entities", []):
        ej_conf = ej_block["entite_juridique"]
        # Re-construire structure mono-EJ compatible avec ensure_demo_structure
        single = {
            "entite_juridique": ej_conf,
            "sites": ej_block.get("sites", []),
        }
        stats = ensure_demo_structure(session, context, single)
        results[ej_conf["finess_ej"]] = stats

    if commit:
        context.updated_at = datetime.utcnow()
        session.add(context)
        session.commit()

    return results


def ensure_endpoints_for_context(
    session: Session,
    context: GHTContext,
    ej_finess_list: List[str],
    base_port: int = 5600,
) -> Dict[str, Counter]:
    """Crée des endpoints MLLP / FHIR réalistes pour chaque entité juridique.

    - Un endpoint MLLP (receiver) + un endpoint MLLP (sender) par EJ
    - Un endpoint FHIR (export API) par EJ
    Ports attribués séquentiellement à partir de base_port.

    Idempotent : recherche par name unique.
    """
    from app.models_shared import SystemEndpoint, EndpointKind, EndpointRole  # local import
    stats = Counter()

    port_cursor = base_port
    for finess_ej in ej_finess_list:
        # Noms normalisés
        recv_name = f"MLLP RECV {finess_ej}"
        send_name = f"MLLP SEND {finess_ej}"
        fhir_name = f"FHIR API {finess_ej}"

        existing_recv = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == recv_name)).first()
        if existing_recv is None:
            ep = SystemEndpoint(
                name=recv_name,
                kind=EndpointKind.MLLP,
                role=EndpointRole.RECEIVER,
                ght_context_id=context.id,
                host="0.0.0.0",
                port=port_cursor,
                sending_app="EXT",
                sending_facility=finess_ej,
                receiving_app="BRIDGE",
                receiving_facility=context.code or context.name,
                pam_validate_enabled=True,
            )
            session.add(ep)
            stats["created"] += 1
        else:
            existing_recv.port = existing_recv.port or port_cursor
            existing_recv.updated_at = datetime.utcnow()
            stats["updated"] += 1
        port_cursor += 1

        existing_send = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == send_name)).first()
        if existing_send is None:
            ep = SystemEndpoint(
                name=send_name,
                kind=EndpointKind.MLLP,
                role=EndpointRole.SENDER,
                ght_context_id=context.id,
                host="127.0.0.1",
                port=port_cursor,
                sending_app="BRIDGE",
                sending_facility=context.code or context.name,
                receiving_app="EXT",
                receiving_facility=finess_ej,
            )
            session.add(ep)
            stats["created"] += 1
        else:
            existing_send.updated_at = datetime.utcnow()
            stats["updated"] += 1
        port_cursor += 1

        existing_fhir = session.exec(select(SystemEndpoint).where(SystemEndpoint.name == fhir_name)).first()
        if existing_fhir is None:
            ep = SystemEndpoint(
                name=fhir_name,
                kind=EndpointKind.FHIR,
                role=EndpointRole.BOTH,
                ght_context_id=context.id,
                base_url=f"https://fhir.demo/{finess_ej}",
                auth_kind="none",
            )
            session.add(ep)
            stats["created"] += 1
        else:
            existing_fhir.updated_at = datetime.utcnow()
            stats["updated"] += 1

    session.commit()
    return {"endpoints": stats}


def seed_demo_population(
    session: Session,
    context: GHTContext,
    target_patients: int = 120,
    admit_ratio: float = 0.65,
    urgence_ratio: float = 0.2,
    externe_ratio: float = 0.15,
) -> Dict[str, int]:
    """Génère une population de patients réaliste répartie dans les structures.

    Stratégie:
      - Idempotence partielle: si déjà >= target_patients, ne crée rien.
      - Sinon ajoute des patients jusqu'au quota.
      - Répartition des types de dossiers selon ratios fournis.
      - Chaque patient hospitalisé reçoit un dossier + une venue + mouvements (A01 + éventuel A02 + A03).
      - Patients urgence: A01 (urgence) + A03 (sortie) rapide.
      - Externe: dossier consultation (EXTERNE) sans mouvements complexes.

    Returns: statistiques de créations.
    """
    from app.models import Patient, Dossier, Venue, Mouvement, DossierType
    from app.db import get_next_sequence

    existing_count = len(session.exec(select(Patient.id)).all())
    if existing_count >= target_patients:
        return {"skipped": existing_count, "target": target_patients}

    # Collecte lits disponibles pour assigner locations
    all_lits = session.exec(select(Lit)).all()
    lit_cycle = list(l.identifier for l in all_lits if l.identifier)
    if not lit_cycle:
        lit_cycle = ["UNKNOWN-LIT"]

    # Prénoms/Noms simplifiés (listes courtes - peuvent être étendues)
    first_names = ["Marie", "Jean", "Pierre", "Luc", "Emma", "Leo", "Alice", "Hugo", "Sophie", "Thomas"]
    last_names = ["Martin", "Bernard", "Thomas", "Petit", "Durand", "Robert", "Richard", "Moreau", "Laurent", "Simon"]

    import random
    random.seed(42)  # stable pour reproductibilité

    to_create = target_patients - existing_count
    created_patients = 0
    created_dossiers = 0
    created_venues = 0
    created_mouvements = 0

    def _pick_lit(idx: int) -> str:
        return lit_cycle[idx % len(lit_cycle)]

    for i in range(to_create):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        birth_year = random.randint(1935, 2023)
        birth_date = f"{birth_year}-" + f"{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        patient = Patient(
            patient_seq=get_next_sequence(session, "patient"),
            family=ln,
            given=fn,
            birth_date=birth_date,
            gender=random.choice(["male", "female"]),
            postal_code=f"69{random.randint(100,999)}",
            city="Lyon",
            identity_reliability_code=random.choice(["PROV", "QUAL", "VALI"]),
        )
        session.add(patient)
        created_patients += 1
        # Déterminer type dossier
        r = random.random()
        if r < admit_ratio:
            dossier_type = DossierType.HOSPITALISE
        elif r < admit_ratio + urgence_ratio:
            dossier_type = DossierType.URGENCE
        else:
            dossier_type = DossierType.EXTERNE

        dossier = Dossier(
            dossier_seq=get_next_sequence(session, "dossier"),
            patient_id=patient.id if patient.id else None,  # assigned after flush
            admit_time=datetime.utcnow(),
            dossier_type=dossier_type,
        )
        session.add(dossier)
        session.flush()  # ensure IDs
        created_dossiers += 1

        # Venue & mouvements selon type
        venue = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id,
            start_time=datetime.utcnow(),
            assigned_location=_pick_lit(i),
            hospital_service="MED",
        )
        session.add(venue)
        session.flush()
        created_venues += 1

        # Admission mouvement
        m_adm = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=venue.id,
            type="ADT^A01",
            trigger_event="A01",
            when=datetime.utcnow(),
            to_location=venue.assigned_location,
            movement_type="admission",
        )
        session.add(m_adm)
        created_mouvements += 1

        if dossier_type == DossierType.HOSPITALISE:
            # Optionnel transfert vers un autre lit
            if random.random() < 0.3:
                new_loc = _pick_lit(i + 17)
                m_tx = Mouvement(
                    mouvement_seq=get_next_sequence(session, "mouvement"),
                    venue_id=venue.id,
                    type="ADT^A02",
                    trigger_event="A02",
                    when=datetime.utcnow(),
                    from_location=venue.assigned_location,
                    to_location=new_loc,
                    movement_type="transfer",
                )
                session.add(m_tx)
                created_mouvements += 1
                venue.assigned_location = new_loc
            # Discharge
            if random.random() < 0.9:  # la majorité sont sortis
                m_dis = Mouvement(
                    mouvement_seq=get_next_sequence(session, "mouvement"),
                    venue_id=venue.id,
                    type="ADT^A03",
                    trigger_event="A03",
                    when=datetime.utcnow(),
                    from_location=venue.assigned_location,
                    movement_type="discharge",
                )
                session.add(m_dis)
                created_mouvements += 1
        elif dossier_type == DossierType.URGENCE:
            # Sortie rapide
            m_dis = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                type="ADT^A03",
                trigger_event="A03",
                when=datetime.utcnow(),
                from_location=venue.assigned_location,
                movement_type="discharge",
            )
            session.add(m_dis)
            created_mouvements += 1
        else:
            # EXTERNE : pas de mouvement supplémentaire
            pass

    session.commit()
    return {
        "patients_created": created_patients,
        "dossiers_created": created_dossiers,
        "venues_created": created_venues,
        "mouvements_created": created_mouvements,
        "total_after": existing_count + created_patients,
    }


# -- internal helpers ---------------------------------------------------------

def _ensure_entite_juridique(
    session: Session,
    context: GHTContext,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> EntiteJuridique:
    """Crée ou met à jour l'entité juridique (EJ) identifiée par finess_ej.
    
    L'EJ représente l'établissement au niveau juridique (FINESS EJ, SIREN, SIRET).
    Rattachée au GHTContext pour isolement multi-tenant.
    
    Args:
        session: Session DB
        context: GHTContext auquel rattacher l'EJ
        data: Dictionnaire de configuration (name, finess_ej, siren, siret, address...)
        stats: Compteurs created/updated
    
    Returns:
        Instance EntiteJuridique créée ou mise à jour
    """
    ej = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.finess_ej == data["finess_ej"])
    ).first()

    values = {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "finess_ej": data["finess_ej"],
        "siren": data.get("siren"),
        "siret": data.get("siret"),
        "address_line": data.get("address_line"),
        "postal_code": data.get("postal_code"),
        "city": data.get("city"),
        "country": data.get("country", "FR"),
        "is_active": data.get("is_active", True),
    }

    if ej is None:
        ej = EntiteJuridique(ght_context_id=context.id, **values)
        session.add(ej)
        session.flush()
        stats["created"]["entite_juridique"] += 1
    else:
        for field, value in values.items():
            setattr(ej, field, value)
        ej.ght_context_id = context.id
        ej.updated_at = datetime.utcnow()
        stats["updated"]["entite_juridique"] += 1

    return ej


def _ensure_entite_geographique(
    session: Session,
    entite_juridique: EntiteJuridique,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> EntiteGeographique:
    """Crée ou met à jour une entité géographique (EG / site) identifiée par identifier.
    
    L'EG représente un site hospitalier avec FINESS géographique, adresse, coordonnées GPS.
    Rattachée à une EntiteJuridique parente.
    
    Args:
        session: Session DB
        entite_juridique: EJ parente
        data: Dictionnaire de configuration (identifier, name, finess, address, latitude/longitude...)
        stats: Compteurs created/updated
    
    Returns:
        Instance EntiteGeographique créée ou mise à jour
    """
    identifier = data["identifier"]
    eg = session.exec(
        select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)
    ).first()

    values = {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "status": _enum_value(data.get("status", LocationStatus.ACTIVE)),
        "mode": _enum_value(data.get("mode", LocationMode.INSTANCE)),
        "physical_type": _enum_value(data.get("physical_type", LocationPhysicalType.SI)),
        "finess": data["finess"],
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2"),
        "address_line3": data.get("address_line3"),
        "address_postalcode": data.get("address_postalcode"),
        "address_city": data.get("address_city"),
        "address_country": data.get("address_country", "FR"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "type": data.get("type"),
        "category_code": data.get("category_code"),
        "category_name": data.get("category_name"),
        "category_sae": data.get("category_sae"),
    }

    if eg is None:
        eg = EntiteGeographique(
            identifier=identifier,
            entite_juridique_id=entite_juridique.id,
            **values,
        )
        session.add(eg)
        session.flush()
        stats["created"]["entite_geographique"] += 1
    else:
        for field, value in values.items():
            setattr(eg, field, value)
        eg.entite_juridique_id = entite_juridique.id
        eg.updated_at = datetime.utcnow()
        stats["updated"]["entite_geographique"] += 1

    return eg


def _ensure_pole(
    session: Session,
    entite_geo: EntiteGeographique,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Pole:
    """Crée ou met à jour un pôle identifié par identifier.
    
    Le Pôle regroupe plusieurs services sous une entité géographique.
    physicalType par défaut : 'area'.
    
    Args:
        session: Session DB
        entite_geo: EG parente
        data: Dictionnaire de configuration (identifier, name, short_name, description...)
        stats: Compteurs created/updated
    
    Returns:
        Instance Pole créée ou mise à jour
    """
    identifier = data["identifier"]
    pole = session.exec(select(Pole).where(Pole.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.AREA,
    )

    if pole is None:
        pole = Pole(identifier=identifier, entite_geo_id=entite_geo.id, **values)
        session.add(pole)
        session.flush()
        stats["created"]["pole"] += 1
    else:
        for field, value in values.items():
            setattr(pole, field, value)
        pole.entite_geo_id = entite_geo.id
        stats["updated"]["pole"] += 1

    return pole


def _ensure_service(
    session: Session,
    pole: Pole,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Service:
    """Crée ou met à jour un service identifié par identifier.
    
    Le Service représente une unité de soins avec service_type (MCO, SSR, PSY...),
    typologie, et optionnellement un responsable (RPPS, ADELI, spécialité).
    physicalType par défaut : 'bu' (building).
    
    Args:
        session: Session DB
        pole: Pole parent
        data: Dictionnaire de configuration (identifier, name, service_type, typology, responsible_*)
        stats: Compteurs created/updated
    
    Returns:
        Instance Service créée ou mise à jour
    """
    identifier = data["identifier"]
    service = session.exec(select(Service).where(Service.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.BU,
    )
    values.update(
        {
            "service_type": data.get("service_type", LocationServiceType.MCO),
            "typology": data.get("typology"),
            "responsible_id": data.get("responsible_id"),
            "responsible_name": data.get("responsible_name"),
            "responsible_firstname": data.get("responsible_firstname"),
            "responsible_rpps": data.get("responsible_rpps"),
            "responsible_adeli": data.get("responsible_adeli"),
            "responsible_specialty": data.get("responsible_specialty"),
        }
    )

    if service is None:
        service = Service(identifier=identifier, pole_id=pole.id, **values)
        session.add(service)
        session.flush()
        stats["created"]["service"] += 1
    else:
        for field, value in values.items():
            setattr(service, field, value)
        service.pole_id = pole.id
        stats["updated"]["service"] += 1

    return service


def _ensure_unite_fonctionnelle(
    session: Session,
    service: Service,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> UniteFonctionnelle:
    """Crée ou met à jour une unité fonctionnelle (UF) identifiée par identifier.
    
    L'UF représente une unité de production de soins avec um_code (code UM), 
    uf_type (hospitalisation, consultations, urgences...).
    Supporte les activités multiples via uf_activities (relation N-N avec UFActivity).
    physicalType par défaut : 'fl' (floor).
    
    Args:
        session: Session DB
        service: Service parent
        data: Dictionnaire de configuration (identifier, name, um_code, uf_type, uf_activities list)
        stats: Compteurs created/updated
    
    Returns:
        Instance UniteFonctionnelle créée ou mise à jour
    """
    identifier = data["identifier"]
    uf = session.exec(
        select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.FL,
    )
    values.update(
        {
            "um_code": data.get("um_code"),
            "uf_type": data.get("uf_type"),
        }
    )

    if uf is None:
        uf = UniteFonctionnelle(identifier=identifier, service_id=service.id, **values)
        session.add(uf)
        session.flush()
        stats["created"]["unite_fonctionnelle"] += 1
    else:
        for field, value in values.items():
            setattr(uf, field, value)
        uf.service_id = service.id
        stats["updated"]["unite_fonctionnelle"] += 1

    # Synchroniser les activités UF (multi-valué)
    _sync_uf_activities(session, uf, data, stats)

    return uf


def _ensure_unite_hebergement(
    session: Session,
    uf: UniteFonctionnelle,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> UniteHebergement:
    """Crée ou met à jour une unité d'hébergement (UH) identifiée par identifier.
    
    L'UH regroupe des chambres sur un étage/aile spécifique.
    physicalType par défaut : 'wi' (wing).
    
    Args:
        session: Session DB
        uf: UniteFonctionnelle parente
        data: Dictionnaire de configuration (identifier, name, etage, aile)
        stats: Compteurs created/updated
    
    Returns:
        Instance UniteHebergement créée ou mise à jour
    """
    identifier = data["identifier"]
    uh = session.exec(
        select(UniteHebergement).where(UniteHebergement.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.WI,
    )
    values.update(
        {
            "etage": data.get("etage"),
            "aile": data.get("aile"),
        }
    )

    if uh is None:
        uh = UniteHebergement(
            identifier=identifier,
            unite_fonctionnelle_id=uf.id,
            **values,
        )
        session.add(uh)
        session.flush()
        stats["created"]["unite_hebergement"] += 1
    else:
        for field, value in values.items():
            setattr(uh, field, value)
        uh.unite_fonctionnelle_id = uf.id
        stats["updated"]["unite_hebergement"] += 1

    return uh


def _ensure_chambre(
    session: Session,
    uh: UniteHebergement,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Chambre:
    """Crée ou met à jour une chambre identifiée par identifier.
    
    La chambre contient un ou plusieurs lits avec type_chambre (simple, double, box...).
    physicalType par défaut : 'ro' (room).
    
    Args:
        session: Session DB
        uh: UniteHebergement parente
        data: Dictionnaire de configuration (identifier, name, type_chambre, gender_usage)
        stats: Compteurs created/updated
    
    Returns:
        Instance Chambre créée ou mise à jour
    """
    identifier = data["identifier"]
    chambre = session.exec(
        select(Chambre).where(Chambre.identifier == identifier)
    ).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.RO,
    )
    values.update(
        {
            "type_chambre": data.get("type_chambre"),
            "gender_usage": data.get("gender_usage"),
        }
    )

    if chambre is None:
        chambre = Chambre(
            identifier=identifier,
            unite_hebergement_id=uh.id,
            **values,
        )
        session.add(chambre)
        session.flush()
        stats["created"]["chambre"] += 1
    else:
        for field, value in values.items():
            setattr(chambre, field, value)
        chambre.unite_hebergement_id = uh.id
        stats["updated"]["chambre"] += 1

    return chambre


def _ensure_lit(
    session: Session,
    chambre: Chambre,
    data: Dict[str, Any],
    stats: Dict[str, Counter],
) -> Lit:
    """Crée ou met à jour un lit identifié par identifier.
    
    Le lit est l'unité atomique d'hébergement avec operational_status (available, occupied, maintenance...).
    physicalType par défaut : 'bd' (bed).
    
    Args:
        session: Session DB
        chambre: Chambre parente
        data: Dictionnaire de configuration (identifier, name, operational_status)
        stats: Compteurs created/updated
    
    Returns:
        Instance Lit créée ou mise à jour
    """
    identifier = data["identifier"]
    lit = session.exec(select(Lit).where(Lit.identifier == identifier)).first()

    values = _base_location_values(
        data,
        default_physical_type=LocationPhysicalType.BD,
    )
    values.update(
        {
            "operational_status": data.get("operational_status"),
        }
    )

    if lit is None:
        lit = Lit(identifier=identifier, chambre_id=chambre.id, **values)
        session.add(lit)
        session.flush()
        stats["created"]["lit"] += 1
    else:
        for field, value in values.items():
            setattr(lit, field, value)
        lit.chambre_id = chambre.id
        stats["updated"]["lit"] += 1

    return lit


def _base_location_values(
    data: Dict[str, Any],
    *,
    default_physical_type: LocationPhysicalType,
) -> Dict[str, Any]:
    """Extrait les champs communs BaseLocation depuis un dictionnaire de configuration.
    
    Applique les valeurs par défaut pour status (ACTIVE), mode (INSTANCE), physical_type (paramétré).
    Utilisé par toutes les fonctions _ensure_* pour normaliser les valeurs avant insertion/update.
    
    Args:
        data: Dictionnaire de configuration (name, short_name, description, status, mode, physical_type, address_*)
        default_physical_type: Valeur par défaut pour physical_type si absente
    
    Returns:
        Dictionnaire de valeurs pour BaseLocation (name, status, mode, physical_type, address_*)
    """
    return {
        "name": data["name"],
        "short_name": data.get("short_name"),
        "description": data.get("description"),
        "status": data.get("status", LocationStatus.ACTIVE),
        "mode": data.get("mode", LocationMode.INSTANCE),
        "physical_type": data.get("physical_type", default_physical_type),
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2"),
        "address_line3": data.get("address_line3"),
        "address_city": data.get("address_city"),
        "address_postalcode": data.get("address_postalcode"),
        "address_country": data.get("address_country"),
        "opening_date": data.get("opening_date"),
        "activation_date": data.get("activation_date"),
        "closing_date": data.get("closing_date"),
        "deactivation_date": data.get("deactivation_date"),
    }


def _ensure_uf_activity(session: Session, code: str) -> UFActivity:
    """Crée ou récupère une UFActivity identifiée par code.
    
    Les UFActivity sont des codes métier (ex: 'urgences', 'consultations', 'hospitalisation')
    utilisés pour décrire les activités d'une unité fonctionnelle (relation N-N).
    
    Args:
        session: Session DB
        code: Code d'activité (normalisé en minuscules)
    
    Returns:
        Instance UFActivity créée ou existante
    
    Raises:
        ValueError: si code est vide
    """
    code = (code or "").strip().lower()
    if not code:
        raise ValueError("UF activity code must be non-empty")
    act = session.exec(select(UFActivity).where(UFActivity.code == code)).first()
    if act is None:
        act = UFActivity(code=code, display=code.title(), system="http://interop-sante.fr/fhir/CodeSystem/fr-uf-type")
        session.add(act)
        session.flush()
    return act


def _sync_uf_activities(session: Session, uf: UniteFonctionnelle, data: Dict[str, Any], stats: Dict[str, Counter]) -> None:
    """Synchronise la liste d'activités (relation N-N) d'une UniteFonctionnelle.
    
    Ajoute les activités manquantes, supprime les obsolètes.
    Source de codes : data["uf_activities"] (liste) ou data["uf_type"] (fallback unique).
    
    Args:
        session: Session DB
        uf: UniteFonctionnelle à synchroniser
        data: Dictionnaire de configuration (uf_activities ou uf_type)
        stats: Compteurs (non utilisé ici mais passé pour cohérence)
    """
    # Détermination des codes depuis la structure fournie
    codes: List[str] = []
    if isinstance(data.get("uf_activities"), list) and data["uf_activities"]:
        codes = [str(x) for x in data["uf_activities"] if x]
    elif data.get("uf_type"):
        codes = [str(data["uf_type"])]

    if not codes:
        return

    # Créer/obtenir les UFActivity puis synchroniser la relation
    activities = [_ensure_uf_activity(session, c) for c in codes]

    # Charger l'entité fraîche pour la relation (si nécessaire)
    session.refresh(uf)
    current_ids = {a.id for a in getattr(uf, "activities", []) if a and a.id}
    desired_ids = {a.id for a in activities if a and a.id}

    # Ajouter les manquantes
    to_add = [a for a in activities if a.id not in current_ids]
    if to_add:
        for a in to_add:
            uf.activities.append(a)
        stats["created"]["uf_activity_link"] += len(to_add)

    # Retirer les obsolètes (ne pas forcer si on ne veut que enrichir)
    to_remove = [a for a in getattr(uf, "activities", []) if a.id not in desired_ids]
    for a in to_remove:
        uf.activities.remove(a)
        stats["updated"]["uf_activity_link_removed"] += 1

    session.add(uf)
    session.flush()
