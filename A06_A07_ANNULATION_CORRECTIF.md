# A06/A07 Annulation: Même Événement avec ZBE-4=CANCEL (CORRECTIF)

## 📋 Pattern d'Annulation IHE PAM France (CORRIGÉ)

**Exactement !** Les A06 et A07 s'annulent **avec eux-mêmes** mais avec `ZBE-4 = CANCEL`:

```
A07 avec ZBE-4=CANCEL → Annule un A06 (annule le passage S → H)
A06 avec ZBE-4=CANCEL → Annule un A07 (annule le passage H → S)
```

C'est le **même trigger_event** mais avec l'action `CANCEL` dans ZBE-4.

---

## 🔄 Structure: ZBE-4 Action

L'annulation est identifiée par:

```
EVN-1 (Event Code)      = "A06" ou "A07"   ← Même code que l'original
ZBE-4 (Action)          = "CANCEL"         ← Indique qu'on annule
ZBE-6 (Original Trigger) = "A07" ou "A06"  ← Indique ce qu'on annule
```

| Mouvement Original | Mouvement Annulation | ZBE-4 | ZBE-6 | Sémantique |
|---|---|---|---|---|
| **A06** (S → H) | **A06** | CANCEL | A07 | Annule passage de H |
| **A07** (H → S) | **A07** | CANCEL | A06 | Annule passage de S |

**IMPORTANT:** Le trigger_event ne change PAS - c'est l'action ZBE-4 qui indique qu'on annule.

---

## 🎯 Modèle: Champs de Suivi

### Mouvement Original (A06 ou A07)

```python
class Mouvement:
    trigger_event: "A06" ou "A07"      # Code original
    action: "INSERT"                    # Action d'insertion
    original_trigger: None              # Pas de trigger original pour INSERT
    cancelled_movement_seq: None        # Pas annulé (yet)
    nature: "H" ou "S"                  # Nature du mouvement
```

### Mouvement d'Annulation (A06 ou A07 avec CANCEL)

```python
class Mouvement:
    trigger_event: "A06" ou "A07"           # MÊME CODE que l'original!
    action: "CANCEL"                        # Action d'annulation
    original_trigger: "A07" ou "A06"        # INVERSE: ce qu'on annule
    cancelled_movement_seq: <seq_number>    # Clé du mouvement annulé
    nature: Same as original                # Même nature conservée
```

**Clé:** Le `trigger_event` est le même, mais `action` change!

---

## 🔄 Exemples: Cycle Complet A06 → A06 CANCEL

### Étape 1: Création Dossier (A01)

```
Dossier.dossier_type = "HOSPITALISE"

HL7 Message:
  MSH|...
  EVN|A01|...
  PID|...
  PV1|1|I|...      ← Patient admis (I = Inpatient)
  ZBE|1|2|INSERT||||||H|

Database:
  Mouvement(
    mouvement_seq=1,
    trigger_event="A01",
    action="INSERT",
    original_trigger=None,
    nature="H"
  )
```

### Étape 2: Changement Type → A06 (INSERT)

```
Dossier.dossier_type CHANGE: "HOSPITALISE" → "EXTERNE"
(PV1-2: "I" → "O")

HL7 Message:
  MSH|...
  EVN|A06|...
  PID|...
  PV1|1|O|...      ← Patient transféré vers externe (O = Outpatient)
  ZBE|1|2|INSERT||||||S|

Database:
  Mouvement(
    mouvement_seq=2,
    trigger_event="A06",
    action="INSERT",
    original_trigger=None,  ← C'est INSERT, pas CANCEL
    nature="S"
  )
```

### Étape 3: Annulation du A06 → A06 CANCEL

```
Admin annule le changement de dossier_type:
  - Marquer mouvement_seq=2 comme annulé

HL7 Message:
  MSH|...
  EVN|A06|...                         ← MÊME CODE A06!
  PID|...
  PV1|1|O|...      ← PV1-2 reste O (état avant annulation)
  ZBE|1|2|CANCEL|Y|A07||||S|
        ↑         ↑   ↑
        action    historic original_trigger
                  Indique on ANNULE un A07 (l'inverse)

Database:
  Mouvement(
    mouvement_seq=3,
    trigger_event="A06",            ← MÊME CODE que mouvement #2
    action="CANCEL",                ← DIFFÉRENT: action change
    original_trigger="A07",         ← INVERSE: on annule A07
    cancelled_movement_seq=2,       ← Clé du mouvement annulé (A06)
    nature="S"
  )
```

