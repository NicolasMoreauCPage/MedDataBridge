# Capture de Dossiers en Templates IHE Réutilisables

## Vue d'ensemble

Cette fonctionnalité permet de **capturer des dossiers/venues existants** comme **ScenarioTemplate** réutilisables, avec **indépendance totale** du dossier source.

### Principe

```
Dossier réel → capture_dossier_as_template() → ScenarioTemplate (snapshot)
                                               → matérialisation HL7/FHIR
                                               → rejeu sur endpoints
```

**Point clé** : Le template créé est un **SNAPSHOT** (copie des données à l'instant T), pas une référence. Vous pouvez supprimer ou modifier le dossier source sans affecter le template.

---

## Architecture

### Indépendance du Template

```
┌─────────────────┐
│ Dossier source  │  ← Peut être modifié/supprimé
│  - id: 42       │
│  - UF: "URG"    │
└─────────────────┘
        │
        │ capture (snapshot)
        ▼
┌──────────────────────────┐
│ ScenarioTemplate         │  ← Indépendant, immuable
│  - key: "captured.42..." │
│  - category: "captured"  │
│  - tags: ["real-data"]   │
└──────────────────────────┘
        │
        │ steps (snapshot)
        ▼
┌──────────────────────────┐
│ ScenarioTemplateStep     │  ← Pas de FK vers Mouvement/Venue
│  - narrative: "..."      │
│  - semantic_code: "..."  │
│  - reference_payload     │  ← Données copiées (texte)
└──────────────────────────┘

AUCUNE FOREIGN KEY vers Dossier/Venue/Mouvement
```

### Données Capturées

Pour chaque mouvement du dossier :
- **Ordre chronologique** (tri par `date_heure_mouvement`)
- **Code sémantique IHE** (ADMISSION_CONFIRMED, TRANSFER, DISCHARGE...)
- **Code HL7** (ADT^A01, ADT^A02, ADT^A03...)
- **Narrative** (description textuelle)
- **Délai suggéré** (écart avec mouvement précédent, en secondes)
- **Snapshot données** (type mouvement, service, UF...)

---

## Utilisation

### 1. Via l'Interface Web

#### Étape 1 : Accéder au dossier
```
http://localhost:8000/dossiers/{id}
```

#### Étape 2 : Cliquer sur "📦 Capturer comme template IHE"
Un formulaire <details> s'affiche avec :
- **Nom du template** (optionnel) : ex. "Parcours urgences COVID"
- **Description** (optionnel) : ex. "Admission urgences → transfert réa → sortie"

#### Étape 3 : Valider
Le template est créé avec :
- **key** : `captured.dossier_{id}_{timestamp}`
- **category** : `captured`
- **tags** : `["captured", "real-data", "dossier-{id}"]`
- **protocols_supported** : `"HL7v2,FHIR"`

#### Étape 4 : Retrouver le template
```
http://localhost:8000/scenarios/templates
```
Filtrer par catégorie "captured" ou tag "real-data".

---

### 2. Via l'API REST

#### Endpoint de capture
```http
POST /dossiers/{id}/capture-as-template
Content-Type: application/x-www-form-urlencoded

template_name=Parcours+urgences+COVID
template_description=Admission+urgences+→+transfert+réa+→+sortie
```

#### Réponse
```
HTTP 303 See Other
Location: /dossiers/{id}
Flash: "Template 'Parcours urgences COVID' créé avec succès (clé: captured.dossier_42_1733769600). Retrouvez-le dans /scenarios/templates"
```

---

### 3. Programmatique (Python)

```python
from sqlmodel import Session
from app.services.scenario_capture import capture_dossier_as_template

# Capturer un dossier
template = capture_dossier_as_template(
    db=session,
    dossier_id=42,
    template_name="Mon parcours patient",
    template_description="Admission → transfert → sortie",
    category="captured",  # Par défaut
)

print(f"Template créé : {template.key}")
print(f"Nombre de steps : {len(template.steps)}")
```

---

## Rejeu du Template Capturé

Une fois capturé, le template se comporte **exactement comme un template IHE importé** :

### 1. Matérialisation HL7v2 ou FHIR

```bash
# Générer HL7v2 pour EJ spécifique
curl -X POST "http://localhost:8000/scenarios/templates/captured.dossier_42_1733769600/materialize" \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "HL7v2",
    "ej_id": 1,
    "ipp_prefix": "9",
    "nda_prefix": "501"
  }'

# Générer FHIR Bundle
curl -X POST "http://localhost:8000/scenarios/templates/captured.dossier_42_1733769600/materialize" \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "FHIR",
    "ej_id": 1
  }'
```

### 2. Rejeu sur Endpoints

```bash
# Rejouer avec envoi sur endpoints
curl -X POST "http://localhost:8000/scenarios/templates/captured.dossier_42_1733769600/play" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "protocol=HL7v2&ej_id=1&endpoint_ids=1&endpoint_ids=2&ipp_prefix=9"
```

---

## Mapping Mouvement → Événement Sémantique

Logique d'inférence dans `_infer_semantic_event()` :

| Type Mouvement      | Statut Venue   | Code Sémantique        | Code HL7   | Rôle     |
|---------------------|----------------|------------------------|------------|----------|
| ENTREE/ADMISSION    | EN_COURS       | ADMISSION_CONFIRMED    | ADT^A01    | inbound  |
| ENTREE/ADMISSION    | autre          | PRE_ADMISSION          | ADT^A05    | inbound  |
| SORTIE/DISCHARGE    | *              | DISCHARGE              | ADT^A03    | inbound  |
| TRANSFERT/MUTATION  | *              | TRANSFER               | ADT^A02    | inbound  |
| ANNULATION          | *              | CANCEL_ADMIT           | ADT^A11    | inbound  |
| Autre               | *              | OTHER_EVENT            | ADT^A01    | inbound  |

**Personnalisation** : Modifier `_infer_semantic_event()` selon vos nomenclatures UF/types mouvements.

---

## Tests d'Indépendance

Fichier : `tests/test_scenario_capture_independence.py`

### Test 1 : Modification du Dossier Source
```python
def test_template_independence_after_dossier_modification(test_session):
    # 1. Créer dossier avec UF="URG"
    # 2. Capturer comme template
    # 3. Modifier dossier : UF="CHIRURGIE"
    # 4. Vérifier : template contient toujours "URG" (snapshot)
```

### Test 2 : Suppression du Dossier Source
```python
def test_template_independence_after_dossier_deletion(test_session):
    # 1. Créer dossier avec 2 mouvements
    # 2. Capturer comme template
    # 3. Supprimer dossier (cascade venues/mouvements)
    # 4. Vérifier : template existe toujours avec 2 steps intacts
```

### Test 3 : Absence de Foreign Keys
```python
def test_template_no_foreign_key_to_dossier(test_session):
    # Vérifier que ScenarioTemplate n'a pas de colonne dossier_id
    # Vérifier que ScenarioTemplateStep n'a pas de mouvement_id/venue_id
```

---

## Comparaison avec InteropScenario

| Critère                     | InteropScenario (ancien)       | ScenarioTemplate (nouveau)     |
|-----------------------------|--------------------------------|--------------------------------|
| **Abstraction**             | Messages concrets              | Événements sémantiques         |
| **Contexte**                | Hardcodé (IPP/NDA fixés)       | Matérialisable (IPP/NDA dynamiques) |
| **Réutilisabilité**         | 1 dossier = 1 scénario         | 1 template = N matérialisations |
| **Indépendance**            | Potentiellement couplé         | 100% indépendant (snapshot)    |
| **Standards**               | HL7 ou FHIR (pas les 2)        | HL7v2 + FHIR (multi-standard)  |
| **Import IHE**              | Non                            | Oui (~50 templates auto-importés) |
| **Capture dossiers**        | Non                            | Oui (cette feature)            |

---

## FAQ

### Q1 : Puis-je capturer un dossier plusieurs fois ?
**R** : Oui, chaque capture crée un nouveau template avec un timestamp unique dans la clé.

### Q2 : Que se passe-t-il si je supprime le dossier source ?
**R** : Rien ! Le template est un snapshot indépendant. Les données sont copiées (pas de FK).

### Q3 : Puis-je modifier un template capturé ?
**R** : Les templates sont en lecture seule pour garantir la reproductibilité. Capturez à nouveau pour créer une nouvelle version.

### Q4 : Comment identifier les templates capturés ?
**R** : Filtrez par `category="captured"` ou tag `"real-data"` dans `/scenarios/templates`.

### Q5 : Les délais entre steps sont-ils préservés ?
**R** : Oui, `delay_suggested_seconds` est calculé depuis les écarts temporels réels entre mouvements.

### Q6 : Puis-je capturer un dossier sans mouvements ?
**R** : Non, une `ValueError` est levée. Un dossier doit avoir au moins 1 venue et 1 mouvement.

---

## Évolutions Futures

### Phase 1 (actuelle) : Snapshot basique
✅ Capture Dossier + Venues + Mouvements  
✅ Inférence sémantique simple  
✅ Indépendance totale (pas de FK)  
✅ Matérialisation HL7v2 + FHIR  

### Phase 2 : Enrichissement clinique
🔲 (Option hors profil) Capturer diagnostics (DG1)
🔲 (Option hors profil) Capturer allergies (AL1)
🔲 Capturer observations vitales (OBX)  
🔲 Capturer prescriptions (RXO/RXE)  

### Phase 3 : Filtres et compression
🔲 Exclure types mouvements (ex: annulations)  
🔲 Compresser délais longs (ex: >24h → 1h)  
🔲 Regrouper transfers multiples  

### Phase 4 : Corrélation avancée
🔲 Matching avec MessageLog existants (si disponibles)  
🔲 Réutilisation payloads originaux (si corrélation réussie)  
🔲 Mode hybride : snapshot + référence optionnelle  

---

## Statistiques

Au 9 novembre 2025 :
- **1 service de capture** : `scenario_capture.py` (~165 lignes)
- **1 endpoint API** : `POST /dossiers/{id}/capture-as-template`
- **1 formulaire UI** : dans `dossier_detail.html` (details amber)
- **3 tests indépendance** : `test_scenario_capture_independence.py` (~230 lignes)
- **5 codes sémantiques IHE** : ADMISSION_CONFIRMED, PRE_ADMISSION, TRANSFER, DISCHARGE, CANCEL_ADMIT
- **Catégorie** : `captured`
- **Tags par défaut** : `["captured", "real-data", "dossier-{id}"]`

---

## Ressources

- **Service** : `app/services/scenario_capture.py`
- **Endpoint** : `app/routers/dossiers.py` ligne ~405
- **UI** : `app/templates/dossier_detail.html` ligne ~70
- **Tests** : `tests/test_scenario_capture_independence.py`
- **Doc matérialisation** : `SCENARIO_TEMPLATES.md`
- **Doc modèles** : `app/models_scenarios.py`
