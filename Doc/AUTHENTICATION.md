# Guide d'Authentification JWT

## Vue d'ensemble

L'API MedDataBridge utilise l'authentification JWT (JSON Web Tokens) pour sécuriser les endpoints sensibles.

## Utilisateurs de test

Deux utilisateurs sont configurés par défaut:

| Username | Password | Roles | Description |
|----------|----------|-------|-------------|
| `admin` | `admin` | admin, user | Accès complet |
| `user` | `user` | user | Accès standard |

⚠️ **IMPORTANT**: Ces identifiants sont pour le développement uniquement. Changez-les en production!

## Obtenir un token

### Méthode 1: OAuth2 Form (recommandé pour outils)

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"
```

### Méthode 2: JSON

```bash
curl -X POST "http://localhost:8000/auth/login/json" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### Réponse

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## Utiliser le token

Ajoutez le token dans l'en-tête `Authorization`:

```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

## Rafraîchir un token

Lorsque le token d'accès expire (30 minutes par défaut), utilisez le refresh token:

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -d "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Durées de vie

- **Access Token**: 30 minutes
- **Refresh Token**: 7 jours

## Protéger des endpoints

### Protection simple (utilisateur authentifié)

```python
from fastapi import APIRouter, Depends
from app.auth import get_current_user, UserInDB

router = APIRouter()

@router.get("/protected")
async def protected_route(user: UserInDB = Depends(get_current_user)):
    return {"message": f"Hello {user.username}"}
```

### Protection par rôle

```python
from app.auth import require_role

@router.get("/admin-only")
async def admin_route(user: UserInDB = Depends(require_role("admin"))):
    return {"message": "Admin access granted"}
```

### Protection par plusieurs rôles

```python
from app.auth import RoleChecker

@router.get("/moderators")
async def mod_route(user: UserInDB = Depends(RoleChecker(["admin", "moderator"]))):
    return {"message": "Moderator access granted"}
```

## Configuration

Variables d'environnement:

```bash
# Clé secrète JWT (OBLIGATOIRE en production)
JWT_SECRET_KEY=votre-cle-secrete-super-longue-et-aleatoire

# Durée de vie access token (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Durée de vie refresh token (jours)
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Tester avec Swagger UI

1. Accédez à http://localhost:8000/docs
2. Cliquez sur le bouton "Authorize" (🔒)
3. Entrez vos identifiants:
   - Username: `admin`
   - Password: `admin`
4. Cliquez sur "Authorize"
5. Vous pouvez maintenant utiliser les endpoints protégés

## Exemples d'utilisation

### Python (requests)

```python
import requests

# Login
response = requests.post("http://localhost:8000/auth/login/json", 
    json={"username": "admin", "password": "admin"})
token = response.json()["access_token"]

# Utiliser le token
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8000/auth/me", headers=headers)
print(response.json())
```

### JavaScript (fetch)

```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/auth/login/json', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: 'admin', password: 'admin'})
});
const {access_token} = await loginResponse.json();

// Utiliser le token
const response = await fetch('http://localhost:8000/auth/me', {
    headers: {'Authorization': `Bearer ${access_token}`}
});
const user = await response.json();
console.log(user);
```

### cURL avec jq

```bash
# Login et extraire le token
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login/json" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  | jq -r '.access_token')

# Utiliser le token
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

## Gestion des erreurs

### 401 Unauthorized

Token invalide, expiré ou absent:

```json
{
  "detail": "Token invalide ou expiré"
}
```

**Solution**: Réauthentifiez-vous ou rafraîchissez le token.

### 403 Forbidden

Rôle insuffisant:

```json
{
  "detail": "Rôle 'admin' requis"
}
```

**Solution**: Utilisez un compte avec les permissions appropriées.

## Sécurité en production

1. **Changez JWT_SECRET_KEY**: Générez une clé aléatoire:
   ```bash
   openssl rand -hex 32
   ```

2. **Utilisez HTTPS**: Les tokens JWT doivent toujours être transmis sur HTTPS.

3. **Stockez les tokens de manière sécurisée**:
   - ❌ localStorage (vulnérable aux XSS)
   - ✅ httpOnly cookies
   - ✅ Secure storage natif (mobile)

4. **Implémentez une vraie base de données utilisateurs** au lieu de `fake_users_db`.

5. **Ajoutez une liste de révocation** pour les tokens compromis.

6. **Limitez les tentatives de login** (rate limiting).

## Migration vers production

Pour remplacer `fake_users_db` par une vraie base de données:

1. Créez un modèle SQLModel `User`:
```python
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    roles: str  # JSON array or separate table
    is_active: bool = True
```

2. Remplacez `get_fake_users_db()` par des requêtes SQL:
```python
def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
```

3. Ajoutez des endpoints de gestion utilisateurs (création, modification, suppression).

## Ressources

- [JWT.io](https://jwt.io/) - Décodeur de tokens JWT
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [OAuth2 Password Flow](https://oauth.net/2/grant-types/password/)
