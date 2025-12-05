"""GHT Context CRUD routes"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
import os
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.models_structure import GHTContext, IdentifierNamespace
from app.models import Dossier
from app.utils.flash import flash
from .helpers import get_context_or_404, get_ej_or_404

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["ght"])


@router.get("/")
async def list_ght_contexts(
    request: Request,
    session: Session = Depends(get_session),
):
    """Liste tous les contextes GHT (page de sélection)."""
    contexts = session.exec(select(GHTContext)).all()
    return templates.TemplateResponse(
        request,
        "ght_contexts.html",
        {"contexts": contexts},
    )


@router.get("/new")
async def new_ght_context_form(request: Request):
    """Affiche le formulaire de création d'un nouveau contexte GHT."""
    return templates.TemplateResponse(
        request,
        "ght_form.html",
        {
            "context": None},
    )


@router.post("/{context_id}/set-ej")
async def set_ej_for_ght(
    request: Request,
    context_id: int,
    ej_id: int = Form(...),
    session: Session = Depends(get_session)
):
    """Enregistre l'entité juridique sélectionnée pour le contexte GHT en session utilisateur."""
    context = get_context_or_404(session, context_id)
    if ej_id:
        ej = get_ej_or_404(session, context, ej_id)
        request.session[f"ght_{context_id}_ej_id"] = ej_id
        request.session[f"ght_{context_id}_ej_name"] = ej.name
        # Définir aussi les contextes globaux pour cohérence de l'UI et des filtres
        request.session["ej_context_id"] = ej_id
        request.session["ght_context_id"] = context_id
        
        # Nettoyer les contextes patient/dossier s'ils n'appartiennent pas à la nouvelle EJ
        current_dossier_id = request.session.get("dossier_id")
        if current_dossier_id:
            dossier = session.get(Dossier, current_dossier_id)
            if dossier and dossier.entite_juridique_id != ej_id:
                # Le dossier n'appartient pas à la nouvelle EJ, le nettoyer
                request.session.pop("dossier_id", None)
                request.session.pop("patient_id", None)  # Nettoyer aussi le patient
        
        # Vérifier aussi le contexte patient seul
        current_patient_id = request.session.get("patient_id")
        if current_patient_id and not request.session.get("dossier_id"):
            # Si on a un patient mais pas de dossier, vérifier s'il a des dossiers dans la nouvelle EJ
            from app.models import Dossier
            patient_dossiers_in_ej = session.exec(
                select(Dossier).where(
                    Dossier.patient_id == current_patient_id,
                    Dossier.entite_juridique_id == ej_id
                )
            ).first()
            if not patient_dossiers_in_ej:
                # Le patient n'a pas de dossiers dans la nouvelle EJ
                request.session.pop("patient_id", None)
        
    else:
        request.session.pop(f"ght_{context_id}_ej_id", None)
        request.session.pop(f"ght_{context_id}_ej_name", None)
        # Si on désélectionne l'EJ, effacer le contexte global EJ mais conserver le GHT courant
        request.session.pop("ej_context_id", None)
        # Nettoyer aussi les contextes patient/dossier car ils ne sont plus valides sans EJ
        request.session.pop("dossier_id", None)
        request.session.pop("patient_id", None)
    return RedirectResponse(f"/admin/ght/{context_id}", status_code=303)


