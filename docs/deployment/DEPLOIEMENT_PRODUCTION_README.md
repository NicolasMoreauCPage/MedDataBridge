# MedDataBridge - Instructions de Déploiement Production

## 🚨 Dépannage - Base de Données Corrompue

### Erreur: `database disk image is malformed` (persistante)

**Cause :** La base de données SQLite reste corrompue même après suppression du fichier. Cela peut être dû à :
- Processus SQLite encore actifs
- Fichiers temporaires (WAL/SHM) non supprimés
- Cache système ou verrouillages persistants

**Solution de secours :**
```bash
# 1. Utiliser le script de récupération amélioré
python recover_database_v2.py meddatabridge.db

# 2. Si cela ne fonctionne pas, arrêt forcé complet
# Tuer tous les processus Python/SQLite
pkill -9 python
pkill -9 sqlite3

# Supprimer manuellement tous les fichiers liés
rm -f meddatabridge.db*
rm -f /tmp/sqlite_*

# 3. Recréer la base
alembic upgrade head
```

### Erreur: `database disk image is malformed` (simple)

**Cause :** La base de données SQLite est corrompue (souvent due à un arrêt brutal ou problème disque).

**Solution :**
```bash
# 1. Sauvegarder la base corrompue
cp meddatabridge.db meddatabridge.db.corrupted

# 2. Utiliser le script de récupération
python recover_database.py meddatabridge.db

# 3. Si la récupération échoue, recréer la base
rm meddatabridge.db
alembic upgrade head  # Recréera la base et appliquera toutes les migrations
```

### Erreur: `NOT NULL constraint failed: interopscenario.preserve_intervals`

**Cause :** Migration déployée avec colonnes manquantes ou incompatibles.

**Solution :** Utilisez la dernière archive de déploiement qui contient la migration corrigée.

### Erreur: `NameError: name 'now' is not defined`

**Cause :** Variable `now` utilisée dans la migration sans être définie.

**Solution :** La migration a été corrigée pour définir `now = datetime.utcnow()` au début de la fonction upgrade.

---

## 📦 Archive de Déploiement

L'archive `meddatabridge-deployment-20251211-153242.zip` contient :
- Sources de l'application MedDataBridge
- Migration Alembic pour les scénarios IHE PAM (compatible SQLite/PostgreSQL)
- Données JSON des 113 scénarios IHE PAM
- Scripts de déploiement et validation

## 🔧 Corrections et Compatibilité

### ✅ Fix SQLite - Colonnes Manquantes
**Problème résolu :** Erreur `NOT NULL constraint failed: interopscenario.preserve_intervals`

**Cause :** La migration Alembic ne définissait pas toutes les colonnes du modèle `InteropScenario`, causant des erreurs de contrainte NOT NULL lors de l'insertion.

**Solution appliquée :**
- Ajout des colonnes manquantes dans la définition de table Alembic :
  - `ght_context_id` (Integer, nullable)
  - `time_anchor_mode` (String, nullable)
  - `time_anchor_days_offset` (Integer, nullable)
  - `time_fixed_start_iso` (String, nullable)
  - `preserve_intervals` (Boolean, default=True)
  - `jitter_min_minutes` (Integer, nullable)
  - `jitter_max_minutes` (Integer, nullable)
  - `apply_jitter_on_events` (String, default="A02,A03,A06,A07,A08")

**Validation :** Migration testée avec succès sur SQLite sans erreurs de contraintes.

### ✅ Compatibilité Base de Données
- ✅ SQLite (production actuelle)
- ✅ PostgreSQL (futur déploiement)
- ✅ Valeurs par défaut appropriées pour tous les champs optionnels

## 🚀 Procédure de Déploiement

### Prérequis
- Python 3.10+
- Base de données configurée (SQLite/PostgreSQL)
- Alembic installé dans l'environnement de production

### Étapes

#### 1. Préparation
```bash
# Sur le serveur de production
mkdir -p /opt/meddatabridge
cd /opt/meddatabridge
```

