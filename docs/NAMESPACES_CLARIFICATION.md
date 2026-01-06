# Clarification des Namespaces : OID, URI et System

## 🔍 Le Problème Identifié

Il existe une confusion dans l'application entre les concepts de **namespace** dans deux standards différents :

### HL7v2 : Namespace = NOM + OID
En HL7v2, un "namespace" (Assigning Authority dans CX-4) est composé de :
- **Nom** (texte) : ex. `"CHPAULON"`
- **OID** (numérique) : ex. `"1.2.250.1.71.1.2.2"`
- Format reçu : `NOM&OID&ISO` ou `NOM` seul ou `OID` seul
- ⚠️ **On ne reçoit JAMAIS d'URI en HL7v2**

### FHIR : Namespace = URI
En FHIR, un "namespace" (Identifier.system) est :
- **URI** uniquement : ex. `"urn:oid:1.2.250.1.71.1.2.2"`
- ⚠️ **On ne reçoit PAS de nom ni d'OID séparés en FHIR**

Cette confusion vient de l'héritage historique de la santé numérique française qui doit gérer **deux standards différents** : **HL7v2** (ancien) et **FHIR** (moderne).

---

## 📊 Structure Actuelle du Modèle

```python
class IdentifierNamespace(SQLModel, table=True):
    id: int                      # Clé primaire interne
    name: Optional[str]          # ❓ LIBELLÉ DESCRIPTIF (ex: "IPP EJ Principal")
    system: str                  # ✅ URI FHIR (ex: "urn:oid:1.2.250.1.71.1.2.2")
    oid: Optional[str]           # ⚠️ OID HL7v2 (ex: "1.2.250.1.71.1.2.2")
    type: str                    # Type d'identifiant (IPP, NDA, MVT, VN, PC)
    description: Optional[str]   # Description longue
    is_active: bool
    ght_context_id: int          # Lien vers GHT/EJ
```

### 🎯 Le Rôle de Chaque Champ

| Champ | Format | D'où ça vient ? | Utilisé pour ? | Exemple |
|-------|--------|-----------------|----------------|------|
| **name** | Texte libre | HL7v2 CX-4 (partie nom) | Export HL7v2, Affichage IHM | `"CHPAULON"` |
| **oid** | Suite de chiffres | HL7v2 CX-4 (partie OID) | Export HL7v2 | `"1.2.250.1.71.1.2.2"` |
| **system** | URI | FHIR Identifier.system | Export FHIR | `"urn:oid:1.2.250.1.71.1.2.2"` |

**Note importante** : 
- En **import HL7v2**, on reçoit `NOM` et `OID` séparés (format `NOM&OID&ISO`)
- En **import FHIR**, on reçoit seulement `URI` (format `urn:oid:X.Y.Z`)
- En **export HL7v2**, on doit reconstruire `NOM&OID&ISO` depuis name + oid
- En **export FHIR**, on utilise system (URI)

---

## 🔄 Comment Sont-Ils Utilisés dans l'Application

### 1️⃣ **Import HL7v2 → Base de Données**

Quand un message HL7v2 arrive (ex: `ADT^A01`), le segment PID-3 contient :
```
PID|1||123456^^^CHPAULON&1.2.250.1.71.1.2.2&ISO^PI
           │       └────┬────┘ └────────┬────────┘ │
        Valeur        NOM              OID      Type
```

**3 formats possibles en HL7v2 CX-4** :
- `NOM&OID&ISO` → Complet (ex: `CHPAULON&1.2.250.1.71.1.2.2&ISO`)
- `NOM` → Nom seul (ex: `CHPAULON`)
- `OID` → OID seul (ex: `1.2.250.1.71.1.2.2`)

**Parsing dans `identifier_manager.py`** :
```python
def parse_hl7_cx_identifier(cx_value: str):
    # cx_value = "123456^^^CHPAULON&1.2.250.1.71.1.2.2&ISO^PI"
    parts = cx_value.split("^")
    value = "123456"                    # CX-1 : Valeur de l'identifiant
    system_full = "CHPAULON&1.2.250.1.71.1.2.2&ISO"  # CX-4 : Assigning Authority
    type_code = "PI"                    # CX-5 : Type d'identifiant
    
    # Extraction du NOM et de l'OID depuis CX-4
    if "&" in system_full:
        system_parts = system_full.split("&")
        authority_name = "CHPAULON"              # ✅ Nom de l'autorité (reçu en HL7v2)
        authority_oid = "1.2.250.1.71.1.2.2"    # ✅ OID de l'autorité (reçu en HL7v2)
    
    # ⚠️ On ne reçoit PAS d'URI en HL7v2 !
    # L'URI sera construite plus tard : "urn:oid:" + authority_oid
```

