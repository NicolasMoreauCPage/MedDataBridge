"""
Système d'authentification JWT pour les API.

Fournit:
- Génération et validation de tokens JWT
- Dépendances FastAPI pour protéger les endpoints
- Gestion des utilisateurs basique
- Rotation de refresh tokens avec blacklist Redis
"""
from datetime import datetime, timedelta
from typing import Optional, Callable
import json
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import os
import uuid
import logging
import sys
from config.settings import settings
from app.models.users import LocalUser

logger = logging.getLogger(__name__)


# Configuration JWT
def _resolve_jwt_secret(runtime_settings=None) -> str:
    """Résout et valide la clé secrète JWT.

    En production, une clé explicite est obligatoire.
    En dev/tests, on autorise une valeur de secours pour ne pas bloquer les exécutions locales.
    """
    active_settings = runtime_settings or settings
    secret = active_settings.jwt_secret_key or os.getenv("JWT_SECRET_KEY") or active_settings.secret_key
    insecure_defaults = {
        "dev-secret-key-change-in-production",
        "change-me-in-production",
        "dev-secret-key",
    }

    if secret and secret not in insecure_defaults:
        return secret

    # Le mode LAN ne monte ni les routes d'authentification ni la frontière
    # JWT. Des routeurs partagent néanmoins les types/dépendances auth au
    # chargement : leur import ne doit pas empêcher le démarrage local ouvert.
    if not active_settings.security_enabled:
        return "local-lan-jwt-secret-not-for-production"

    testing_env = os.getenv("TESTING", "false").strip().lower() in ("1", "true", "yes", "on")
    debug_env = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes", "on")
    running_under_pytest = "pytest" in sys.modules

    if active_settings.testing or active_settings.debug or testing_env or debug_env or running_under_pytest:
        logger.warning(
            "JWT_SECRET_KEY non sécurisé détecté en mode dev/test, utilisation d'une clé de secours locale"
        )
        return "local-dev-jwt-secret-not-for-production"

    raise RuntimeError(
        "JWT_SECRET_KEY doit être défini avec une valeur forte en environnement non test"
    )


SECRET_KEY = _resolve_jwt_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configuration password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer(auto_error=False)


def _local_operator() -> "UserInDB":
    """Identité technique utilisée uniquement lorsque la sécurité est désactivée."""
    return UserInDB(
        id=0,
        username="local-operator",
        email="local@medbridge.invalid",
        hashed_password="",
        roles=["admin", "user"],
    )


class TokenData(BaseModel):
    """Données contenues dans le token."""
    username: Optional[str] = None
    user_id: Optional[int] = None
    roles: list[str] = Field(default_factory=list)


class Token(BaseModel):
    """Token de réponse."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    roles: list[str] = Field(default_factory=list)


class UserInDB(BaseModel):
    """Utilisateur en base (simulé)."""
    id: int
    username: str
    email: str
    hashed_password: str
    roles: list[str] = Field(default_factory=list)
    is_active: bool = True


def _database_user(
    username: str,
    session_factory: Callable | None = None,
) -> Optional[UserInDB]:
    """Charge un compte local depuis la fabrique de sessions de l'application."""
    if session_factory is None:
        from app.db import session_factory as default_session_factory
        session_factory = default_session_factory
    from sqlmodel import select
    with session_factory() as session:
        row = session.exec(select(LocalUser).where(LocalUser.username == username)).first()
    if row is None:
        return None
    return UserInDB(id=row.id or 0, username=row.username, email=row.email, hashed_password=row.password_hash, roles=json.loads(row.roles_json), is_active=row.is_active)


