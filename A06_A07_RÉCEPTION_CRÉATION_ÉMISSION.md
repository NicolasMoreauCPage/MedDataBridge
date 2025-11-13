# 🔄 A06/A07 en Réception, Création et Émission

**Date**: 13 novembre 2025  
**Question**: "Quand on reçoit des A06/A07, crée-t-on automatiquement un mouvement d'admission ? Le validateur en tient-il compte ?"  
**Status**: ⚠️ **PARTIEL - À COMPLÉTER**

---

## 🎯 Synthèse Rapide

| Phase | A06/A07 | Mouvement créé ? | Comportement |
|-------|---------|-----------------|---|
| **RÉCEPTION** ❌ | `ADT^A06` ou `ADT^A07` | ❌ Non automatique | Importe mouvement avec `type="ADT^A06"`, `movement_type="mutation"` (mappé) |
| **CRÉATION** ✅ | Auto-détecté | ✅ Oui | Crée mouvement puis génère `ADT^A06/A07` |
| **ÉMISSION** ✅ | Généré | ✅ Oui (doit) | Emit le mouvement → Génère `ADT^A06/A07` |
| **VALIDATION** ⚠️ | Logique ignorée | ❓ Partial | IHE PAM valide le HL7, pas la sémantique A06/A07 |

---

## 📥 RÉCEPTION: Quand on reçoit `ADT^A06` ou `ADT^A07`

### Flux Actuel

```python
# File: app/services/import_hl7_mouvement.py

def import_mouvement_from_hl7(hl7_message: str, venue, session) -> Optional[Mouvement]:
    """
    Parse HL7 ADT et crée un Mouvement
    """
    segments = hl7_message.split('\r')
    msh = next((s for s in segments if s.startswith('MSH|')), None)
    
    # Extraire type de message
    msh_fields = msh.split('|')
    msg_type = msh_fields[8]  # Ex: "ADT^A06^ADT_A06"
    hl7_code = "ADT^A06"
    
    # MAPPER vers le code métier
    # movement_type = from_standard_movement_code("ADT^A06", 'hl7')
    # → Retourne "mutation" (mapping table)
    
    movement_type = "mutation"  # OU "retour" pour A07
    
    # Créer le mouvement
    m = Mouvement(
        venue_id=venue.id,
        type="ADT^A06",           # Code HL7 reçu
        movement_type="mutation",  # Code métier
        when=when_dt,
        status="active",
    )
    return m
```

### 📊 Mapping HL7 → Métier

```python
# File: app/movement_type_mapping.py

MOVEMENT_TYPE_MAPPINGS = {
    "admission":              {"hl7": "ADT^A01", "fhir": "admit"},
    "transfert":              {"hl7": "ADT^A02", "fhir": "transfer"},
    "sortie":                 {"hl7": "ADT^A03", "fhir": "discharge"},
    "consultation":           {"hl7": "ADT^A04", "fhir": "outpatient"},
    "pre_admission":          {"hl7": "ADT^A05", "fhir": "pre-admit"},
    "mutation":               {"hl7": "ADT^A06", "fhir": "mutation"},  # ← A06
    "retour":                 {"hl7": "ADT^A07", "fhir": "return"},    # ← A07
    "annulation_admission":   {"hl7": "ADT^A11", "fhir": "cancel-admit"},
    "annulation_transfert":   {"hl7": "ADT^A12", "fhir": "cancel-transfer"},
    "annulation_sortie":      {"hl7": "ADT^A13", "fhir": "cancel-discharge"},
}
```

### ⚠️ **PROBLÈME IDENTIFIÉ**

**Quand on reçoit `ADT^A06`, on crée un mouvement avec `movement_type="mutation"`**

Mais:
- ❌ **Pas de vérification** que ce mouvement représente vraiment une transition S → H
- ❌ **Pas de création de mouvement d'admission implicite**
- ❌ **Pas de validation** de la sémantique ("il y avait vraiment un passage S avant ?")

