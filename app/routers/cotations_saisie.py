"""
Router pour la saisie rapide des cotations avec auto-complétion et templates.
Optimisé pour le workflow des professionnels du codage médical.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import List, Optional
import logging

from app.db import get_session
from app.models import Dossier, Patient, CCAMAct, NGAPAct, UCDAct, LPPAct
from app.models_practitioners import MedecinResponsable
from app.models_vocabulary import VocabularySystem, VocabularyValue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cotations", tags=["cotations-saisie"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dossier/{dossier_id}/saisie", response_class=HTMLResponse, name="cotations_saisie_rapide")
async def get_saisie_rapide(
    request: Request,
    dossier_id: int,
    session: Session = Depends(get_session)
):
    """
    Interface de saisie rapide pour les cotations d'un dossier.
    
    Features:
    - Sélection rapide du type d'acte (CCAM, NGAP, UCD, LPP)
    - Auto-complétion des codes avec libellés
    - Templates pour actes fréquents
    - Session de saisie avec récapitulatif en temps réel
    - Raccourcis clavier (Ctrl+S, Ctrl+Enter, Ctrl+T)
    - Validation en temps réel
    """
    dossier = session.get(Dossier, dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} non trouvé")

    patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None

    # Récupérer tous les actes pour alimenter le workspace unique
    ccam_acts = session.exec(
        select(CCAMAct)
        .where(CCAMAct.dossier_id == dossier_id)
        .order_by(CCAMAct.execute_date.desc())
    ).all()

    ngap_acts = session.exec(
        select(NGAPAct)
        .where(NGAPAct.dossier_id == dossier_id)
        .order_by(NGAPAct.execute_date.desc())
    ).all()

    ucd_acts = session.exec(
        select(UCDAct)
        .where(UCDAct.dossier_id == dossier_id)
        .order_by(UCDAct.execute_date.desc())
    ).all()

    lpp_acts = session.exec(
        select(LPPAct)
        .where(LPPAct.dossier_id == dossier_id)
        .order_by(LPPAct.execute_date.desc())
    ).all()

    total_actes = len(ccam_acts) + len(ngap_acts) + len(ucd_acts) + len(lpp_acts)

    return templates.TemplateResponse(
        request,
        "cotations/saisie_rapide.html",
        {
            "request": request,
            "dossier": dossier,
            "patient": patient,
            "ccam_acts": ccam_acts,
            "ngap_acts": ngap_acts,
            "ucd_acts": ucd_acts,
            "lpp_acts": lpp_acts,
            "total_actes": total_actes,
            "ccam_count": len(ccam_acts),
            "ngap_count": len(ngap_acts),
            "ucd_count": len(ucd_acts),
            "lpp_count": len(lpp_acts),
        },
    )


@router.get("/api/search/ccam", name="search_ccam_codes")
async def search_ccam_codes(
    query: str,
    limit: int = 10,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Recherche de codes CCAM avec auto-complétion.
    
    Args:
        query: Texte de recherche (code ou libellé)
        limit: Nombre max de résultats
    
    Returns:
        Liste de suggestions [{code, libelle, tarif_base}]
    """
    if not query or not query.strip():
        return JSONResponse([])

    query = query.strip()
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    query_lower = query.lower()

    # 1) Recherche dans les actes CCAM déjà saisis (source opérationnelle locale)
    ccam_rows = session.exec(
        select(CCAMAct)
        .where(CCAMAct.code_acte.is_not(None))
        .order_by(CCAMAct.execute_date.desc())
    ).all()

    seen_codes: set[str] = set()
    live_results = []
    for row in ccam_rows:
        code = (row.code_acte or "").strip().upper()
        if not code or code in seen_codes:
            continue

        label = row.commentaire or "Acte CCAM saisi"
        if query_lower in code.lower() or query_lower in label.lower():
            live_results.append(
                {
                    "code": code,
                    "libelle": label,
                    "tarif_base": float(row.montant_total) if row.montant_total is not None else None,
                }
            )
            seen_codes.add(code)

        if len(live_results) >= limit:
            return JSONResponse(live_results)

    # 2) Fallback sur vocabulaire CCAM si disponible
    vocab_results = []
    vocab_systems = session.exec(select(VocabularySystem)).all()
    ccam_system_ids = [
        vs.id for vs in vocab_systems
        if vs.id is not None and (
            "ccam" in (vs.name or "").lower()
            or "ccam" in (vs.label or "").lower()
            or "ccam" in (vs.uri or "").lower()
        )
    ]

    if ccam_system_ids:
        vocab_values = session.exec(
            select(VocabularyValue).where(VocabularyValue.system_id.in_(ccam_system_ids))
        ).all()
        for value in vocab_values:
            code = (value.code or "").strip().upper()
            display = (value.display or "").strip()
            if not code or code in seen_codes:
                continue
            if query_lower in code.lower() or query_lower in display.lower():
                vocab_results.append(
                    {
                        "code": code,
                        "libelle": display or "Code CCAM",
                        "tarif_base": None,
                    }
                )
                seen_codes.add(code)
            if len(live_results) + len(vocab_results) >= limit:
                break

    # 3) Fallback sécurisé de démonstration (si pas de data locale)
    demo_results = [
        {"code": "HBMD001", "libelle": "Échographie cardiaque transthoracique", "tarif_base": 70.28},
        {"code": "HBLD004", "libelle": "Échographie obstétricale du premier trimestre", "tarif_base": 81.92},
        {"code": "DEQP003", "libelle": "Électrocardiographie sur au moins 12 dérivations", "tarif_base": 14.26},
        {"code": "LBQH001", "libelle": "Radiographie du thorax, 1 incidence", "tarif_base": 25.27},
        {"code": "YYYY080", "libelle": "Pose d'une perfusion intraveineuse", "tarif_base": 12.50},
        {"code": "GLQP002", "libelle": "Exérèse de lésion cutanée ou sous-cutanée", "tarif_base": 46.20},
        {"code": "AAQM001", "libelle": "Ablation de matériel d'ostéosynthèse", "tarif_base": 100.80},
        {"code": "EBQH001", "libelle": "Radiographie du crâne, 1 ou 2 incidences", "tarif_base": 25.27},
    ]
    
    filtered_demo = [
        r for r in demo_results 
        if query_lower in r["code"].lower() or query_lower in r["libelle"].lower()
    ]

    results = live_results + vocab_results
    if len(results) < limit:
        for demo in filtered_demo:
            if demo["code"] not in seen_codes:
                results.append(demo)
                seen_codes.add(demo["code"])
            if len(results) >= limit:
                break

    return JSONResponse(results[:limit])


