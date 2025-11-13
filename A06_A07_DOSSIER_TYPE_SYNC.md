# A06/A07 et Synchronisation dossier_type ↔ PV1-2

## 🔄 Boucle Bidirectionnelle: Causalité Complète

**Exactement !** Les A06/A07 créent une **boucle causale bidirectionnelle**:

```
┌─────────────────────────────────────────────────┐
│ ÉMISSION (Création/Modification)                │
├─────────────────────────────────────────────────┤
│ 1. User change dossier_type: HOSPITALISE → EXTERNE
│ 2. Génère message avec PV1-2: I → O
│ 3. Auto-détecte trigger_event: A06
│ 4. Message envoyé: ADT^A06 + PV1|1|O|
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ RÉCEPTION (Import HL7)                          │
├─────────────────────────────────────────────────┤
│ 1. Reçoit message A06 avec PV1-2 = O
│ 2. Extrait PV1-2 = O (EXTERNE)
│ 3. **À FAIRE:** Synchronise dossier_type = EXTERNE
│ 4. Crée Mouvement(trigger_event=A06, nature=S)
│ 5. Valide cohérence sémantique
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ ÉTATS SYNCHRONISÉS                              │
├─────────────────────────────────────────────────┤
│ Dossier.dossier_type = EXTERNE (mis à jour)
│ Dossier.PV1-2 en générateur = O (en sync)
│ Mouvement(A06) créé avec nature=S
└─────────────────────────────────────────────────┘
```

---

## 📊 Mapping: PV1-2 ↔ dossier_type

### Transformation Bidirectionnelle

```
┌─────────────────┬──────────────────┬──────────────┐
│ dossier_type    │ PV1-2 (HL7)      │ nature (ZBE) │
├─────────────────┼──────────────────┼──────────────┤
│ HOSPITALISE     │ I (Inpatient)    │ H            │
│ EXTERNE         │ O (Outpatient)   │ S            │
│ URGENCE         │ E (Emergency)    │ O ou S       │
└─────────────────┴──────────────────┴──────────────┘

Directionnel (ÉMISSION):
  dossier_type → patient_class (dans generator)
  
Inverse (RÉCEPTION - À IMPLÉMENTER):
  PV1-2 → dossier_type (dans import)
```

---

## 🔄 Cycle Complet: Émission → Réception → Synchronisation

### Étape 1: Création Initiale (A01)

```
┌─ USER CRÉE DOSSIER
│  Dossier(dossier_type="HOSPITALISE")
│
└─ GÉNÉRATION MESSAGE
   emit_on_create.py:
     dossier_type = "HOSPITALISE"
     → patient_class = "I"
     → PV1|1|I|...
     → Message: ADT^A01 + PV1|1|I|
     
─ ENVOI (ou stockage local)
   Message envoyé avec PV1-2 = I
```

### Étape 2: Changement de Type (A06)

```
┌─ USER CHANGE DOSSIER
│  Dossier(dossier_type: HOSPITALISE → EXTERNE)
│
└─ GÉNÉRATION MESSAGE (auto-detect A06)
   emit_on_create.py:
     dossier_type_ancien = "HOSPITALISE" (I)
     dossier_type_nouveau = "EXTERNE" (O)
     → Détecte changement
     → event_code = "A06"
     → patient_class = "O"
     → PV1|1|O|...
     → nature = "S"
     → Message: ADT^A06 + PV1|1|O|
     
─ ENVOI
   Message envoyé avec PV1-2 = O
```

### Étape 3: Réception et Synchronisation (À IMPLÉMENTER)

```
┌─ RÉCEPTION MESSAGE
│  Message: ADT^A06 + PV1|1|O|...
│
├─ PARSING
│  event_code = A06 (from EVN-1)
│  pv1_2 = "O" (from PV1-2)
│  nature = "S" (from ZBE-2)
│
├─ SYNCHRONISATION DOSSIER_TYPE ← À AJOUTER
│  if event_code in ["A06", "A07"]:
│      dossier_type_nouveau = map_pv1_to_dossier_type(pv1_2)
│      # O → EXTERNE
│      # I → HOSPITALISE
│      # E → URGENCE
│      dossier.dossier_type = dossier_type_nouveau
│
├─ CRÉATION MOUVEMENT
│  Mouvement(
│    trigger_event="A06",
│    nature="S",
│    venue_id=venue.id
│  )
│
└─ VALIDATION
   Cohérence sémantique A06: S→H
   (avant: nature=H, après: nature=S) ✓
```

### État Final: Synchronisation Bidirectionnelle

```
Base de Données (après réception):

Dossier:
  - dossier_type = EXTERNE (mis à jour par réception!)
  
Venue (au moment de création A01):
  - nature = H (original)
  
Mouvement:
  - #1: A01, nature=H, trigger_event="A01"
  - #2: A06, nature=S, trigger_event="A06"
  
État cohérent: Dossier et Mouvement synchronisés
```

