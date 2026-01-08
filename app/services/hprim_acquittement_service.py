"""
Service for handling HPRIM acquittements (acknowledgments)
Processes msgAcquittementsServeurActes2_4 messages
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session
from app.hprim_models import HprimAcquittement, HprimReponse, HprimStatutReponse


class HprimAcquittementService:
    """Service pour gérer les acquittements HPRIM"""
    
    def __init__(self, session: Session):
        self.session = session
    
    async def process_acquittement(
        self,
        acquittement_data: Dict[str, Any]
    ) -> Optional[HprimAcquittement]:
        """
        Traite un message d'acquittement reçu du serveur
        
        Args:
            acquittement_data: Données brutes du message d'acquittement
            
        Returns:
            Objet HprimAcquittement analysé
        """
        try:
            # Extraire les données du message
            statut = acquittement_data.get('statut', 'ERREUR')
            message_id_original = acquittement_data.get('message_id_original', '')
            
            # Parser les réponses par acte
            reponses_actes = await self._parse_reponses_actes(
                acquittement_data.get('reponses_actes', [])
            )
            
            # Parser les réponses d'interventions
            reponses_interventions = await self._parse_reponses_interventions(
                acquittement_data.get('reponses_interventions', [])
            )
            
            # Créer l'objet acquittement
            acquittement = HprimAcquittement(
                statut=statut,
                message_id_original=message_id_original,
                date_acquittement=datetime.now(),
                erreurs=acquittement_data.get('erreurs', []),
                avertissements=acquittement_data.get('avertissements', []),
                reponses_actes=reponses_actes,
                reponses_interventions=reponses_interventions,
            )
            
            # TODO: persister l'acquittement dans la table hprim_acquittement
            return acquittement
            
        except Exception as e:
            raise Exception(f"Erreur lors du traitement de l'acquittement: {str(e)}")
    
    async def _parse_reponses_actes(self, reponses_data: List[Dict]) -> List[HprimReponse]:
        """Parse les réponses pour les actes (CCAM, NGAP, LPP, UCD)"""
        reponses = []
        for resp in reponses_data:
            try:
                reponse = HprimReponse(
                    identifiant_acte=resp.get('identifiant_acte', ''),
                    type_acte=resp.get('type_acte', 'CCAM'),
                    code=resp.get('code', ''),
                    statut=resp.get('statut', 'OK'),
                    codeErreur=resp.get('codeErreur'),
                    messageErreur=resp.get('messageErreur'),
                )
                reponses.append(reponse)
            except Exception as e:
                # Log l'erreur mais continue
                print(f"Erreur parsing réponse acte: {e}")
                continue
        return reponses
    
    async def _parse_reponses_interventions(
        self,
        reponses_data: List[Dict]
    ) -> List[HprimReponse]:
        """Parse les réponses pour les interventions"""
        reponses = []
        for resp in reponses_data:
            try:
                reponse = HprimReponse(
                    identifiant_acte=resp.get('identifiant_intervention', ''),
                    type_acte='INTERVENTION',
                    code=resp.get('code_intervention', ''),
                    statut=resp.get('statut', 'OK'),
                    codeErreur=resp.get('codeErreur'),
                    messageErreur=resp.get('messageErreur'),
                )
                reponses.append(reponse)
            except Exception as e:
                print(f"Erreur parsing réponse intervention: {e}")
                continue
        return reponses
    
    async def get_acquittement_by_message_id(self, message_id: str) -> Optional[HprimAcquittement]:
        """Récupère un acquittement par son ID de message original"""
        # TODO: implémenter la requête sur la table hprim_acquittement
        return None
    
    async def get_acquittement_status_summary(self, message_id: str) -> Dict[str, Any]:
        """Retourne un résumé du statut des actes dans l'acquittement"""
        acquittement = await self.get_acquittement_by_message_id(message_id)
        if not acquittement:
            return {}
        
        # Compter les statuts
        ok_count = sum(1 for r in acquittement.reponses_actes if r.statut == 'OK')
        erreur_count = sum(1 for r in acquittement.reponses_actes if r.statut == 'ERREUR')
        avertissement_count = sum(1 for r in acquittement.reponses_actes if r.statut == 'AVERTISSEMENT')
        
        return {
            'message_id': message_id,
            'statut_global': acquittement.statut,
            'date_acquittement': acquittement.date_acquittement.isoformat(),
            'reponses': {
                'ok': ok_count,
                'erreurs': erreur_count,
                'avertissements': avertissement_count,
            },
            'details_erreurs': [
                {
                    'acte_id': r.identifiant_acte,
                    'type': r.type_acte,
                    'code_erreur': r.codeErreur,
                    'message': r.messageErreur,
                }
                for r in acquittement.reponses_actes if r.statut == 'ERREUR'
            ]
        }
