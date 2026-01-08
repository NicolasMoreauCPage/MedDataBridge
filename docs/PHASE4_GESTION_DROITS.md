# 🔐 Phase 4.2 : Gestion des Droits d'Accès

## 🎯 Objectif
Mettre en place un système de gestion des droits permettant de contrôler l'accès aux fonctionnalités selon les profils utilisateurs et d'auditer toutes les modifications.

---

## 👥 Rôles Utilisateurs

### 1. **Administrateur Système** (`admin`)
- **Périmètre** : Toute l'application
- **Droits** :
  - ✅ Créer/modifier/supprimer tous les éléments de structure
  - ✅ Gérer les utilisateurs et leurs droits
  - ✅ Accéder aux logs d'audit
  - ✅ Configuration système (endpoints, transport, etc.)
  - ✅ Import/export Excel
  - ✅ Validation modifications critiques

### 2. **Gestionnaire d'Établissement** (`gestionnaire`)
- **Périmètre** : Son établissement (EJ) uniquement
- **Droits** :
  - ✅ Voir/modifier structure de son établissement
  - ✅ Créer/modifier pôles, services, UF, UH, chambres, lits
  - ✅ Analytics et KPIs de son établissement
  - ✅ Configuration alertes
  - ✅ Export rapports Excel/PDF
  - ❌ Supprimer EG ou Pôles (validation admin requise)
  - ❌ Gérer les utilisateurs
  - ❌ Voir autres établissements

### 3. **Responsable Médical** (`medical`)
- **Périmètre** : Ses services/UF uniquement
- **Droits** :
  - ✅ Voir structure de ses services
  - ✅ Modifier capacités, effectifs, organisation UF
  - ✅ Analytics de ses services
  - ❌ Créer/supprimer services ou UF
  - ❌ Modifier codes FINESS/UM
  - ❌ Accès autres services

### 4. **Personnel DIM** (`dim`)
- **Périmètre** : Lecture seule étendue
- **Droits** :
  - ✅ Voir toute la structure (lecture seule)
  - ✅ Analytics et statistiques
  - ✅ Export rapports pour PMSI
  - ✅ Validation codes FINESS/UM
  - ❌ Modifier quoi que ce soit
  - ❌ Accès configuration

### 5. **Personnel Technique** (`technique`)
- **Périmètre** : Gestion locaux et équipements
- **Droits** :
  - ✅ Voir structure hébergement (UH, chambres, lits)
  - ✅ Modifier équipements, surfaces, états
  - ❌ Modifier organisation médicale
  - ❌ Accès données patients

### 6. **Invité/Consultation** (`viewer`)
- **Périmètre** : Lecture seule limitée
- **Droits** :
  - ✅ Voir structure (sans données sensibles)
  - ❌ Aucune modification
  - ❌ Export
  - ❌ Analytics

---

## 🔒 Matrice des Permissions

| Ressource | Admin | Gestionnaire | Médical | DIM | Technique | Viewer |
|-----------|-------|--------------|---------|-----|-----------|--------|
| **EG (Entité Géographique)** |
| Créer | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Lire | ✅ | ✅ (son EJ) | ✅ (ses services) | ✅ | ✅ | ✅ |
| Modifier | ✅ | ✅ (son EJ) | ❌ | ❌ | ❌ | ❌ |
| Supprimer | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Pôle** |
| Créer | ✅ | ✅ (dans son EJ) | ❌ | ❌ | ❌ | ❌ |
| Lire | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Modifier | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Supprimer | ✅ | ⚠️ (validation admin) | ❌ | ❌ | ❌ | ❌ |
| **Service** |
| Créer | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Lire | ✅ | ✅ | ✅ (ses services) | ✅ | ✅ | ✅ |
| Modifier | ✅ | ✅ | ✅ (ses services) | ❌ | ❌ | ❌ |
| Supprimer | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **UF (Unité Fonctionnelle)** |
| Créer | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Lire | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Modifier | ✅ | ✅ | ✅ (capacité, effectifs) | ❌ | ❌ | ❌ |
| Supprimer | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **UH/Chambre/Lit** |
| Créer | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Lire | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Modifier | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Supprimer | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Analytics/Rapports** |
| Voir KPIs | ✅ | ✅ (son EJ) | ✅ (ses services) | ✅ | ❌ | ❌ |
| Config alertes | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Export Excel/PDF | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Administration** |
| Gérer utilisateurs | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Logs audit | ✅ | ⚠️ (son EJ) | ❌ | ⚠️ (lecture) | ❌ | ❌ |
| Import Excel | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 📝 Logs d'Audit

### Événements Loggés
- **Création** d'entité (EG, Pôle, Service, UF, UH, Chambre, Lit)
- **Modification** de champs (ancien → nouveau)
- **Suppression** d'entité
- **Déplacement** (drag & drop)
- **Import Excel** (fichier, nombre lignes, résultat)
- **Export** rapports
- **Connexion/Déconnexion** utilisateurs
- **Changement** de droits utilisateur

### Format Log
```json
{
  "id": 12345,
  "timestamp": "2026-01-08T15:30:00Z",
  "user_id": 42,
  "user_name": "Dr. Dupont",
  "user_role": "gestionnaire",
  "action": "UPDATE",
  "entity_type": "service",
  "entity_id": 123,
  "entity_name": "Cardiologie",
  "changes": {
    "field": "nom",
    "old_value": "Cardio",
    "new_value": "Cardiologie"
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "success": true,
  "error_message": null
}
```

