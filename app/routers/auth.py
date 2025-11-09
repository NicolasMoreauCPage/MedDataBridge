"""
Router pour l'authentification JWT.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta

from app.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    require_role,
    UserInDB,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    """Requête de login."""
    username: str
    password: str


class UserResponse(BaseModel):
    """Réponse utilisateur (sans mot de passe)."""
    id: int
    username: str
    email: str
    roles: list[str]
    is_active: bool


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authentification et génération de tokens.
    
    Args:
        form_data: Formulaire OAuth2 (username, password)
        
    Returns:
        Token JWT d'accès et de refresh
        
    Exemple:
        ```bash
        curl -X POST "http://localhost:8000/auth/login" \\
          -H "Content-Type: application/x-www-form-urlencoded" \\
          -d "username=admin&password=admin123"
        ```
    """
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Créer le token d'accès
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "roles": user.roles},
        expires_delta=access_token_expires
    )
    
    # Créer le refresh token
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/login/json", response_model=Token)
async def login_json(login_data: LoginRequest):
    """
    Authentification avec JSON (alternative à OAuth2 form).
    
    Args:
        login_data: Données de login en JSON
        
    Returns:
        Token JWT
        
    Exemple:
        ```bash
        curl -X POST "http://localhost:8000/auth/login/json" \\
          -H "Content-Type: application/json" \\
          -d '{"username": "admin", "password": "admin123"}'
        ```
    """
    user = authenticate_user(login_data.username, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "roles": user.roles},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """
    Rafraîchit un token d'accès.
    
    Args:
        refresh_token: Token de refresh
        
    Returns:
        Nouveau token d'accès
    """
    try:
        token_data = decode_token(refresh_token)
        
        # Créer un nouveau token d'accès
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_data.username, "user_id": token_data.user_id, "roles": token_data.roles},
            expires_delta=access_token_expires
        )
        
        return Token(access_token=access_token)
        
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserInDB = Depends(get_current_user)):
    """
    Récupère les informations de l'utilisateur courant.
    
    Requiert une authentification Bearer token.
    
    Exemple:
        ```bash
        curl -X GET "http://localhost:8000/auth/me" \\
          -H "Authorization: Bearer YOUR_TOKEN_HERE"
        ```
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        roles=current_user.roles,
        is_active=current_user.is_active
    )


@router.get("/admin-only")
async def admin_only_route(user: UserInDB = Depends(require_role("admin"))):
    """
    Exemple d'endpoint accessible uniquement aux admins.
    
    Démontre l'utilisation de require_role().
    """
    return {
        "message": "Accès administrateur accordé",
        "user": user.username,
        "roles": user.roles
    }
