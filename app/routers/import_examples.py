from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlmodel import Session
from app.db import get_session
from app.models_structure import GHTContext, EntiteJuridique
from pathlib import Path
import tempfile
import importlib.util
from functools import lru_cache

from config.settings import settings

router = APIRouter(prefix="/import", tags=["import"])

@lru_cache(maxsize=1)
def _load_import_impls():
    """Charge dynamiquement les implémentations d'import depuis l'outil existant."""
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "tools" / "import_test_exemples.py"

    if not script_path.exists():
        raise RuntimeError(f"Script d'import introuvable: {script_path}")

    module_name = "import_test_exemples_runtime"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger le module d'import: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import_structure = getattr(module, "import_structure_mfn", None)
    import_pam = getattr(module, "import_pam_messages", None)
    if import_structure is None or import_pam is None:
        raise RuntimeError("Fonctions d'import MFN/PAM introuvables dans le script d'import")

    return import_structure, import_pam


def _resolve_ej_in_ght(session: Session, ght_id: int, ej_id: int) -> EntiteJuridique:
    """Valide que l'EJ existe et appartient bien au GHT fourni."""
    ght = session.get(GHTContext, ght_id)
    if not ght:
        raise HTTPException(status_code=404, detail=f"GHT {ght_id} introuvable")

    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail=f"Entité juridique {ej_id} introuvable")

    if ej.ght_context_id != ght_id:
        raise HTTPException(
            status_code=400,
            detail=f"L'entité juridique {ej_id} n'appartient pas au GHT {ght_id}",
        )

    return ej


def _resolve_ej(session: Session, ej_id: int) -> EntiteJuridique:
    """Valide que l'EJ existe."""
    ej = session.get(EntiteJuridique, ej_id)
    if not ej:
        raise HTTPException(status_code=404, detail=f"Entité juridique {ej_id} introuvable")
    return ej

@router.post("/structure_mfn/")
def import_structure_mfn_endpoint(
    ght_id: int = Form(...),
    ej_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Importe une structure MFN via upload."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier MFN manquant")

    max_size = settings.max_upload_size_mb * 1024 * 1024
    file_bytes = file.file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Fichier MFN vide")
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=413, detail="Fichier MFN trop volumineux")

    ej = _resolve_ej_in_ght(session, ght_id, ej_id)
    import_structure_mfn_impl, _ = _load_import_impls()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".hl7") as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        import_structure_mfn_impl(session, ej, tmp_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur import structure MFN: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "status": "ok",
        "type": "structure_mfn",
        "ght_id": ght_id,
        "ej_id": ej_id,
        "filename": file.filename,
        "bytes": len(file_bytes),
    }

@router.post("/pam_messages/")
def import_pam_messages_endpoint(
    ej_id: int = Form(...),
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    """Importe des messages PAM HL7 via upload."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier PAM fourni")

    ej = _resolve_ej(session, ej_id)
    _, import_pam_messages_impl = _load_import_impls()

    max_size = settings.max_upload_size_mb * 1024 * 1024
    imported_filenames: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="Un fichier PAM n'a pas de nom")
            if not file.filename.lower().endswith(".hl7"):
                raise HTTPException(status_code=400, detail=f"Extension non supportée pour {file.filename} (attendu .hl7)")

            content = file.file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail=f"Fichier PAM vide: {file.filename}")
            if len(content) > max_size:
                raise HTTPException(status_code=413, detail=f"Fichier PAM trop volumineux: {file.filename}")

            file_path = tmpdir_path / file.filename
            with open(file_path, "wb") as f:
                f.write(content)
            imported_filenames.append(file.filename)

        try:
            imported_count = import_pam_messages_impl(session, ej, tmpdir_path, max_files=len(imported_filenames))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Erreur import messages PAM: {exc}") from exc

    return {
        "status": "ok",
        "type": "pam_messages",
        "ej_id": ej_id,
        "files_received": len(imported_filenames),
        "files": imported_filenames,
        "messages_imported": imported_count,
    }
