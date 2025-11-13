# PV1-2 et Chaîne de Génération des Messages A06/A07

## 📋 Confirmation: A06/A07 = Changement PV1-2

**OUI, vous avez raison !** Les A06 et A07 sont directement liés aux **changements du champ PV1-2** (Patient Class) dans les messages IHE PAM.

```
A06 = Transfer to another care setting   (Change in patient_class in HL7)
A07 = Transfer from another care setting (Change in patient_class in HL7)
```

---

## 🔗 Chaîne de Génération: Modèle → Message IHE PAM

### 1️⃣ **Modèle (Source de Vérité)**

```
┌─────────────────────────────────────────┐
│ Dossier (Encounter - niveau patient)    │
├─────────────────────────────────────────┤
│ dossier_type: DossierType               │  ← Détermine PV1-2
│   - HOSPITALISE → "I" (Inpatient)       │
│   - EXTERNE     → "O" (Outpatient)      │
│   - URGENCE     → "E" (Emergency)       │
└─────────────────────────────────────────┘

        ↓ (contains)

┌─────────────────────────────────────────┐
│ Venue (Episode - niveau stay)           │
├─────────────────────────────────────────┤
│ nature: str (S/H/O/U)                   │  ← Dérivé de PV1-2
│ start_time: datetime                    │
│ uf_responsabilite: str                  │
│ uf_soins_code: str                      │
└─────────────────────────────────────────┘

        ↓ (contains)

┌─────────────────────────────────────────┐
│ Mouvement (Movement - niveau transition)│
├─────────────────────────────────────────┤
│ trigger_event: str (A01, A06, A07...)   │  ← Déterminé par PV1-2 change
│ nature: str (S/H/O/U)                   │  ← Dérivé de PV1-2
│ when: datetime                          │
│ uf_responsabilite: str                  │
│ uf_soins_code: str                      │
└─────────────────────────────────────────┘
```

---

## 🎯 Chaîne Causale: PV1-2 → A06/A07

### Étape 1: **Création du Dossier**

**Flux de création UI:**
```
User Interface
  ↓
Crée un Dossier avec encounter_class (IMP, AMB, EMER)
  ↓
Exemple: encounter_class = "IMP" (hospitalisé)
  ↓
Génère automatiquement:
  - dossier_type = HOSPITALISE
  - patient_class = "I" ← Direct mapping
```

**Code dans `emit_on_create.py` (ligne 413):**
```python
patient_class_map = {"hospitalise": "I", "externe": "O", "urgence": "E", "IMP": "I", "AMB": "O", "EMER": "E"}
patient_class = patient_class_map.get(encounter_class, "I")
```

### Étape 2: **Première Venue**

**À la création du Dossier (ADT^A01/A03):**
```
Dossier.dossier_type = "HOSPITALISE"
  ↓
Crée une Venue avec:
  - nature = "H" ← Extrait du mapping
  - trigger_event = "A01" (admission) ou "A03" (outpatient)
  
Message généré:
  PV1|1|I|location|...  ← patient_class = "I"
  ZBE|2|H|A01|...       ← nature = "H"
```

### Étape 3: **Changement de Type de Dossier → A06 ou A07**

**Scénario: Passage d'un patient de HOSPITALISE → EXTERNE**

```
Dossier.dossier_type = "HOSPITALISE" (PV1-2 = "I")
  ↓
User change le dossier_type → "EXTERNE"
  ↓
Détection du changement dans emit_on_create.py:
  - ancien_type: HOSPITALISE (nature = "H")
  - nouveau_type: EXTERNE (nature = "S")
  ↓
Génère automatiquement:
  - trigger_event = "A07" ← (Transfer from inpatient)
  - message.patient_class = "O" ← Nouveau patient_class
  - mouvement.nature = "S" ← Nouveau nature
  
Message généré:
  PV1|1|O|location|...  ← patient_class CHANGE: "I" → "O"
  ZBE|2|S|A07|...       ← nature CHANGE: "H" → "S"
```

