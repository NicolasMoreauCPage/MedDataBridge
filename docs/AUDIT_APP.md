
# Audit approfondi du dossier `app/` – MedData Bridge

## Synthèse
MedData Bridge est une plateforme d’interopérabilité santé basée sur FastAPI et SQLModel, facilitant l’échange de données médicales (HL7, FHIR, HPRIM) et la gestion d’entités métier via une interface web. L’architecture est robuste et modulaire, mais plusieurs axes d’amélioration sont identifiés pour garantir la sécurité, la performance et la maintenabilité à l’échelle.

---

## Points forts

- **Modularité** : séparation claire des responsabilités (routeurs, services, modèles)
- **ORM moderne** : SQLModel (type safety, validation, migrations possibles)
- **Middlewares personnalisés** : gestion avancée des sessions/contextes/messages flash
- **Gestion du cycle de vie** : initialisation propre (DB, serveurs MLLP, scheduler)
- **Base de tests** : structure de tests variée (unitaires, intégration, sécurité, performance)

---

## Axes d’amélioration majeurs

### 1. Fragmentation excessive des modèles
**Constat** : Plus de 15 fichiers de modèles (`models_*.py`) rendent la navigation et la maintenance difficiles.

**Exemple** :
```text
app/models.py
app/models_contacts.py
app/models_context.py
... (voir liste complète dans le projet)
```

**Pistes d’amélioration** :
- Regrouper les modèles par domaine métier (core, structure, transport, scenarios)
- Créer un module `models/` avec sous-modules et un `__init__.py` centralisé
- Documenter les dépendances entre modèles

### 2. Imports circulaires
**Constat** : Présence d’astuces pour éviter les imports circulaires, signe d’un couplage trop fort entre certains modules.

**Exemple** :
```python
# Import ght router first to avoid circular imports
import app.routers.ght as ght
```

**Pistes d’amélioration** :
- Refactoriser les dépendances entre routeurs (injection de dépendances, registry)
- Limiter les imports croisés, privilégier l’inversion de dépendance

### 3. Base de données SQLite en production
**Constat** : SQLite reste la base par défaut, même en production, ce qui limite la scalabilité et la robustesse.

**Exemple** :
```python
engine = create_engine(
    "sqlite:///./medbridge.db",
    ...
)
```

**Pistes d’amélioration** :
- Prévoir une configuration PostgreSQL pour la production
- Utiliser Alembic pour les migrations
- Centraliser la configuration DB (fichier unique, variables d’environnement obligatoires)

---

## Sécurité

### 1. Authentification simpliste
**Constat** : Utilisateurs codés en dur dans `auth.py`, pas de gestion réelle des comptes ni de stockage sécurisé.

**Exemple** :
```python
fake_users_db = { ... }
```

**Pistes d’amélioration** :
- Intégrer une vraie base utilisateurs (SQL, LDAP, OAuth2)
- Ajouter la gestion des rôles et permissions
- Privilégier OAuth2/OpenID Connect pour l’API

### 2. Gestion des secrets
**Constat** : Clé JWT par défaut, risque de fuite en production.