### État Final: Mouvement A06 Annulé

```
Venue: [A01: H] → [A06: S (INSERT)] → [A06: S (CANCEL A07)]
                           ↑                       ↓
                      Mouvement #2           Annule mouvement #2
                      (passage S)            via cancelled_movement_seq=2
```

**Vue logique:**
```
Mouvement #2 (A06 original): trigger_event=A06, action=INSERT, nature=S
                                      ↓
                              Annulé par...
                                      ↓
Mouvement #3 (A06 annulation): trigger_event=A06, action=CANCEL, original_trigger=A07
```

---

## 📊 Tableau: Mappages A06/A07 Annulation

### Annulation de A06 (S → H)

```
Situation Initiale:
  Dossier: HOSPITALISE (I)
  Mouvement #N: A06 (transfert vers EXTERNE) = transfert externe
  
Annulation:
  Event Code: A06 (MÊME CODE!)
  ZBE-4: CANCEL
  ZBE-6: A07 (INVERSE - on annule la destination)
  cancelled_movement_seq: N
  
Sémantique:
  "On ANNULE le fait que le patient ait été transféré vers l'externe"
  "On réverse le mouvement A06 en envoyant un A06 avec CANCEL"
```

### Annulation de A07 (H → S)

```
Situation Initiale:
  Dossier: EXTERNE (O)
  Mouvement #N: A07 (transfert depuis HOSPITALISE) = sortie
  
Annulation:
  Event Code: A07 (MÊME CODE!)
  ZBE-4: CANCEL
  ZBE-6: A06 (INVERSE - on annule la source)
  cancelled_movement_seq: N
  
Sémantique:
  "On ANNULE le fait que le patient soit sorti/transféré vers l'externe"
  "On réverse le mouvement A07 en envoyant un A07 avec CANCEL"
```

### Matrice Complète

| Mouvement Original | Trigger | Action | Code Annulation | Trigger | Action | ZBE-6 | Cas |
|---|---|---|---|---|---|---|---|
| A06 (S→H) | A06 | INSERT | A06 | A06 | CANCEL | A07 | Annule transfert I |
| A07 (H→S) | A07 | INSERT | A07 | A07 | CANCEL | A06 | Annule sortie S |

**CLÉS:**
- ✅ `trigger_event` reste le MÊME dans l'annulation
- ✅ `action` change: INSERT → CANCEL
- ✅ `original_trigger` est INVERSE: A06 ↔ A07
- ✅ `cancelled_movement_seq` pointe sur le mouvement original

---

## 🔄 Logique d'Annulation en Réception

### Dans import_hl7_mouvement.py

```python
def import_mouvement_from_hl7(hl7_message, venue, session):
    
    # 1. Extraire l'event code
    event_code = extract_event_code(hl7_message)  # "A06" ou "A07"
    
    # 2. Extraire la nature (PV1-2 ou ZBE-2)
    nature = extract_nature_from_hl7(pv1, zbe)
    
    # 3. Extraire ZBE-4 et ZBE-6
    action = extract_zbe_4(hl7_message)          # "INSERT" ou "CANCEL"
    original_trigger = extract_zbe_6(hl7_message)  # "A07" ou "A06"
    
    # 4. Si CANCEL A06/A07, chercher le mouvement original
    if action == "CANCEL" and event_code in ["A06", "A07"]:
        # Pour A06/CANCEL: chercher A06/INSERT (pas A07/INSERT)
        # Pour A07/CANCEL: chercher A07/INSERT (pas A06/INSERT)
        original_mouvement = find_mouvement_by_trigger_on_venue(
            venue=venue,
            trigger_event=event_code,  # Même code!
            action="INSERT"
        )
        
        if original_mouvement:
            cancelled_movement_seq = original_mouvement.mouvement_seq
        else:
            # Mouvement original pas trouvé → Warning non-bloquant
            cancelled_movement_seq = None
    
    # 5. Créer le mouvement d'annulation
    mouvement = Mouvement(
        trigger_event=event_code,      # MÊME CODE
        action=action,                 # "CANCEL"
        original_trigger=original_trigger,  # "A07" ou "A06" (inverse)
        cancelled_movement_seq=cancelled_movement_seq,
        nature=nature,  # Même nature que l'original
        when=extracted_timestamp
    )
    
    session.add(mouvement)
    session.commit()
```

### Validation Sémantique en Réception

