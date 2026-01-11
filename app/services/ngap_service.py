"""
Service de gestion de la Nomenclature Générale des Actes Professionnels (NGAP).
"""
from typing import Optional, List, Dict, Any
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
    montant: Optional[float] = None
    commentaire: Optional[str] = None
    valide: bool = False
    facture: bool = False


class NGAPService:
    """Service pour gérer la nomenclature NGAP."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def search_acte(self, code: str) -> Optional[Dict[str, Any]]:
        """Recherche un acte NGAP par code."""
        # TODO: Implémenter la recherche dans la nomenclature NGAP
        return {
            "code": code,
            "libelle": f"Acte NGAP {code}",
            "tarif": 0.0
        }
    
    def get_actes(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Récupère la liste des actes NGAP."""
        # TODO: Implémenter la récupération depuis la base
        return []
    
    def validate_acte(self, code: str) -> bool:
        """Valide qu'un code NGAP existe."""
        # TODO: Implémenter la validation
        return True

    # Minimal CRUD-like methods expected by API layer/tests
    def create_act(self, act: NGAPActCreate) -> NGAPActResponse:
        # Basic validation expected by tests
        if not act.lettre_cle or not isinstance(act.lettre_cle, str) or not act.lettre_cle.isalpha():
            raise ValueError("Invalid lettre_cle")
        if act.coefficient is None or act.coefficient <= 0:
            raise ValueError("Invalid coefficient")

        ngap = NGAPAct(
            dossier_id=getattr(act, "dossier_id", None),
            lettre_cle=act.lettre_cle,
            coefficient=act.coefficient,
            denombrement=act.denombrement,
            execute_date=act.execute_date or datetime.now(),
            identifiant_acte=act.identifiant_acte,
            montant_total=getattr(act, "montant", None),
            commentaire=getattr(act, "commentaire", None),
            valide=False,
            facture="non",
        )
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)

        return NGAPActResponse(
            id=ngap.id,
            dossier_id=ngap.dossier_id,
            lettre_cle=ngap.lettre_cle,
            coefficient=ngap.coefficient,
            denombrement=ngap.denombrement,
            execute_date=ngap.execute_date,
            identifiant_acte=ngap.identifiant_acte,
            montant=ngap.montant_total,
            commentaire=ngap.commentaire,
            valide=ngap.valide,
            facture=False,
        )

    def get_acts_by_dossier(self, dossier_id: int) -> List[NGAPActResponse]:
        stmt = select(NGAPAct).where(NGAPAct.dossier_id == dossier_id).order_by(NGAPAct.id)
        result = self.session.execute(stmt)
        rows = result.scalars().all()
        def _facture_bool(val):
            if val is None:
                return False
            if isinstance(val, bool):
                return val
            # Treat string values like 'non' as False
            if isinstance(val, str):
                return val.lower() not in ("non", "no", "false", "0", "")
            return bool(val)

        return [NGAPActResponse(
            id=r.id,
            dossier_id=r.dossier_id,
            lettre_cle=r.lettre_cle,
            coefficient=r.coefficient,
            denombrement=r.denombrement,
            execute_date=r.execute_date,
            identifiant_acte=r.identifiant_acte,
            montant=r.montant_total,
            commentaire=r.commentaire,
            valide=r.valide,
            facture=_facture_bool(r.facture) if hasattr(r, 'facture') else False,
        ) for r in rows]

    def update_act(self, act_id: int, act: NGAPActCreate) -> NGAPActResponse:
        ngap = self.session.get(NGAPAct, act_id)
        if not ngap:
            raise ValueError("Act not found")
        ngap.lettre_cle = act.lettre_cle
        ngap.coefficient = act.coefficient
        ngap.denombrement = act.denombrement
        ngap.execute_date = act.execute_date or ngap.execute_date
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)
        return NGAPActResponse(id=ngap.id, lettre_cle=ngap.lettre_cle, coefficient=ngap.coefficient)

    def delete_act(self, act_id: int) -> None:
        ngap = self.session.get(NGAPAct, act_id)
        if ngap:
            self.session.delete(ngap)
            self.session.commit()
        return None

    def validate_act(self, act_id: int) -> NGAPActResponse:
        ngap = self.session.get(NGAPAct, act_id)
        if not ngap:
            raise ValueError("Act not found")
        ngap.valide = True
        self.session.add(ngap)
        self.session.commit()
        self.session.refresh(ngap)
        return NGAPActResponse(id=ngap.id, valide=ngap.valide, lettre_cle=ngap.lettre_cle, coefficient=ngap.coefficient)
