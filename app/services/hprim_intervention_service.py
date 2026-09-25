"""
Service for managing HPRIM interventions and their associated cotations
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select
from app.models import Dossier, Intervention, CCAMAct, NGAPAct, LPPAct, UCDAct
from app.protocols.hprim.models import HprimIntervention, HprimCotation


class HprimInterventionService:
    """Service pour gérer les interventions HPRIM et cotations"""

    def __init__(self, session: Session):
        self.session = session

    def get_dossier_cotations_count(self, dossier_id: int) -> int:
        """Récupère le nombre de cotations liées à un dossier"""
        dossier = self.session.get(Dossier, dossier_id)
        if not dossier:
            return 0

        count = 0
        count += len(dossier.ccam_acts) if dossier.ccam_acts else 0
        count += len(dossier.ngap_acts) if dossier.ngap_acts else 0
        count += len(dossier.lpp_acts) if dossier.lpp_acts else 0
        count += len(dossier.ucd_acts) if dossier.ucd_acts else 0
        return count

    def update_dossier_cotations_flags(self, dossier_id: int) -> bool:
        """Met à jour les flags has_cotations et cotations_count du dossier"""
        dossier = self.session.get(Dossier, dossier_id)
        if not dossier:
            return False

        count = self.get_dossier_cotations_count(dossier_id)
        dossier.has_cotations = count > 0
        dossier.cotations_count = count
        self.session.add(dossier)
        self.session.commit()
        return True

    def create_intervention(
        self,
        dossier_id: int,
        identifiant: str,
        libelle: str,
        date_intervention: datetime,
        venue_id: Optional[str] = None,
        lieu_execution: Optional[str] = None,
        statut: str = "en_cours",
    ) -> Intervention:
        """Crée et persiste une intervention à partir de champs simples (utilisé par l'API REST)."""
        try:
            intervention = Intervention(
                dossier_id=dossier_id,
                identifiant=identifiant,
                libelle=libelle,
                date_intervention=date_intervention,
                venue_id=venue_id,
                lieu_execution=lieu_execution,
                statut=statut,
            )
            self.session.add(intervention)
            self.session.commit()
            self.session.refresh(intervention)
            return intervention
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Erreur lors de la création de l'intervention: {str(e)}")

    def create_intervention_from_hprim(
        self, hprim_intervention: HprimIntervention, dossier_id: int
    ) -> Optional[Intervention]:
        """Crée et persiste une intervention à partir d'un modèle HPRIM déjà parsé (message XML entrant)."""
        return self.create_intervention(
            dossier_id=dossier_id,
            identifiant=hprim_intervention.identifiant,
            libelle=hprim_intervention.libelle,
            date_intervention=hprim_intervention.date_intervention,
            venue_id=hprim_intervention.venue_id,
            lieu_execution=hprim_intervention.lieu_execution,
            statut=hprim_intervention.statut,
        )

    def link_cotation_to_intervention(
        self, intervention_id: int, cotation: HprimCotation
    ) -> bool:
        """
        Lie une cotation à une intervention existante en rattachant les actes CCAM/NGAP/LPP/UCD
        déjà persistés (identifiés par `identifiant_acte` dans le dossier de l'intervention) à
        cette intervention via leur colonne `intervention_id`.

        Args:
            intervention_id: ID de l'intervention
            cotation: Cotation HPRIM (les actes y sont identifiés par leur identifiant_acte)

        Returns:
            True si l'intervention existe et qu'au moins un acte a été rattaché, False sinon
        """
        intervention = self.session.get(Intervention, intervention_id)
        if not intervention:
            return False

        linked = 0
        for acte_model, actes in (
            (
                CCAMAct,
                [cotation.actes_ccam]
                if not isinstance(cotation.actes_ccam, list)
                else cotation.actes_ccam,
            ),
            (
                NGAPAct,
                [cotation.actes_ngap]
                if not isinstance(cotation.actes_ngap, list)
                else cotation.actes_ngap,
            ),
            (LPPAct, [cotation.actes_lpp] if cotation.actes_lpp else []),
            (UCDAct, [cotation.actes_ucd] if cotation.actes_ucd else []),
        ):
            for acte in actes:
                if not acte or not getattr(acte, "identifiant", None):
                    continue
                row = self.session.exec(
                    select(acte_model).where(
                        acte_model.dossier_id == intervention.dossier_id,
                        acte_model.identifiant_acte == acte.identifiant,
                    )
                ).first()
                if row:
                    row.intervention_id = intervention_id
                    self.session.add(row)
                    linked += 1

        intervention.statut = cotation.statut or intervention.statut
        intervention.updated_at = datetime.now()
        self.session.add(intervention)
        self.session.commit()
        return linked > 0

    def get_interventions_for_dossier(self, dossier_id: int) -> List[Intervention]:
        """Récupère toutes les interventions d'un dossier"""
        return self.session.exec(
            select(Intervention)
            .where(Intervention.dossier_id == dossier_id)
            .order_by(Intervention.date_intervention.desc())
        ).all()

    def get_cotations_for_intervention(
        self, intervention_id: int
    ) -> List[HprimCotation]:
        """
        Récupère la cotation regroupant les actes CCAM/NGAP/LPP/UCD réellement rattachés
        (colonne `intervention_id`) à cette intervention.
        """
        intervention = self.session.get(Intervention, intervention_id)
        if not intervention:
            return []

        ccam_acts = self.session.exec(
            select(CCAMAct).where(CCAMAct.intervention_id == intervention_id)
        ).all()
        ngap_acts = self.session.exec(
            select(NGAPAct).where(NGAPAct.intervention_id == intervention_id)
        ).all()
        lpp_acts = self.session.exec(
            select(LPPAct).where(LPPAct.intervention_id == intervention_id)
        ).all()
        ucd_acts = self.session.exec(
            select(UCDAct).where(UCDAct.intervention_id == intervention_id)
        ).all()

        return [
            HprimCotation(
                cotation_id=f"intervention-{intervention_id}",
                intervention_id=str(intervention_id),
                actes_ccam=ccam_acts,
                actes_ngap=ngap_acts,
                actes_lpp=lpp_acts[0] if lpp_acts else None,
                actes_ucd=ucd_acts[0] if ucd_acts else None,
                date_creation=intervention.created_at,
                date_modification=intervention.updated_at,
                statut=intervention.statut,
            )
        ]