### Table Audit
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    user_name TEXT,
    user_role TEXT,
    action TEXT, -- CREATE, UPDATE, DELETE, MOVE, EXPORT, LOGIN, etc.
    entity_type TEXT, -- eg, pole, service, uf, uh, chambre, lit
    entity_id INTEGER,
    entity_name TEXT,
    changes JSON, -- {field, old_value, new_value}
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN,
    error_message TEXT
);
```

---

## 🏗️ Architecture Technique

### 1. Modèle Utilisateur

```python
# app/models/user.py

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    GESTIONNAIRE = "gestionnaire"
    MEDICAL = "medical"
    DIM = "dim"
    TECHNIQUE = "technique"
    VIEWER = "viewer"

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    role: UserRole
    
    # Périmètre d'accès
    ej_id: Optional[int] = Field(default=None, foreign_key="entitegeographique.id")
    service_ids: Optional[str] = Field(default=None)  # JSON array "[1, 2, 3]"
    
    # Métadonnées
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # Relations
    audit_logs: list["AuditLog"] = Relationship(back_populates="user")
```

### 2. Middleware d'Autorisation

```python
# app/middleware/authorization.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class AuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Récupérer l'utilisateur courant
        user = request.state.user if hasattr(request.state, "user") else None
        
        if not user:
            # Routes publiques autorisées
            if request.url.path.startswith("/docs") or request.url.path.startswith("/health"):
                return await call_next(request)
            raise HTTPException(status_code=401, detail="Non authentifié")
        
        # Vérifier permissions selon route et rôle
        if not self.has_permission(user, request):
            raise HTTPException(status_code=403, detail="Accès refusé")
        
        response = await call_next(request)
        return response
    
    def has_permission(self, user, request: Request) -> bool:
        # Logique de vérification des permissions
        # Basée sur la matrice ci-dessus
        pass
```

### 3. Décorateurs de Permission

```python
# app/utils/permissions.py

from functools import wraps
from fastapi import HTTPException, Depends
from app.auth import get_current_user
from app.models.user import User, UserRole

def require_role(*roles: UserRole):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user: User = Depends(get_current_user), **kwargs):
            if current_user.role not in roles:
                raise HTTPException(status_code=403, detail=f"Rôle requis: {roles}")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

def require_permission(action: str, entity_type: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, entity_id: int, current_user: User = Depends(get_current_user), **kwargs):
            if not check_permission(current_user, action, entity_type, entity_id):
                raise HTTPException(status_code=403, detail="Permission refusée")
            return await func(*args, entity_id=entity_id, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# Utilisation dans un endpoint:
@router.patch("/service/{service_id}")
@require_permission("update", "service")
async def update_service(service_id: int, data: dict, current_user: User):
    # Modification autorisée
    pass
```

### 4. Logging d'Audit

```python
# app/services/audit_service.py

from sqlmodel import Session
from app.models.audit import AuditLog
from app.models.user import User

class AuditService:
    @staticmethod
    def log_action(
        session: Session,
        user: User,
        action: str,
        entity_type: str,
        entity_id: int,
        entity_name: str,
        changes: dict = None,
        ip_address: str = None,
        success: bool = True,
        error_message: str = None
    ):
        log = AuditLog(
            user_id=user.id,
            user_name=user.full_name,
            user_role=user.role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            changes=changes,
            ip_address=ip_address,
            success=success,
            error_message=error_message
        )
        session.add(log)
        session.commit()

# Utilisation dans un endpoint:
@router.patch("/service/{service_id}")
async def update_service(
    service_id: int, 
    data: dict, 
    current_user: User,
    request: Request,
    session: Session = Depends(get_session)
):
    service = session.get(Service, service_id)
    old_name = service.nom
    service.nom = data["nom"]
    
    session.add(service)
    session.commit()
    
    # Log audit
    AuditService.log_action(
        session=session,
        user=current_user,
        action="UPDATE",
        entity_type="service",
        entity_id=service_id,
        entity_name=service.nom,
        changes={"field": "nom", "old_value": old_name, "new_value": data["nom"]},
        ip_address=request.client.host
    )
    
    return service
```

---

## 📌 Plan de Développement

### Sprint 4.2.1 : Authentification & Utilisateurs _(1 jour)_
- [ ] Créer modèle User avec rôles
- [ ] Endpoints authentification (login, logout, refresh token)
- [ ] Middleware authentification JWT
- [ ] Page admin gestion utilisateurs

### Sprint 4.2.2 : Autorisations _(1 jour)_
- [ ] Middleware vérification permissions
- [ ] Décorateurs @require_role, @require_permission
- [ ] Filtrage données selon périmètre user
- [ ] Tests unitaires permissions

### Sprint 4.2.3 : Audit Logging _(0.5 jour)_
- [ ] Modèle AuditLog
- [ ] AuditService avec log_action()
- [ ] Intégration dans tous les endpoints CRUD
- [ ] Page admin visualisation logs

### Sprint 4.2.4 : UI Permissions _(0.5 jour)_
- [ ] Affichage conditionnel boutons (ex: Supprimer seulement si admin)
- [ ] Messages d'erreur utilisateurs (403 Forbidden)
- [ ] Profil utilisateur (rôle, périmètre, dernière connexion)

---

## ✅ Critères de Validation

- ✅ Un gestionnaire ne peut PAS modifier un autre établissement
- ✅ Un médical ne peut PAS supprimer un service
- ✅ Un viewer ne peut RIEN modifier
- ✅ Tous les changements sont loggés dans audit_logs
- ✅ Les logs contiennent user, timestamp, action, before/after
- ✅ Les admins peuvent voir tous les logs
- ✅ Interface utilisateurs fonctionnelle (CRUD users + assign roles)

---

**Prêt pour implémentation sécurisée ! 🔐**
