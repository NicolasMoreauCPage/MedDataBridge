"""Dépendances asynchrones limitées à la lecture du corps HTTP.

Elles permettent aux routes qui utilisent SQLModel synchrone de rester des
fonctions synchrones (donc exécutées dans le pool de threads FastAPI), tout en
laissant Starlette lire les formulaires dans la boucle événementielle.
"""

from fastapi import File, Request, UploadFile
from starlette.datastructures import FormData


async def read_form_data(request: Request) -> FormData:
    return await request.form()


async def read_body(request: Request) -> bytes:
    """Lit le corps HTTP avant l'exécution synchrone de la route."""
    return await request.body()


async def read_uploaded_file(file: UploadFile = File(...)) -> tuple[str, bytes]:
    """Charge un upload avant l'exécution SQL synchrone de la route."""
    return file.filename or "", await file.read()


async def read_optional_json_upload(
    json_file: UploadFile | None = File(None),
) -> bytes | None:
    """Charge facultativement le fichier ``json_file`` d'un import.

    La dépendance conserve la lecture de l'upload dans la boucle événementielle
    sans obliger le workflow d'import, qui utilise SQLModel synchrone, à devenir
    une route asynchrone hybride.
    """
    if json_file is None:
        return None
    return await json_file.read()
