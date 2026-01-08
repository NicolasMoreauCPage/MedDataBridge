"""
Service for managing HPRIM interventions and their associated cotations
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import Session, select
from app.models import Dossier, Patient
from app.hprim_models import HprimIntervention, HprimCotation, HprimTypeActe


class HprimInterventionService:
    """Service pour gérer les interventions HPRIM et cotations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    async def get_dossier_cotations_count(self, dossier_id: int) -> int:
        """Récupère le nombre de cotations liées à un dossier"""
        # TODO: implémenter quand la table hprim_intervention sera créée
        # Pour l'instant, compter les actes existants
        dossier = self.session.get(Dossier, dossier_id)
        if not dossier:
            return 0
        
        count = 0
        count += len(dossier.ccam_acts) if dossier.ccam_acts else 0
        count += len(dossier.ngap_acts) if dossier.ngap_acts else 0
        count += len(dossier.lpp_acts) if dossier.lpp_acts else 0
        count += len(dossier.ucd_acts) if dossier.ucd_acts else 0
        return count
    
    async def update_dossier_cotations_flags(self, dossier_id: int) -> bool:
        """Met à jour les flags has_cotations et cotations_count du dossier"""
        dossier = self.session.get(Dossier, dossier_id)
        if not dossier:
            return False
        
        count = await self.get_dossier_cotations_count(dossier_id)
        dossier.has_cotations = count > 0
        dossier.cotations_count = count
        self.session.add(dossier)
        self.session.commit()
        return True
    
    async def create_intervention_from_hprim(
        self,
        hprim_intervention: HprimIntervention,
        dossier_id: int
    ) -> Optional[dict]:
        """
        Crée une intervention à partir d'un modèle HPRIM
        
        Args:
            hprim_intervention: Intervention HPRIM
            dossier_id: ID du dossier associé
            
        Returns:
            Dictionnaire avec les détails de l'intervention créée
        """
        try:
            # TODO: créer la table hprim_intervention avec les champs
            # - id, dossier_id, identifiant, libelle, date_intervention
            # - medecin_id, venue_id, lieu_execution, statut
            # - date_creation, date_modification
            
            intervention_data = {
                'dossier_id': dossier_id,
                'identifiant': hprim_intervention.identifiant,
                'libelle': hprim_intervention.libelle,
                'date_intervention': hprim_intervention.date_intervention,
                'venue_id': hprim_intervention.venue_id,
                'lieu_execution': hprim_intervention.lieu_execution,
                'statut': hprim_intervention.statut,
                'date_creation': datetime.now(),
                'date_modification': datetime.now(),
            }
            
            # TODO: persister l'intervention
            return intervention_data
        except Exception as e:
            raise Exception(f"Erreur lors de la création de l'intervention: {str(e)}")
    
    async def link_cotation_to_intervention(
        self,
        intervention_id: str,
        cotation: HprimCotation
    ) -> bool:
        """
        Lie une cotation à une intervention
        
        Args:
            intervention_id: ID de l'intervention
            cotation: Cotation HPRIM
            
        Returns:
            True si succès, False sinon
        """
        try:
            # TODO: créer la table hprim_cotation_intervention
            # - id, intervention_id, cotation_id
            # - date_creation
            # - actes_ccam_ids, actes_ngap_ids, etc.
            pass
        except Exception as e:
            raise Exception(f"Erreur lors du lien cotation-intervention: {str(e)}")
    
    async def get_interventions_for_dossier(self, dossier_id: int) -> List[dict]:
        """Récupère toutes les interventions d'un dossier"""
        # TODO: implémenter quand la table hprim_intervention sera créée
        return []
    
    async def get_cotations_for_intervention(self, intervention_id: str) -> List[HprimCotation]:
        """Récupère toutes les cotations d'une intervention"""
        # TODO: implémenter quand les tables seront créées
        return []
