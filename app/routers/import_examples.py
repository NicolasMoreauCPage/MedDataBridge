from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlmodel import Session
from app.db import get_session
from app.models_structure_fhir import GHTContext, EntiteJuridique
from app.models import Patient
from pathlib import Path
import tempfile
from tools.import_test_exemples import import_structure_mfn, import_pam_messages

router = APIRouter(prefix="/import", tags=["import"])

@router.post("/structure_mfn/")
def import_structure_mfn_endpoint(
    ght_id: int = Form(...),
    ej_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Importe une structure MFN via upload."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)
    ej = session.get(EntiteJuridique, ej_id)
    import_structure_mfn(session, ej, tmp_path)
    tmp_path.unlink(missing_ok=True)
    return {"status": "ok"}

@router.post("/pam_messages/")
def import_pam_messages_endpoint(
    ej_id: int = Form(...),
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    """Importe des messages PAM HL7 via upload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        for file in files:
            file_path = tmpdir_path / file.filename
            with open(file_path, "wb") as f:
                f.write(file.file.read())
        ej = session.get(EntiteJuridique, ej_id)
        import_pam_messages(session, ej, tmpdir_path)
    return {"status": "ok"}