**Scénario inverse: EXTERNE → HOSPITALISE (A06)**

```
Dossier.dossier_type = "EXTERNE" (PV1-2 = "O")
  ↓
User change le dossier_type → "HOSPITALISE"
  ↓
Génère automatiquement:
  - trigger_event = "A06" ← (Transfer to inpatient)
  - message.patient_class = "I" ← Nouveau patient_class
  - mouvement.nature = "H" ← Nouveau nature
  
Message généré:
  PV1|1|I|location|...  ← patient_class CHANGE: "O" → "I"
  ZBE|2|H|A06|...       ← nature CHANGE: "S" → "H"
```

---

## 📊 Tableau des Mappings

### PV1-2 ↔ dossier_type ↔ nature

| dossier_type   | patient_class (PV1-2) | nature (ZBE-2/PV1-2) | Cas d'usage |
|---|---|---|---|
| HOSPITALISE | `I` | `H` | Patient hospitalisé (inpatient) |
| EXTERNE | `O` | `S` | Patient ambulatoire (outpatient) |
| URGENCE | `E` | `O` | Patient urgence (emergency) |

### Transitions → Trigger Events

| Changement | Nouveau PV1-2 | Trigger Event | Nouveau Mouvement |
|---|---|---|---|
| HOSPITALISE → EXTERNE | I → O | **A07** | Transfer from inpatient |
| EXTERNE → HOSPITALISE | O → I | **A06** | Transfer to inpatient |
| URGENCE → HOSPITALISE | E → I | **A06** | Transfer to inpatient |
| HOSPITALISE → URGENCE | I → E | **A07** | Transfer from inpatient |
| EXTERNE → URGENCE | O → E | **A07** | Transfer from inpatient |
| URGENCE → EXTERNE | E → O | **A07** | Transfer from inpatient |

---

## 🔄 Champs du Modèle Liés à PV1-2

### Dossier (niveau patient)
```python
class Dossier:
    dossier_type: DossierType  # ← Directement mappé à patient_class (PV1-2)
    # De ce champ dépend:
    #   - patient_class dans le message HL7
    #   - trigger_event (A06/A07 auto-détection)
    #   - nature de la Venue
```

### Venue (niveau séjour)
```python
class Venue:
    nature: Optional[str]      # ← Extrait du dossier_type via PV1-2
    # Représente le type de soins pour cet épisode
```

### Mouvement (niveau transition)
```python
class Mouvement:
    trigger_event: Optional[str]      # ← AUTO-DÉTECTÉ: A06/A07 si dossier_type change
    nature: Optional[str]             # ← Extrait de PV1-2 en réception
    # ZBE fields:
    action: Optional[str]             # INSERT|UPDATE|CANCEL (ZBE-4)
    original_trigger: Optional[str]    # Trigger original si UPDATE/CANCEL (ZBE-6)
```

---

## 🚀 Processus Complet: Création → Émission → Réception

### 1️⃣ **Création (UI)**

```
┌─────────────────────────────────────────────────────────────┐
│ POST /api/dossiers (create)                                 │
│ Body: { encounter_class: "IMP" (dossier_type: HOSPITALISE) }│
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ GÉNÉRATION DE MESSAGE (emit_on_create.py)                   │
│ 1. Mappe: IMP → patient_class = "I"                         │
│ 2. Crée Dossier + Venue + Mouvement (A01)                   │
│ 3. Génère HL7 message:                                      │
│    MSH|...                                                  │
│    EVN|A01|...                                              │
│    PV1|1|I|...  ← patient_class = "I"                      │
│    ZBE|2|H|A01|... ← nature = "H"                          │
└─────────────────────────────────────────────────────────────┘
```

### 2️⃣ **Changement de Type (UI)**

