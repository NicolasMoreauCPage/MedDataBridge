"""
Router pour l'authentification JWT.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer
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
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    blacklist_token
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
        data={"sub": user.username, "user_id": user.id, "roles": user.roles}
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
        data={"sub": user.username, "user_id": user.id, "roles": user.roles}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token
    )


class RefreshTokenRequest(BaseModel):
    """Requête de rafraîchissement de token."""
    refresh_token: str


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(request: RefreshTokenRequest):
    """
    Rafraîchit un token d'accès avec rotation du refresh token.
    
    Le refresh token utilisé est révoqué et un nouveau est généré (rotation).
    Cela améliore la sécurité en limitant la durée de vie effective des refresh tokens.
    
    Args:
        request: Requête contenant le refresh token
        
    Returns:
        Nouveau token d'accès ET nouveau refresh token
        
    Exemple:
        ```bash
        curl -X POST "http://localhost:8000/auth/refresh" \\
          -H "Content-Type: application/json" \\
          -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
        ```
    """
    from jose import jwt as jose_jwt
    
    try:
        # Décoder le refresh token
        token_data = decode_token(request.refresh_token)
        
        # Extraire le jti pour révocation
        payload = jose_jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        old_jti = payload.get("jti")
        
        # Révoquer l'ancien refresh token (le mettre en blacklist)
        if old_jti:
            ttl_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            blacklist_token(old_jti, ttl_seconds)
        
        # Créer un nouveau token d'accès
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_data.username, "user_id": token_data.user_id, "roles": token_data.roles},
            expires_delta=access_token_expires
        )
        
        # Créer un NOUVEAU refresh token (rotation)
        new_refresh_token = create_refresh_token(
            data={"sub": token_data.username, "user_id": token_data.user_id, "roles": token_data.roles}
        )
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            roles=token_data.roles
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré"
        )


@router.post("/logout")
async def logout(
    token: str = Depends(HTTPBearer()),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Révoque le token d'accès en cours en l'ajoutant à la blacklist.
    Le client doit supprimer son refresh token localement.
    """
    from jose import jwt as jose_jwt
    
    try:
        # Extraire le jti du token d'accès
        payload = jose_jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        
        if jti:
            # Calculer le TTL basé sur l'expiration du token
            exp = payload.get("exp", 0)
            import time
            ttl_seconds = max(0, int(exp - time.time()))
            
            # Ajouter à la blacklist
            blacklist_token(jti, ttl_seconds)
        
        return {"message": "Déconnexion réussie"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la déconnexion"
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