**Exemple problématique**:
```
Reçu: ADT^A06^ADT_A06 sur venue CARDIO
→ Crée Mouvement(type="ADT^A06", movement_type="mutation", nature=None)
❌ Manque: Vérifier qu'il y avait un mouvement S avant
❌ Manque: Créer implicitement un mouvement d'admission (nature=H)
```

---

## ✨ CRÉATION: Quand on crée un mouvement manuellement

### Flux Actuel (CORRECT ✅)

```python
# File: app/services/emit_on_create.py
# Dans le handler de création Mouvement

if operation == "insert" and entity_type == "mouvement":
    
    # Priority 1.5: Auto-détection A06/A07
    a0607_code, prev_nature = detect_a06_a07_from_history(entity, session, operation)
    
    if a0607_code == "A06":
        # Vérifié: transition S → H
        event_code = "A06"
        msg_type = "ADT^A06"
    
    elif a0607_code == "A07":
        # Vérifié: transition H → S
        event_code = "A07"
        msg_type = "ADT^A07"
    
    else:
        # Pas de transition: utiliser autre logique
        event_code = "A01"  # Défaut
    
    # Générer HL7 avec event_code correct
    hl7 = generate_pam_hl7(...)
    emit_hl7(hl7)
```

### ✅ **COMPORTEMENT CORRECT**

```
Créé: Mouvement(venue_id=X, nature="H", when=2025-11-13)
  
Historique venue X:
  - 2025-10-01: Mouvement(nature="S") ← consultation
  
Détection A06:
  ✅ Trouve le mouvement S antérieur
  ✅ Détecte transition S → H
  ✅ Génère ADT^A06 (pas A01)
  ✅ Valide le message IHE PAM
```

---

## 📤 ÉMISSION: Quand on émet un mouvement

### Flux Actuel (CORRECT ✅)

```python
# File: app/services/emit_on_create.py

def emit_mouvement_hl7(entity, session, operation):
    """
    Émettre un message HL7 quand un Mouvement est créé
    """
    # 1. Vérifier trigger_event explicite
    if entity.trigger_event:
        event_code = entity.trigger_event  # A06, A07, etc.
    
    # 2. Auto-détecte A06/A07 si pas de trigger_event
    else:
        a0607_code, _ = detect_a06_a07_from_history(entity, session, operation)
        event_code = a0607_code or "A01"  # Défaut: A01
    
    # 3. Générer le message HL7 avec le bon event_code
    hl7 = generate_pam_hl7(
        entity=entity,
        operation=operation,
        event_code=event_code,
        msg_type=f"ADT^{event_code}",
        msg_structure="ADT_A06" if event_code in ["A06", "A07"] else "ADT_A01"
    )
    
    # 4. Émettre
    emit_to_endpoints(hl7)
```

### ✅ **COMPORTEMENT CORRECT**

L'émission fonctionne car le mouvement est créé **avant** le HL7 est généré.

---

## ✓ VALIDATION: Est-ce que le validateur en tient compte ?

### Validateur IHE PAM (`validate_pam()`)

```python
# File: app/services/pam.py

def validate_pam(hl7_message: str, direction="in"):
    """
    Valide un message HL7 contre IHE PAM France
    """
    # Charge adaptateur France
    adapter = importlib.import_module("adapters.hl7_pam_fr")
    
    # Vérifie:
    # ✅ Segments obligatoires (MSH, EVN, PID, PV1, ZBE)
    # ✅ Types de message valides (A01, A02, A06, A07, etc.)
    # ✅ Champs obligatoires HL7 v2.5
    # ✅ ZBE format et composantes
    # ❌ Ne vérifie PAS la sémantique: "Y a-t-il vraiment eu un passage S avant ?"
    
    result = adapter.validate_hl7_message(hl7_message)
    return result  # {is_valid: bool, level: str, issues: list}
```

### 📋 Ce que le validateur VÉRIFIE

✅ **Structure HL7**:
```
✓ MSH présent et bien formé
✓ PV1.2 (patient class) = "I" ou "O" ou "E"
✓ ZBE-2 (nature) = "S", "H", "O"
✓ ZBE-3 (trigger) = A01, A06, A07, etc.
```

