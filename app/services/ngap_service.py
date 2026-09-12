"""
Service de gestion de la Nomenclature Générale des Actes Professionnels (NGAP).
"""
from typing import Optional, List, Dict, Any
import math
import re
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime
from app.models import NGAPAct


class NGAPActCreate(BaseModel):
    dossier_id: Optional[int] = None
    lettre_cle: str
    coefficient: float
    denombrement: Optional[int] = 1
    execute_date: Optional[datetime] = None
    identifiant_acte: Optional[str] = None
    prestataire_id: Optional[int] = None
    position_dentaire: Optional[str] = None
    execute_heure: Optional[str] = None
    numero_seance: Optional[int] = None
    montant: Optional[float] = None
    commentaire: Optional[str] = None


class NGAPActResponse(BaseModel):
    id: Optional[int] = None
    dossier_id: Optional[int] = None
    lettre_cle: str = ""
    coefficient: float = 0.0
    denombrement: Optional[int] = 1
    execute_date: Optional[datetime] = None
    identifiant_acte: Optional[str] = None
    prestataire_id: Optional[int] = None
    position_dentaire: Optional[str] = None
    numero_seance: Optional[int] = None
    montant: Optional[float] = None
    commentaire: Optional[str] = None
    valide: bool = False
    facture: bool = False


class NGAPService:
    """Service des actes NGAP locaux.

    Le projet ne livre pas le référentiel national NGAP : ce service ne doit
    donc jamais prétendre qu'un code inventé existe. La recherche porte sur les
    actes enregistrés localement et la validation de code est seulement
    syntaxique ; la validation réglementaire demeure celle du référentiel
    partenaire importé par l'établissement.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def search_acte(self, code: str) -> Optional[Dict[str, Any]]:
        """Recherche une lettre-clé parmi les actes déjà enregistrés.

        Aucun tarif ni libellé fictif n'est fabriqué lorsqu'aucun référentiel
        NGAP n'est installé.
        """
        normalized = self._normalize_code(code)
        if not normalized:
            return None
        row = self.session.execute(
            select(NGAPAct).where(NGAPAct.lettre_cle == normalized).order_by(NGAPAct.id)
        ).scalars().first()
        if row is None:
            return None
        return {
            "code": normalized,
            "source": "actes_locaux",
            "last_act_id": row.id,
            "last_coefficient": row.coefficient,
        }
    
    def get_actes(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Liste paginée des actes NGAP locaux, sans faux référentiel."""
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        rows = self.session.execute(
            select(NGAPAct).order_by(NGAPAct.id).offset(safe_offset).limit(safe_limit)
        ).scalars().all()
        return [self._as_dict(row) for row in rows]

    @staticmethod
    def _normalize_code(code: str | None) -> str:
        return (code or "").strip().upper()

    @classmethod
    def validate_code(cls, code: str | None) -> bool:
        """Valide uniquement la forme d'une lettre-clé NGAP locale."""
        return bool(re.fullmatch(r"[A-Z]{1,10}", cls._normalize_code(code)))

    @staticmethod
    def _as_dict(row: NGAPAct) -> Dict[str, Any]:
        facture = row.facture
        facture_bool = (
            facture
            if isinstance(facture, bool)
            else str(facture or "").lower() not in {"", "0", "false", "no", "non"}
        )
        return {
            "id": row.id,
            "dossier_id": row.dossier_id,
            "lettre_cle": row.lettre_cle,
            "coefficient": row.coefficient,
            "denombrement": row.denombrement,
            "execute_date": row.execute_date,
            "identifiant_acte": row.identifiant_acte,
            "prestataire_id": row.prestataire_id,
            "position_dentaire": row.position_dentaire,
            "numero_seance": row.numero_seance,
            "montant": row.montant_total,
            "commentaire": row.commentaire,
            "valide": row.valide,
            "facture": facture_bool,
        }

    @classmethod
    def _validate_create(cls, act: NGAPActCreate) -> tuple[str, int]:
        code = cls._normalize_code(act.lettre_cle)
        if not cls.validate_code(code):
            raise ValueError("Lettre-clé NGAP invalide (1 à 10 lettres A-Z)")
        if act.dossier_id is None:
            raise ValueError("Un dossier est requis")
        if act.coefficient is None or not math.isfinite(act.coefficient) or act.coefficient <= 0:
            raise ValueError("Coefficient NGAP invalide")
        denombrement = act.denombrement if act.denombrement is not None else 1
        if not isinstance(denombrement, int) or denombrement <= 0:
            raise ValueError("Dénombrement NGAP invalide")
        return code, denombrement

    # Minimal CRUD-like methods expected by API layer/tests
    def create_act(self, act: NGAPActCreate) -> NGAPActResponse:
        code, denombrement = self._validate_create(act)

        ngap = NGAPAct(
            dossier_id=getattr(act, "dossier_id", None),
            lettre_cle=code,
            coefficient=act.coefficient,
            denombrement=denombrement,
            execute_date=act.execute_date or datetime.now(),
            identifiant_acte=act.identifiant_acte,
            prestataire_id=getattr(act, "prestataire_id", None),
            position_dentaire=getattr(act, "position_dentaire", None),
            numero_seance=getattr(act, "numero_seance", None),
            montant_total=getattr(act, "montant", None),
            commentaire=getattr(act, "commentaire", None),
            valide=False,
            facture="non",
        )
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)

        return NGAPActResponse(**self._as_dict(ngap))

    def get_acts_by_dossier(self, dossier_id: int) -> List[NGAPActResponse]:
        stmt = select(NGAPAct).where(NGAPAct.dossier_id == dossier_id).order_by(NGAPAct.id)
        result = self.session.execute(stmt)
        rows = result.scalars().all()
        return [NGAPActResponse(**self._as_dict(r)) for r in rows]

    def update_act(self, act_id: int, act: NGAPActCreate) -> NGAPActResponse:
        ngap = self.session.get(NGAPAct, act_id)
        if not ngap:
            raise ValueError("Act not found")
        code, denombrement = self._validate_create(act)
        ngap.lettre_cle = code
        ngap.coefficient = act.coefficient
        ngap.denombrement = denombrement
        ngap.execute_date = act.execute_date or ngap.execute_date
        ngap.identifiant_acte = act.identifiant_acte
        ngap.prestataire_id = act.prestataire_id
        ngap.position_dentaire = act.position_dentaire
        ngap.numero_seance = act.numero_seance
        ngap.montant_total = act.montant
        ngap.commentaire = act.commentaire
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)
        return NGAPActResponse(**self._as_dict(ngap))

    def delete_act(self, act_id: int) -> None:
        ngap = self.session.get(NGAPAct, act_id)
        if not ngap:
            raise ValueError("Act not found")
        self.session.delete(ngap)
        self.session.commit()

    def validate_act(self, act_id: int) -> NGAPActResponse:
        ngap = self.session.get(NGAPAct, act_id)
        if not ngap:
            raise ValueError("Act not found")
        ngap.valide = True
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)
        return NGAPActResponse(**self._as_dict(ngap))
