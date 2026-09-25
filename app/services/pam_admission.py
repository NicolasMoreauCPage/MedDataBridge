"""Cas d'usage d'admission et de mise à jour administrative PAM."""
from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime, timezone
import logging

from sqlmodel import Session, select

from app.models import Dossier, Patient, Venue, Mouvement
from app.db import get_next_sequence
from app.services.identifier_manager import (
    create_identifier_from_hl7,
    create_identifiers_from_hl7_with_namespace_check,
    parse_hl7_cx_identifier,
)
from app.models.identifiers import Identifier, IdentifierType
from app.services.vocabulary_translate import map_code
from app.services.medecin_extractor import extract_and_store_medecin_from_pv1
from app.services.pam_correlations import (
    _identifier_tuple_for_classifier,
    validate_movement_timing,
)
from app.services.pam_extensions import (
    _apply_french_extension_segments_to_patient,
    _apply_zfv_to_mouvement,
)
from app.services.pam_intake import _extract_pv1_segment, _parse_zbe_segment
from app.services.pam_constants import MOVEMENT_KIND_BY_TRIGGER, MOVEMENT_STATUS_BY_TRIGGER
from app.services.pam_cancellations import _handle_cancel_admission

logger = logging.getLogger(__name__)

async def handle_admission_message(
    session: Session,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str] = None,
    ej_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """Traitement des messages d'admission et d'annulation.

    - Pour les admissions normales (A01, A04, A05, A06, A07): crée Patient/Dossier/Venue/Mouvement
    - Pour les messages d'identité (A28, A31): mise à jour patient SANS mouvement
    - Pour les annulations (A11, A23, A38): parse ZBE-1 pour trouver le mouvement à annuler

    Args:
        session: Session DB
        trigger: Code trigger (A01, A04, A11, A28, A31, etc.)
        pid_data: Données PID parsées
        pv1_data: Données PV1 parsées
        message: Message HL7 complet (requis pour parser ZBE segment sur messages de mouvements)

    Returns:
        Tuple[bool, Optional[str]]: (succès, message d'erreur)
    """
    try:
        # Parser le segment ZBE (présent uniquement dans les messages de MOUVEMENTS)
        # Les messages d'identité (A28, A31, A40, A47) n'ont PAS de segment ZBE
        zbe_data = None
        if message and trigger not in ["A28", "A31", "A40", "A47"]:
            zbe_data = _parse_zbe_segment(message)
            if zbe_data:
                logger.info(f"[pam][admission] ZBE parsed: {zbe_data}")

        # Extraire les identifiants supplémentaires pour classification EJ
        account_number = pid_data.get("account_number")
        visit_number = pv1_data.get("visit_number")
        movement_id = zbe_data.get("movement_id") if zbe_data else None

        logger.info(f"[pam][admission] Variables: account_number={account_number}, visit_number={visit_number}, movement_id={movement_id}, trigger={trigger}")
        logger.debug(f"[pam][admission] PID data keys: {list(pid_data.keys())}")
        if trigger in ["A11", "A23", "A38"]:
            return await _handle_cancel_admission(session, trigger, pid_data, pv1_data, message, ej_id)

        # Gestion normale des admissions
        # Identifier patient (prendre le premier identifiant PID-3)
        logger.info("[pam][admission] Entering patient identification block")

        # --- PATCH: Robust PID-3 parsing and identifier assignment ---
        # Build robust identifier list from PID-3
        identifiers_raw = pid_data.get("identifiers", [])
        identifiers = []
        for cx_value, *_ in identifiers_raw:
            value, system, oid, type_code = parse_hl7_cx_identifier(cx_value)
            # Passer (value, system, type_code) pour classification, pas cx_value complet
            # Mais garder cx_value pour fallback
            identifiers.append((value, system, type_code, cx_value))

        # Main patient identifier (Solution de repli logic)
        identifier = None
        if identifiers:
            # Prefer classified main identifier, Solution de repli to first PID-3 value
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                try:
                    _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                    if isinstance(_res, (list, tuple)) and len(_res) == 3:
                        identifiers_list, main_id_value, external_id_value = _res
                    elif isinstance(_res, list):
                        identifiers_list, main_id_value, _external_id_value = _res, None, None
                    elif isinstance(_res, dict):
                        identifiers_list = _res.get('identifiers', [])
                        main_id_value = _res.get('main_identifier') or _res.get('main')
                        _external_id_value = _res.get('external_id') or _res.get('external')
                    else:
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                except Exception as _e:
                    logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                    identifiers_list, main_id_value, _external_id_value = [], None, None
                identifier = main_id_value or (identifiers[0][0] if identifiers else None)  # identifiers[0][0] = value
            except Exception as e:
                logger.warning(f"[pam] Failed to classify identifiers: {e}")
                identifier = identifiers[0][0] if identifiers else None  # identifiers[0][0] = value
        logger.debug(f"[pam][admission] Resolved identifier={identifier} (identifiers_count={len(identifiers)})")

        # Nom / prénom

        # Create or update patient
        reused_patient = None
        if identifier:
            # use global select
            from app.services.patient_update_helper import update_patient_from_pid_data
            existing = session.exec(select(Patient).where(Patient.identifier == identifier)).first()
            if existing:
                update_patient_from_pid_data(existing, pid_data, session, create_mode=False)
                session.add(existing)
                session.flush()
                # Persist all PID-3 identifiers with namespace classification
                try:
                    from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                    try:
                        _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                        if isinstance(_res, (list, tuple)) and len(_res) == 3:
                            identifiers_list, main_id_value, _external_id_value = _res
                        elif isinstance(_res, list):
                            identifiers_list, main_id_value, _external_id_value = _res, None, None
                        elif isinstance(_res, dict):
                            identifiers_list = _res.get('identifiers', [])
                            main_id_value = _res.get('main_identifier') or _res.get('main')
                            _external_id_value = _res.get('external_id') or _res.get('external')
                        else:
                            identifiers_list, main_id_value, _external_id_value = [], None, None
                    except Exception as _e:
                        logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                    for ident in identifiers_list:
                        ident.patient_id = existing.id
                        exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists_dup:
                            session.add(ident)
                except Exception as e:
                    logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                    # Solution de repli to legacy method
                    for value, system, type_code, raw_cx in identifiers:
                        try:
                            ident = create_identifier_from_hl7(raw_cx, "patient", existing.id)
                            exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                            if not exists_dup:
                                session.add(ident)
                        except Exception:
                            continue
                reused_patient = existing
                _apply_french_extension_segments_to_patient(existing, message)
                session.add(existing)
                if trigger in ("A28", "A31"):
                    # Identity-only update: no new dossier/venue/mouvement. Renvoie early.
                    logger.info(f"[pam][admission] Identity-only update detected for existing patient, trigger={trigger}")
                    return True, None

        # Debug: inspect identifier resolution and reuse
        logger.debug(f"[pam][admission] identifiers={identifiers!r}")
        logger.debug(f"[pam][admission] identifier={identifier!r}, reused_patient={reused_patient!r}")

        # If patient already updated and trigger is identity, Renvoie early
        if reused_patient:
            patient = reused_patient
            logger.debug(f"[pam][admission] Using reused_patient id={getattr(patient,'id', None)}")
        else:
            from app.services.patient_update_helper import create_patient_from_pid_data
            patient = create_patient_from_pid_data(pid_data, session, identifier, ej_id)
            session.add(patient)
            session.flush()
            logger.debug(f"[pam][admission] Created patient id={getattr(patient,'id', None)}")

            # Persist all identifiers from PID-3 with namespace classification
            try:
                from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
                try:
                    _res = create_identifiers_from_hl7_with_namespace_check(identifiers, "patient", session, ej_id)
                    if isinstance(_res, (list, tuple)) and len(_res) == 3:
                        identifiers_list, main_id_value, _external_id_value = _res
                    elif isinstance(_res, list):
                        identifiers_list, main_id_value, _external_id_value = _res, None, None
                    elif isinstance(_res, dict):
                        identifiers_list = _res.get('identifiers', [])
                        main_id_value = _res.get('main_identifier') or _res.get('main')
                        _external_id_value = _res.get('external_id') or _res.get('external')
                    else:
                        identifiers_list, main_id_value, _external_id_value = [], None, None
                except Exception as _e:
                    logger.warning(f"[pam] Failed to classify identifiers (soft): {_e}")
                    identifiers_list, main_id_value, _external_id_value = [], None, None
                for ident in identifiers_list:
                    ident.patient_id = patient.id
                    exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                    if not exists:
                        session.add(ident)
            except Exception as e:
                logger.warning(f"[pam] Failed to create identifiers with namespace check: {e}")
                # Solution de repli to legacy method
                for value, system, type_code, raw_cx in identifiers:
                    try:
                        ident = create_identifier_from_hl7(raw_cx, "patient", patient.id)
                        exists = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                        if not exists:
                            session.add(ident)
                    except Exception:
                        continue

            _apply_french_extension_segments_to_patient(patient, message)
            session.add(patient)

            # For identity-only messages, do not create dossier/venue/mouvement
            if trigger in ("A28", "A31"):
                logger.debug(f"[pam][admission] Early return for identity-only trigger after create/update, trigger={trigger}, patient_id={getattr(patient,'id', None)}")
                return True, None

        return await _create_admission_stay(
            session,
            trigger=trigger,
            pid_data=pid_data,
            pv1_data=pv1_data,
            message=message,
            ej_id=ej_id,
            zbe_data=zbe_data,
            account_number=account_number,
            visit_number=visit_number,
            movement_id=movement_id,
            patient=patient,
        )
    except Exception as e:
        logger.error(f"[pam][admission] Exception during admission handler: {e}", exc_info=True)
        logger.debug(f"[pam][admission] handler returning: success=False, err={e!r}")
        return False, str(e)