✅ **Champs obligatoires**:
```
✓ PID (identifiants patient)
✓ PV1 (localisation, classe patient)
✓ ZBE (nature, raison, UF responsabilité)
```

✅ **Codes de vocabulaire**:
```
✓ ADT code existe (A01, A02, A06, A07 OK)
✓ Patient class valide
✓ Admission type valide (si fourni)
```

### ❌ Ce que le validateur ne VÉRIFIE PAS

❌ **Sémantique A06/A07**:
```
✗ Si A06, y avait-il vraiment un mouvement S avant ?
✗ Si A07, y avait-il vraiment un mouvement H avant ?
✗ La nature du mouvement courant correspond-elle au code ?
```

**Exemple**:
```
Message reçu:
  MSH|...|ADT^A06^ADT_A06|...
  PV1|...|O|...    ← Patient class "O" (outpatient)
  ZBE|1|S|A06|...  ← Nature "S"
  
❌ INCOHÉRENCE: A06 = "changement à l'hospitalisation"
                 Mais nature="S" (externe) et class="O"
                 
Le validateur: ✅ PASSE (structure correcte)
Sémantique: ❌ ÉCHOUE (incohérent)
```

---

## 🔍 Analyse Détaillée: Réception

### Scénario 1: Réception d'un `ADT^A06` Valide

```
HL7 reçu:
  MSH|...|ADT^A06^ADT_A06|...
  EVN|...|20251113120000|...
  PID|...|DOE^JOHN|...|... (patient)
  PV1|...|H|URG1|... (patient class: H = inpatient)
  ZBE|1|H|A06|...  (nature: H, code: A06)

Flux de réception:
  1. Reconnaître venue (URG1)
  2. Importer mouvement:
     type="ADT^A06"
     movement_type="mutation"
     nature=? (PAS extracte du PV1 ou ZBE)
     when=20251113120000
  3. ❌ PAS de vérification de la transition S→H
  4. ❌ PAS de création implicite d'admission mouvement
```

### Scénario 2: Réception d'un `ADT^A06` Reçu Seul (Sans historique S)

```
Situation: Première réception du patient sur cette venue
  
HL7 reçu:
  ADT^A06 (changement externe → hospitalisé)
  
Historique venue: ∅ (vide)
  
Problème:
  ✗ Le A06 n'a pas de sens sans un mouvement S antérieur
  ✗ Devrait créer implicitement: Mouvement(nature="S") ?
  ✗ Ou rejeter comme incohérent ?
```

---

## 📊 Tableau Récapitulatif Complet

### RÉCEPTION

| Reçu | Mouvement créé | Nature extracte | Mouvement implicit ? | Validé ? |
|------|---|---|---|---|
| ADT^A06 | ✅ Oui | ❌ Non | ❌ Non | ✅ Structure OK |
| ADT^A07 | ✅ Oui | ❌ Non | ❌ Non | ✅ Structure OK |
| ADT^A01 | ✅ Oui | ❌ Non | ❌ Non | ✅ Structure OK |

### CRÉATION (depuis UI/API)

| Créé | Auto-détecte ? | Mouvement antérieur requis ? | Génère ADT code | Validé ? |
|---|---|---|---|---|
| Mouvement nature=H | ✅ A06 si S avant | ✅ Oui | ✅ A06 | ✅ OK |
| Mouvement nature=S | ✅ A07 si H avant | ✅ Oui | ✅ A07 | ✅ OK |
| Mouvement nature=H | ❌ Pas A06 | ❌ Non | ✅ A01 | ✅ OK |
| Mouvement trigger_event="A06" | ❌ Override | ❌ Non | ✅ A06 | ✅ OK |

### ÉMISSION

| Message | ADT Code | Généré depuis | Validé ? |
|---|---|---|---|
| A06 | Correct | Détection historique | ✅ OK |
| A07 | Correct | Détection historique | ✅ OK |
| A01 | Correct | Défaut (pas A06/A07) | ✅ OK |

---

## 🛠️ Recommandations pour Compléter

### 1️⃣ **À la RÉCEPTION** (import_hl7_mouvement.py)

