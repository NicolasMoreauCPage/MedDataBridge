"""
Router pour l'interface de validation de messages HL7 v2.5
Permet de valider un message HL7 en dehors du contexte GHT (unitaire ou scénario)
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest
from app.services.pam_validation import validate_pam
from app.services.hprim.hprim_service import HprimService
from app.services.scenario_validation import validate_scenario
import json


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
    example_message = """MSH|^~\\&|SENDING_APP|SEND_FAC|RECEIVING_APP|RECV_FAC|20251105120000||ADT^A01^ADT_A01|MSG001|P|2.5
EVN|A01|20251105120000
PID|1||123456^^^HOSP||DUPONT^JEAN||19800101|M
PV1|1|I|CARDIO^101^1|||||||||||||||||1"""
    
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
    print(f"[VALIDATION] Received message of length: {len(hl7_message)}")
    print(f"[VALIDATION] Direction: {direction}, Profile: {profile}")

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
        print(f"[VALIDATION] Result level: {result.level}, issues: {len(result.issues)}")

        # Classifier les issues par sévérité
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warn"]
        infos = [i for i in result.issues if i.severity == "info"]

        # Classifier par couche de validation
        ihe_pam = []
        hapi = []
        hl7_base = []
        datatypes = []
        segment_order = []

        for issue in result.issues:
            code = issue.code
            if "ORDER" in code:
                segment_order.append(issue)
            elif code.startswith("PV1_MISSING") or code.startswith("EVN_MISSING") or code.startswith("PID_MISSING"):
                ihe_pam.append(issue)
            elif "SEGMENT" in code or code.endswith("_REQUIRED") or code.endswith("_FORBIDDEN") or "OPTIONAL_SEGMENTS" in code:
                hapi.append(issue)
            elif code.startswith("MSH") or code.startswith("EVN_MISMATCH"):
                hl7_base.append(issue)
            elif "_CX_" in code or "_XPN_" in code or "_XAD_" in code or "_XTN_" in code or "_TS_" in code or code.startswith("PV1_2") or code.startswith("PV1_3") or code.startswith("PV1_7") or code.startswith("PID"):
                datatypes.append(issue)
            else:
                hl7_base.append(issue)

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
            "hapi": hapi,
            "hl7_base": hl7_base,
            "datatypes": datatypes,
            "segment_order": segment_order,
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
    
    print(f"[SCENARIO VALIDATION] Received scenario of length: {len(scenario_messages)}")
    print(f"[SCENARIO VALIDATION] Direction: {direction}, Profile: {profile}")
    
    # Validation du scénario
    result = validate_scenario(scenario_messages, direction, profile)
    print(f"[SCENARIO VALIDATION] Result level: {result.level}, "
          f"messages: {result.total_messages}, "
          f"valid: {result.valid_messages}, "
          f"workflow issues: {len(result.workflow_issues)}, "
          f"coherence issues: {len(result.coherence_issues)}")
    
    return get_templates_with_filters(request).TemplateResponse(request, "validation.html", {
        "title": "Validation Scénario HL7 v2.5",
        "validation_done": False,
        "scenario_result": result,
        "scenario_messages": scenario_messages,
        "direction": direction,
        "profile": profile,
    })
