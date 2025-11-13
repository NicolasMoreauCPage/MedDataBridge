# A06/A07 Annulation: Même Event avec ZBE-4=CANCEL

## 📋 Pattern d'Annulation IHE PAM France (CORRIGÉ)

**Exactement !** Les A06 et A07 s'annulent **avec eux-mêmes** mais avec `ZBE-4 = CANCEL`:

- **A07 avec ZBE-4=CANCEL** → Annule un **A06** (annule le passage de S → H)
- **A06 avec ZBE-4=CANCEL** → Annule un **A07** (annule le passage de H → S)

C'est le **même trigger_event** mais avec l'action `CANCEL` dans ZBE-4.

---

## 🔗 Structure: ZBE-6 Original Trigger

L'annulation est identifiée par:

```
ZBE-4 (Action)      = "CANCEL"     ← Indique qu'on annule
ZBE-6 (Original)    = "A06" ou "A07"   ← Indique ce qu'on annule
EVN-1 (Event Code)  = "A12" ou "A13"   ← Code d'annulation utilisé
```

| Mouvement Original | Action | Événement d'Annulation | Sémantique |
|---|---|---|---|
| **A06** (S → H) | CANCEL | **A12** (Cancel Transfer) | Annule le passage H |
| **A07** (H → S) | CANCEL | **A13** (Cancel Discharge) | Annule la sortie S |

---

## 🎯 Modèle: Champs de Suivi

### Mouvement Original (A06/A07)

```python
class Mouvement:
    trigger_event: "A06" ou "A07"      # Code original
    action: "INSERT"                    # Action d'insertion
    original_trigger: None              # Pas de trigger original pour INSERT
    cancelled_movement_seq: None        # Pas annulé (yet)
    nature: "H" ou "S"                  # Nature du mouvement
```

### Mouvement d'Annulation (A12/A13)

```python
class Mouvement:
    trigger_event: "A12" ou "A13"           # Code d'annulation
    action: "CANCEL"                        # Action d'annulation
    original_trigger: "A06" ou "A07"        # Reference le mouvement annulé
    cancelled_movement_seq: <seq_number>    # Clé du mouvement annulé
    nature: Same as original                # Même nature conservée
```

---

## 🔄 Exemples: Cycle Complet A06 → A12

### Étape 1: Création Dossier (A01)

```
Dossier.dossier_type = "HOSPITALISE"

HL7 Message:
  MSH|...
  EVN|A01|...
  PID|...
  PV1|1|I|...      ← Patient admis (I = Inpatient)
  ZBE|...|H|A01|...|

Database:
  Mouvement(
    trigger_event="A01",
    action="INSERT",
    original_trigger=None,
    nature="H",
    mouvement_seq=1
  )
```

### Étape 2: Changement Type → A06

```
Dossier.dossier_type CHANGE: "HOSPITALISE" → "EXTERNE"
(PV1-2: "I" → "O")

HL7 Message:
  MSH|...
  EVN|A06|...
  PID|...
  PV1|1|O|...      ← Patient transféré vers externe (O = Outpatient)
  ZBE|...|S|A06|...|

Database:
  Mouvement(
    trigger_event="A06",
    action="INSERT",
    original_trigger=None,  ← C'est INSERT, pas UPDATE
    nature="S",
    mouvement_seq=2
  )
```

### Étape 3: Annulation du A06 → A12

```
Admin annule le changement de dossier_type:
  - Cancel movement with mouvement_seq=2

HL7 Message:
  MSH|...
  EVN|A12|...      ← Cancel Transfer
  PID|...
  PV1|1|O|...      ← PV1-2 reste O (état avant annulation)
  ZBE|1|2|CANCEL|Y||A06|...|  
        ↑         ↑   ↑  ↑
        action    original_trigger
                  Indique on annule A06

Database:
  Mouvement(
    trigger_event="A12",
    action="CANCEL",
    original_trigger="A06",         ← Référence le A06 annulé
    cancelled_movement_seq=2,       ← Pointe sur mouvement A06
    nature="S",                     ← Même nature que A06
    mouvement_seq=3
  )
```

### État Final: Mouvement A06 Annulé

```
Venue: [A01: H] → [A06: S (CANCELLED)] → [A12: CANCEL A06]
                           ↑                       ↓
                      Annulé par               Événement d'annulation
```

---

## 📊 Tableau: Mappages A06/A07 ↔ A12/A13

### Annulation de A06

```
Situation Initiale:
  Dossier: HOSPITALISE (I)
  Venue/Mouvement: A06 (transfert vers EXTERNE)
  
Annulation:
  Event Code: A12 (Cancel Transfer)
  ZBE-4: CANCEL
  ZBE-6: A06 (original trigger)
  
Sémantique:
  "On annule le fait que le patient ait été transféré vers l'externe"
```

