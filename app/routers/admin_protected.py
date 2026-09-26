"""Routes d'administration protégées par rôles."""
import json

from fastapi import APIRouter, Depends, Request
from sqlmodel import select

from app.auth import UserInDB, require_role, RoleChecker, get_current_user
from app.models.users import LocalUser


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def list_users(request: Request, user: UserInDB = Depends(require_role("admin"))):
    """
    Liste tous les utilisateurs (admin only).
    
    Requires: role "admin"
    """
    with request.app.state.session_factory() as session:
        accounts = session.exec(select(LocalUser).order_by(LocalUser.username)).all()
    return {
        "users": [
            {
                "id": account.id,
                "username": account.username,
                "email": account.email,
                "roles": json.loads(account.roles_json),
                "is_active": account.is_active,
            }
            for account in accounts
        ]
    }


@router.get("/stats")
def get_system_stats(request: Request, user: UserInDB = Depends(RoleChecker(["admin", "moderator"]))):
    """
    Récupère les statistiques système.
    
    Requires: role "admin" OR "moderator"
    """
    with request.app.state.session_factory() as session:
        accounts = session.exec(select(LocalUser)).all()
    return {
        "status": "ok",
        "user": user.username,
        "roles": user.roles,
        "stats": {
            "total_users": len(accounts),
            "active_users": sum(account.is_active for account in accounts),
        }
    }


@router.post("/maintenance")
async def trigger_maintenance(user: UserInDB = Depends(require_role("admin"))):
    """
    Déclenche une maintenance système.
    
    Requires: role "admin"
    """
    return {
        "message": "Maintenance déclenchée",
        "triggered_by": user.username
    }


@router.get("/profile")
async def get_my_profile(user: UserInDB = Depends(get_current_user)):
    """
    Récupère le profil de l'utilisateur connecté (tous les rôles).
    
    Requires: authentification valide
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "is_active": user.is_active
    }


@router.get("/config")
async def get_system_config(user: UserInDB = Depends(RoleChecker(["admin"]))):
    """
    Récupère la configuration système.
    
    Requires: role "admin"
    """
    return {
        "config": {
            "environment": "development",
            "features": {
                "cache": True,
                "monitoring": True
            }
        }
    }