**Recherche du namespace** :
```python
# On cherche le namespace par OID (car c'est ce qu'on a reçu en HL7v2)
namespace = session.exec(
    select(IdentifierNamespace)
    .where(IdentifierNamespace.oid == authority_oid)
    .where(IdentifierNamespace.type == "IPP")
).first()

if namespace:
    # On stocke avec l'URI FHIR du namespace trouvé
    system_uri = namespace.system  # "urn:oid:1.2.250.1.71.1.2.2"
else:
    # Fallback : construire l'URI depuis l'OID
    system_uri = f"urn:oid:{authority_oid}"
```

### 2️⃣ **Export FHIR → Envoi URI Uniquement**

Quand on exporte un Patient vers FHIR dans `fhir_converter.py` :

```python
def create_identifier(identifier: Identifier, namespace: IdentifierNamespace) -> FHIRIdentifier:
    # En FHIR, on envoie UNIQUEMENT l'URI (depuis namespace.system)
    return FHIRIdentifier(
        system=namespace.system,    # ✅ URI FHIR (ex: "urn:oid:1.2.250.1.71.1.2.2")
        value=identifier.value       # Valeur de l'identifiant (ex: "123456")
    )
    # ⚠️ On n'envoie PAS le nom ni l'OID séparément en FHIR !

# Génération JSON FHIR
{
  "resourceType": "Patient",
  "identifier": [
    {
      "system": "urn:oid:1.2.250.1.71.1.2.2",   # ✅ URI complète
      "value": "123456"
    }
  ]
}
```

