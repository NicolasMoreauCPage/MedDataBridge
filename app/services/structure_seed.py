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
    UniteFonctionnelle,
    Lit,
)
from app.models_structure import EntiteJuridique, GHTContext
from app.services.structure_seed_data import DEMO_STRUCTURE, EXTENDED_GHT_DATA
from app.services.structure_seed_persistence import (
    _ensure_chambre,
    _ensure_entite_geographique,
    _ensure_entite_juridique,
    _ensure_lit,
    _ensure_pole,
    _ensure_service,
    _ensure_unite_fonctionnelle,
    _ensure_unite_hebergement,
)









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
    from app.models.shared import SystemEndpoint, EndpointKind, EndpointRole  # local import
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
                   emit_hl7_pam=True,
                   emit_hl7_mfn=False,
                   emit_fhir_structure=False,
                   emit_fhir_identity=True,
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
                   emit_hl7_pam=True,
                   emit_hl7_mfn=False,
                   emit_fhir_structure=False,
                   emit_fhir_identity=True,
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
                role=EndpointRole.RECEIVER,  # FHIR receiver for FHIR structure/identity
                ght_context_id=context.id,
                base_url=f"https://fhir.demo/{finess_ej}",
                auth_kind="none",
                   emit_hl7_pam=False,
                   emit_hl7_mfn=False,
                   emit_fhir_structure=True,
                   emit_fhir_identity=True,
            )
            session.add(ep)
            stats["created"] += 1
        else:
            existing_fhir.updated_at = datetime.utcnow()
            stats["updated"] += 1

    session.commit()
    return {"endpoints": stats}


