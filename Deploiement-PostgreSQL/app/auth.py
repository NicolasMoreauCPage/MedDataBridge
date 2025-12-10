"""
Système d'authentification JWT pour les API.

Fournit:
- Génération et validation de tokens JWT
- Dépendances FastAPI pour protéger les endpoints
- Gestion des utilisateurs basique
- Rotation de refresh tokens avec blacklist Redis
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
import uuid
import logging

logger = logging.getLogger(__name__)


# Configuration JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configuration password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Données contenues dans le token."""
    username: Optional[str] = None
    user_id: Optional[int] = None
    roles: list[str] = []


class Token(BaseModel):
    """Token de réponse."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    roles: list[str] = []


class UserInDB(BaseModel):
    """Utilisateur en base (simulé)."""
    id: int
    username: str
    email: str
    hashed_password: str
    roles: list[str] = []
    is_active: bool = True


# Base de données utilisateurs simulée (à remplacer par vraie DB)
# Hashes pré-calculés pour éviter les problèmes bcrypt à l'import
# admin:admin = $2b$12$... (bcrypt)
# user:user = $2b$12$... (bcrypt)
fake_users_db: Dict[str, UserInDB] = {
    "admin": UserInDB(
        id=1,
        username="admin",
        email="admin@example.com",
        # Password: "admin" (bcrypt hashed)
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5yx3zf8xKqw0.",
        roles=["admin", "user"],
        is_active=True
    ),
    "user": UserInDB(
        id=2,
        username="user",
        email="user@example.com",
        # Password: "user" (bcrypt hashed)
        hashed_password="$2b$12$7qlKjQeOG3ZWHbrXdD1pGuLX9dwxZxOv3D7K7XOC.qXpTfZ7r3rRC",
        roles=["user"],
        is_active=True
    )
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash un mot de passe."""
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authentifie un utilisateur."""
    user = fake_users_db.get(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un token JWT avec jti (JWT ID) unique."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Ajouter jti (JWT ID) unique pour traçabilité et révocation
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "type": "access", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, include_roles: bool = True) -> str:
    """Crée un refresh token avec jti unique.

    Args:
        data: Données de base (sub, user_id, roles optionnel)
        include_roles: Inclure ou non les rôles dans le refresh token. Par défaut True pour permettre leur persistance.
    """
    to_encode = data.copy()
    if include_roles and "roles" not in to_encode:
        # Si les rôles ne sont pas présents mais l'utilisateur existe dans la DB factice, les récupérer
        username = to_encode.get("sub")
        if username and username in fake_users_db:
            to_encode["roles"] = fake_users_db[username].roles
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Ajouter jti unique pour rotation et révocation
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def is_token_blacklisted(jti: str) -> bool:
    """Vérifie si un token est blacklisté."""
    try:
        from app.services.cache_service import get_cache_service
        cache = get_cache_service()
        return cache.exists(f"token:blacklist:{jti}")
    except Exception as e:
        logger.warning(f"Erreur vérification blacklist: {e}")
        # En cas d'erreur Redis, on autorise (fail-open pour disponibilité)
        return False


def blacklist_token(jti: str, ttl_seconds: int) -> bool:
    """Ajoute un token à la blacklist.
    
    Args:
        jti: JWT ID du token
        ttl_seconds: Durée de vie en secondes (doit correspondre à l'expiration du token)
    
    Returns:
        True si ajouté avec succès, False sinon
    """
    try:
        from app.services.cache_service import get_cache_service
        cache = get_cache_service()
        # Stocker avec TTL pour nettoyage automatique
        return cache.set(f"token:blacklist:{jti}", {"revoked": True}, ttl=ttl_seconds)
    except Exception as e:
        logger.error(f"Erreur blacklist token: {e}")
        return False


def decode_token(token: str, check_blacklist: bool = True) -> TokenData:
    """Décode et valide un token JWT.
    
    Args:
        token: Token JWT à décoder
        check_blacklist: Vérifier si le token est révoqué (défaut: True)
    
    Returns:
        TokenData avec les informations du token
    
    Raises:
        HTTPException: Si le token est invalide, expiré ou révoqué
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        roles: list = payload.get("roles", [])
        jti: str = payload.get("jti")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Vérifier la blacklist si demandé
        if check_blacklist and jti and is_token_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token révoqué",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return TokenData(username=username, user_id=user_id, roles=roles)
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """
    Dépendance FastAPI pour obtenir l'utilisateur courant.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: UserInDB = Depends(get_current_user)):
            return {"message": f"Hello {user.username}"}
    """
    token = credentials.credentials
    token_data = decode_token(token)
    
    user = fake_users_db.get(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur inactif"
        )
    
    return user


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """Dépendance pour utilisateur actif uniquement."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Utilisateur inactif")
    return current_user


def require_role(required_role: str):
    """
    Créé une dépendance qui vérifie qu'un utilisateur a un rôle spécifique.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(user: UserInDB = Depends(require_role("admin"))):
            return {"message": "Admin access"}
    """
    async def role_checker(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle '{required_role}' requis"
            )
        return user
    
    return role_checker


class RoleChecker:
    """
    Vérifie que l'utilisateur a au moins un des rôles requis.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(user: UserInDB = Depends(RoleChecker(["admin", "moderator"]))):
            return {"message": "Access granted"}
    """
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if not any(role in user.roles for role in self.allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Un des rôles suivants est requis: {', '.join(self.allowed_roles)}"
            )
        return user
