
"""
Module de tests roundtrip HPRIM (stub).
"""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter(prefix="/roundtrip-hprim", tags=["Roundtrip HPRIM"])

@router.post("/generate")
async def generate_hprim_xml(payload: dict, request: Request):
    # Dummy implementation: create a temp file and return its path/filename
    # In real implementation, generate XML based on payload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w") as tmp:
        tmp.write("<evenementsServeurActes></evenementsServeurActes>")
        filepath = tmp.name
    filename = os.path.basename(filepath)
    return JSONResponse({"filepath": filepath, "filename": filename})

@router.get("/download/{filename}")
async def download_hprim_xml(filename: str):
    # Dummy implementation: serve the file from temp directory
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/xml", filename=filename)

@router.post("/reintegrate")
async def reintegrate_hprim_xml(file: UploadFile = File(...)):
    # Dummy implementation: save the uploaded file to temp dir
    temp_dir = tempfile.gettempdir()
    save_path = os.path.join(temp_dir, file.filename)
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"status": "ok", "filename": file.filename, "saved_to": save_path}