#### 2. Déploiement
```bash
# Copier l'archive depuis votre machine locale
# scp meddatabridge-deployment-sqlite-fix.zip user@prod-server:/tmp/

# Extraire l'archive
unzip /tmp/meddatabridge-deployment-sqlite-fix.zip
cd meddatabridge-deployment-*

# ⚠️  IMPORTANT: Ne PAS activer de venv local en production
# L'environnement virtuel doit être géré par le système de déploiement

# Installer les dépendances dans l'environnement système
pip install -r requirements.txt
# ou pip3 install -r requirements.txt
# ou utiliser le gestionnaire de paquets de votre système
```

#### 3. Configuration
```bash
# Configurer la base de données dans app/config.py ou variables d'environnement
# Exemple pour PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/meddatabridge_prod

# Configurer les autres paramètres de production
# - Clés API
# - URLs des endpoints
# - Paramètres de sécurité
```

#### 4. Migration Base de Données
```bash
# IMPORTANT: Exécuter dans l'environnement de production (PAS dans un venv local)

# Appliquer toutes les migrations
alembic upgrade head

# Vérifier que la migration IHE PAM a été appliquée
alembic current  # Doit afficher: bdebea0e6af4 (add_ihe_pam_scenarios_data)
```

#### 5. Validation
```bash
# Vérifier que les scénarios IHE PAM sont présents
python -c "
from app.db import engine
from app.models_scenarios import InteropScenario
from sqlmodel import Session, select

with Session(engine) as session:
    count = session.exec(select(InteropScenario).where(InteropScenario.name.like('%IHE PAM%'))).all()
    print(f'✅ {len(count)} scénarios IHE PAM déployés')
"

# Démarrer l'application
uvicorn app.app:app --host 0.0.0.0 --port 8000
```

## 🔧 Environnements Virtuels

### ❌ Erreur Courante : Venv Local en Production

```bash
# 🚫 NE PAS FAIRE en production
[meddata@qualifinterop meddata-bridge]$ source .venv/bin/activate
-bash: .venv/bin/activate: Aucun fichier ou dossier de ce type
```

**Pourquoi cette erreur ?**
- L'archive de déploiement ne contient PAS de répertoire `.venv/`
- Les environnements virtuels locaux sont pour le développement uniquement
- En production, utiliser l'environnement système ou conteneurisé

### Développement (avec venv local)
```bash
# Sur votre machine de développement
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate     # Windows

# Ici vous pouvez utiliser alembic pour tester
alembic upgrade head
```

### Production (environnement système)
```bash
# En production - AUCUN venv local
# Alembic doit être installé globalement ou dans l'environnement système

# Vérifier que alembic est disponible
which alembic
# ou
alembic --version

# Appliquer les migrations
alembic upgrade head
```

## 📊 Contenu Déployé

Après migration, la base contiendra :
- **113 scénarios IHE PAM** avec leurs métadonnées
- **515 étapes HL7** complètes
- **Catégories** : HOSPITALISATION (23), MATERNITE (1), PREADMISSION (8), SEANCES (4), GENERAL (77)

## 🔄 Rollback (si nécessaire)

```bash
# Revenir à la migration précédente
alembic downgrade -1

# Vérifier
alembic current
```

## 📞 Support

En cas de problème :

### Erreur ".venv/bin/activate: Aucun fichier ou dossier de ce type"
```bash
# ✅ Solution : Ne pas utiliser de venv local en production
# Vérifier que alembic est installé globalement
pip list | grep alembic
# ou
alembic --version

# Si manquant, installer globalement
pip install alembic
# ou
sudo pip install alembic
```

### Autres problèmes :
1. **Erreur SQLite "RETURNING": syntax error**
   ```bash
   # ✅ Solution : Migration corrigée pour compatibilité SQLite
   # La migration utilise maintenant une approche compatible avec SQLite
   alembic upgrade head  # Fonctionne maintenant avec SQLite et PostgreSQL
   ```

2. Vérifier les logs Alembic : `alembic history`
3. Contrôler la configuration DB
4. Valider que l'environnement de production a accès à Alembic
5. Consulter les logs de l'application

---

**Archive générée le :** Décembre 2025
**Migration IHE PAM :** `bdebea0e6af4`
**Scénarios déployés :** 113