@router.post("/new")
async def create_ght_context(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    description: Optional[str] = Form(None),
    is_active: str = Form("true"),
    session: Session = Depends(get_session),
):
    """Crée un nouveau contexte GHT et initialise des namespaces par défaut."""
    # Uniqueness check for code
    existing = session.exec(select(GHTContext).where(GHTContext.code == code)).first()
    if existing:
        flash(request, "Ce code est déjà utilisé par un autre contexte GHT.", "error")
        return templates.TemplateResponse(
            request,
        "ght_form.html",
        {
                "context": None,
                "form_data": {
                    "name": name,
                    "code": code,
                    "description": description,
                    "is_active": is_active},
            },
            status_code=400,
        )

    context = GHTContext(
        name=name,
        code=code,
        description=description,
        is_active=str(is_active).lower() in ("1", "true", "yes", "on"),
    )
    session.add(context)
    session.commit()
    session.refresh(context)

    # Default namespaces for the new context
    default_namespaces = [
        {
            "name": "IPP",
            "system": f"urn:oid:1.2.250.1.{context.id}.1.0",
            "type": "PI",
            "description": "Identifiant Patient Principal",
        },
        {
            "name": "NDA",
            "system": f"urn:oid:1.2.250.1.{context.id}.1.1",
            "type": "VN",
            "description": "Numéro de Dossier Administratif",
        },
        {
            "name": "FINESS EJ",
            "system": "urn:oid:1.2.250.1.71.4.2.2",
            "type": "XX",
            "description": "FINESS Entité Juridique",
        },
        {
            "name": "FINESS EG",
            "system": "urn:oid:1.2.250.1.71.4.2.1",
            "type": "XX",
            "description": "FINESS Entité Géographique",
        },
    ]

    for ns in default_namespaces:
        namespace = IdentifierNamespace(
            name=ns["name"],
            system=ns["system"],
            type=ns["type"],
            description=ns["description"],
            ght_context_id=context.id,
        )
        session.add(namespace)

    session.commit()

    flash(request, f'Contexte GHT "{context.name}" créé avec succès.', "success")

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"ok": True, "id": context.id, "redirect": "/admin/ght"}

    return RedirectResponse("/admin/ght", status_code=303)


@router.get("/{context_id}/edit")
async def edit_ght_context_form(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session)
):
    """Affiche le formulaire d'édition d'un contexte GHT."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    return templates.TemplateResponse(
        request,
        "ght_form.html",
        {
            "context": context
        }
    )


@router.post("/{context_id}/edit")
async def update_ght_context(
    request: Request,
    context_id: int,
    name: str = Form(...),
    code: str = Form(...),
    description: Optional[str] = Form(None),
    is_active: str = Form("true"),
    session: Session = Depends(get_session)
):
    """Met à jour un contexte GHT existant."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    # Vérifier l'unicité du code si modifié
    if code != context.code:
        existing = session.exec(
            select(GHTContext).where(GHTContext.code == code)
        ).first()
        if existing:
            flash(request, "Ce code est déjà utilisé par un autre contexte GHT.", "error")
            accept = request.headers.get("accept", "")
            if "application/json" in accept:
                return {"ok": False, "message": "Ce code est déjà utilisé", "errors": {"code": "Code déjà utilisé"}}

            return templates.TemplateResponse(
                request,
        "ght_form.html",
        {
                    "context": context,
                    "form_data": {
                        "name": name,
                        "code": code,
                        "description": description,
                        "is_active": is_active},
                },
                status_code=400,
            )
    
    context.name = name
    context.code = code
    context.description = description
    context.is_active = str(is_active).lower() in ("1", "true", "yes", "on")
    context.updated_at = datetime.utcnow()
    
    session.add(context)
    session.commit()

    flash(request, f'Contexte GHT "{context.name}" mis à jour.', "success")
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"ok": True, "id": context.id, "redirect": "/admin/ght"}

    return RedirectResponse(
        "/admin/ght",
        status_code=303
    )


@router.get("/{context_id}")
async def view_ght_context(
    request: Request,
    context_id: int,
    session: Session = Depends(get_session)
):
    """Affiche les détails d'un contexte GHT et ses entités."""
    context = session.get(GHTContext, context_id)
    if not context:
        raise HTTPException(status_code=404, detail="Contexte non trouvé")
    
    # Stocker le contexte sélectionné en session
    request.session["ght_context_id"] = context_id
    
    # Charger explicitement les entités juridiques pour éviter le lazy loading
    from app.models_structure import EntiteJuridique
    entites_juridiques = session.exec(
        select(EntiteJuridique).where(EntiteJuridique.ght_context_id == context_id)
    ).all()
    
    selected_ej_id = request.session.get(f"ght_{context_id}_ej_id")
    selected_ej_name = request.session.get(f"ght_{context_id}_ej_name")
    return templates.TemplateResponse(
        request,
        "ght_detail.html",
        {
            "context": context,
            "namespaces": context.namespaces,
            "entites_juridiques": entites_juridiques,
            "selected_ej_id": selected_ej_id,
            "selected_ej_name": selected_ej_name}
    )


