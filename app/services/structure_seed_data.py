"""Jeux de données déclaratifs utilisés par le service de seed de structure."""
from __future__ import annotations

from typing import Any, Dict

from app.models_structure import (
    LocationMode,
    LocationPhysicalType,
    LocationServiceType,
    LocationStatus,
)
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

