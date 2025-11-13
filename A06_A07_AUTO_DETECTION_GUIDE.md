# 🔄 Détection Automatique A06/A07 - Guide Complet

**Date**: 13 novembre 2025  
**Version**: 1.0  
**Statut**: ✅ Implémenté et Validé

---

## 📋 Vue d'ensemble

Le système génère automatiquement les codes **A06** et **A07** en fonction de l'historique des mouvements sur une même venue, conformément à la spécification IHE PAM France.

### Codes concernés

| Code | Signification | Condition |
|------|---|---|
| **A06** | Change Outpatient to Inpatient | Nature: S → H |
| **A07** | Change Inpatient to Outpatient | Nature: H → S |

---

## 🎯 Logique de Détection

### A06 (Externe → Hospitalisé)

```
Condition:
  - Mouvement nouveau avec nature="H" (hospitalisé)
  - ET existe un mouvement antérieur sur MÊME venue avec nature="S" (externe)
  → Génère ADT^A06
```

**Exemple**:
```
Venue: Consultation (CONSULT)
├─ Mouvement 1: nature=S (externe) → A01 ou A04
├─ Mouvement 2: nature=H (hospitalisé) → A06 AUTO-DÉTECTÉ ✅
```

### A07 (Hospitalisé → Externe)

```
Condition:
  - Mouvement nouveau avec nature="S" (externe)
  - ET existe un mouvement antérieur sur MÊME venue avec nature="H" (hospitalisé)
  → Génère ADT^A07
```

**Exemple**:
```
Venue: Hospitalisation (CARDIO)
├─ Mouvement 1: nature=H (hospitalisé) → A01
├─ Mouvement 2: nature=S (externe) → A07 AUTO-DÉTECTÉ ✅
```

---

## 🔧 Implémentation Technique

### Fichier: `app/services/emit_on_create.py`

#### Helper Function

```python
def detect_a06_a07_from_history(entity, session, operation):
    """
    Detect A06 or A07 based on venue movement history.
    
    Returns: ("A06"|"A07"|None, previous_nature)
    """
    # Only for new insertions
    if operation != "insert":
        return None, None
    
    # Get current nature
    current_nature = getattr(entity, "nature", None)
    if not current_nature or current_nature not in ["H", "S"]:
        return None, None
    
    # Query previous movements on same venue
    previous_movements = session.exec(
        select(Mouvement)
        .where(Mouvement.venue_id == entity.venue_id)
        .where(Mouvement.when < entity.when)
        .order_by(Mouvement.when.desc())
    ).all()
    
    if not previous_movements:
        return None, None  # No history
    
    # Find last movement with defined nature
    last_nature = None
    for prev in previous_movements:
        if getattr(prev, "nature", None) in ["H", "S"]:
            last_nature = getattr(prev, "nature")
            break
    
    if not last_nature:
        return None, None
    
    # Detect transition
    if last_nature == "S" and current_nature == "H":
        return "A06", last_nature  # S → H
    if last_nature == "H" and current_nature == "S":
        return "A07", last_nature  # H → S
    
    return None, None
```

#### Intégration dans `generate_pam_hl7()`

```python
# Priority 1.5: Auto-detect A06/A07 based on movement history
a0607_code, _prev = detect_a06_a07_from_history(entity, session, operation)
if a0607_code:
    event_code = a0607_code
    msg_type = f"ADT^{a0607_code}"
else:
    # Priority 2: Use movement_type mapping
    # ... continue with other priorities
```

---

## 📊 Priorité de Génération

```
1. trigger_event explicite (si fourni)
   ↓ (Non défini)
2. Auto-détection A06/A07 (NOUVEAU)
   ↓ (Pas de transition)
3. movement_type mapping
   ↓ (Pas de mapping)
4. operation + action fallback
   ↓
5. A01 (défaut)
```

---

## ✅ Validation

### Tests

Le suite de tests `test_a06_a07_auto_detection.py` valide:

1. **test_a06_external_to_hospitalized_auto_detection**
   - Crée venue externe (S)
   - Crée mouvement externe (S)
   - Crée mouvement hospitalisé (H)
   - ✅ Vérifie ADT^A06 généré

2. **test_a07_hospitalized_to_external_auto_detection**
   - Crée venue hospitalisée (H)
   - Crée mouvement hospitalisé (H)
   - Crée mouvement externe (S)
   - ✅ Vérifie ADT^A07 généré

3. **test_no_a06_a07_without_history**
   - Crée venue
   - Crée mouvement H sans antécédent
   - ✅ Vérifie ADT^A01 généré (pas A06)

### Validation IHE PAM

Chaque message généré passe:

```python
result = validate_pam(hl7, direction="out")
assert result.is_valid and result.level == "ok"
```

Conformité garantie avec:
- Segments HL7 v2.5 corrects
- ZBE segments avec composantes requises
- XON format pour UF identifiers

---

## 🎓 Cas d'Usage Clinique

### Scénario 1: Patient en Consultation, puis Admission

```
Patient → Dossier (externe) → Venue (consultation)
  ├─ Mouvement 1: Consultation (S) → ADT^A04 ou A01
  └─ Mouvement 2: Devient urgent, admission → ADT^A06 ✅

ZBE segments:
  A04: nature=S, action=INSERT, no ZBE-6
  A06: nature=H, action=INSERT, no ZBE-6
```

### Scénario 2: Patient Hospitalisé, puis Retour Externe

```
Patient → Dossier (hospitalisé) → Venue (hospitalisation)
  ├─ Mouvement 1: Admission (H) → ADT^A01
  └─ Mouvement 2: Changement d'UF, devient consultation (S) → ADT^A07 ✅

ZBE segments:
  A01: nature=H, action=INSERT, no ZBE-6
  A07: nature=S, action=INSERT, no ZBE-6
```

---

## 🔒 Limitations et Règles

### ✅ Quand A06/A07 est généré

- ✅ Transition S → H ou H → S sur **même venue**
- ✅ Mouvement est une **insertion** (`operation="insert"`)
- ✅ Nature précédente ET nouvelle sont définies
- ✅ Il existe au moins **un** mouvement antérieur

### ❌ Quand A06/A07 n'est PAS généré

- ❌ Première insertion sans historique → A01 (défaut)
- ❌ `trigger_event` explicite fourni → utilise ce code
- ❌ Pas de changement de nature (H→H ou S→S) → A01
- ❌ `operation="update"` ou action="CANCEL" → utilise autres priorités
- ❌ Nature undefined (ni H ni S) → A01

---

## 📁 Fichiers Modifiés

- **app/services/emit_on_create.py**
  - Ajout helper `detect_a06_a07_from_history()`
  - Intégration dans mouvement block (priorité 1.5)
  - Chargement explicite venue/dossier/patient relationships

- **tests/test_a06_a07_auto_detection.py** (NEW)
  - 3 tests de détection automatique
  - Helper `extract_event_code_from_hl7()`
  - Validation complète IHE PAM

- **VALIDATION_REPORT_IHMS.md**
  - Mise à jour rapport avec résultats A06/A07
  - 6 test suites documentées

---

## 📞 Support et Questions

Pour les questions sur la détection A06/A07:

1. Vérifier que la `nature` du mouvement est S ou H
2. Vérifier que des mouvements antérieurs existent sur même `venue_id`
3. Vérifier que pas de `trigger_event` explicite qui override
4. Vérifier `operation="insert"` (par défaut)
5. Consulter logs de validation pour détails

---

**Version**: 1.0  
**Last Updated**: 13 novembre 2025  
**Status**: ✅ Production Ready