**Exemple** :
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
```

**Pistes d’amélioration** :
- Rendre obligatoire la définition des secrets en production
- Mettre en place une rotation automatique des clés
- Stocker les secrets dans un vault sécurisé

### 3. Rate limiting absent
**Constat** : Aucun contrôle de débit sur les endpoints, risque de DoS.

**Pistes d’amélioration** :
- Ajouter un middleware de rate limiting (Redis, in-memory, etc.)
- Journaliser et alerter sur les abus

### 4. Logs et données sensibles
**Constat** : Logs détaillés activables globalement, risque d’exposition de données de santé.

**Pistes d’amélioration** :
- Filtrer/sanitiser les logs (PHI, PII)
- Chiffrer les logs sensibles
- S’assurer de la conformité RGPD/HIPAA

---

## Performance

### 1. Sessions DB longues
**Constat** : Sessions maintenues ouvertes, risque de fuite de connexions.

**Pistes d’amélioration** :
- Utiliser des sessions courtes et le pooling
- Optimiser les accès concurrents

### 2. Absence de cache
**Constat** : Pas de stratégie de cache (Redis, HTTP) pour les données fréquentes.

**Pistes d’amélioration** :
- Mettre en place un cache Redis pour les vocabulaires, métadonnées, etc.
- Utiliser le cache HTTP pour les endpoints statiques

### 3. Logique métier dans les templates
**Constat** : Calculs et logique dans les templates Jinja2, ce qui nuit à la maintenabilité.

**Pistes d’amélioration** :
- Déplacer la logique métier dans les services Python
- Pré-calculer les données dans les vues

---

## Maintenabilité

### 1. Mélange de langues
**Constat** : Variables et commentaires en français et anglais, ce qui nuit à la cohérence.

**Pistes d’amélioration** :
- Standardiser la langue du code (anglais recommandé)
- Documenter en français si besoin, mais garder le code homogène

### 2. Documentation
**Constat** : Docstrings inégales, documentation API partielle.

**Pistes d’amélioration** :
- Générer une documentation OpenAPI complète
- Ajouter des guides d’architecture et de déploiement

### 3. Gestion d’erreurs
**Constat** : Exceptions non standardisées, gestion disparate.

**Pistes d’amélioration** :
- Créer des classes d’exceptions personnalisées
- Ajouter un middleware global de gestion d’erreurs

---

## Qualité, tests et CI/CD

### 1. Couverture de tests
**Constat** : Structure de tests présente, mais couverture à vérifier.

**Pistes d’amélioration** :
- Ajouter des tests end-to-end et de sécurité (OWASP)
- Automatiser la mesure de couverture (>80%)

### 2. CI/CD
**Constat** : Pas de pipeline CI/CD visible.

**Pistes d’amélioration** :
- Mettre en place GitHub Actions ou équivalent
- Automatiser les tests et le déploiement

---

## Déploiement, configuration et monitoring

### 1. Configuration
**Constat** : Paramètres dispersés, pas de validation centralisée.

**Pistes d’amélioration** :
- Centraliser la configuration (fichier unique, validation au démarrage)
- Documenter toutes les variables d’environnement

### 2. Monitoring
**Constat** : Peu de métriques exposées, logs peu structurés.

**Pistes d’amélioration** :
- Ajouter des métriques Prometheus
- Structurer les logs (JSON, ELK stack)
- Mettre en place des alertes automatiques

---

## Synthèse des recommandations prioritaires

### Phase 1 (Sécurité – Critique)
1. Remplacer l’authentification simulée par une vraie gestion des utilisateurs
2. Migrer la base de données vers PostgreSQL
3. Implémenter un rate limiting global
4. Sécuriser la gestion des secrets (vault, rotation)

### Phase 2 (Performance)
1. Optimiser la gestion des sessions DB
2. Mettre en place un cache Redis
3. Refactorer la logique métier hors des templates

### Phase 3 (Maintenabilité)
1. Regrouper les modèles par domaine
2. Résoudre les imports circulaires
3. Standardiser la langue et la documentation

### Phase 4 (Production-Readiness)
1. Mettre en place une CI/CD complète
2. Ajouter du monitoring et des alertes
3. Réaliser des tests de charge et de sécurité

---

## Indicateurs de suivi

- **Complexité cyclomatique** : viser la simplicité, refactoriser les fonctions longues
- **Couverture de tests** : objectif >80%
- **Temps de réponse** : benchmarks réguliers
- **Security score** : audit externe annuel

---

*Audit réalisé le 26 décembre 2025 par analyse statique du code source. Pour toute évolution, suivre les axes proposés ci-dessus.*

#### 1. Fragmentation Excessive des Modèles
**Problème** : 15+ fichiers de modèles séparés (`models_*.py`) rendent la navigation difficile
```
app/models.py (456 lignes)
app/models_contacts.py
app/models_context.py
app/models_endpoints.py
app/models_identifiers.py
app/models_practitioners.py
app/models_scenario_config.py
app/models_scenario_runs.py
app/models_scenarios.py
app/models_shared.py
app/models_structure.py
app/models_structure_fhir.py
app/models_transport.py
app/models_vocabulary.py
app/models_workflows.py
```

**Recommandations** :
- Regrouper par domaine métier (core, structure, transport, scenarios)
- Créer un `__init__.py` central pour les imports
- Utiliser des modules plutôt que des fichiers plats

#### 2. Gestion des Imports Circulaires
**Problème** : Mention explicite d'imports circulaires dans `app.py`
```python
# Import ght router first to avoid circular imports
import app.routers.ght as ght
```

**Recommandations** :
- Refactorer les dépendances entre routeurs
- Utiliser des dépendances injectées plutôt que des imports directs
- Implémenter un système de registry pour les routeurs

#### 3. Base de Données SQLite en Production
**Problème** : SQLite utilisé même en prod, malgré les optimisations WAL
```python
engine = create_engine(
    "sqlite:///./medbridge.db",
    pool_size=20, max_overflow=30,  # Tentatives d'optimisation
    pool_timeout=60, pool_pre_ping=True
)
```

**Recommandations** :
- Migrer vers PostgreSQL pour la production
- Prévoir une configuration multi-base de données
- Implémenter des migrations Alembic complètes

## Sécurité

### Problèmes Critiques

#### 1. Authentification Simpliste
**Problème** : Utilisateurs codés en dur dans `auth.py`
```python
fake_users_db: Dict[str, UserInDB] = {
    "admin": UserInDB(
        hashed_password="$2b$12$...",  # Hash pré-calculé
        roles=["admin", "user"]
    ),
    "user": UserInDB(...)
}
```

**Recommandations** :
- Implémenter une vraie base utilisateurs
- Ajouter OAuth2/OpenID Connect
- Gestion des rôles et permissions granulaire

#### 2. Secret JWT Codé en Dur
**Problème** : Fallback à une clé de dev
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
```