def ensure_namespaces_for_context(
    session: Session,
    context: GHTContext,
    ej_finess_list: List[str],
) -> Dict[str, Any]:
    """Crée ou met à jour les namespaces d'identifiants pour chaque EJ du contexte.
    
    Génère pour chaque EJ (FINESS) :
    - IPP (Identifiant Patient Permanent)
    - NDA (Numéro Dossier Administratif)
    - VENUE (Identifiant de Venue/Séjour)
    
    Plus un namespace global de structure pour le contexte GHT.
    
    Idempotent : recherche par name unique.
    """
    from app.models_structure import IdentifierNamespace
    stats = Counter()
    
    # OID racine du contexte (Solution de repli si absent)
    oid_base = context.oid_racine or "1.2.250.1.71.1.1"
    
    # Namespace global structure GHT
    struct_name = f"Structure {context.name}"
    existing_struct = session.exec(
        select(IdentifierNamespace).where(IdentifierNamespace.name == struct_name)
    ).first()
    if existing_struct is None:
        ns = IdentifierNamespace(
            name=struct_name,
            description=f"Identifiants structure pour contexte {context.name}",
            oid=f"{oid_base}.99",
            system=f"http://{context.code or 'ght'}.fr/ns/structure",
            type="STRUCTURE",
            ght_context_id=context.id,
        )
        session.add(ns)
        stats["created"] += 1
    else:
        existing_struct.updated_at = datetime.utcnow()
        stats["updated"] += 1
    
    # Namespaces par EJ
    for idx, finess_ej in enumerate(ej_finess_list, start=1):
        # Récupérer l'EJ pour l'associer
        ej = session.exec(
            select(EntiteJuridique).where(EntiteJuridique.finess_ej == finess_ej)
        ).first()
        ej_id = ej.id if ej else None
        
        types_ns = [
            ("IPP", "Identifiant Patient Permanent", "2", "ipp"),
            ("NDA", "Numéro Dossier Administratif", "3", "nda"),
            ("VENUE", "Identifiant de Venue", "4", "venue"),
        ]
        
        for ns_type, desc, oid_suffix, system_suffix in types_ns:
            ns_name = f"{ns_type} {finess_ej}"
            existing_ns = session.exec(
                select(IdentifierNamespace).where(IdentifierNamespace.name == ns_name)
            ).first()
            if existing_ns is None:
                ns = IdentifierNamespace(
                    name=ns_name,
                    description=f"{desc} pour EJ {finess_ej}",
                    oid=f"{oid_base}.{idx}.{oid_suffix}",
                    system=f"http://{finess_ej}.fr/ns/{system_suffix}",
                    type=ns_type,
                    ght_context_id=context.id,
                    entite_juridique_id=ej_id,
                )
                session.add(ns)
                stats["created"] += 1
            else:
                existing_ns.updated_at = datetime.utcnow()
                stats["updated"] += 1
    
    session.commit()
    return {"namespaces": stats}


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
    from app.models.vocabulary import VocabularySystem
    from sqlalchemy import func
    from sqlmodel import select

    # Fonction helper pour récupérer une valeur aléatoire depuis un vocabulaire
    def _get_random_vocab_value(system_name: str) -> str:
        """Récupère une valeur aléatoire depuis un système de vocabulaire."""
        system = session.exec(
            select(VocabularySystem).where(VocabularySystem.name == system_name)
        ).first()
        if system and system.values:
            return random.choice(system.values).code
        return None

    existing_count = session.exec(select(func.count()).select_from(Patient)).one()
    if existing_count >= target_patients:
        return {"skipped": existing_count, "target": target_patients}

    # Collecte lits disponibles pour assigner locations
    all_lits = session.exec(select(Lit)).all()
    lit_cycle = list(lit.identifier for lit in all_lits if lit.identifier)
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

    # Sélectionner toutes les EJ du contexte
    ej_list = session.exec(select(EntiteJuridique).where(EntiteJuridique.ght_context_id == context.id)).all()
    num_ej = len(ej_list)

    for i in range(to_create):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        birth_year = random.randint(1935, 2023)
        birth_date_str = f"{birth_year}-" + f"{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        from datetime import datetime
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        except Exception:
            birth_date = None

        # Répartition cyclique des patients sur les EJ
        ej = ej_list[i % num_ej] if num_ej > 0 else None
        ej_id = ej.id if ej else None

        # Générer un IPP comme identifiant externe
        from app.models_structure import IdentifierNamespace
        from app.models.identifiers import Identifier, IdentifierType
        # Sélectionner le namespace IPP principal pour cette EJ
        ipp_namespace = session.exec(select(IdentifierNamespace).where(IdentifierNamespace.type == "IPP").where(IdentifierNamespace.entite_juridique_id == ej_id)).first()
        ipp_value = None
        if ipp_namespace:
            from app.services.identifier_generator import generate_identifier
            ipp_value = generate_identifier(session, ipp_namespace, IdentifierType.IPP)

        patient = Patient(
            patient_seq=get_next_sequence(session, "patient"),
            family=ln,
            given=fn,
            birth_date=birth_date,
            gender=_get_random_vocab_value("administrative-gender"),
            postal_code=f"69{random.randint(100,999)}",
            city="Lyon",
            identity_reliability_code=_get_random_vocab_value("identity-reliability-rniv"),
            external_id=ipp_value,
            ght_context_id=context.id,
            entite_juridique_id=ej_id,  # Always assign EJ
        )
        session.add(patient)
        session.flush()  # ensure patient.id
        created_patients += 1

        # Create an Identifier if an IPP value/namespace exists (optional)
        if ipp_value and ipp_namespace:
            identifier = Identifier(
                value=ipp_value,
                type=IdentifierType.IPP,
                system=ipp_namespace.system,
                status="active",
                assigned_date=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                patient_id=patient.id,
            )
            session.add(identifier)

        # Decide dossier type and create dossier/venue/mouvements regardless
        r = random.random()
        if r < admit_ratio:
            dossier_type = DossierType.HOSPITALISE
        elif r < admit_ratio + urgence_ratio:
            dossier_type = DossierType.URGENCE
        else:
            dossier_type = DossierType.EXTERNE

        # Dates réalistes pour le séjour
        from datetime import timedelta
        admit_dt = datetime.utcnow() - timedelta(days=random.randint(1, 30), hours=random.randint(0, 12))
        discharge_dt = admit_dt + timedelta(days=random.randint(1, 10), hours=random.randint(1, 12))
        # Sélectionner une UF de responsabilité et une UF d'hébergement pour l'EJ
        ufs_resp = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id.is_not(None))).all()
        ufs_ej = [uf for uf in ufs_resp if getattr(uf.service, 'pole', None) and getattr(uf.service.pole, 'entite_geo', None) and getattr(uf.service.pole.entite_geo, 'entite_juridique_id', None) == ej_id]
        uf_resp = random.choice(ufs_ej) if ufs_ej else None
        uf_heberg = random.choice(ufs_ej) if ufs_ej else None
        dossier = Dossier(
            dossier_seq=get_next_sequence(session, "dossier"),
            patient_id=patient.id,
            admit_time=admit_dt,
            discharge_time=discharge_dt if dossier_type in [DossierType.HOSPITALISE, DossierType.URGENCE] else None,
            dossier_type=dossier_type,
            entite_juridique_id=ej_id,  # Always assign EJ
            uf_responsabilite=uf_resp.um_code if uf_resp else None,
            uf_hebergement=uf_heberg.um_code if uf_heberg else None,
        )
        session.add(dossier)
        session.flush()  # ensure IDs
        created_dossiers += 1

        # Venue & mouvements selon type
        venue_start = admit_dt + timedelta(hours=random.randint(0, 3))
        venue = Venue(
            venue_seq=get_next_sequence(session, "venue"),
            dossier_id=dossier.id,
            start_time=venue_start,
            assigned_location=_pick_lit(i),
            entite_juridique_id=ej_id,
        )
        session.add(venue)
        session.flush()
        created_venues += 1

        # Admission mouvement
        m_adm = Mouvement(
            mouvement_seq=get_next_sequence(session, "mouvement"),
            venue_id=venue.id,
            type=None,
            trigger_event="A01",
            when=venue_start,
            to_location=venue.assigned_location,
            movement_type="admission",
            entite_juridique_id=ej_id,
        )
        session.add(m_adm)
        created_mouvements += 1

        if dossier_type == DossierType.HOSPITALISE:
            # Optionnel transfert vers un autre lit
            if random.random() < 0.3:
                new_loc = _pick_lit(i + 17)
                transfer_dt = venue_start + timedelta(days=random.randint(0, 5), hours=random.randint(1, 8))
                m_tx = Mouvement(
                    mouvement_seq=get_next_sequence(session, "mouvement"),
                    venue_id=venue.id,
                    type=None,
                    trigger_event="A02",
                    when=transfer_dt,
                    from_location=venue.assigned_location,
                    to_location=new_loc,
                    movement_type="transfer",
                    entite_juridique_id=ej_id,
                )
                session.add(m_tx)
                created_mouvements += 1
                venue.assigned_location = new_loc
            # Discharge
            if random.random() < 0.9:  # la majorité sont sortis
                discharge_dt = discharge_dt
                m_dis = Mouvement(
                    mouvement_seq=get_next_sequence(session, "mouvement"),
                    venue_id=venue.id,
                    type=None,
                    trigger_event="A03",
                    when=discharge_dt,
                    from_location=venue.assigned_location,
                    movement_type="discharge",
                    entite_juridique_id=ej_id,
                )
                session.add(m_dis)
                created_mouvements += 1
        elif dossier_type == DossierType.URGENCE:
            # Sortie rapide
            m_dis = Mouvement(
                mouvement_seq=get_next_sequence(session, "mouvement"),
                venue_id=venue.id,
                type=None,
                trigger_event="A03",
                when=datetime.utcnow(),
                from_location=venue.assigned_location,
                movement_type="discharge",
                entite_juridique_id=ej_id,
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
