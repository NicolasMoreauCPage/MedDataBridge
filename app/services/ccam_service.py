# app/services/ccam_service.py
"""
Service pour la gestion des actes CCAM avec validation HPRIM
"""

import re
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models import CCAMAct, Dossier
from app.models_practitioners import MedecinResponsable


class CCAMService:
    """Service pour la gestion des actes CCAM avec validation HPRIM"""

    @staticmethod
    def create_act(
        session: Session,
        dossier_id: int,
        code_acte: str,
        code_activite: str,
        execute_date: datetime,
        code_phase: Optional[str] = None,
        modificateurs: Optional[List[str]] = None,
        execute_heure: Optional[str] = None,
        quantite: int = 1,
        montant: Optional[float] = None,
        extension: Optional[str] = None,
        executant_id: Optional[int] = None,
        prescripteur_id: Optional[int] = None,
        commentaire: Optional[str] = None
    ) -> CCAMAct:
        """Créer un acte CCAM avec validation HPRIM"""

        # Validation HPRIM des champs obligatoires
        CCAMService._validate_hprim_required_fields(
            code_acte, code_activite, execute_date
        )

        # Validation des formats HPRIM
        CCAMService._validate_hprim_formats(
            code_acte, code_activite, code_phase, modificateurs, execute_heure, extension
        )

        # Validation métier
        CCAMService._validate_business_rules(
            session, dossier_id, execute_date
        )

        # Normalisation des données
        modificateurs_str = ",".join(modificateurs) if modificateurs else ""

        # Création de l'acte
        act = CCAMAct(
            dossier_id=dossier_id,
            code_acte=code_acte.upper(),
            code_activite=code_activite,
            code_phase=code_phase,
            modificateurs=modificateurs_str,
            execute_date=execute_date,
            execute_heure=execute_heure,
            quantite=quantite,
            montant=montant,
            extension=extension,
            executant_id=executant_id,
            prescripteur_id=prescripteur_id,
            commentaire=commentaire,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        session.add(act)
        session.commit()
        session.refresh(act)

        return act

    @staticmethod
    def get_acts_by_dossier(session: Session, dossier_id: int) -> List[CCAMAct]:
        """Récupérer les actes CCAM d'un dossier"""
        return session.query(CCAMAct).filter(
            CCAMAct.dossier_id == dossier_id
        ).order_by(CCAMAct.execute_date.desc()).all()

    @staticmethod
    def get_act_by_id(session: Session, act_id: int) -> Optional[CCAMAct]:
        """Récupérer un acte CCAM par son ID"""
        return session.query(CCAMAct).filter(CCAMAct.id == act_id).first()

    @staticmethod
    def update_act_validation(session: Session, act_id: int, valide: bool) -> CCAMAct:
        """Mettre à jour le statut de validation d'un acte"""
        act = session.query(CCAMAct).filter(CCAMAct.id == act_id).first()
        if not act:
            raise ValueError(f"Acte CCAM {act_id} non trouvé")

        act.valide = valide
        act.updated_at = datetime.utcnow()

        session.commit()
        session.refresh(act)

        return act

    @staticmethod
    def _validate_hprim_required_fields(code_acte: str, code_activite: str, execute_date: datetime):
        """Validation HPRIM des champs obligatoires"""
        if not code_acte or not code_acte.strip():
            raise ValueError("Le code acte CCAM est obligatoire (HPRIM)")

        if not code_activite or not code_activite.strip():
            raise ValueError("Le code activité est obligatoire (HPRIM)")

        if not execute_date:
            raise ValueError("La date d'exécution est obligatoire (HPRIM)")

        # Vérifier que la date n'est pas dans le futur
        if execute_date.date() > date.today():
            raise ValueError("La date d'exécution ne peut pas être dans le futur")

    @staticmethod
    def _validate_hprim_formats(
        code_acte: str,
        code_activite: str,
        code_phase: Optional[str],
        modificateurs: Optional[List[str]],
        execute_heure: Optional[str],
        extension: Optional[str]
    ):
        """Validation des formats HPRIM"""

        # Code acte: AAAA999 (4 lettres + 3 chiffres)
        if not re.match(r'^[A-Z]{4}\d{3}$', code_acte.upper()):
            raise ValueError("Format code acte CCAM invalide. Attendu: AAAA999 (4 lettres + 3 chiffres)")

        # Code activité: 2 chiffres
        if not re.match(r'^\d{2}$', code_activite):
            raise ValueError("Format code activité invalide. Attendu: 2 chiffres")

        # Code phase: optionnel, 2 chiffres si présent
        if code_phase and not re.match(r'^\d{2}$', code_phase):
            raise ValueError("Format code phase invalide. Attendu: 2 chiffres ou vide")

        # Modificateurs: codes alphanumériques A-Z, 0-9
        if modificateurs:
            for mod in modificateurs:
                if not re.match(r'^[A-Z0-9]$', mod.upper()):
                    raise ValueError(f"Modificateur invalide: {mod}. Attendu: A-Z ou 0-9")

        # Heure d'exécution: format HH:MM si présent
        if execute_heure and not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', execute_heure):
            raise ValueError("Format heure invalide. Attendu: HH:MM")

        # Extension: format spécifique si présent
        if extension and not re.match(r'^[A-Z0-9]{1,3}$', extension.upper()):
            raise ValueError("Format extension invalide. Attendu: 1-3 caractères alphanumériques")

    @staticmethod
    def _validate_business_rules(session: Session, dossier_id: int, execute_date: datetime):
        """Validation des règles métier"""
        # Vérifier que le dossier existe
        dossier = session.query(Dossier).filter(Dossier.id == dossier_id).first()
        if not dossier:
            raise ValueError(f"Dossier {dossier_id} non trouvé")

        # Vérifier que la date est cohérente avec les dates du dossier
        if dossier.date_entree and execute_date.date() < dossier.date_entree:
            raise ValueError("La date d'exécution ne peut pas être antérieure à la date d'entrée du dossier")

    @staticmethod
    def get_modificateurs_list(act: CCAMAct) -> List[str]:
        """Extraire la liste des modificateurs depuis la chaîne stockée"""
        if not act.modificateurs:
            return []
        return [mod.strip() for mod in act.modificateurs.split(",") if mod.strip()]

    @staticmethod
    def calculate_total_amount(act: CCAMAct) -> float:
        """Calculer le montant total de l'acte"""
        if act.montant is not None:
            return act.montant * act.quantite
        return 0.0

    @staticmethod
    def validate_ccam_code(session: Session, code_acte: str) -> bool:
        """Valider qu'un code CCAM existe (à implémenter avec référentiel CCAM)"""
        # TODO: Implémenter la validation contre le référentiel CCAM officiel
        # Pour l'instant, on valide seulement le format
        return bool(re.match(r'^[A-Z]{4}\d{3}$', code_acte.upper()))