def ensure_bootstrap_admin(session_factory, runtime_settings) -> None:
    if not runtime_settings.security_enabled:
        return
    from sqlmodel import select
    with session_factory() as session:
        existing = session.exec(select(LocalUser).where(LocalUser.username == runtime_settings.bootstrap_admin_username)).first()
        if existing is None:
            session.add(LocalUser(username=runtime_settings.bootstrap_admin_username, email="", password_hash=get_password_hash(runtime_settings.bootstrap_admin_password), roles_json='["admin", "user"]'))
            session.commit()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash un mot de passe."""
    return pwd_context.hash(password)


def authenticate_user(
    username: str,
    password: str,
    *,
    session_factory: Callable | None = None,
) -> Optional[UserInDB]:
    """Authentifie un compte local persistant.

    Cette fonction ne possède volontairement aucun compte de démonstration :
    dès que les routes d'authentification sont montées, l'unique source de
    vérité est la base de données de l'instance FastAPI concernée.
    """
    user = _database_user(username, session_factory)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    *,
    runtime_settings=None,
) -> str:
    """Crée un token JWT avec jti (JWT ID) unique."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Ajouter jti (JWT ID) unique pour traçabilité et révocation
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "type": "access", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, _resolve_jwt_secret(runtime_settings), algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    data: dict,
    include_roles: bool = True,
    *,
    runtime_settings=None,
    session_factory: Callable | None = None,
) -> str:
    """Crée un refresh token avec jti unique.

    Args:
        data: Données de base (sub, user_id, roles optionnel)
        include_roles: Inclure ou non les rôles dans le refresh token. Par défaut True pour permettre leur persistance.
    """
    to_encode = data.copy()
    if include_roles and "roles" not in to_encode:
        # Si les rôles ne sont pas présents, les relire depuis les comptes locaux.
        username = to_encode.get("sub")
        if username:
            user = _database_user(username, session_factory)
            if user:
                to_encode["roles"] = user.roles
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Ajouter jti unique pour rotation et révocation
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, _resolve_jwt_secret(runtime_settings), algorithm=ALGORITHM)
    return encoded_jwt


def is_token_blacklisted(
    jti: str,
    *,
    cache=None,
    fallback_blacklist: dict[str, float] | None = None,
    security_enabled: bool | None = None,
) -> bool:
    """Vérifie si un token est blacklisté."""
    if fallback_blacklist is not None:
        expires_at = fallback_blacklist.get(jti)
        if expires_at is not None:
            if expires_at > datetime.utcnow().timestamp():
                return True
            fallback_blacklist.pop(jti, None)
        # Les tests ont volontairement Redis désactivé. Ce magasin éphémère
        # est alors la source de révocation complète, pas une simple cache
        # secondaire qui ferait échouer tous les jetons valides.
        return False
    try:
        if cache is None:
            from app.services.cache_service import get_cache_service
            cache = get_cache_service()
        if not getattr(cache, "enabled", False):
            return bool(security_enabled)
        return cache.exists(f"token:blacklist:{jti}")
    except Exception as e:
        logger.warning(f"Erreur vérification blacklist: {e}")
        # Le mode LAN n'utilise pas de tokens. En mode sécurisé, refuser un
        # token dont la révocation ne peut pas être vérifiée (fail-closed).
        return settings.security_enabled if security_enabled is None else security_enabled


def blacklist_token(
    jti: str,
    ttl_seconds: int,
    *,
    cache=None,
    fallback_blacklist: dict[str, float] | None = None,
) -> bool:
    """Ajoute un token à la blacklist.
    
    Args:
        jti: JWT ID du token
        ttl_seconds: Durée de vie en secondes (doit correspondre à l'expiration du token)
    
    Returns:
        True si ajouté avec succès, False sinon
    """
    if fallback_blacklist is not None:
        fallback_blacklist[jti] = datetime.utcnow().timestamp() + max(ttl_seconds, 0)
        return True
    try:
        if cache is None:
            from app.services.cache_service import get_cache_service
            cache = get_cache_service()
        # Stocker avec TTL pour nettoyage automatique
        return cache.set(f"token:blacklist:{jti}", {"revoked": True}, ttl=ttl_seconds)
    except Exception as e:
        logger.error(f"Erreur blacklist token: {e}")
        return False


def decode_token(
    token: str,
    check_blacklist: bool = True,
    expected_type: Optional[str] = None,
    *,
    runtime_settings=None,
    cache=None,
    fallback_blacklist: dict[str, float] | None = None,
) -> TokenData:
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
        active_settings = runtime_settings or settings
        payload = jwt.decode(token, _resolve_jwt_secret(active_settings), algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        roles: list = payload.get("roles", [])
        jti: str = payload.get("jti")
        token_type: str = payload.get("type")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if expected_type and token_type != expected_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Type de token invalide: {expected_type} requis",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Vérifier la blacklist si demandé
        if check_blacklist and jti and is_token_blacklisted(
            jti,
            cache=cache,
            fallback_blacklist=fallback_blacklist,
            security_enabled=active_settings.security_enabled,
        ):
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
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserInDB:
    """
    Dépendance FastAPI pour obtenir l'utilisateur courant.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: UserInDB = Depends(get_current_user)):
            return {"message": f"Hello {user.username}"}
    """
    app_settings = request.app.state.settings
    if not app_settings.security_enabled:
        return _local_operator()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    token_data = decode_token(
        token,
        runtime_settings=app_settings,
        cache=request.app.state.cache,
        fallback_blacklist=request.app.state.token_blacklist,
    )
    
    user = _database_user(token_data.username, request.app.state.session_factory)
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
