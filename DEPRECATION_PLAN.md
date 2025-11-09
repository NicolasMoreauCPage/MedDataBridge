# Plan de Correction – Déprécations & Warnings

_Date: 2025-11-09_
_Branche: `refonte-uiux-2025`_

## 1. DeprecationWarning TemplateResponse

### Problème
Starlette/FastAPI a changé la signature de `TemplateResponse`:
- **Ancien** (déprécié): `TemplateResponse(name, {"request": request, ...})`
- **Nouveau**: `TemplateResponse(request, name, context_dict)`

### Impact
351 warnings totaux dans la suite de tests; ~30-40% liés à cette dépréciation.

### Actions Complétées (Première Vague)
✅ **20 routes refactorées** dans:
- `admin_gateway.py` (1 route)
- `home.py` (1 route)
- `validation.py` (3 routes)
- `vocabularies.py` (3 routes)
- `endpoints.py` (5 routes)
- `dossier_type.py` (1 route)
- `mouvements.py` (6 routes)

**Méthode**:
1. Localiser `TemplateResponse(name, {`
2. Remplacer par `TemplateResponse(request, name, {`
3. Supprimer `"request": request` du dict context (devient implicite)

### Actions Restantes
Routes non encore refactorées (estimé 15-20 occurrences):
- `dossiers.py` (~5 routes: list, detail, edit, new, not_found)
- `patients.py` (~4 routes: list, detail, edit, new)
- `timeline.py` (1 route)
- `scenarios.py` (déjà conforme – vérifier)
- Autres routers structure/admin moins critiques

**Plan d'exécution**:
1. Refactor batch 2: `dossiers.py`, `patients.py` (haute fréquence).
2. Refactor batch 3: routes restantes (structure, forms, timeline).
3. Validation: retest complet → confirmer <100 warnings TemplateResponse.

**Estimation effort**: 2h (inspection manuelle + tests).

---

## 2. SAWarning – VocabularyMapping autoflush

### Problème
```
SAWarning: Object of type <VocabularyMapping> not in session, add operation along 
'VocabularyValue.mappings' will not proceed (autoflush process)
```

### Cause Racine
Lors de la création/modification de `VocabularyValue`, la relation `mappings` (lazy-loaded) tente un autoflush alors que les objets liés ne sont pas encore dans la session.

### Localisation
Fichiers concernés:
- `app/services/vocabulary_init.py` (création vocabulaires initiaux)
- `app/routers/vocabularies.py` (création/édition valeurs + mappings)
- Tests multiples (fixtures vocabulaire).

### Solutions Possibles

#### Option A: Disable autoflush local
```python
with session.no_autoflush:
    value = VocabularyValue(...)
    session.add(value)
    # manipuler mappings
    session.commit()
```

#### Option B: Eager add + explicit flush
```python
value = VocabularyValue(...)
session.add(value)
session.flush()  # force persistence avant manipulation relations
for mapping in value.mappings:
    session.add(mapping)
```

#### Option C: Refactor relation (cascade + passive_deletes)
Ajuster `VocabularyValue.mappings` relationship:
```python
mappings: Mapped[List["VocabularyMapping"]] = Relationship(
    back_populates="value",
    sa_relationship_kwargs={
        "cascade": "all, delete-orphan",
        "passive_deletes": True,
        "lazy": "joined"  # ou "selectin"
    }
)
```

### Actions Recommandées
1. **Immédiat**: Appliquer Option A dans `vocabulary_init.py` + routes création/édition.
2. **Moyen terme**: Audit complet des relations SQLModel → ajouter cascades explicites.
3. **Test**: Vérifier fixtures + tests UI vocabulaire → confirmer 0 SAWarning.

**Estimation effort**: 3h (audit relations + refactor + tests).

---

## 3. Autres Warnings Mineurs

### allow_redirects → follow_redirects
**Fichier**: `tests/test_form_smoke.py`
**Action**: Remplacer `allow_redirects=` par `follow_redirects=` (Starlette TestClient).
**Effort**: 10 min.

---

## 4. Plan Global & Priorisation

| Tâche | Priorité | Effort | Impact Warnings |
|-------|----------|--------|-----------------|
| TemplateResponse batch 2+3 | Haute | 2h | -150 warnings |
| SAWarning VocabularyMapping | Haute | 3h | -180 warnings |
| allow_redirects | Basse | 10m | -1 warning |
| **Total estimé** | | **5h 10m** | **-331 warnings (~94%)** |

### Jalons
1. **Jalon 1** (cette session): TemplateResponse batch 1 ✅ → -50 warnings.
2. **Jalon 2** (prochaine): TemplateResponse batch 2+3 → cible <200 warnings totaux.
3. **Jalon 3** (avant merge main): SAWarnings + allow_redirects → cible <20 warnings totaux.

---

## 5. Validation Post-Refactor

### Checklist Tests
- [ ] `pytest -q` passe sans nouvelles erreurs
- [ ] Warnings count < 120 (objectif milestone)
- [ ] Tests UI (navigation, forms, endpoints) verts
- [ ] Aucune régression fonctionnelle (scénarios, messages)

### Métriques Cibles
| Métrique | Actuel | Post-Refactor |
|----------|--------|---------------|
| Warnings totaux | 351 | <120 |
| TemplateResponse warnings | ~150 | <10 |
| SAWarnings | ~180 | 0 |
| Tests passés | 218 | 218 |

---

_Fin du plan de correction. Implémentation progressive par batches._