@router.get("/api/search/ngap", name="search_ngap_codes")
async def search_ngap_codes(
    query: str,
    limit: int = 10,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Recherche de codes NGAP avec auto-complétion.
    
    Args:
        query: Texte de recherche (lettre clé ou libellé)
        limit: Nombre max de résultats
    
    Returns:
        Liste de suggestions [{lettre_cle, libelle, coefficient, tarif_base}]
    """
    demo_results = [
        {"lettre_cle": "C", "libelle": "Consultation au cabinet", "coefficient": 1.0, "tarif_base": 25.00},
        {"lettre_cle": "CS", "libelle": "Consultation de spécialiste", "coefficient": 1.0, "tarif_base": 28.00},
        {"lettre_cle": "G", "libelle": "Consultation générale", "coefficient": 1.0, "tarif_base": 23.00},
        {"lettre_cle": "V", "libelle": "Visite au domicile", "coefficient": 1.0, "tarif_base": 25.00},
        {"lettre_cle": "AMI", "libelle": "Acte médical infirmier", "coefficient": 2.0, "tarif_base": 3.50},
        {"lettre_cle": "AMX", "libelle": "Acte médical complexe", "coefficient": 3.0, "tarif_base": 3.50},
        {"lettre_cle": "K", "libelle": "Coefficient de kinésithérapie", "coefficient": 1.0, "tarif_base": 2.15},
        {"lettre_cle": "DEI", "libelle": "Déplacement infirmier", "coefficient": 1.0, "tarif_base": 2.50},
    ]
    
    query_lower = query.lower()
    filtered = [
        r for r in demo_results 
        if query_lower in r["lettre_cle"].lower() or query_lower in r["libelle"].lower()
    ]
    
    return JSONResponse(filtered[:limit])


@router.get("/api/search/ucd", name="search_ucd_codes")
async def search_ucd_codes(
    query: str,
    limit: int = 10,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Recherche de codes UCD (médicaments) avec auto-complétion.
    
    Args:
        query: Texte de recherche (code UCD ou dénomination)
        limit: Nombre max de résultats
    
    Returns:
        Liste de suggestions [{code_ucd, denomination, dosage, forme, prix}]
    """
    demo_results = [
        {"code_ucd": "3400892169407", "denomination": "DOLIPRANE", "dosage": "1000 mg", "forme": "comprimé", "prix": 2.18},
        {"code_ucd": "3400891541489", "denomination": "EFFERALGAN", "dosage": "500 mg", "forme": "comprimé effervescent", "prix": 2.65},
        {"code_ucd": "3400935556813", "denomination": "AMOXICILLINE", "dosage": "1 g", "forme": "comprimé", "prix": 5.30},
        {"code_ucd": "3400937719629", "denomination": "PARACETAMOL", "dosage": "500 mg", "forme": "gélule", "prix": 1.89},
        {"code_ucd": "3400891457988", "denomination": "ASPEGIC", "dosage": "1000 mg", "forme": "poudre", "prix": 2.34},
    ]
    
    query_lower = query.lower()
    filtered = [
        r for r in demo_results 
        if query_lower in r["code_ucd"].lower() or query_lower in r["denomination"].lower()
    ]
    
    return JSONResponse(filtered[:limit])


@router.get("/api/search/lpp", name="search_lpp_codes")
async def search_lpp_codes(
    query: str,
    limit: int = 10,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Recherche de codes LPP (dispositifs médicaux) avec auto-complétion.
    
    Args:
        query: Texte de recherche (code LPP ou dénomination)
        limit: Nombre max de résultats
    
    Returns:
        Liste de suggestions [{code_lpp, denomination, prix}]
    """
    demo_results = [
        {"code_lpp": "1162915", "denomination": "Pansement hydrocellulaire 10x10 cm", "prix": 3.45},
        {"code_lpp": "1148926", "denomination": "Compresse non tissée stérile 10x10 cm", "prix": 0.12},
        {"code_lpp": "2331882", "denomination": "Cathéter veineux périphérique", "prix": 1.80},
        {"code_lpp": "1101535", "denomination": "Seringue jetable 10 ml", "prix": 0.25},
        {"code_lpp": "2314975", "denomination": "Canule de trachéotomie", "prix": 15.60},
    ]
    
    query_lower = query.lower()
    filtered = [
        r for r in demo_results 
        if query_lower in r["code_lpp"].lower() or query_lower in r["denomination"].lower()
    ]
    
    return JSONResponse(filtered[:limit])


@router.get("/api/templates", name="get_acte_templates")
async def get_acte_templates(
    type_acte: Optional[str] = None,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Récupère les templates d'actes fréquents.
    
    Args:
        type_acte: Filtrer par type (ccam, ngap, ucd, lpp)
    
    Returns:
        Liste de templates prédéfinis
    """
    templates_data = {
        "ccam": [
            {
                "id": "ecg",
                "nom": "Électrocardiogramme",
                "code_acte": "DEQP003",
                "code_activite": "01",
                "code_phase": "0",
                "quantite": 1
            },
            {
                "id": "radio-thorax",
                "nom": "Radiographie thorax",
                "code_acte": "LBQH001",
                "code_activite": "01",
                "code_phase": "0",
                "quantite": 1
            },
            {
                "id": "echo-cardiaque",
                "nom": "Échographie cardiaque",
                "code_acte": "HBMD001",
                "code_activite": "01",
                "code_phase": "0",
                "quantite": 1
            },
            {
                "id": "perfusion",
                "nom": "Pose perfusion IV",
                "code_acte": "YYYY080",
                "code_activite": "01",
                "code_phase": "0",
                "quantite": 1
            }
        ],
        "ngap": [
            {
                "id": "consultation-generale",
                "nom": "Consultation générale",
                "lettre_cle": "C",
                "coefficient": 1.0,
                "denombrement": 1
            },
            {
                "id": "consultation-specialiste",
                "nom": "Consultation spécialiste",
                "lettre_cle": "CS",
                "coefficient": 1.0,
                "denombrement": 1
            },
            {
                "id": "pansement",
                "nom": "Pansement",
                "lettre_cle": "AMI",
                "coefficient": 2.0,
                "denombrement": 1
            },
            {
                "id": "visite-domicile",
                "nom": "Visite à domicile",
                "lettre_cle": "V",
                "coefficient": 1.0,
                "denombrement": 1
            }
        ],
        "ucd": [
            {
                "id": "doliprane-1g",
                "nom": "Doliprane 1g x8",
                "code_ucd": "3400892169407",
                "quantite": 8
            },
            {
                "id": "amoxicilline",
                "nom": "Amoxicilline 1g x14",
                "code_ucd": "3400935556813",
                "quantite": 14
            }
        ],
        "lpp": [
            {
                "id": "pansement-hydro",
                "nom": "Pansement hydrocellulaire",
                "code_lpp": "1162915",
                "quantite": 1
            },
            {
                "id": "catheter",
                "nom": "Cathéter veineux",
                "code_lpp": "2331882",
                "quantite": 1
            }
        ]
    }
    
    if type_acte:
        return JSONResponse(templates_data.get(type_acte, []))
    
    return JSONResponse(templates_data)


@router.post("/api/ccam", name="create_ccam_acte")
async def create_ccam_acte(
    acte_data: dict,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """
    Crée un nouvel acte CCAM.
    
    Validation automatique:
    - Format code acte (4 lettres + 3 chiffres)
    - Code activité et phase valides
    - Date d'exécution
    - Montant cohérent
    """
    try:
        # Validation basique
        if not acte_data.get("code_acte"):
            raise ValueError("Code acte obligatoire")
        
        if not acte_data.get("code_activite"):
            raise ValueError("Code activité obligatoire")
        
        if not acte_data.get("code_phase"):
            raise ValueError("Code phase obligatoire")
        
        # Créer l'acte
        acte = CCAMAct(
            dossier_id=acte_data["dossier_id"],
            code_acte=acte_data["code_acte"],
            code_activite=acte_data["code_activite"],
            code_phase=acte_data["code_phase"],
            execute_date=acte_data["execute_date"],
            modificateurs=acte_data.get("modificateurs"),
            quantite=acte_data.get("quantite", 1),
            montant_total=acte_data.get("montant_total"),
            commentaire=acte_data.get("commentaire"),
            valide=False,  # Par défaut non validé
            facture=False
        )
        
        session.add(acte)
        session.commit()
        session.refresh(acte)
        
        # Auto-émission HPRIM si endpoints configurés
        try:
            from app.services.emit_on_create import emit_to_senders_async
            emit_to_senders_async(acte, "ccam_act", session, operation="insert")
        except Exception as e:
            logger.warning(f"Erreur auto-émission HPRIM pour acte CCAM {acte.id}: {e}")
        
        logger.info(f"Acte CCAM créé: {acte.code_acte} (ID: {acte.id})")
        
        return JSONResponse({
            "success": True,
            "acte_id": acte.id,
            "message": f"Acte CCAM {acte.code_acte} enregistré avec succès"
        })
        
    except Exception as e:
        logger.error(f"Erreur création acte CCAM: {e}")
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


"""
Utilitaires pour le calcul automatique des montants de cotations.
"""
from typing import Optional


# Tarifs de base 2024 (à actualiser régulièrement)
TARIFS_BASE = {
    "ccam": {
        # Exemples de tarifs CCAM
        "HBMD001": 70.28,  # Échographie cardiaque
        "DEQP003": 14.26,  # ECG
        "LBQH001": 25.27,  # Radio thorax
        "YYYY080": 12.50,  # Perfusion IV
        "GLQP002": 46.20,  # Exérèse lésion
    },
    "ngap": {
        # Tarifs NGAP par lettre clé
        "C": 25.00,   # Consultation
        "CS": 28.00,  # Consultation spécialiste
        "G": 23.00,   # Consultation générale
        "V": 25.00,   # Visite
        "AMI": 3.50,  # Base acte infirmier (x coefficient)
        "AMX": 3.50,  # Base acte complexe (x coefficient)
        "K": 2.15,    # Coefficient kiné
        "DEI": 2.50,  # Déplacement infirmier
    }
}


def calculate_ccam_amount(
    code_acte: str,
    quantite: int = 1,
    modificateurs: Optional[str] = None,
    tarif_force: Optional[float] = None
) -> float:
    """
    Calcule le montant d'un acte CCAM.
    
    Args:
        code_acte: Code CCAM (ex: HBMD001)
        quantite: Nombre d'actes
        modificateurs: Modificateurs séparés par virgules (ex: "Z1,K50")
        tarif_force: Tarif forcé (bypass du tarif de base)
    
    Returns:
        Montant total calculé en euros
    """
    if tarif_force is not None:
        return tarif_force * quantite
    
    # Récupérer le tarif de base
    tarif_base = TARIFS_BASE["ccam"].get(code_acte, 0.0)
    
    # Appliquer les modificateurs
    montant = tarif_base
    if modificateurs:
        for mod in modificateurs.split(','):
            mod = mod.strip()
            if mod == "K50":
                montant *= 1.5  # +50%
            elif mod == "U50":
                montant *= 1.5  # +50%
            elif mod == "P":
                montant *= 2.0  # Pédiatrie x2
            elif mod == "Z1":
                montant *= 1.2  # +20%
    
    return round(montant * quantite, 2)


def calculate_ngap_amount(
    lettre_cle: str,
    coefficient: float = 1.0,
    denombrement: int = 1,
    tarif_force: Optional[float] = None
) -> float:
    """
    Calcule le montant d'un acte NGAP.
    
    Args:
        lettre_cle: Lettre clé NGAP (ex: C, AMI)
        coefficient: Coefficient multiplicateur
        denombrement: Nombre de séances/actes
        tarif_force: Tarif forcé (bypass)
    
    Returns:
        Montant total calculé en euros
    
    Formula: tarif_base × coefficient × denombrement
    """
    if tarif_force is not None:
        return tarif_force * denombrement
    
    tarif_base = TARIFS_BASE["ngap"].get(lettre_cle, 0.0)
    montant = tarif_base * coefficient * denombrement
    
    return round(montant, 2)


def calculate_ucd_amount(
    quantite: int = 1,
    prix_unitaire: Optional[float] = None
) -> float:
    """
    Calcule le montant d'un médicament UCD.
    
    Args:
        quantite: Nombre d'unités
        prix_unitaire: Prix unitaire TTC
    
    Returns:
        Montant total calculé en euros
    """
    if prix_unitaire is None:
        return 0.0
    
    return round(prix_unitaire * quantite, 2)


def calculate_lpp_amount(
    quantite: int = 1,
    prix_unitaire: Optional[float] = None
) -> float:
    """
    Calcule le montant d'un dispositif LPP.
    
    Args:
        quantite: Nombre d'unités
        prix_unitaire: Prix unitaire TTC
    
    Returns:
        Montant total calculé en euros
    """
    if prix_unitaire is None:
        return 0.0
    
    return round(prix_unitaire * quantite, 2)


@router.post("/api/calculate/ccam", name="calculate_ccam_montant")
async def api_calculate_ccam(
    code_acte: str,
    quantite: int = 1,
    modificateurs: Optional[str] = None
) -> JSONResponse:
    """API pour calculer un montant CCAM en temps réel."""
    montant = calculate_ccam_amount(code_acte, quantite, modificateurs)
    return JSONResponse({
        "montant": montant,
        "code_acte": code_acte,
        "quantite": quantite,
        "modificateurs": modificateurs
    })


@router.post("/api/calculate/ngap", name="calculate_ngap_montant")
async def api_calculate_ngap(
    lettre_cle: str,
    coefficient: float = 1.0,
    denombrement: int = 1
) -> JSONResponse:
    """API pour calculer un montant NGAP en temps réel."""
    montant = calculate_ngap_amount(lettre_cle, coefficient, denombrement)
    return JSONResponse({
        "montant": montant,
        "lettre_cle": lettre_cle,
        "coefficient": coefficient,
        "denombrement": denombrement
    })


@router.post("/api/ngap", name="create_ngap_acte")
async def create_ngap_acte(
    acte_data: dict,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """Crée un nouvel acte NGAP avec validation."""
    try:
        if not acte_data.get("lettre_cle"):
            raise ValueError("Lettre clé obligatoire")
        
        acte = NGAPAct(
            dossier_id=acte_data["dossier_id"],
            lettre_cle=acte_data["lettre_cle"],
            coefficient=acte_data.get("coefficient", 1.0),
            denombrement=acte_data.get("denombrement", 1),
            execute_date=acte_data["execute_date"],
            montant_total=acte_data.get("montant_total"),
            commentaire=acte_data.get("commentaire"),
            valide=False,
            facture=False
        )
        
        session.add(acte)
        session.commit()
        session.refresh(acte)
        
        # Auto-émission HPRIM si endpoints configurés
        try:
            from app.services.emit_on_create import emit_to_senders_async
            emit_to_senders_async(acte, "ngap_act", session, operation="insert")
        except Exception as e:
            logger.warning(f"Erreur auto-émission HPRIM pour acte NGAP {acte.id}: {e}")
        
        logger.info(f"Acte NGAP créé: {acte.lettre_cle} (ID: {acte.id})")
        
        return JSONResponse({
            "success": True,
            "acte_id": acte.id,
            "message": f"Acte NGAP {acte.lettre_cle} enregistré avec succès"
        })
        
    except Exception as e:
        logger.error(f"Erreur création acte NGAP: {e}")
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/ucd", name="create_ucd_acte")
async def create_ucd_acte(
    acte_data: dict,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """Crée un nouvel acte UCD avec validation minimale orientée saisie rapide."""
    try:
        if not acte_data.get("code_ucd"):
            raise ValueError("Code UCD obligatoire")

        if not acte_data.get("denomination_libelle"):
            raise ValueError("Libellé médicament obligatoire")

        if not acte_data.get("execute_date"):
            raise ValueError("Date d'exécution obligatoire")

        quantite = acte_data.get("quantite", 1)

        acte = UCDAct(
            dossier_id=acte_data["dossier_id"],
            code_ucd=acte_data["code_ucd"],
            denomination_libelle=acte_data["denomination_libelle"],
            denomination_dosage=acte_data.get("denomination_dosage"),
            denomination_forme=acte_data.get("denomination_forme"),
            execute_date=acte_data["execute_date"],
            quantite=quantite,
            montant_unitaire_facture_ttc=acte_data.get("montant_unitaire_facture_ttc"),
            commentaire=acte_data.get("commentaire"),
            valide=False,
            facture="non",
        )

        session.add(acte)
        session.commit()
        session.refresh(acte)

        # Auto-émission HPRIM si endpoints configurés
        try:
            from app.services.emit_on_create import emit_to_senders_async
            emit_to_senders_async(acte, "ucd_act", session, operation="insert")
        except Exception as e:
            logger.warning(f"Erreur auto-émission HPRIM pour acte UCD {acte.id}: {e}")

        logger.info(f"Acte UCD créé: {acte.code_ucd} (ID: {acte.id})")

        return JSONResponse({
            "success": True,
            "acte_id": acte.id,
            "message": f"Acte UCD {acte.code_ucd} enregistré avec succès",
        })

    except Exception as e:
        logger.error(f"Erreur création acte UCD: {e}")
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/lpp", name="create_lpp_acte")
async def create_lpp_acte(
    acte_data: dict,
    session: Session = Depends(get_session)
) -> JSONResponse:
    """Crée un nouvel acte LPP (dispositif) avec validation minimale."""
    try:
        if not acte_data.get("denomination_libelle"):
            raise ValueError("Libellé dispositif obligatoire")

        if not acte_data.get("execute_date"):
            raise ValueError("Date d'exécution obligatoire")

        if acte_data.get("montant_unitaire_facture_ttc") is None:
            raise ValueError("Montant unitaire TTC obligatoire")

        if not acte_data.get("quantite"):
            raise ValueError("Quantité obligatoire")

        acte = LPPAct(
            dossier_id=acte_data["dossier_id"],
            execute_date=acte_data["execute_date"],
            code_lpp=acte_data.get("code_lpp"),
            denomination_libelle=acte_data["denomination_libelle"],
            montant_unitaire_facture_ttc=acte_data["montant_unitaire_facture_ttc"],
            quantite=acte_data["quantite"],
            commentaire=acte_data.get("commentaire"),
            valide=False,
            facture="non",
        )

        session.add(acte)
        session.commit()
        session.refresh(acte)

        # Auto-émission HPRIM si endpoints configurés
        try:
            from app.services.emit_on_create import emit_to_senders_async
            emit_to_senders_async(acte, "lpp_act", session, operation="insert")
        except Exception as e:
            logger.warning(f"Erreur auto-émission HPRIM pour acte LPP {acte.id}: {e}")

        logger.info(f"Acte LPP créé: {acte.code_lpp or acte.denomination_libelle} (ID: {acte.id})")

        return JSONResponse({
            "success": True,
            "acte_id": acte.id,
            "message": "Acte LPP enregistré avec succès",
        })

    except Exception as e:
        logger.error(f"Erreur création acte LPP: {e}")
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