@router.post("/_test/session")
async def _test_set_session(
    request: Request,
    session: Session = Depends(get_session),
):
    """Test-only helper: set GHT/EJ context in the session via JSON payload.

    This endpoint exists only when tests run (guarded at runtime). It accepts
    a JSON body like {"ght_id": 1, "ej_id": 2} and sets the corresponding
    session keys so UI tests can deterministically establish context.
    """
    # Only enable when either TESTING is set, or when a valid test auth header
    # is supplied. This lets the test harness use a short-lived secret header
    # to call this helper without enabling full TESTING mode in the server
    # process. The secret should be provided via the TEST_AUTH_TOKEN env var.
    token = os.getenv("TEST_AUTH_TOKEN")
    header = request.headers.get("x-test-auth") or request.headers.get("X-TEST-AUTH")
    if not (os.getenv("TESTING", "0") in ("1", "true", "True") or (token and header == token)):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        body = await request.json()
    except Exception:
        # If the client posted form-encoded data (auto-submitted form from
        # the HTML setter), parse form data as a Solution de repli so tests can use
        # a simple form POST without triggering JSON preflight issues.
        try:
            form = await request.form()
            body = {k: v for k, v in form.items()}
        except Exception:
            body = {}

    ght_id = body.get("ght_id")
    ght_code = body.get("ght_code")
    ej_id = body.get("ej_id")

    # If a ght_code was supplied, resolve it to the current DB id to avoid
    # mismatches between the test process' DB and the server process DB.
    if ght_code and not ght_id:
        found = session.exec(select(GHTContext).where(GHTContext.code == str(ght_code))).first()
        if found:
            ght_id = found.id
        else:
            # Create the context on-the-fly in the server DB so tests can
            # rely on navigating to a stable ght_code without needing
            # pre-seeded numeric IDs that may differ across processes.
            try:
                new_ctx = GHTContext(name=str(ght_code), code=str(ght_code), is_active=True)
                session.add(new_ctx)
                session.commit()
                session.refresh(new_ctx)
                ght_id = new_ctx.id
            except Exception:
                # If creation fails, continue without raising to avoid
                # breaking non-test flows; the session setter will simply
                # not set a valid id.
                pass

    if ght_id is not None:
        try:
            request.session["ght_context_id"] = int(ght_id)
        except Exception:
            request.session["ght_context_id"] = ght_id

    if ej_id is not None and ght_id is not None:
        try:
            request.session[f"ght_{int(ght_id)}_ej_id"] = int(ej_id)
            request.session["ej_context_id"] = int(ej_id)
        except Exception:
            request.session[f"ght_{ght_id}_ej_id"] = ej_id
            request.session["ej_context_id"] = ej_id
    # Provide an explicit test cookie so browser contexts can detect the
    # session-setting flow reliably even if signed session cookie parsing
    # behaves unexpectedly in headless environments. Also set simple
    # ght/ej id cookies as an unprotected Solution de repli for the middleware
    # to read when running tests.
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    try:
        resp.set_cookie("medbridge_test", "1", path="/", httponly=False)
        if ght_id is not None:
            resp.set_cookie("ght_context_id", str(ght_id), path="/", httponly=False)
        if ej_id is not None:
            resp.set_cookie("ej_context_id", str(ej_id), path="/", httponly=False)
        # Also set a small JSON payload cookie to help middleware/tests share
        # a simple, unsigned representation of the context. Use SameSite=Lax
        # and do not set Secure so it works on local HTTP.
        try:
            import json as _json
            payload = {}
            if ght_id is not None:
                payload["ght_id"] = int(ght_id) if isinstance(ght_id, (int, str)) and str(ght_id).isdigit() else ght_id
            if ej_id is not None:
                payload["ej_id"] = int(ej_id) if isinstance(ej_id, (int, str)) and str(ej_id).isdigit() else ej_id
            if payload:
                resp.set_cookie("medbridge_test_data", _json.dumps(payload), path="/", httponly=False, samesite="lax")
        except Exception:
            # Best-effort; do not break test helper on cookie serialization errors
            pass
    except Exception:
        pass
    return resp