### Annulation de A07

```
Situation Initiale:
  Dossier: EXTERNE (O)
  Venue/Mouvement: A07 (transfert depuis HOSPITALISE)
  
Annulation:
  Event Code: A13 (Cancel Discharge)
  ZBE-4: CANCEL
  ZBE-6: A07 (original trigger)
  
Sémantique:
  "On annule le fait que le patient soit sorti/transféré vers l'externe"
```

### Matrice Complète

| Mouvement Original | PV1-2 Original | Mouvement Annulation | PV1-2 Annulation | ZBE-6 | Cas |
|---|---|---|---|---|---|
| A06 (S→H) | O → I | A12 (Cancel Transfer) | O | A06 | Annule transfert I |
| A07 (H→S) | I → O | A13 (Cancel Discharge) | I | A07 | Annule sortie S |
| A01 (Admit) | - → I | A11 (Cancel Admit) | I | A01 | Annule admission |
| A03 (Discharge) | I → - | A13 (Cancel Discharge) | I | A03 | Annule sortie |

---

## 🔄 Logique d'Annulation en Réception

### Dans import_hl7_mouvement.py

```python
# À la réception d'un A12/A13:

def import_mouvement_from_hl7(hl7_message, venue, session):
    
    # 1. Extraire l'event code
    event_code = extract_event_code(hl7_message)  # "A12" ou "A13"
    
    # 2. Extraire la nature (PV1-2 ou ZBE-2)
    nature = extract_nature_from_hl7(pv1, zbe)
    
    # 3. Extraire ZBE-4 et ZBE-6
    action = extract_zbe_4(hl7_message)      # "CANCEL"
    original_trigger = extract_zbe_6(hl7_message)  # "A06" ou "A07"
    
    # 4. Si CANCEL, chercher le mouvement original
    if action == "CANCEL":
        original_mouvement = find_mouvement_by_trigger_on_venue(
            venue=venue,
            trigger_event=original_trigger  # "A06" ou "A07"
        )
        
        if original_mouvement:
            cancelled_movement_seq = original_mouvement.mouvement_seq
        else:
            # Mouvement original pas trouvé → Warning non-bloquant
            cancelled_movement_seq = None
    
    # 5. Créer le mouvement d'annulation
    mouvement = Mouvement(
        trigger_event=event_code,      # "A12" ou "A13"
        action=action,                 # "CANCEL"
        original_trigger=original_trigger,  # "A06" ou "A07"
        cancelled_movement_seq=cancelled_movement_seq,
        nature=nature,  # Même nature que l'original
        when=extracted_timestamp
    )
    
    session.add(mouvement)
    session.commit()
```

### Validation Sémantique en Réception

```python
# Dans pam_validation.py - validate_pam_semantics()

if trigger_event in ["A12", "A13"] and action == "CANCEL":
    # Valider que le mouvement original existe
    original_trigger = zbe_6  # "A06" ou "A07"
    
    if original_trigger in ["A06", "A07"]:
        # Chercher un mouvement A06 ou A07 sur la même venue
        existing = session.exec(
            select(Mouvement).where(
                Mouvement.venue_id == venue_id,
                Mouvement.trigger_event == original_trigger,
                Mouvement.action == "INSERT"
            )
        ).first()
        
        if not existing:
            # Warning: mouvement original pas trouvé
            issues.append(
                ValidationIssue(
                    "CANCEL_MOVEMENT_NOT_FOUND",
                    f"Mouvement original {original_trigger} non trouvé",
                    severity="warn"  # Non-bloquant
                )
            )
```

---

## 🎯 Champs du Modèle Impliqués

### Mouvement

```python
class Mouvement:
    # Identification du mouvement
    mouvement_seq: int                    # Clé métier unique
    
    # Événement
    trigger_event: str                    # "A06", "A07", "A12", "A13", etc.
    
    # Actions ZBE
    action: str                           # "INSERT", "UPDATE", "CANCEL"
    original_trigger: Optional[str]       # "A06"/"A07" si action="CANCEL"
    
    # Lien au mouvement annulé
    cancelled_movement_seq: Optional[int] # Clé du mouvement annulé
    
    # Nature du soin
    nature: Optional[str]                 # Conservée de l'original
    
    # ZBE fields
    is_historic: bool                     # Y/N (ZBE-5)
```

---

## ✅ Pattern Validé: Annulation avec Traçabilité

### Règles d'Annulation A06 ↔ A12

```
Condition: Un A06 (S → H) a été généré/reçu

Annulation possible via A12:
  ✓ ZBE-4: CANCEL
  ✓ ZBE-6: A06 (original_trigger)
  ✓ cancelled_movement_seq: <seq du A06>
  ✓ nature: S (conservée)
  ✓ trigger_event: A12
  
Résultat: Mouvement A06 marqué comme annulé
          Traçabilité: A06 ← A12 via cancelled_movement_seq
```