```python
# AMÉLIORATION À FAIRE:

def import_mouvement_from_hl7(hl7_message: str, venue, session):
    """
    Enrichir: Extraire la nature du mouvement du HL7
    """
    
    # Extraire nature depuis ZBE-2 ou PV1.2
    zbe = find_segment(segments, 'ZBE')
    if zbe:
        nature = zbe.split('|')[2]  # ZBE-2: S, H, O, U
    else:
        # Fallback: déduire du patient class PV1-2
        pv1_fields = pv1.split('|')
        patient_class = pv1_fields[2]
        nature = "H" if patient_class == "I" else "S"
    
    # Créer mouvement avec nature
    m = Mouvement(
        venue_id=venue.id,
        type=hl7_code,
        movement_type=movement_type,
        nature=nature,  # ✅ AJOUTER
        when=when_dt,
    )
    
    # OPTIONNEL: Si reçu A06/A07, vérifier cohérence
    if hl7_code in ["ADT^A06", "ADT^A07"]:
        verify_a06_a07_coherence(m, session, venue)
```

### 2️⃣ **À la CRÉATION** (déjà OK ✅)

Pas de changement: `detect_a06_a07_from_history()` fonctionne.

### 3️⃣ **À la VALIDATION** (pam.py)

```python
# AMÉLIORATION À FAIRE:

def validate_pam_semantics(hl7_message: str, venue, session):
    """
    Valider la sémantique A06/A07 en plus de la structure
    """
    
    event_code = extract_event_code(hl7_message)
    
    if event_code == "A06":
        # Vérifier qu'il existe un mouvement S antérieur
        previous = find_last_movement_with_nature(venue, "S", session)
        if not previous:
            return {
                is_valid: False,
                level: "error",
                issues: ["A06 reçu mais pas de mouvement externe (S) antérieur"]
            }
    
    elif event_code == "A07":
        # Vérifier qu'il existe un mouvement H antérieur
        previous = find_last_movement_with_nature(venue, "H", session)
        if not previous:
            return {
                is_valid: False,
                level: "error",
                issues: ["A07 reçu mais pas de mouvement hospitalisé (H) antérieur"]
            }
    
    return validate_pam(hl7_message)  # Validation structure
```

---

## 📝 Résumé Final: Votre Question

### ❓ "Quand on reçoit A06/A07, crée-t-on automatiquement un mouvement d'admission ?"

**Réponse Actuelle**:
```
❌ Non, on crée UN mouvement avec type="ADT^A06"/"ADT^A07"
   Mais on n'extrait pas la nature
   Et on n'en déduit pas implicitement que c'est une "transition"
```

**Devrait être**:
```
✅ Oui, mais il faudrait:
   1. Extraire nature du ZBE-2 ou PV1-2
   2. Vérifier qu'il y avait un mouvement antérieur avec nature différente
   3. Optionnel: créer implicitement le mouvement antérieur (S) si absent
```

### ❓ "Le validateur prend-il ça en compte ?"

**Réponse Actuelle**:
```
❌ Partiellement:
   ✅ Valide la STRUCTURE du HL7
   ❌ Ne valide PAS la SÉMANTIQUE (cohérence A06↔historique)
```

**Devrait être**:
```
✅ Oui avec amélioration:
   - Ajouter validate_pam_semantics() qui vérifie la transition
   - Intégrer dans la chaîne de validation globale
```

---

## 🚀 Prochaines Étapes

**Priorité 1** (Sécurité):
- [ ] Enrichir `import_hl7_mouvement.py` pour extraire `nature` du HL7
- [ ] Valider cohérence A06/A07 reçu vs historique

**Priorité 2** (Qualité):
- [ ] Ajouter `validate_pam_semantics()` dans `pam.py`
- [ ] Intégrer vérification sémantique aux tests

**Priorité 3** (Évolutivité):
- [ ] Documenter dans IHE_PAM_EVENTS_GUIDE.md
- [ ] Tests complets pour réception A06/A07

---

**Version**: 1.0 DRAFT  
**Statut**: ⚠️ À valider avec domaine métier  
**Last Updated**: 13 novembre 2025