**Recommandations** :
- Générer dynamiquement des secrets
- Utiliser des variables d'environnement obligatoires
- Rotation automatique des clés

#### 3. Absence de Rate Limiting
**Problème** : Aucun contrôle de débit visible sur les endpoints

**Recommandations** :
- Implémenter rate limiting (Redis-based)
- Protection contre les attaques par déni de service
- Monitoring des requêtes suspectes

### Données Sensibles

#### 1. Logs Détaillés en Production
**Problème** : Logs MLLP détaillés activables globalement
```python
if os.getenv("MLLP_TRACE", "0") in ("1","true","True"):
    logging.getLogger("mllp").setLevel(logging.DEBUG)
```

**Recommandations** :
- Sanitiser les logs pour les données PHI
- Chiffrement des logs sensibles
- Conformité RGPD/HIPAA

## Performance

### Points d'Amélioration

#### 1. Sessions DB Longues
**Problème** : Sessions maintenues ouvertes dans les dépendances FastAPI
```python
def get_session():
    with Session(engine) as session:
        yield session
```

**Recommandations** :
- Utiliser des sessions courtes avec pooling
- Implémenter du caching (Redis) pour les données fréquentes
- Optimiser les requêtes N+1

#### 2. Pas de Cache Visible
**Problème** : Aucune stratégie de cache implémentée

**Recommandations** :
- Cache Redis pour les vocabulaires et métadonnées
- Cache HTTP pour les endpoints statiques
- Invalidation intelligente du cache

#### 3. Calculs en Ligne dans les Templates
**Problème** : Logique métier dans les templates Jinja2

**Recommandations** :
- Déplacer la logique vers les services
- Utiliser des context processors
- Pré-calculer les données dans les vues

## Maintenabilité

### Code Quality

#### 1. Mélange Langues
**Problème** : Code en français et anglais
```python
# Identité
family: str = Field(alias="nom")  # Nom de famille (obligatoire)
given: Optional[str] = None  # Prénom
```

**Recommandations** :
- Standardiser sur l'anglais
- Documentation en français si nécessaire
- Noms de variables consistants

#### 2. Documentation Insuffisante
**Problème** : Docstrings présents mais pas systématiques

**Recommandations** :
- Documentation API complète (OpenAPI)
- Guides d'architecture et de déploiement
- Tests documentés

#### 3. Gestion d'Erreurs Inconsistante
**Problème** : Exceptions non standardisées

**Recommandations** :
- Classes d'exceptions personnalisées
- Middleware de gestion d'erreurs global
- Logging structuré des erreurs

## Tests et Qualité

### Couverture
**État** : Structure de tests présente mais couverture à vérifier

**Recommandations** :
- Tests d'intégration end-to-end
- Tests de performance automatisés
- Tests de sécurité (OWASP)

### CI/CD
**Manquant** : Pas de configuration CI/CD visible

**Recommandations** :
- GitHub Actions ou équivalent
- Tests automatisés à chaque push
- Déploiement automatisé

## Déploiement et Ops

### Configuration
**Problème** : Configuration éparpillée

**Recommandations** :
- Fichier de configuration centralisé
- Variables d'environnement documentées
- Validation de configuration au démarrage

### Monitoring
**Manquant** : Métriques limitées

**Recommandations** :
- Métriques Prometheus
- Logs structurés (ELK stack)
- Alertes automatiques

## Recommandations Prioritaires

### Phase 1 (Sécurité - Critique)
1. Remplacer l'authentification simulée
2. Migrer vers PostgreSQL
3. Implémenter rate limiting
4. Sécuriser la gestion des secrets

### Phase 2 (Performance)
1. Optimiser les sessions DB
2. Implémenter le caching Redis
3. Refactorer la logique des templates

### Phase 3 (Maintenabilité)
1. Regrouper les modèles par domaine
2. Résoudre les imports circulaires
3. Standardiser la langue et la documentation

### Phase 4 (Production-Readiness)
1. Configuration CI/CD
2. Monitoring complet
3. Tests de charge

## Métriques d'Amélioration

- **Complexité Cyclomatique** : Réduire en refactorant les fonctions longues
- **Coverage de Tests** : Viser 80%+ de couverture
- **Temps de Réponse** : Benchmarks avant/après optimisations
- **Security Score** : Audit sécurité indépendant

---

*Audit réalisé le 26 décembre 2025 par analyse statique du code source.*