### Règles d'Annulation A07 ↔ A13

```
Condition: Un A07 (H → S) a été généré/reçu

Annulation possible via A13:
  ✓ ZBE-4: CANCEL
  ✓ ZBE-6: A07 (original_trigger)
  ✓ cancelled_movement_seq: <seq du A07>
  ✓ nature: H (conservée)
  ✓ trigger_event: A13
  
Résultat: Mouvement A07 marqué comme annulé
          Traçabilité: A07 ← A13 via cancelled_movement_seq
```

---

## 🔍 Cas d'Usage Complet

### Scénario: Hospitalisé → Externe → Annulation

```
Timeline:
  T1: Créer Dossier (HOSPITALISE) → A01
  T2: Changer Type (EXTERNE) → A06 (auto-détecté)
  T3: Annuler le changement → A12 (annule A06)

Base de Données:

  Venue 1 (du Dossier):
    ├─ Mouvement #1: A01, nature=H, action=INSERT
    ├─ Mouvement #2: A06, nature=S, action=INSERT
    └─ Mouvement #3: A12, nature=S, action=CANCEL, 
                      original_trigger=A06, 
                      cancelled_movement_seq=2

  Historique (pour dashboard):
    Admission (A01) [H]
      ↓
    Transfert externe (A06) [S]
      ↓
    ✗ Annulation transfert (A12) [cancel A06]
    
  État final: Patient retour état HOSPITALISE (avant A06)
```

### Messages Générés

```
Message 1 - ADT^A01:
MSH|...
EVN|A01|20251113100000|
PID|...
PV1|1|I|location|A|
ZBE|1|2|INSERT||||||H

Message 2 - ADT^A06:
MSH|...
EVN|A06|20251113120000|
PID|...
PV1|1|O|location|A|
ZBE|1|2|INSERT||||||S

Message 3 - ADT^A12:
MSH|...
EVN|A12|20251113150000|
PID|...
PV1|1|O|location|A|          ← PV1-2 ne change pas en annulation
ZBE|1|2|CANCEL|Y|A06||||H    ← ZBE-6 référence A06
        ↑     ↑ ↑
        action historic original_trigger
```

---

## 📝 Résumé: Identifiant de Mouvement en Annulation

### Le Lien: cancelled_movement_seq

```
Mouvement Original (A06/A07):
  mouvement_seq = N
  
Mouvement d'Annulation (A12/A13):
  cancelled_movement_seq = N  ← Pointe sur le mouvement original
  original_trigger = "A06" ou "A07"  ← Indique quoi annuler
```

### Avantages

✅ **Traçabilité**: On sait exactement quel mouvement est annulé
✅ **Validation**: On peut vérifier existence du mouvement original
✅ **Récupération**: On peut "undo" une annulation (via UPDATE)
✅ **Audit**: Historique complet des modifications

---

## 🚀 Implementation Status

### Champs du Modèle

```python
# app/models.py - Mouvement
cancelled_movement_seq: Optional[int] = None  # ✅ Implémenté
action: Optional[str]                         # ✅ Implémenté
original_trigger: Optional[str]               # ✅ Implémenté
is_historic: bool                             # ✅ Implémenté
```

### Génération (emit_on_create.py)

```python
# Lines 525-533: Gestion des CANCEL
if action == "CANCEL":
    original_trigger = getattr(entity, "original_trigger", None)
    if original_trigger == "A06":
        event_code = "A12"  # ✅ Auto-mappé
    elif original_trigger == "A07":
        event_code = "A13"  # ✅ Auto-mappé
```

### Validation (pam_validation.py)

```python
# ZBE-6 original trigger requirement
if zbe_4 in {"UPDATE", "CANCEL"} and not zbe_6:
    issues.append(ValidationIssue(...))  # ✅ Validé
```

### Import (import_hl7_mouvement.py)

```python
# À enrichir: 
# - Extraire cancelled_movement_seq depuis ZBE-6
# - Chercher mouvement original correspondant
# - Valider existence avant persister
```

---

## 📌 Conclusion

**Vous avez raison:** L'annulation d'A06/A07 suit exactement ce pattern:

| Mouvement | Code Annulation | Lien | Champ |
|---|---|---|---|
| A06 | **A12** (Cancel Transfer) | cancelled_movement_seq | ZBE-6=A06 |
| A07 | **A13** (Cancel Discharge) | cancelled_movement_seq | ZBE-6=A07 |

Le système utilise **`cancelled_movement_seq`** pour tracer exactement quel mouvement est annulé, ce qui permet une traçabilité et un audit complets. ✅
