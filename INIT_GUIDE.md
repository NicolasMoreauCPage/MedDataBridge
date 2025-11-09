# Guide d'initialisation de la base de données

## Vue d'ensemble

Ce projet fournit plusieurs scripts pour initialiser la base de données SQLite locale (`medbridge.db`) avec toutes les données nécessaires pour le développement et les tests.

## Script principal recommandé

### `init_db.py` ⭐

Script d'initialisation complète tout-en-un (recommandé pour démarrer).

```bash
# Initialisation complète (première utilisation)
python init_db.py

# Réinitialisation totale (supprime DB existante)
python init_db.py --reset

# Sans vocabulaires
python init_db.py --skip-vocab

# Sans population de patients
python init_db.py --skip-population
```

**Ce qui est initialisé:**
- ✅ **Schéma** : Toutes les tables (40+)
- ✅ **Vocabulaires** : 35 systèmes, 207 valeurs (codes IHE PAM FR, FHIR, types mouvements…)
- ✅ **Structure multi-EJ** : 4 Entités Juridiques réalistes
  - CHU (FINESS 020000000) : MCO complet avec urgences, cardiologie, maternité
  - Hôpital local (030000000) : Structure simplifiée
  - EHPAD (040000000) : Hébergement médicalisé
  - Psychiatrie (050000000) : Pôles spécialisés
- ✅ **Hiérarchie complète** : EG → Pôles → Services → UF → UH → Chambres → Lits
- ✅ **Endpoints** : 12 endpoints (MLLP RECV/SEND + FHIR API pour chaque EJ)
- ✅ **Namespaces d'identifiants** : 13 namespaces
  - Par EJ : IPP, NDA, VENUE (avec OID structurés)
  - Global : STRUCTURE
- ✅ **Population** : 120 patients avec dossiers, venues et mouvements (A01, A02, A03)

**Idempotence:** Tous les appels sont sûrs - ré-exécuter `init_db.py` ne créera pas de doublons.

---

## Scripts modulaires (usage avancé)

### 1. `tools/init_vocabularies.py`

Charge uniquement les vocabulaires standards.

```bash
python tools/init_vocabularies.py
```

**Contenu:**
- Codes IHE PAM FR (types patient, mouvements, locations)
- Vocabulaires FHIR (spécialités, rôles, types organisation)
- Codes métiers (statuts, modes, natures mouvement ZBE)

### 2. `tools/init_extended_demo.py`

Crée la structure multi-EJ + endpoints + namespaces + population.

```bash
python tools/init_extended_demo.py
```

**Contenu:**
- Structure hospitalière étendue (4 EJ avec hiérarchie complète)
- 12 endpoints MLLP et FHIR
- 13 namespaces d'identifiants (IPP/NDA/VENUE par EJ)
- 120 patients avec mouvements réalistes

### 3. `scripts_manual/init_full.py` (legacy)

Ancien script avec options avancées (conservé pour compatibilité).

```bash
# Avec structure étendue et vocabulaires
python scripts_manual/init_full.py --extended-structure --with-vocab

# Avec seed riche et scénarios démo
python scripts_manual/init_full.py --rich-seed --demo-scenarios
```

---

## Vérification post-initialisation

### Compter les entités créées

```bash
# Via script dédié
python tools/check_namespaces.py

# Via Python one-liner
python -c "
from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import GHTContext, EntiteJuridique, IdentifierNamespace
from app.models_vocabulary import VocabularySystem, VocabularyValue
from app.models import Patient

with Session(engine) as s:
    ctx = len(s.exec(select(GHTContext)).all())
    ej = len(s.exec(select(EntiteJuridique)).all())
    ns = len(s.exec(select(IdentifierNamespace)).all())
    vs = len(s.exec(select(VocabularySystem)).all())
    vv = len(s.exec(select(VocabularyValue)).all())
    pat = len(s.exec(select(Patient)).all())
    print(f'''
Contextes GHT      : {ctx}
Entités juridiques : {ej}
Namespaces         : {ns}
Systèmes vocab     : {vs}
Valeurs vocab      : {vv}
Patients           : {pat}
''')
"
```

### Accès UI après init

```bash
# Démarrer le serveur
uvicorn app.app:app --reload

# Ouvrir dans le navigateur
# - Page admin EJ: http://localhost:8000/admin/ght/1/ej/1
# - Vocabulaires: http://localhost:8000/api/vocabularies
# - Dashboard: http://localhost:8000/dashboard
```

---

## Ordre d'exécution recommandé (première installation)

1. **Créer/activer venv:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # ou .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Initialisation complète:**
   ```bash
   python init_db.py
   ```

3. **Démarrer le serveur:**
   ```bash
   uvicorn app.app:app --reload
   ```

4. **Vérifier:**
   - Ouvrir http://localhost:8000/admin/ght/1/ej/1
   - Naviguer dans la structure, voir les namespaces et endpoints

---

## Résolution de problèmes

### "Table already exists"
→ Normal si init_db() est rappelé. SQLModel ne recrée que les tables manquantes.

### "Vocabulaires absents"
→ Relancer `python tools/init_vocabularies.py`

### "Namespaces count = 0"
→ Relancer `python tools/init_extended_demo.py` (intègre maintenant les namespaces)

### "Patients count < 120"
→ Vérifier logs de `seed_demo_population`: si "skipped", c'est que la cible est déjà atteinte

### Réinitialisation totale
```bash
rm medbridge.db
python init_db.py
```

---

## Structure des données créées

### Contexte GHT
- **Code:** GHT-DEMO
- **OID racine:** 1.2.250.1.71.1.1

### Entités Juridiques (4)
| FINESS      | Nom                        | Type       |
|-------------|----------------------------|------------|
| 020000000   | CHU Demo Interop           | CHU        |
| 030000000   | Hôpital Local Saint-Martin | Hôpital    |
| 040000000   | EHPAD Les Tilleuls         | EHPAD      |
| 050000000   | Centre Psychiatrique       | Psychiatrie|

### Namespaces par EJ (exemple 020000000)
- **IPP 020000000:** `1.2.250.1.71.1.1.1.2`
- **NDA 020000000:** `1.2.250.1.71.1.1.1.3`
- **VENUE 020000000:** `1.2.250.1.71.1.1.1.4`

### Endpoints par EJ
- MLLP RECV (ports 2575+)
- MLLP SEND (ports 2576+)
- FHIR API (https://fhir.demo/{FINESS})

---

## Références

- **Documentation vocabulaires:** `Doc/vocabularies.md` (à créer si besoin)
- **Architecture structure:** `Doc/architecture.md`
- **Guide benchmark:** `Doc/benchmark_guide.md`
- **API admin:** `/admin/ght/{context_id}/ej/{ej_id}`