```
┌──────────────────────────────────────────────────────────┐
│ PUT /api/dossiers/{id} (update type)                     │
│ Body: { dossier_type: "EXTERNE" }  ← Change HOSPITALISÉ │
└──────────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│ AUTO-DÉTECTION (emit_on_create.py)                       │
│ - Comparer ancien vs nouveau dossier_type                │
│ - Détecte: HOSPITALISE → EXTERNE                         │
│ - Génère trigger_event = "A07" ← AUTO-DETECTÉ            │
│ - Crée Mouvement(trigger_event="A07")                    │
│ - Génère message:                                        │
│   MSH|...                                                │
│   EVN|A07|...                                            │
│   PV1|1|O|...  ← patient_class CHANGE: "I" → "O"       │
│   ZBE|2|S|A07|... ← nature CHANGE: "H" → "S"           │
└──────────────────────────────────────────────────────────┘
```

### 3️⃣ **Réception du Message**

```
┌────────────────────────────────────────────────────────┐
│ POST /api/hl7/import (import)                          │
│ Message: ADT^A07 avec PV1|1|O|...                      │
└────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│ PARSING (import_hl7_mouvement.py)                      │
│ 1. Parse PV1-2: "O"                                    │
│ 2. Extract nature via:                                 │
│    - Priority 1: ZBE-2 (France standard)               │
│    - Priority 2: PV1-2 mapping                         │
│       - "O" → nature = "S"                             │
│ 3. Crée Mouvement:                                     │
│    - trigger_event = "A07" (from EVN-1)                │
│    - nature = "S" (from ZBE-2 or PV1-2)               │
│ 4. Valide cohérence A07:                               │
│    - Require: previous nature = "H" ✓                  │
│    - Valide: "H" → "S" OK                              │
└────────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────────┐
│ DATABASE UPDATE                                         │
│ Mouvement(                                              │
│   trigger_event="A07",                                 │
│   nature="S",                                          │
│   ...                                                  │
│ ) ← PERSISTED                                           │
└────────────────────────────────────────────────────────┘
```

---

## 📝 Résumé: Relation PV1-2 ↔ A06/A07

### **Implication Directe**

```
PV1-2 CHANGE
    ↓
A06 ou A07 DÉTECTÉ
    ↓
Mouvement créé/importé avec nature correcte
    ↓
Message IHE PAM valide
```

### **Champs du Modèle Impliqués**

| Entité | Champ | Lien à PV1-2 | Impact A06/A07 |
|---|---|---|---|
| **Dossier** | `dossier_type` | Mappé directement | Détermine si A06/A07 sera détecté |
| **Venue** | `nature` | Extrait du dossier_type | Détermine transition valide |
| **Mouvement** | `trigger_event` | AUTO = A06/A07 si change | Peuplé automatiquement |
| **Mouvement** | `nature` | Extrait de PV1-2 | Validé à la réception |

### **Validation en Réception**

```python
# En réception, validation sémantique (non-bloquante):
if trigger_event == "A06":
    # Valide: doit avoir une Venue antérieure avec nature="S"
    # A06 = transition S → H (externe → hospitalisé)
    
elif trigger_event == "A07":
    # Valide: doit avoir une Venue antérieure avec nature="H"
    # A07 = transition H → S (hospitalisé → externe)
```

---

## ✅ Conclusion

**Vous avez raison:** Les A06 et A07 ne sont pas simplement "des messages qui créent des mouvements" - ils représentent un **changement dans le champ PV1-2 du message IHE PAM**.

Les champs du modèle liés à cette logique:
1. **`Dossier.dossier_type`** - Source de vérité (détermine PV1-2)
2. **`Venue.nature`** - État du séjour (dérivé de PV1-2)
3. **`Mouvement.trigger_event`** - Événement (A06/A07 détecté via changement dossier_type)
4. **`Mouvement.nature`** - Nature du mouvement (extrait de PV1-2 en réception)

La chaîne complète est **entièrement tracée et validée** ✅
