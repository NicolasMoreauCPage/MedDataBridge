"""
Router pour l'interface de validation de messages HL7 v2.5
Permet de valider un message HL7 en dehors du contexte GHT (unitaire ou scénario)
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest
from app.services.pam_validation import validate_pam
from app.services.hl7_display import build_hl7_view
from app.services.hprim.hprim_service import HprimService
from app.services.scenario_validation import validate_scenario


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter()


def detect_message_format(content: str) -> str:
    """Détecte le format du message: 'HL7' ou 'HPRIM_XML' ou 'UNKNOWN'."""
    c = (content or "").strip()
    if not c:
        return "UNKNOWN"
    lower = c.lower()
    # Heuristique HPRIM XML: balises XML et namespace hprim
    if (c.startswith("<?xml") or c.startswith("<")) and (
        "http://www.hprim.org/hprimxml" in lower or
        "<evenementsserveuractes" in lower or
        "<acquittementsserveuractes" in lower or
        "<evenementsfraisdivers" in lower or
        "<acquittementsfraisdivers" in lower or
        "<evenementspmsi" in lower or
        "<acquittementspmsi" in lower or
        "<evenementsserveuretatspatient" in lower or
        "<acquittementsserveuretatspatient" in lower
    ):
        return "HPRIM_XML"
    # Heuristique HL7 v2: segments pipe 'MSH|', 'PID|', etc.
    if "MSH|" in c:
        return "HL7"
    return "UNKNOWN"


@router.get("/validation", response_class=HTMLResponse)
async def validation_page(request: Request):
    """Page de validation de messages HL7."""
    # Message exemple par défaut
    example_message = """MSH|^~\\&|SENDING_APP|SEND_FAC|RECEIVING_APP|RECV_FAC|20251105120000||ADT^A01^ADT_A01|MSG001|P|2.5^FRA^2.11|||||FRA|UNICODE UTF-8
EVN|A01|20251105120000
PID|1||123456^^^HOSP^PI||DUPONT^JEAN||19800101|M||||||||||||||||||||||||VALI
PV1|1|I|CARDIO^101^1||||||||||||||||1
ZBE|MVT001^HOSP^1.2.250.1.1^ISO|20251105120000||INSERT|N|||^^^^^^^^^UF01|H"""
    
    return get_templates_with_filters(request).TemplateResponse(request, "validation.html", {
        "title": "Validation Messages HL7 v2.5",
        "validation_done": False,
        "hl7_message": example_message,
        "scenario_result": None
    })


@router.post("/validation/validate", response_class=HTMLResponse)
async def validate_message(
    request: Request,
    hl7_message: str = Form(...),
    direction: str = Form(default="inbound"),
    profile: str = Form(default="IHE_PAM_FR")
):
    """Valide un message HL7 et retourne le rapport."""
    # L'écran est celui du profil France ; ne pas laisser croire qu'un second
    # profil est effectivement appliqué.
    profile = "IHE_PAM_FR"

    fmt = detect_message_format(hl7_message)
    if fmt == "HPRIM_XML":
        # Validation HPRIM XML avec XSD + contenu
        hprim = HprimService()
        xml_result = hprim.traiter_message_xml(hl7_message)

        return get_templates_with_filters(request).TemplateResponse(request, "validation.html", {
            "title": "Validation Messages HL7 v2.5 / HPRIM XML",
            "validation_done": True,
            "hl7_message": hl7_message,
            "direction": direction,
            "profile": profile,
            "format_detected": fmt,
            "xsd_valid": xml_result.get("succes", False),
            "xsd_errors": xml_result.get("erreurs") if xml_result.get("type_erreur") == "XSD_VALIDATION" else None,
            "hprim_result": xml_result,
            "scenario_result": None
        })
    else:
        # Validation HL7/PAM
        result = validate_pam(hl7_message, direction, profile)
        # Classifier les issues par sévérité
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warn"]
        infos = [i for i in result.issues if i.severity == "info"]

        # Les couches sont portées par le validateur afin que le journal et
        # l'écran immédiat utilisent exactement le même contrat.
        ihe_pam = [i for i in result.issues if i.layer == "ihe_pam"]
        structure = [i for i in result.issues if i.layer == "structure"]
        hl7_base = [i for i in result.issues if i.layer == "hl7_base"]
        datatypes = [i for i in result.issues if i.layer == "datatypes"]

        return get_templates_with_filters(request).TemplateResponse(request, "validation.html", {
            "title": "Validation Messages HL7 v2.5 / HPRIM XML",
            "validation_done": True,
            "hl7_message": hl7_message,
            "direction": direction,
            "profile": profile,
            "format_detected": fmt,
            "result": result,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "ihe_pam": ihe_pam,
            "hl7_base": hl7_base,
            "datatypes": datatypes,
            "structure": structure,
            "hl7_view": build_hl7_view(hl7_message),
            "scenario_result": None
        })


@router.post("/validation/validate-scenario", response_class=HTMLResponse)
async def validate_scenario_route(
    request: Request,
    scenario_messages: str = Form(...),
    direction: str = Form(default="inbound"),
    profile: str = Form(default="IHE_PAM_FR")
):
    """Valide un scénario de plusieurs messages HL7 et retourne le rapport."""
    profile = "IHE_PAM_FR"
    
    # Validation du scénario
    result = validate_scenario(scenario_messages, direction, profile)
    return get_templates_with_filters(request).TemplateResponse(request, "validation.html", {
        "title": "Validation Scénario HL7 v2.5",
        "validation_done": False,
        "scenario_result": result,
        "scenario_messages": scenario_messages,
        "direction": direction,
        "profile": profile,
    })