---

## 🎯 Scénarios de Synchronisation

### Scénario 1: Système Local (Émission Seulement)

```
┌─ Création: Dossier(HOSPITALISE)
│  → Message A01 avec PV1-2=I
│
├─ Changement: Dossier(EXTERNE)
│  → Message A06 avec PV1-2=O
│  → dossier_type synchronisé localement (pas besoin de réception)
│
└─ État: Cohérent (local only)
```

### Scénario 2: Système Interopérable (Émission + Réception)

```
┌─ Création: Dossier(HOSPITALISE)
│  → Message A01 avec PV1-2=I
│  → Envoi au système externe
│
├─ Réception du même message A01
│  → Importe: crée Dossier avec dossier_type=HOSPITALISE (de PV1-2=I)
│  → Synchronisation correcte
│
├─ Changement: Dossier(EXTERNE)
│  → Message A06 avec PV1-2=O
│  → Envoi au système externe
│
├─ Réception du message A06
│  → Importe: met à jour Dossier.dossier_type = EXTERNE (de PV1-2=O)
│  → Crée Mouvement A06
│  → Synchronisation complète
│
└─ État: Synchronisé entre systèmes
```

### Scénario 3: Annulation (A06 CANCEL)

```
Situation:
  Dossier.dossier_type = EXTERNE (suite A06)
  
Réception A06 CANCEL avec PV1-2=O (reste O):
  → Ne change pas dossier_type (PV1-2 ne change pas en CANCEL)
  → Crée Mouvement(A06, action=CANCEL, original_trigger=A07)
  → Marque Mouvement#1 (A06 original) comme annulé
  
Résultat:
  Dossier.dossier_type = EXTERNE (inchangé)
  mais Mouvement A06 marqué annulé
  → Historique conservé, traçabilité complète
```

---

## 🔗 Champs Impliqués

### Dossier

```python
class Dossier:
    dossier_type: DossierType  # ← À SYNCHRONISER en réception A06/A07
                               #   Source de vérité LOCALE après création
                               #   Mise à jour en RÉCEPTION si A06/A07
```

### Mapping Bidirectionnel Requis

```python
# ÉMISSION (existant):
def map_dossier_type_to_patient_class(dossier_type: DossierType) -> str:
    """Dossier → PV1-2"""
    mapping = {
        "HOSPITALISE": "I",
        "EXTERNE": "O",
        "URGENCE": "E"
    }
    return mapping.get(str(dossier_type), "I")

# RÉCEPTION (À AJOUTER):
def map_patient_class_to_dossier_type(patient_class: str) -> DossierType:
    """PV1-2 → Dossier"""
    mapping = {
        "I": DossierType.HOSPITALISE,
        "O": DossierType.EXTERNE,
        "E": DossierType.URGENCE
    }
    return mapping.get(patient_class, DossierType.HOSPITALISE)
```

---

## 📝 Implémentation Requise: Synchronisation en Réception

### Dans import_hl7_mouvement.py

```python
def import_mouvement_from_hl7(hl7_message, venue, session):
    """
    Importe un mouvement depuis HL7 ET synchronise dossier_type si A06/A07.
    """
    
    # 1. Parser le message
    event_code = extract_event_code(hl7_message)  # A06, A07, etc.
    pv1_2 = extract_pv1_2(hl7_message)  # I, O, E
    nature = extract_nature_from_hl7(hl7_message)
    
    # 2. NOUVEAU: Synchroniser dossier_type pour A06/A07
    if event_code in ["A06", "A07"] and pv1_2:
        dossier = venue.dossier
        
        # Mapper PV1-2 → dossier_type
        new_dossier_type = map_patient_class_to_dossier_type(pv1_2)
        
        # Valider transition (optionnel mais recommandé)
        old_type = dossier.dossier_type
        if old_type != new_dossier_type:
            logger.info(
                f"A06/A07 synchronization: {old_type} → {new_dossier_type} "
                f"(PV1-2={pv1_2})"
            )
            
            # Mettre à jour le dossier
            dossier.dossier_type = new_dossier_type
            session.add(dossier)  # Marquer pour commit
    
    # 3. Créer le mouvement (comme avant)
    mouvement = Mouvement(
        trigger_event=event_code,
        nature=nature,
        when=extracted_timestamp,
        venue_id=venue.id
    )
    
    session.add(mouvement)
    session.commit()
```

### Validation Sémantique Enrichie

