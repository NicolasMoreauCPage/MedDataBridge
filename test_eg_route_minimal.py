from fastapi import FastAPI, APIRouter, Depends, Request, HTTPException
from sqlmodel import Session

app = FastAPI()
router = APIRouter(prefix="/ght", tags=["ght"])

# Dummy dependency and models
class DummySession: pass
class GHTContext: pass
class EntiteJuridique: pass
class EntiteGeographique: pass

def get_session(): return DummySession()

def get_context_or_404(session, context_id): return GHTContext()
def get_ej_or_404(session, context, ej_id): return EntiteJuridique()
def get_entite_geo_or_404(session, entite, eg_id): return EntiteGeographique()

@router.get("/{context_id}/ej/{ej_id}/eg/{eg_id}")
async def view_entite_geographique(request: Request, context_id: int, ej_id: int, eg_id: int, session: Session = Depends(get_session)):
    return {"context_id": context_id, "ej_id": ej_id, "eg_id": eg_id}

app.include_router(router, prefix="/admin")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