**Ce qui est envoyé** :
- ✅ **URI** : `"urn:oid:1.2.250.1.71.1.2.2"` (depuis `namespace.system`)
- ❌ **Nom** : NON envoyé (FHIR n'a pas ce concept)
- ❌ **OID seul** : NON envoyé (l'OID est intégré dans l'URI)

### 3️⃣ **Export HL7v2 → Reconstruction NOM + OID**

Quand on génère un message HL7v2 dans `hl7_generator.py` :

```python
# On a dans la base un Identifier avec system (URI FHIR)
identifier.system = "urn:oid:1.2.250.1.71.1.2.2"  # Ce qu'on a stocké (format FHIR)

# Recherche du namespace via URI
namespace = session.exec(
    select(IdentifierNamespace)
    .where(IdentifierNamespace.system == identifier.system)
).first()

if namespace:
    # On reconstruit le format HL7v2 : NOM&OID&ISO
    authority_name = namespace.name or namespace.type  # "CHPAULON" ou fallback "IPP"
    authority_oid = namespace.oid                      # "1.2.250.1.71.1.2.2"
    
    # Format CX : ID^^^NOM&OID&ISO^TYPE
    pid_3 = f"{identifier.value}^^^{authority_name}&{authority_oid}&ISO^PI"
    # Résultat: "123456^^^CHPAULON&1.2.250.1.71.1.2.2&ISO^PI"
else:
    # Fallback: extraire l'OID de l'URI et envoyer OID seul
    oid = identifier.system.split(":")[-1]  # "urn:oid:1.2.3.4" → "1.2.3.4"
    pid_3 = f"{identifier.value}^^^{oid}^PI"
    # Résultat: "123456^^^1.2.250.1.71.1.2.2^PI" (OID seul, sans nom)
```

**Récapitulatif export HL7v2** :
- ✅ **NOM** : Depuis `namespace.name` (ex: `"CHPAULON"`)
- ✅ **OID** : Depuis `namespace.oid` (ex: `"1.2.250.1.71.1.2.2"`)
- ❌ **URI** : NON envoyée (HL7v2 n'a pas ce concept)
- Format envoyé : `NOM&OID&ISO` ou `OID` seul si pas de nom

---

## 🚨 Problèmes Actuels

### Problème 1 : Confusion Terminologique dans l'IHM

**Template `ej_namespace_form.html`** :
```html
<label>System (URI)</label>
<input name="system" value="urn:oid:1.2.250.1.71.1.2.2">

<label>OID</label>
<input name="oid" value="1.2.250.1.71.1.2.2">
```

**Confusion** : L'utilisateur voit deux champs qui contiennent presque la même valeur :
- `system` : `"urn:oid:1.2.250.1.71.1.2.2"`
- `oid` : `"1.2.250.1.71.1.2.2"`

### Problème 2 : Le Champ `name` est Redondant

Le champ `name` est facultatif et uniquement affiché dans l'IHM, mais :
- Il n'est **jamais utilisé** dans les conversions FHIR
- Il est **parfois utilisé** dans les exports HL7v2 (CX-4 Authority Name)
- Il crée de la **confusion** : est-ce un identifiant technique ou un libellé ?

### Problème 3 : Validation Insuffisante

**Validation actuelle** (dans `namespaces.py`) :
```python
# ✅ Vérifie : system + type (correct depuis dernier commit)
existing = session.exec(
    select(IdentifierNamespace)
    .where(IdentifierNamespace.system == system)
    .where(IdentifierNamespace.type == type)
    .where(IdentifierNamespace.ght_context_id == context.id)
).first()
```

**Mais il manque** :
- Validation du format de l'OID (ex: doit être `\d+(\.\d+)+`)
- Cohérence entre `system` et `oid` (si `system` = `"urn:oid:X.Y.Z"`, alors `oid` doit être `"X.Y.Z"`)
- Avertissement si `system` ne commence pas par `"urn:oid:"` (rare mais possible pour d'autres URI)

---

## ✅ Recommandations de Clarification

### 1. Renommer les Champs dans l'IHM

**IHM actuelle (confuse)** :
```
[Nom] "IPP EJ Principal"
[System (URI)] "urn:oid:1.2.250.1.71.1.2.2"
[OID] "1.2.250.1.71.1.2.2"
```

**IHM proposée (claire)** :
```
[Libellé descriptif] "IPP EJ Principal"
  └─ Aide : "Nom affiché dans l'interface (ex: IPP EJ Principal, NDA Urgences)"

[URI FHIR (system)] "urn:oid:1.2.250.1.71.1.2.2"  [Obligatoire]
  └─ Aide : "Identifiant complet utilisé dans les ressources FHIR (format: urn:oid:X.Y.Z)"

[OID HL7v2] "1.2.250.1.71.1.2.2"  [Facultatif]
  └─ Aide : "Identifiant utilisé dans les messages HL7v2 (automatiquement extrait de l'URI si non renseigné)"
```

### 2. Validation Automatique

Ajouter dans `namespaces.py` :

```python
import re

def validate_namespace(system: str, oid: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Valide la cohérence entre system et oid.
    Returns: (is_valid, error_message)
    """
    # Vérifier que system est une URI
    if not system:
        return False, "L'URI FHIR (system) est obligatoire"
    
    # Si system est un urn:oid, extraire l'OID
    if system.startswith("urn:oid:"):
        extracted_oid = system[8:]  # Remove "urn:oid:"
        
        # Vérifier que l'OID est au bon format
        if not re.match(r'^\d+(\.\d+)+$', extracted_oid):
            return False, f"L'OID extrait '{extracted_oid}' n'est pas au format valide (ex: 1.2.250.1.71)"
        
        # Si l'utilisateur a fourni un OID, vérifier qu'il correspond
        if oid and oid != extracted_oid:
            return False, f"Incohérence : l'OID '{oid}' ne correspond pas à l'URI '{system}' (extrait: '{extracted_oid}')"
        
        # Si pas d'OID fourni, utiliser l'extrait
        if not oid:
            oid = extracted_oid
    
    # Si system n'est pas un urn:oid (rare), l'OID est facultatif
    elif oid:
        if not re.match(r'^\d+(\.\d+)+$', oid):
            return False, f"L'OID '{oid}' n'est pas au format valide (ex: 1.2.250.1.71)"
    
    return True, None
```

### 3. Auto-Complétion de l'OID

Si l'utilisateur saisit uniquement `system = "urn:oid:1.2.250.1.71.1.2.2"`, l'application doit **automatiquement extraire et remplir** `oid = "1.2.250.1.71.1.2.2"`.

```python
@router.post("/new")
async def create_namespace(..., system: str, oid: str = Form(None), ...):
    # Auto-extraction de l'OID
    if not oid and system.startswith("urn:oid:"):
        oid = system[8:]
    
    # Validation
    is_valid, error = validate_namespace(system, oid)
    if not is_valid:
        flash(request, error, "error")
        return RedirectResponse(...)
```

### 4. Documentation dans l'IHM

Ajouter une section d'aide dans `ej_namespace_form.html` :

```html
<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
  <h3 class="font-semibold text-blue-900 mb-2">📘 Comprendre les namespaces</h3>
  <ul class="text-sm text-blue-800 space-y-1">
    <li>• <strong>URI FHIR (system)</strong> : Identifiant complet utilisé dans les ressources FHIR (ex: urn:oid:1.2.250.1.71.1.2.2)</li>
    <li>• <strong>OID HL7v2</strong> : Identifiant court utilisé dans les messages HL7v2 (ex: 1.2.250.1.71.1.2.2) - extrait automatiquement de l'URI</li>
    <li>• <strong>Libellé</strong> : Nom descriptif affiché dans l'interface (ex: "IPP EJ Principal")</li>
    <li>• <strong>Type</strong> : Type d'identifiant (IPP=patient, NDA=dossier, VN=venue, MVT=mouvement)</li>
  </ul>
  <p class="text-sm text-blue-700 mt-2">
    💡 <strong>Astuce</strong> : Vous pouvez réutiliser la même URI pour plusieurs types (ex: IPP et NDA avec urn:oid:1.2.250.1.71.1.2.2)
  </p>
</div>
```

---

## 🧪 Tests de Validation

### Test 1 : Création Valide
```
Input:
  system = "urn:oid:1.2.250.1.71.1.2.2"
  oid = "" (vide)
  type = "IPP"

Expected:
  ✅ oid auto-rempli avec "1.2.250.1.71.1.2.2"
  ✅ Création réussie
```

### Test 2 : Incohérence
```
Input:
  system = "urn:oid:1.2.250.1.71.1.2.2"
  oid = "1.2.250.1.71.9.9.9"
  type = "IPP"

Expected:
  ❌ Erreur: "Incohérence : l'OID '1.2.250.1.71.9.9.9' ne correspond pas à l'URI..."
```

### Test 3 : Même URI, Types Différents
```
Input 1:
  system = "urn:oid:1.2.250.1.71.1.2.2"
  type = "IPP"
  ✅ Création OK

Input 2:
  system = "urn:oid:1.2.250.1.71.1.2.2"
  type = "NDA"
  ✅ Création OK (même URI, type différent)

Input 3:
  system = "urn:oid:1.2.250.1.71.1.2.2"
  type = "IPP"
  ❌ Erreur: "Un namespace de type 'IPP' avec l'URI '...' existe déjà"
```

---

## 📈 Schéma de Flux

```
┌─────────────────────────────────────────────────────────────────┐
│                    NAMESPACE CONFIGURATION                       │
│                                                                  │
│  IHM (User Input)                                               │
│  ┌────────────────────────────────────────┐                     │
│  │ Libellé: "IPP EJ Principal"            │ (optionnel, IHM)   │
│  │ Type: IPP                              │ (obligatoire)       │
│  │ URI FHIR: "urn:oid:1.2.250.1.71.1.2.2"│ (obligatoire)       │
│  │ OID HL7v2: [auto] "1.2.250.1.71.1.2.2"│ (auto-extrait)      │
│  └────────────────────────────────────────┘                     │
│                       ↓                                          │
│  Base de Données (IdentifierNamespace)                          │
│  ┌────────────────────────────────────────┐                     │
│  │ name: "IPP EJ Principal"               │                     │
│  │ type: "IPP"                            │                     │
│  │ system: "urn:oid:1.2.250.1.71.1.2.2"  │ → Pour FHIR        │
│  │ oid: "1.2.250.1.71.1.2.2"             │ → Pour HL7v2       │
│  └────────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
                       ↓                ↓
        ┌──────────────┘                └──────────────┐
        ↓                                              ↓
  FHIR Export                                    HL7v2 Export
  {                                              PID|1||123456
    "identifier": [                                  ^^^CHPAULON
      {                                                &1.2.250.1.71.1.2.2
        "system": "urn:oid:1.2.250.1.71.1.2.2",        &ISO^PI
        "value": "123456"
      }
    ]
  }
```

---

## 📝 Conclusion

### État Actuel
- ✅ Le modèle `IdentifierNamespace` est **techniquement correct**
- ✅ La validation `system + type` est **correcte**
- ⚠️ L'IHM est **confuse** pour l'utilisateur
- ⚠️ Pas de validation de **cohérence** entre `system` et `oid`

### Actions Prioritaires
1. **P0** : Améliorer les libellés dans l'IHM (renommer "System (URI)" → "URI FHIR")
2. **P0** : Ajouter une aide contextuelle expliquant la différence entre URI/OID
3. **P1** : Auto-extraction de l'OID depuis l'URI si non fourni
4. **P1** : Validation de cohérence entre `system` et `oid`
5. **P2** : Rendre le champ `oid` en lecture seule si extrait automatiquement

### Compatibilité Standards
- ✅ **FHIR R4** : Le champ `system` (URI) est correct
- ✅ **HL7v2** : Le champ `oid` est correct
- ✅ **IHE PAM** : Compatible avec les deux standards
- ✅ **ANS** : Conforme aux recommandations françaises (urn:oid:1.2.250.1.71.x.x.x)
