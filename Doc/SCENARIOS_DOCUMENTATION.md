# Documentation des Scénarios d'Interopérabilité

## Vue d'ensemble

Le module de scénarios permet de créer, gérer et exécuter des séquences de messages HL7v2 et FHIR pour tester l'interopérabilité avec des systèmes tiers. Il offre :

- **Templates prédéfinis** : modèles IHE PAM réutilisables (admission, transfert, sortie)
- **Matérialisation** : génération de scénarios concrets avec identifiants uniques
- **Exécution** : envoi vers des endpoints configurés (dry-run ou réel)
- **Dashboard** : statistiques, timeline et analyse des ACK

## Architecture

### Modèles de données

```
ScenarioTemplate          →  InteropScenario           →  ScenarioExecutionRun
     (modèle)               (instance concrète)            (trace d'exécution)
        │                           │                              │
        ▼                           ▼                              ▼
ScenarioTemplateStep      InteropScenarioStep          ScenarioExecutionStepLog
   (étapes types)            (messages HL7)              (logs par étape)
```

#### ScenarioTemplate

Modèle abstrait définissant une séquence d'événements métier.

| Champ | Type | Description |
|-------|------|-------------|
| `key` | string | Identifiant unique (ex: `ihe.hospitSimple`) |
| `name` | string | Nom lisible |
| `category` | string | `IHE`, `DEMO`, `TEST`, `CUSTOM` |
| `protocols_supported` | string | `HL7v2`, `FHIR`, `HL7v2,FHIR` |
| `steps` | relation | Étapes du template |

#### InteropScenario

Instance concrète d'un template avec les messages HL7/FHIR générés.

| Champ | Type | Description |
|-------|------|-------------|
| `key` | string | Identifiant unique |
| `protocol` | string | `HL7`, `FHIR`, `MIXED` |
| `time_anchor_mode` | string | `now`, `admission_minus_days`, `fixed_start` |
| `preserve_intervals` | bool | Conserver les délais entre événements |
| `jitter_min_minutes` | int | Jitter minimum (optionnel) |
| `jitter_max_minutes` | int | Jitter maximum (optionnel) |
| `steps` | relation | Messages à envoyer |

### Services

| Service | Fichier | Description |
|---------|---------|-------------|
| **Materializer** | `scenario_template_materializer.py` | Génère un `InteropScenario` depuis un `ScenarioTemplate` |
| **Runner** | `scenario_runner.py` | Exécute un scénario (envoi MLLP ou dry-run) |
| **Capture** | `scenario_capture.py` | Capture un dossier existant en scénario |
| **Import** | `scenario_import.py` | Import depuis JSON ou fichiers IHE |
| **Dashboard** | `scenario_dashboard.py` | Statistiques et analytics |
| **Timeplan** | `scenario_timeplan.py` | Calcul avancé des horodatages |

## Utilisation

### 1. Via l'interface web

#### Accéder aux scénarios

Menu **Interopérabilité** → **Scénarios** ou directement `/scenarios`

#### Consulter les templates

`/scenarios/templates` — Liste des modèles prédéfinis disponibles

#### Matérialiser un template

1. Cliquer sur un template
2. Sélectionner l'entité juridique (EJ)
3. Configurer les préfixes d'identifiants (optionnel)
4. Cliquer sur "Matérialiser"

#### Exécuter un scénario

1. Ouvrir un scénario matérialisé
2. Sélectionner un endpoint de destination
3. Choisir le mode :
   - **Dry-run** : prévisualisation sans envoi
   - **Envoi réel** : transmission MLLP
4. Cliquer sur "Envoyer"

#### Dashboard des exécutions

`/scenarios/runs` — Vue d'ensemble des exécutions

- Statistiques globales (taux de succès, durée moyenne)
- Distribution des codes ACK
- Timeline des exécutions
- Filtres par scénario, endpoint, période

### 2. Via l'API REST

#### Lister les scénarios

```http
GET /scenarios
```

#### Détail d'un scénario

```http
GET /scenarios/{scenario_id}
```

#### Exporter en JSON

```http
GET /scenarios/{scenario_id}/export
```

Réponse :

```json
{
  "id": 1,
  "key": "test-scenario",
  "name": "Scénario de test",
  "protocol": "HL7",
  "time_config": {
    "anchor_mode": "now",
    "preserve_intervals": true
  },
  "steps": [
    {
      "order_index": 1,
      "message_type": "ADT^A01",
      "format": "hl7",
      "payload": "MSH|^~\\&|..."
    }
  ]
}
```

#### Importer depuis JSON

```http
POST /scenarios/import
Content-Type: multipart/form-data

ght_context_id=1
json_file=@scenario.json
```

#### Envoyer un scénario

```http
POST /scenarios/{scenario_id}/send
Content-Type: application/x-www-form-urlencoded

endpoint_id=1&dry_run=false
```

#### API Dashboard

```http
GET /scenarios/api/stats?days_back=30
GET /scenarios/api/ack-distribution?scenario_id=1
GET /scenarios/api/timeline?endpoint_id=2
GET /scenarios/api/comparison?limit=10
GET /scenarios/runs.json
```

### 3. Capture depuis un dossier

Pour capturer les messages d'un dossier existant :

