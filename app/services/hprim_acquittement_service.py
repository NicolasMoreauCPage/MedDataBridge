"""
Service for handling HPRIM acquittements (acknowledgments)
Processes msgAcquittementsServeurActes2_4 messages
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models import Acquittement, AcquittementReponse


class HprimAcquittementService:
    """Service pour gérer les acquittements HPRIM"""

    def __init__(self, session: Session):
        self.session = session

    async def process_acquittement(
        self,
        acquittement_data: Dict[str, Any]
    ) -> Optional[Acquittement]:
        """
        Traite et persiste un message d'acquittement reçu du serveur

        Args:
            acquittement_data: Données brutes du message d'acquittement

        Returns:
            L'acquittement persisté
        """
        try:
            statut = acquittement_data.get('statut', 'ERREUR')
            message_id_original = acquittement_data.get('message_id_original', '')

            acquittement = Acquittement(
                statut=statut,
                message_id_original=message_id_original,
                date_acquittement=datetime.now(),
                erreurs="\n".join(str(e) for e in acquittement_data.get('erreurs', [])) or None,
                avertissements="\n".join(str(a) for a in acquittement_data.get('avertissements', [])) or None,
            )
            self.session.add(acquittement)
            self.session.commit()
            self.session.refresh(acquittement)

            for resp in acquittement_data.get('reponses_actes', []):
                self._add_reponse(acquittement.id, resp, resp.get('type_acte', 'CCAM'))
            for resp in acquittement_data.get('reponses_interventions', []):
                self._add_reponse(acquittement.id, resp, 'INTERVENTION', identifiant_key='identifiant_intervention', code_key='code_intervention')

            self.session.commit()
            self.session.refresh(acquittement)
            return acquittement
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Erreur lors du traitement de l'acquittement: {str(e)}")

    def _add_reponse(
        self,
        acquittement_id: int,
        resp: Dict[str, Any],
        type_acte: str,
        identifiant_key: str = 'identifiant_acte',
        code_key: str = 'code',
    ) -> None:
        reponse = AcquittementReponse(
            acquittement_id=acquittement_id,
            identifiant_acte=resp.get(identifiant_key, ''),
            type_acte=type_acte,
            code=resp.get(code_key, ''),
            statut=resp.get('statut', 'OK'),
            code_erreur=resp.get('codeErreur'),
            message_erreur=resp.get('messageErreur'),
        )
        self.session.add(reponse)

    async def get_acquittement_by_message_id(self, message_id: str) -> Optional[Acquittement]:
        """Récupère un acquittement par son ID de message original (le plus récent en cas de doublon)"""
        return self.session.exec(
            select(Acquittement)
            .where(Acquittement.message_id_original == message_id)
            .order_by(Acquittement.date_acquittement.desc())
        ).first()

    async def get_acquittement_status_summary(self, message_id: str) -> Dict[str, Any]:
        """Retourne un résumé du statut des actes dans l'acquittement"""
        acquittement = await self.get_acquittement_by_message_id(message_id)
        if not acquittement:
            return {}

        reponses = self.session.exec(
            select(AcquittementReponse).where(AcquittementReponse.acquittement_id == acquittement.id)
        ).all()

        ok_count = sum(1 for r in reponses if r.statut == 'OK')
        erreur_count = sum(1 for r in reponses if r.statut == 'ERREUR')
        avertissement_count = sum(1 for r in reponses if r.statut == 'AVERTISSEMENT')

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
                    'code_erreur': r.code_erreur,
                    'message': r.message_erreur,
                }
                for r in reponses if r.statut == 'ERREUR'
            ]
        }

    async def list_recent_acquittements(self, limit: int = 50) -> List[Acquittement]:
        """Liste les acquittements les plus récents"""
        return self.session.exec(
            select(Acquittement).order_by(Acquittement.date_acquittement.desc()).limit(limit)
        ).all()
