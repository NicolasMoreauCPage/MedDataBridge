# app/services/contract_service.py
"""
Service pour la gestion des contrats médicaux avec validation HPRIM
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import Contract, Dossier
from app.models_practitioners import MedecinResponsable


class ContractService:
    """Service pour la gestion des contrats médicaux avec validation HPRIM"""

    @staticmethod
    def create_contract(
        session: Session,
        dossier_id: int,
        contract_type: str,
        status: str,
        date_debut: date,
        date_fin: Optional[date] = None,
        organisme_payeur: Optional[str] = None,
        numero_contrat: Optional[str] = None,
        taux_prise_en_charge: Optional[float] = None,
        plafond_annuel: Optional[float] = None,
        conditions_particulieres: Optional[str] = None,
        medecin_responsable_id: Optional[int] = None
    ) -> Contract:
        """Créer un nouveau contrat avec validation HPRIM"""

        # Validation HPRIM des champs obligatoires
        ContractService._validate_hprim_required_fields(
            contract_type, status, date_debut
        )

        # Validation métier
        ContractService._validate_business_rules(
            session, dossier_id, contract_type, date_debut, date_fin
        )

        # Validation des formats HPRIM
        ContractService._validate_hprim_formats(
            numero_contrat, taux_prise_en_charge, plafond_annuel
        )

        # Création du contrat
        contract = Contract(
            dossier_id=dossier_id,
            contract_type=contract_type,
            status=status,
            date_debut=date_debut,
            date_fin=date_fin,
            organisme_payeur=organisme_payeur,
            numero_contrat=numero_contrat,
            taux_prise_en_charge=taux_prise_en_charge,
            plafond_annuel=plafond_annuel,
            conditions_particulieres=conditions_particulieres,
            medecin_responsable_id=medecin_responsable_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        session.add(contract)
        session.commit()
        session.refresh(contract)

        return contract

    @staticmethod
    def get_contracts_for_dossier(session: Session, dossier_id: int) -> List[Contract]:
        """Récupérer tous les contrats d'un dossier"""
        return session.query(Contract).filter(
            Contract.dossier_id == dossier_id
        ).order_by(Contract.date_debut.desc()).all()

    @staticmethod
    def get_active_contracts_for_dossier(session: Session, dossier_id: int, contract_type: Optional[str] = None) -> List[Contract]:
        """Récupérer les contrats actifs d'un dossier"""
        query = session.query(Contract).filter(
            and_(
                Contract.dossier_id == dossier_id,
                Contract.status == 'actif',
                Contract.date_debut <= date.today(),
                or_(Contract.date_fin.is_(None), Contract.date_fin >= date.today())
            )
        )

        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)

        return query.order_by(Contract.date_debut.desc()).all()

    @staticmethod
    def update_contract_status(session: Session, contract_id: int, new_status: str) -> Contract:
        """Mettre à jour le statut d'un contrat"""
        if new_status not in ['actif', 'suspendu', 'termine']:
            raise ValueError(f"Statut invalide: {new_status}")

        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"Contrat {contract_id} non trouvé")

        contract.status = new_status
        contract.updated_at = datetime.utcnow()

        session.commit()
        session.refresh(contract)

        return contract

    @staticmethod
    def _validate_hprim_required_fields(contract_type: str, status: str, date_debut: date):
        """Validation HPRIM des champs obligatoires"""
        if not contract_type:
            raise ValueError("Le type de contrat est obligatoire (HPRIM)")

        if contract_type not in ['NGAP', 'UCD', 'LPP']:
            raise ValueError("Type de contrat invalide. Valeurs autorisées: NGAP, UCD, LPP")

        if not status:
            raise ValueError("Le statut du contrat est obligatoire (HPRIM)")

        if status not in ['actif', 'suspendu', 'termine']:
            raise ValueError("Statut invalide. Valeurs autorisées: actif, suspendu, termine")

        if not date_debut:
            raise ValueError("La date de début est obligatoire (HPRIM)")

        # Vérifier que la date de début n'est pas dans le futur
        if date_debut > date.today():
            raise ValueError("La date de début ne peut pas être dans le futur")

    @staticmethod
    def _validate_business_rules(session: Session, dossier_id: int, contract_type: str, date_debut: date, date_fin: Optional[date]):
        """Validation des règles métier"""
        # Vérifier que le dossier existe
        dossier = session.query(Dossier).filter(Dossier.id == dossier_id).first()
        if not dossier:
            raise ValueError(f"Dossier {dossier_id} non trouvé")

        # Vérifier les chevauchements de contrats actifs du même type
        overlapping_contracts = session.query(Contract).filter(
            and_(
                Contract.dossier_id == dossier_id,
                Contract.contract_type == contract_type,
                Contract.status == 'actif',
                Contract.date_debut <= (date_fin or date(2099, 12, 31)),
                or_(Contract.date_fin.is_(None), Contract.date_fin >= date_debut)
            )
        ).all()

        if overlapping_contracts:
            raise ValueError(
                f"Un contrat {contract_type} actif existe déjà pour cette période "
                f"(du {overlapping_contracts[0].date_debut} au {overlapping_contracts[0].date_fin or 'indéterminé'})"
            )

        # Validation des dates
        if date_fin and date_debut > date_fin:
            raise ValueError("La date de fin doit être postérieure à la date de début")

    @staticmethod
    def _validate_hprim_formats(
        numero_contrat: Optional[str],
        taux_prise_en_charge: Optional[float],
        plafond_annuel: Optional[float]
    ):
        """Validation des formats HPRIM"""
        if numero_contrat and len(numero_contrat.strip()) > 50:
            raise ValueError("Le numéro de contrat ne peut pas dépasser 50 caractères")

        if taux_prise_en_charge is not None:
            if taux_prise_en_charge < 0 or taux_prise_en_charge > 100:
                raise ValueError("Le taux de prise en charge doit être entre 0 et 100%")

        if plafond_annuel is not None and plafond_annuel < 0:
            raise ValueError("Le plafond annuel ne peut pas être négatif")

    @staticmethod
    def get_contract_coverage(session: Session, dossier_id: int, contract_type: str, act_date: date) -> Optional[Contract]:
        """Trouver le contrat applicable pour un acte à une date donnée"""
        return session.query(Contract).filter(
            and_(
                Contract.dossier_id == dossier_id,
                Contract.contract_type == contract_type,
                Contract.status == 'actif',
                Contract.date_debut <= act_date,
                or_(Contract.date_fin.is_(None), Contract.date_fin >= act_date)
            )
        ).order_by(Contract.date_debut.desc()).first()

    @staticmethod
    def calculate_reimbursement_amount(contract: Contract, act_amount: float) -> float:
        """Calculer le montant de remboursement selon le contrat"""
        if not contract.taux_prise_en_charge:
            return 0.0

        reimbursed_amount = act_amount * (contract.taux_prise_en_charge / 100)

        # Appliquer le plafond annuel si défini
        if contract.plafond_annuel:
            # Calculer le total déjà remboursé cette année
            # Cette logique serait plus complexe en production avec historique des remboursements
            # Pour l'instant, on applique simplement le plafond au montant calculé
            reimbursed_amount = min(reimbursed_amount, contract.plafond_annuel)

        return round(reimbursed_amount, 2)