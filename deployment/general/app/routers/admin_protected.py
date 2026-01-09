"""Routes d'administration protégées par rôles."""
from fastapi import APIRouter, Depends
from app.auth import UserInDB, require_role, RoleChecker, get_current_user


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def list_users(user: UserInDB = Depends(require_role("admin"))):
    """
    Liste tous les utilisateurs (admin only).
    
    Requires: role "admin"
    """
    from app.auth import fake_users_db
    
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "roles": u.roles,
                "is_active": u.is_active
            }
            for u in fake_users_db.values()
        ]
    }


@router.get("/stats")
async def get_system_stats(user: UserInDB = Depends(RoleChecker(["admin", "moderator"]))):
    """
    Récupère les statistiques système.
    
    Requires: role "admin" OR "moderator"
    """
    return {
        "status": "ok",
        "user": user.username,
        "roles": user.roles,
        "stats": {
            "total_users": 2,
            "active_users": 2
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