```python
def validate_a06_a07_dossier_sync(hl7_message, venue, session):
    """
    Valide que A06/A07 apporte une cohérence au dossier_type.
    """
    
    event_code = extract_event_code(hl7_message)
    pv1_2 = extract_pv1_2(hl7_message)
    
    if event_code not in ["A06", "A07"]:
        return ValidationResult(is_valid=True)  # Pas une transition
    
    # Vérifier que PV1-2 change
    dossier = venue.dossier
    old_type = str(dossier.dossier_type.value) if dossier.dossier_type else "IMP"
    old_pv1_2 = map_dossier_type_to_patient_class(old_type)
    
    if pv1_2 == old_pv1_2:
        # PV1-2 n'a pas changé → avertissement
        return ValidationResult(
            is_valid=True,
            issues=[
                ValidationIssue(
                    "A06_A07_NO_CLASS_CHANGE",
                    f"A06/A07 with unchanged PV1-2 ({pv1_2})",
                    severity="warn"
                )
            ]
        )
    
    # Valider l'inverse A06/A07
    if event_code == "A06":
        # A06: doit passer de I → O (ou E → I, etc.)
        if not (old_pv1_2 != pv1_2):
            return ValidationResult(
                is_valid=False,
                issues=["A06 must change PV1-2"]
            )
    elif event_code == "A07":
        # A07: doit passer de H (I) → S (O)
        if not (old_pv1_2 != pv1_2):
            return ValidationResult(
                is_valid=False,
                issues=["A07 must change PV1-2"]
            )
    
    return ValidationResult(is_valid=True)
```

---

## 📊 État de l'Implémentation

### ✅ Déjà Implémenté

| Aspect | Statut | Où |
|---|---|---|
| dossier_type défini | ✅ | app/models.py |
| Mapping ÉMISSION | ✅ | emit_on_create.py (lines 401-413) |
| A06/A07 auto-detection | ✅ | emit_on_create.py (lines 465-513) |
| PV1-2 en réception | ✅ | import_hl7_mouvement.py (nature extraction) |
| Validation structure | ✅ | pam_validation.py |

### 🔄 À Ajouter

| Aspect | Priorité | Description |
|---|---|---|
| Mapping RÉCEPTION | 🔴 HIGH | PV1-2 → dossier_type en import |
| Synchronisation Dossier | 🔴 HIGH | Mettre à jour dossier_type lors A06/A07 |
| Validation Cohérence | 🟡 MEDIUM | Valider que PV1-2 change avec A06/A07 |
| Tests d'Intégration | 🟡 MEDIUM | Tester cycle complet émission↔réception |

---

## 🎯 Cas d'Usage: Cycle Complet Testé

### Test: Création + Changement + Réception + Synchronisation

```python
def test_a06_dossier_type_sync():
    """Test que A06 en réception synchronise dossier_type."""
    
    # 1. Créer dossier HOSPITALISE (via UI ou A01)
    dossier = Dossier(
        dossier_type=DossierType.HOSPITALISE,
        patient_id=1
    )
    venue = Venue(dossier_id=dossier.id)
    session.add(dossier)
    session.add(venue)
    session.commit()
    
    # 2. Simuler réception A06 avec PV1-2=O
    hl7_message = """MSH|...
EVN|A06|...
PID|...
PV1|1|O|...
ZBE|...|S|A06|..."""
    
    # 3. Importer (doit synchroniser dossier_type)
    import_mouvement_from_hl7(hl7_message, venue, session)
    
    # 4. Vérifier synchronisation
    session.refresh(dossier)
    assert dossier.dossier_type == DossierType.EXTERNE, \
        "dossier_type doit être EXTERNE après A06 en réception"
    
    # 5. Vérifier mouvement
    mouvement = session.exec(
        select(Mouvement).where(Mouvement.venue_id == venue.id)
    ).first()
    assert mouvement.trigger_event == "A06"
    assert mouvement.nature == "S"
```

---

## 📌 Résumé: Synchronisation Bidirectionnelle

### ÉMISSION (existant)
```
Dossier.dossier_type → patient_class → PV1-2 → Message HL7
```

### RÉCEPTION (À AJOUTER)
```
Message HL7 → PV1-2 → patient_class → Dossier.dossier_type
```

### BOUCLE COMPLÈTE
```
┌─ Création locale: dossier_type = HOSPITALISE
│  → Génère A01 avec PV1-2 = I
│  ↓
├─ Réception A01 externe: PV1-2 = I
│  → Crée Dossier avec dossier_type = HOSPITALISE ✓
│  ↓
├─ Changement local: dossier_type = EXTERNE
│  → Génère A06 avec PV1-2 = O
│  ↓
├─ Réception A06 externe: PV1-2 = O
│  → Met à jour dossier_type = EXTERNE ✓
│  → Crée Mouvement A06
│  ↓
└─ SYNCHRONISÉ: Tous les systèmes connaissent le type actuel
```

**Implémentation requise:** Ajouter `map_patient_class_to_dossier_type()` et appeler dans `import_mouvement_from_hl7()` pour A06/A07. ✅