```python
def validate_a06_a07_cancellation(hl7_message, venue_id, session):
    """Valide que l'annulation A06/A07 est cohérente."""
    
    event_code = extract_event_code(hl7_message)  # "A06" ou "A07"
    action = extract_zbe_4(hl7_message)           # "CANCEL"
    original_trigger = extract_zbe_6(hl7_message)  # inverse
    
    if action != "CANCEL" or event_code not in ["A06", "A07"]:
        return ValidationResult(is_valid=True)  # Pas une annulation A06/A07
    
    # Valider l'inverse: si A06/CANCEL, ZBE-6 doit être A07
    if event_code == "A06" and original_trigger != "A07":
        return ValidationResult(
            is_valid=False,
            issues=["A06 CANCEL requiert ZBE-6=A07"]
        )
    
    if event_code == "A07" and original_trigger != "A06":
        return ValidationResult(
            is_valid=False,
            issues=["A07 CANCEL requiert ZBE-6=A06"]
        )
    
    # Vérifier existence du mouvement original
    original_mouvement = session.exec(
        select(Mouvement).where(
            Mouvement.venue_id == venue_id,
            Mouvement.trigger_event == event_code,  # Même code!
            Mouvement.action == "INSERT"
        )
    ).first()
    
    if not original_mouvement:
        return ValidationResult(
            is_valid=True,  # Non-bloquant
            issues=["Mouvement original non trouvé (peut être d'un autre système)"]
        )
    
    return ValidationResult(is_valid=True)
```

---

## 🎯 Champs du Modèle Impliqués

### Mouvement

```python
class Mouvement:
    # Identification du mouvement
    mouvement_seq: int                    # Clé métier unique
    
    # Événement
    trigger_event: str                    # "A06" ou "A07"
    
    # Actions ZBE
    action: str                           # "INSERT" ou "CANCEL"
    original_trigger: Optional[str]       # "A07" si A06/CANCEL, "A06" si A07/CANCEL
    
    # Lien au mouvement annulé
    cancelled_movement_seq: Optional[int] # Clé du mouvement annulé
    
    # Nature du soin
    nature: Optional[str]                 # Conservée de l'original (S ou H)
    
    # ZBE fields
    is_historic: bool                     # Y/N (ZBE-5)
```

---

## ✅ Pattern Validé: Annulation par Inversion

### Règle d'Annulation A06 ↔ A06 CANCEL

```
Condition: Un A06 (S → H) a été généré/reçu
  Mouvement(trigger_event=A06, action=INSERT, nature=S, mouvement_seq=N)

Annulation possible via A06 CANCEL:
  ✓ trigger_event: A06 (MÊME CODE)
  ✓ action: CANCEL (CHANGE)
  ✓ original_trigger: A07 (INVERSE)
  ✓ cancelled_movement_seq: N
  ✓ nature: S (conservée)
  
Message HL7:
  EVN|A06|...
  ZBE|1|2|CANCEL|Y|A07||||S|
      ↑         ↑   ↑
      code      action inverse
  
Résultat: Mouvement A06 original marqué comme annulé
          Traçabilité: A06/INSERT ← A06/CANCEL via cancelled_movement_seq
```

### Règle d'Annulation A07 ↔ A07 CANCEL

```
Condition: Un A07 (H → S) a été généré/reçu
  Mouvement(trigger_event=A07, action=INSERT, nature=H, mouvement_seq=M)

Annulation possible via A07 CANCEL:
  ✓ trigger_event: A07 (MÊME CODE)
  ✓ action: CANCEL (CHANGE)
  ✓ original_trigger: A06 (INVERSE)
  ✓ cancelled_movement_seq: M
  ✓ nature: H (conservée)
  
Message HL7:
  EVN|A07|...
  ZBE|1|2|CANCEL|Y|A06||||H|
      ↑         ↑   ↑
      code      action inverse
  
Résultat: Mouvement A07 original marqué comme annulé
          Traçabilité: A07/INSERT ← A07/CANCEL via cancelled_movement_seq
```

---

## 📌 Conclusion

**Vous avez raison:** L'annulation d'A06/A07 suit exactement ce pattern:

| Mouvement | Code Annulation | Action | ZBE-6 | Lien |
|---|---|---|---|---|
| A06 (S→H) | **A06** | CANCEL | **A07** | cancelled_movement_seq |
| A07 (H→S) | **A07** | CANCEL | **A06** | cancelled_movement_seq |

Le système utilise **`cancelled_movement_seq`** avec **même trigger_event mais action inversée** pour tracer exactement quel mouvement est annulé. L'inversion en ZBE-6 indique sémantiquement ce qui est annulé. ✅