```http
POST /scenarios/capture
Content-Type: application/x-www-form-urlencoded

dossier_id=123
```

Cela crée un `InteropScenario` à partir des `MessageLog` du dossier.

## Configuration avancée

### Recalage temporel (Time Shifting)

Le système peut recaler automatiquement les horodatages des messages :

| Mode | Description |
|------|-------------|
| `now` | L'admission démarre maintenant |
| `admission_minus_days` | L'admission démarre il y a N jours |
| `fixed_start` | Horodatage fixe (ISO 8601) |

Exemple de configuration :

```python
scenario.time_anchor_mode = "admission_minus_days"
scenario.time_anchor_days_offset = 3  # Admission il y a 3 jours
scenario.preserve_intervals = True     # Garder les délais entre événements
```

### Jitter (variation aléatoire)

Pour simuler des variations réalistes :

```python
scenario.jitter_min_minutes = 5
scenario.jitter_max_minutes = 30
scenario.apply_jitter_on_events = "A02,A03,A06,A07,A08"  # Transferts, sorties
```

### Préfixes d'identifiants

Pour éviter les collisions avec les données existantes :

```python
options = MaterializationOptions(
    ipp_prefix="TEST",      # IPP → TEST00000001
    nda_prefix="SC",        # NDA → SC0000001
    namespace_oid="1.2.3.4" # Namespace dans CX
)
```

## Templates IHE PAM disponibles

### Hospitalisation simple (`ihe.hospitSimple`)

Parcours standard d'hospitalisation :

1. `PARCOURS_START` — Ouverture du parcours
2. `ADMISSION_PLANNED` — Pré-admission (A14)
3. `ADMISSION_CONFIRMED` — Admission confirmée (A01)
4. `TRANSFER_OUT` — Sortie de service (A02)
5. `TRANSFER_IN` — Entrée dans nouveau service (A02)
6. `DISCHARGE` — Sortie (A03)
7. `PARCOURS_END` — Clôture du parcours

### Autres templates

D'autres templates sont importés automatiquement depuis les fichiers IHE PAM si disponibles dans `Doc/interfaces.integration_src/`.

## Statistiques et Dashboard

### Métriques disponibles

- **Taux de succès** : % de runs terminés sans erreur
- **Durée moyenne** : temps d'exécution moyen par scénario
- **Distribution ACK** : répartition des codes de réponse (AA, AE, AR)
- **Erreurs récentes** : dernières anomalies rencontrées

### Filtres

- Par scénario
- Par endpoint de destination
- Par période (derniers N jours)
- Par statut (success, error, partial, dry_run)

## Bonnes pratiques

### Tests d'intégration

1. **Dry-run d'abord** : toujours prévisualiser avant envoi réel
2. **Utiliser des préfixes** : éviter les collisions d'identifiants
3. **Vérifier les ACK** : s'assurer que le système cible répond correctement
4. **Conserver les traces** : les logs d'exécution permettent le debug

### Production

1. **Endpoints séparés** : utiliser des endpoints dédiés pour les tests
2. **Monitoring** : surveiller le dashboard pour détecter les anomalies
3. **Export régulier** : sauvegarder les scénarios fonctionnels en JSON

## Dépannage

### Erreur 422 sur `/scenarios/import`

**Cause** : Champ `ght_context_id` manquant dans le formulaire.

**Solution** : Sélectionner un contexte GHT dans le formulaire d'import.

### ACK AE ou AR

**Cause** : Le message n'est pas conforme aux attentes du système cible.

**Vérifications** :
- Valider la structure HL7 (segments obligatoires)
- Vérifier les identifiants (format IPP/NDA)
- Consulter les logs du système cible

### Timeout MLLP

**Cause** : L'endpoint ne répond pas dans le délai imparti.

**Solutions** :
- Vérifier la connectivité réseau
- Augmenter le timeout dans la configuration de l'endpoint
- Vérifier que le service MLLP distant est actif

## Fichiers clés

```
app/
├── models_scenarios.py              # Modèles ScenarioTemplate, InteropScenario
├── models_scenario_runs.py          # Modèles d'exécution (Run, StepLog)
├── routers/
│   ├── scenarios.py                 # Routes UI et API (/scenarios/*)
│   └── scenario_templates.py        # Routes templates (/scenarios/templates/*)
├── services/
│   ├── scenario_runner.py           # Exécution des scénarios
│   ├── scenario_template_materializer.py  # Génération depuis templates
│   ├── scenario_capture.py          # Capture depuis dossiers
│   ├── scenario_import.py           # Import JSON
│   ├── scenario_dashboard.py        # Analytics
│   └── scenario_timeplan.py         # Calcul des horodatages
└── templates/
    ├── scenario_detail.html         # Détail d'un scénario
    ├── scenario_import.html         # Formulaire d'import
    ├── scenario_template_detail.html # Détail d'un template
    └── scenarios/
        └── dashboard.html           # Dashboard des exécutions
```

## Voir aussi

- [Guide API développeur](api_guide.md) — Section Scénarios
- [IHE PAM — Intégration](IHE_PAM_INTEGRATION_COMPLETE_FR.md) — Profil IHE PAM France
- [Préfixes d'identifiants](identifier_prefixes.md) — Configuration des préfixes