@router.get("/_test/session/debug")
async def _test_get_session_debug(request: Request, session: Session = Depends(get_session)):
    """Test-only helper: return a snapshot of the current session for debugging.

    Only available when TESTING is enabled.
    """
    token = os.getenv("TEST_AUTH_TOKEN")
    header = request.headers.get("x-test-auth") or request.headers.get("X-TEST-AUTH")
    if not (os.getenv("TESTING", "0") in ("1", "true", "True") or (token and header == token)):
        raise HTTPException(status_code=404, detail="Not found")

    # Renvoie shallow copy of session keys and values (JSON-serializable best-effort)
    data = {}
    for k, v in request.session.items():
        try:
            # Some session values may not be JSON-serializable; coerce to string in that case
            import json

            json.dumps(v)
            data[k] = v
        except Exception:
            data[k] = str(v)

    return {"ok": True, "session": data}


@router.get("/_test/session/set")
async def _test_set_session_get(request: Request, token: str | None = None, ght_id: int | None = None, ej_id: int | None = None, ght_code: str | None = None, session: Session = Depends(get_session)):
    """Test-only GET helper: set session via a navigable URL.

    Allows tests to navigate the browser to a URL like
    /admin/ght/_test/session/set?token=...&ght_id=1 which sets the
    session cookie and redirects to /admin/ght. This avoids CORS
    preflight issues because it's a simple browser navigation.
    """
    env_token = os.getenv("TEST_AUTH_TOKEN")
    if not (os.getenv("TESTING", "0") in ("1", "true", "True") or (env_token and token == env_token)):
        raise HTTPException(status_code=404, detail="Not found")

    # Resolve code -> id if needed to avoid cross-process id skews
    if ght_code and not ght_id:
        found = session.exec(select(GHTContext).where(GHTContext.code == str(ght_code))).first()
        if found:
            ght_id = found.id
        else:
            # Create the context on-the-fly in the server DB so tests can
            # rely on navigating to a stable ght_code without needing
            # pre-seeded numeric IDs that may differ across processes.
            try:
                new_ctx = GHTContext(name=str(ght_code), code=str(ght_code), is_active=True)
                session.add(new_ctx)
                session.commit()
                session.refresh(new_ctx)
                ght_id = new_ctx.id
            except Exception:
                # If creation fails, continue without raising
                pass

    if ght_id is not None:
        try:
            request.session["ght_context_id"] = int(ght_id)
        except Exception:
            request.session["ght_context_id"] = ght_id

    if ej_id is not None and ght_id is not None:
        try:
            request.session[f"ght_{int(ght_id)}_ej_id"] = int(ej_id)
            request.session["ej_context_id"] = int(ej_id)
        except Exception:
            request.session[f"ght_{ght_id}_ej_id"] = ej_id
            request.session["ej_context_id"] = ej_id

    # Instead of a redirect response which may not guarantee the browser
    # has applied the cookies before subsequent resource loads, Renvoie a
    # tiny HTML page that sets the plain cookies via document.cookie in the
    # browser and then submits a hidden form (targeting an iframe) to the
    # POST test endpoint so the server will issue a signed session cookie
    # in the POST response. After the iframe submission completes we then
    # navigate to /admin/ght. This avoids CORS/preflight problems and
    # guarantees the signed session cookie is set by the server.
    try:
        import json as _json
        payload = {}
        if ght_id is not None:
            payload["ght_id"] = int(ght_id) if isinstance(ght_id, (int, str)) and str(ght_id).isdigit() else ght_id
        if ej_id is not None:
            payload["ej_id"] = int(ej_id) if isinstance(ej_id, (int, str)) and str(ej_id).isdigit() else ej_id
        payload_raw = _json.dumps(payload) if payload else ""
    except Exception:
        payload_raw = ""

    # Build inline JS that sets cookies, posts the payload to the server via
    # an auto-submitted hidden form in an iframe, and then redirects.
    js_lines = []
    js_lines.append("(function(){")
    js_lines.append("document.cookie = 'medbridge_test=1; path=/; SameSite=Lax';")
    if payload_raw:
        # Inject minimal payload construction in JS
        try:
            import json as _json
            payload_obj = _json.loads(payload_raw) if payload_raw else {}
        except Exception:
            payload_obj = {}
        # Build JS object literal from payload_obj
        parts = []
        for k, v in (payload_obj.items() if isinstance(payload_obj, dict) else []):
            # numbers shouldn't be quoted
            if isinstance(v, (int, float)):
                parts.append(f"{k}: {v}")
            else:
                # escape single quotes in strings
                sval = str(v).replace("'", "\\'")
                parts.append(f"{k}: '{sval}'")
        obj_js = "{" + ", ".join(parts) + "}"
        js_lines.append(f"var payload = {obj_js};")
    js_lines.append("document.cookie = 'medbridge_test_data=' + encodeURIComponent(JSON.stringify(payload)) + '; path=/; SameSite=Lax';")
    if ght_id is not None:
        js_lines.append(f"document.cookie = 'ght_context_id={ght_id}; path=/; SameSite=Lax';")
    if ej_id is not None:
        js_lines.append(f"document.cookie = 'ej_context_id={ej_id}; path=/; SameSite=Lax';")

    # Create a hidden iframe and a form that posts to the POST test endpoint
    # so the server response can set the signed session cookie. The form is
    # submitted targeting the iframe; after a short delay we navigate to
    # /admin/ght.
    js_lines.append("var iframe = document.createElement('iframe'); iframe.style.display='none'; iframe.name='session_iframe'; document.body.appendChild(iframe);")
    js_lines.append("var form = document.createElement('form'); form.method='POST'; form.action='/admin/ght/_test/session'; form.target='session_iframe';")
    if ght_id is not None:
        js_lines.append(f"var i = document.createElement('input'); i.type='hidden'; i.name='ght_id'; i.value='{ght_id}'; form.appendChild(i);")
    if ej_id is not None:
        js_lines.append(f"var j = document.createElement('input'); j.type='hidden'; j.name='ej_id'; j.value='{ej_id}'; form.appendChild(j);")
    if ght_code is not None:
        js_lines.append(f"var k = document.createElement('input'); k.type='hidden'; k.name='ght_code'; k.value='{ght_code}'; form.appendChild(k);")
    js_lines.append("document.body.appendChild(form); form.submit();")
    js_lines.append("iframe.onload = function(){ window.location.href = '/admin/ght'; };")
    js_lines.append("})();")
    body = """
    <html><head><meta charset='utf-8'></head>
    <body>
    <script>
    """ + "\n".join(js_lines) + """
    </script>
    </body></html>
    """
    from fastapi.responses import HTMLResponse
    # Also set the plain test cookies server-side so user agents receive
    # them even if JS execution or iframe timing is flaky. Use percent-encoding
    # for the JSON payload to ensure it's safe in cookie values.
    try:
        from urllib.parse import quote_plus
        _cookie_val = quote_plus(payload_raw) if payload_raw else ""
    except Exception:
        _cookie_val = payload_raw

    resp = HTMLResponse(content=body)
    try:
        resp.set_cookie("medbridge_test", "1", path="/", httponly=False)
        if payload_raw:
            resp.set_cookie("medbridge_test_data", _cookie_val, path="/", httponly=False, samesite="lax")
        if ght_id is not None:
            resp.set_cookie("ght_context_id", str(ght_id), path="/", httponly=False)
        if ej_id is not None:
            resp.set_cookie("ej_context_id", str(ej_id), path="/", httponly=False)
    except Exception:
        # Best-effort, don't break tests if cookies can't be set
        pass

    return resp


@router.get("/_test/session/debug-html")
async def _test_get_session_debug_html(request: Request, token: str | None = None):
    """Return a tiny HTML page showing the session for browser-based debugging.

    Accessible via ?token=... when TESTING is not enabled.
    """
    env_token = os.getenv("TEST_AUTH_TOKEN")
    if not (os.getenv("TESTING", "0") in ("1", "true", "True") or (env_token and token == env_token)):
        raise HTTPException(status_code=404, detail="Not found")

    items = []
    for k, v in request.session.items():
        items.append(f"<li><strong>{k}</strong>: {v}</li>")
    body = f"<html><body><h1>Session</h1><ul>{''.join(items)}</ul></body></html>"
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=body)