async def _create_admission_stay(
    session: Session,
    *,
    trigger: str,
    pid_data: dict,
    pv1_data: dict,
    message: Optional[str],
    ej_id: Optional[int],
    zbe_data: dict | None,
    account_number: str | None,
    visit_number: str | None,
    movement_id: str | None,
    patient: Patient,
) -> Tuple[bool, Optional[str]]:
    """Crée ou confirme le séjour, la venue et le mouvement d'admission."""
    # Créer un dossier et une venue
    # Utiliser l'identifiant dossier fourni dans PID-18 si disponible, sinon générer une séquence
    d_seq = None
    if account_number:
        try:
            # Extraire le numéro de dossier du format HL7 CX (peut contenir namespace)
            cx_parts = account_number.split("^")
            d_seq = int(cx_parts[0])
            logger.info(f"[pam][admission] Using provided dossier sequence: {d_seq} from PID-18")
        except (ValueError, IndexError) as e:
            logger.warning(f"[pam][admission] Invalid dossier sequence in PID-18 '{account_number}': {e}")

    if d_seq is None:
        d_seq = get_next_sequence(session, "dossier")
        logger.info(f"[pam][admission] Generated new dossier sequence: {d_seq}")
    # Date clinique du séjour : PV1-44, puis ZBE-2. Les données PID (date
    # de naissance) ne constituent jamais une date d'admission valide et ne
    # sont conservées qu'en dernier recours de compatibilité pour les anciens
    # flux sans aucune date de mouvement.
    admit_time = pv1_data.get("admit_time")
    if not admit_time and zbe_data and zbe_data.get("movement_datetime"):
        try:
            admit_time = datetime.strptime(zbe_data["movement_datetime"], "%Y%m%d%H%M%S")
        except (TypeError, ValueError):
            admit_time = None
    if not admit_time and pid_data.get("birth_date_dt"):
        admit_time = pid_data.get("birth_date_dt")
    elif not admit_time and pid_data.get("birth_date"):
        try:
            admit_time = datetime.strptime(pid_data.get("birth_date"), "%Y%m%d")
        except Exception:
            admit_time = None
    if not admit_time:
        admit_time = datetime.now(timezone.utc)

    # Map PV1-2 patient_class (HL7v2) -> internal encounter-class (FHIR ActCode) via vocabulary mapping
    hl7_patient_class = pv1_data.get("patient_class") or "I"
    encounter_class_code = map_code(session, "patient-class", hl7_patient_class, "encounter-class") or (
        {"I": "IMP", "O": "AMB", "E": "EMER"}.get(hl7_patient_class, "IMP")
    )
    # Vérifier si le dossier_seq existe déjà
    existing_dossier = session.exec(select(Dossier).where(Dossier.dossier_seq == d_seq)).first()
    if existing_dossier:
        # IHE PAM France: workflow A05 → A01 (hospitalisation) ou A05 → A04
        # (urgences/consultation externe) — spec IHE PAM France (CP-2013-078,
        # §8.5.7.3) : la confirmation d'une pré-admission (A05) se fait par A01
        # pour une hospitalisation, par A04 pour un passage aux urgences ou une
        # consultation externe. A05 crée le dossier en état "planned" ; le trigger
        # de confirmation réutilise le même numéro de dossier (PID-18).
        if trigger in ("A01", "A04") and existing_dossier.patient_id == patient.id:
            # Workflow normal: confirmation d'admission après pré-admission (A05)
            logger.info(f"[pam][admission] {trigger} confirming pre-admission for dossier_seq={d_seq}")
            dossier = existing_dossier
            # Mettre à jour la date d'admission si nécessaire
            if admit_time:
                dossier.admit_time = admit_time
        else:
            logger.error(f"[pam][admission] Doublon dossier_seq détecté: {d_seq}. Import annulé.")
            raise Exception(f"Un dossier avec le numéro {d_seq} existe déjà. Import ADT/PAM annulé.")
    else:
        # Extract médecin responsable from PV1-7 for the dossier
        medecin = None
        if message:
            pv1_segment = _extract_pv1_segment(message)
            if pv1_segment:
                medecin = extract_and_store_medecin_from_pv1(pv1_segment, session, commit=False)
                if medecin:
                    logger.info(f"[pam][admission] Médecin responsable extrait pour dossier: {medecin}")

        dossier = Dossier(
            dossier_seq=d_seq,
            patient_id=patient.id,
            uf_responsabilite=pv1_data.get("hospital_service") or "UNKNOWN",
            admit_time=admit_time,
            encounter_class=encounter_class_code,
            medecin_responsable_id=medecin.id if medecin else None,
            entite_juridique_id=ej_id,
        )
        session.add(dossier)
        session.flush()
    logger.info(
        "PAM dossier prepared id=%s dossier_seq=%s patient_id=%s",
        dossier.id,
        dossier.dossier_seq,
        dossier.patient_id,
    )

    # If PID-18 (account number) was provided, persist it as a Dossier identifier
    acc_raw = pid_data.get("account_number")
    if acc_raw:
        try:
            ident = create_identifier_from_hl7(acc_raw, "dossier", dossier.id)
        except (TypeError, ValueError):
            # Un PID-18 mal formé n'empêche pas l'admission, mais il doit
            # être visible pour corriger l'émetteur.
            logger.warning("Invalid PID-18 dossier identifier value=%r", acc_raw, exc_info=True)
        else:
            # PID-18 est un compte administratif (AN/NDA), jamais un IPP.
            if ident.type == IdentifierType.IPP:
                ident.type = IdentifierType.NDA
            exists = session.exec(
                select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)
            ).first()
            if not exists:
                session.add(ident)
                session.flush()

    v_seq = get_next_sequence(session, "venue")

    # Utiliser l'identifiant venue fourni dans PV1-19 si disponible
    if visit_number:
        try:
            # Extraire le numéro de venue du format HL7 CX (peut contenir namespace)
            cx_parts = visit_number.split("^")
            v_seq = int(cx_parts[0])
            logger.info(f"[pam][admission] Using provided venue sequence: {v_seq} from PV1-19")
        except (ValueError, IndexError) as e:
            logger.warning(f"[pam][admission] Invalid venue sequence in PV1-19 '{visit_number}': {e}")
            v_seq = get_next_sequence(session, "venue")

    # Vérifier si une venue existe déjà pour ce dossier (workflow IHE PAM A05→A01)
    existing_venue = session.exec(
        select(Venue).where(Venue.dossier_id == dossier.id, Venue.venue_seq == v_seq)
    ).first()

    location_raw = (pv1_data.get("location") or "").strip()
    location_value = location_raw or None
    previous_location = (pv1_data.get("previous_location") or "").strip() or None
    hospital_service = (pv1_data.get("hospital_service") or "").strip() or None
    movement_code = f"ADT^{trigger}"
    movement_kind = MOVEMENT_KIND_BY_TRIGGER.get(trigger, "admission")
    movement_status = MOVEMENT_STATUS_BY_TRIGGER.get(trigger, "completed")

    if existing_venue and trigger in ("A01", "A04"):
        # IHE PAM: A01/A04 confirme une pré-admission (A05)
        # Mettre à jour la localisation de la venue existante si fournie
        logger.info(f"[pam][admission] {trigger} confirming pre-admission for existing venue {existing_venue.id}")
        if location_value:
            existing_venue.assigned_location = location_value
        venue = existing_venue
        logger.info(
            "PAM venue updated id=%s venue_seq=%s trigger=%s",
            venue.id,
            venue.venue_seq,
            trigger,
        )
    else:
        venue = Venue(
            venue_seq=v_seq,
            dossier_id=dossier.id,
            uf_responsabilite=hospital_service or pv1_data.get("hospital_service") or dossier.uf_responsabilite,
            start_time=admit_time,
            assigned_location=location_value,
            entite_juridique_id=ej_id,
        )
        session.add(venue)
        session.flush()
        logger.info(
            "PAM venue prepared id=%s venue_seq=%s dossier_id=%s",
            venue.id,
            venue.venue_seq,
            venue.dossier_id,
        )

    # If PV1-19 (visit number) was provided, persist it as a Venue identifier
    visit_raw = pv1_data.get("visit_number")
    if visit_raw:
        try:
            ident = create_identifier_from_hl7(visit_raw, "venue", venue.id)
        except (TypeError, ValueError):
            logger.warning("Invalid PV1-19 venue identifier value=%r", visit_raw, exc_info=True)
        else:
            # PV1-19 est un numéro de venue (VN), jamais un IPP.
            if ident.type == IdentifierType.IPP:
                ident.type = IdentifierType.VN
            exists = session.exec(
                select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)
            ).first()
            if not exists:
                session.add(ident)
                session.flush()

    # Déterminer la date du mouvement : priorité ZBE-2, puis PV1, puis now
    movement_datetime = datetime.now(timezone.utc)
    if zbe_data and zbe_data.get("movement_datetime"):
        try:
            # Parse HL7 timestamp: YYYYMMDDHHmmss
            dt_str = zbe_data["movement_datetime"]
            movement_datetime = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
        except Exception as e:
            logger.warning(f"[pam][admission] Failed to parse ZBE-2 datetime '{dt_str}': {e}")
    elif pv1_data.get("admit_time"):
        movement_datetime = pv1_data["admit_time"]

    # Déterminer les UF selon ZBE et PV1
    # - UF hébergement : PV1-3-1 (location)
    # - UF médicale : ZBE-7-10

    # - UF soins : ZBE-8-10
    uf_resp = dossier.uf_responsabilite
    uf_code_from_zbe = None

    # UF médicale depuis ZBE-7
    if zbe_data and zbe_data.get("uf_medicale"):
        uf_code_from_zbe = zbe_data["uf_medicale"]
        uf_resp = uf_code_from_zbe

        # Vérifier que l'UF existe dans la structure associée à l'EJ
        # Récupérer l'EJ depuis le patient (via un identifiant de type système)
        try:
            # use global select
            from app.models_structure import UniteFonctionnelle

            # Chercher l'UF dans la structure
            uf_found = session.exec(
                select(UniteFonctionnelle)
                .where(UniteFonctionnelle.identifier == uf_code_from_zbe)
            ).first()

            if not uf_found:
                # Option d'auto-création contrôlée par variable d'environnement
                import os
                if os.getenv("PAM_AUTO_CREATE_UF", "0") in ("1", "true", "True"):
                    try:
                        from app.models_structure import (
                            UniteFonctionnelle, LocationPhysicalType
                        )
                        from app.models_structure import EntiteGeographique
                        # use global select

                        # Récupérer/Créer une entité géographique (placeholder si absente)
                        eg = session.exec(select(EntiteGeographique)).first()
                        if not eg:
                            eg = EntiteGeographique(
                                identifier="AUTO_EG", name="Entité Géographique Auto",
                                finess="000000000"
                            )
                            session.add(eg)
                            session.flush()

                        # Récupérer/Créer un pôle virtuel
                        from app.models_structure import Pole as _PoleModel
                        pole = session.exec(select(_PoleModel).where(_PoleModel.identifier == "AUTO_POLE")).first()
                        if not pole:
                            pole = _PoleModel(
                                identifier="AUTO_POLE",
                                name="Pôle Auto",
                                physical_type=LocationPhysicalType.SI,
                                entite_geo_id=eg.id,
                                is_virtual=True,
                            )
                            session.add(pole)
                            session.flush()

                        # Récupérer/Créer un service virtuel
                        from app.models_structure import Service as _ServiceModel, LocationServiceType
                        service = session.exec(select(_ServiceModel).where(_ServiceModel.identifier == "AUTO_SERVICE")).first()
                        if not service:
                            service = _ServiceModel(
                                identifier="AUTO_SERVICE",
                                name="Service Auto",
                                physical_type=LocationPhysicalType.SI,
                                service_type=LocationServiceType.MCO,
                                pole_id=pole.id,
                                is_virtual=True,
                            )
                            session.add(service)
                            session.flush()

                        # Créer l'UF minimale
                        uf_found = UniteFonctionnelle(
                            identifier=uf_code_from_zbe,
                            name=f"UF {uf_code_from_zbe}",
                            physical_type=LocationPhysicalType.SI,
                            service_id=service.id,
                            is_virtual=True,
                        )
                        session.add(uf_found)
                        session.flush()
                        logger.warning(
                            f"[pam][admission] UF '{uf_code_from_zbe}' auto-créée (placeholder) sous service 'AUTO_SERVICE'"
                        )
                    except Exception as _auto_e:
                        error_msg = (
                            f"UF Responsable '{uf_code_from_zbe}' (ZBE-7) introuvable et échec auto-création: {_auto_e}"
                        )
                        logger.error(f"[pam][admission] {error_msg}", exc_info=True)
                        return False, error_msg
                else:
                    error_msg = (
                        f"UF Responsable '{uf_code_from_zbe}' (ZBE-7) introuvable dans la structure. "
                        f"Activer PAM_AUTO_CREATE_UF=1 pour auto-création placeholder ou importer via MFN^M05 avant."
                    )
                    logger.error(f"[pam][admission] {error_msg}")
                    return False, error_msg

            logger.info(f"[pam][admission] UF Responsable '{uf_code_from_zbe}' validée: {uf_found.name}")

        except Exception as e:
            logger.error(f"[pam][admission] Erreur validation UF: {e}", exc_info=True)
            return False, f"Erreur validation UF Responsable: {str(e)}"

    # Mettre à jour l'UF responsabilité du dossier et de la venue
    dossier.uf_responsabilite = uf_resp
    venue.uf_responsabilite = uf_resp
    session.add(dossier)
    session.add(venue)

    m_seq = get_next_sequence(session, "mouvement")

    # Utiliser l'identifiant mouvement fourni dans ZBE-1 si disponible
    #
    # NOTE (architecture, confirmée intentionnelle) : comme pour dossier_seq (PID-18,
    # voir d_seq plus haut) et venue_seq (PV1-19, voir v_seq plus haut), quand l'émetteur
    # fournit son propre identifiant métier pour l'entité (ici le mouvement via ZBE-1),
    # on l'adopte directement comme notre mouvement_seq interne plutôt que de garder deux
    # numérotations totalement indépendantes. Ce choix reste sûr car ZBE-1 est de toute
    # façon aussi persisté séparément dans la table Identifier (type=MVT, voir plus bas
    # "Mouvement identifiers (ZBE-1...)") : la corrélation pour les messages UPDATE/CANCEL
    # ultérieurs (_find_mouvement_by_movement_id) consulte d'abord cette table Identifier
    # avant de retomber sur un parse direct de mouvement_seq, donc une éventuelle collision
    # entre la numérotation ZBE-1 d'un émetteur externe et notre propre séquence auto-générée
    # (get_next_sequence) resterait résolvable sans ambiguïté via l'Identifier associé.
    if movement_id:
        try:
            # Extraire le numéro de mouvement du format HL7 CX (peut contenir namespace)
            cx_parts = movement_id.split("^")
            m_seq = int(cx_parts[0])
            logger.info(f"[pam][admission] Using provided mouvement sequence: {m_seq} from ZBE-1")
        except (ValueError, IndexError) as e:
            logger.warning(f"[pam][admission] Invalid mouvement sequence in ZBE-1 '{movement_id}': {e}")
            m_seq = get_next_sequence(session, "mouvement")

    # Valider l'écart temporel avec le dernier mouvement
    try:
        validate_movement_timing(session, venue.id, movement_datetime)
    except ValueError as e:
        return False, str(e)

    # Extract médecin responsable from PV1-7
    medecin = None
    if message:
        pv1_segment = _extract_pv1_segment(message)
        if pv1_segment:
            medecin = extract_and_store_medecin_from_pv1(pv1_segment, session, commit=False)
            if medecin:
                logger.info(f"[pam][admission] Médecin responsable extrait: {medecin}")

    # Inject UF codes from ZBE if available (ZBE-7 / ZBE-8)
    uf_medicale_code = zbe_data.get("uf_medicale") if zbe_data else None
    uf_soins_code = zbe_data.get("uf_soins") if zbe_data else None
    mouvement = Mouvement(
        mouvement_seq=m_seq,
        venue_id=venue.id,
        type=movement_code,
        when=movement_datetime,
        status=movement_status,
        movement_type=movement_kind,
        trigger_event=trigger,  # Pour validation des transitions IHE PAM
        from_location=previous_location,
        to_location=location_value,
        location=location_value,  # PV1-3: Localisation actuelle
        uf_medicale_code=uf_medicale_code,
        uf_medicale_label=uf_medicale_code,
        uf_soins_code=uf_soins_code,
        uf_soins_label=uf_soins_code,
        medecin_responsable_id=medecin.id if medecin else None,
        entite_juridique_id=ej_id,
    )
    _apply_zfv_to_mouvement(mouvement, message)
    session.add(mouvement)
    session.flush()
    logger.info(
        f"[pam] Created mouvement mouv_seq={mouvement.mouvement_seq} venue_id={mouvement.venue_id} "
        f"movement_type={mouvement.movement_type} when={mouvement.when} "
        f"location={mouvement.location} uf_responsable={uf_resp}"
    )

    # Traiter les identifiants supplémentaires avec classification EJ.
    # create_identifiers_from_hl7_with_namespace_check() ne fait que classifier/construire
    # les objets Identifier : c'est à l'appelant de leur assigner l'entité (FK) et de les
    # ajouter à la session (même contrat que pour les identifiants patient plus haut).
    # Dossier identifiers (PID-18)
    if account_number:
        dossier_identifiers = _identifier_tuple_for_classifier(account_number)
        if dossier_identifiers:
            _res = await create_identifiers_from_hl7_with_namespace_check(
                session, [dossier_identifiers], dossier, "dossier"
            )
            for ident in (_res[0] if _res else []):
                ident.dossier_id = dossier.id
                exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                if not exists_dup:
                    session.add(ident)

    # Venue identifiers (PV1-19)
    if visit_number:
        venue_identifiers = _identifier_tuple_for_classifier(visit_number)
        if venue_identifiers:
            _res = await create_identifiers_from_hl7_with_namespace_check(
                session, [venue_identifiers], venue, "venue"
            )
            for ident in (_res[0] if _res else []):
                ident.venue_id = venue.id
                exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                if not exists_dup:
                    session.add(ident)

    # Mouvement identifiers (ZBE-1, répétable : plusieurs systèmes peuvent porter chacun
    # leur propre identifiant pour le même mouvement physique - "cooperative Movement
    # Management" - on les enregistre tous, pas seulement le premier).
    movement_ids = (zbe_data.get("movement_ids") or ([movement_id] if movement_id else [])) if zbe_data else []
    if movement_ids:
        all_mouvement_identifiers = [
            _identifier_tuple_for_classifier(mid) for mid in movement_ids if mid
        ]
        if all_mouvement_identifiers:
            _res = await create_identifiers_from_hl7_with_namespace_check(
                session, all_mouvement_identifiers, mouvement, "mouvement"
            )
            for ident in (_res[0] if _res else []):
                ident.mouvement_id = mouvement.id
                exists_dup = session.exec(select(Identifier).where(Identifier.system == ident.system, Identifier.value == ident.value)).first()
                if not exists_dup:
                    session.add(ident)

    # REMARQUE: Message emission is now automatic via entity_events.py listeners
    logger.debug("[pam][admission] handler returning: success=True, err=None")
    return True, None
