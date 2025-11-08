# Génération d'identifiants avec préfixes pour scénarios IHE

## Vue d'ensemble

Cette fonctionnalité permet de générer dynamiquement des identifiants (IPP, NDA, VENUE) avec des préfixes configurables pour éviter les collisions avec les données du système récepteur lors de l'exécution de scénarios de test.

## Problématique

Lors de l'envoi de scénarios IHE vers un logiciel connecté, les identifiants contenus dans les messages (IPP patient, NDA dossier) peuvent entrer en collision avec les données existantes du système récepteur. Par exemple:
- Le système récepteur gère les IPP de 1 à 100000
- Le système récepteur gère les NDA de 200000 à 300000

Si le scénario contient `IPP=42` ou `NDA=250000`, cela créera une collision avec les données réelles.

## Solution

### 1. Configuration des préfixes par namespace

Chaque `IdentifierNamespace` peut maintenant être configuré avec:

- **Mode "fixed"**: Préfixe fixe + chiffres aléatoires
  - Pattern: `9...` génère 9000-9999 (préfixe "9" + 3 chiffres)
  - Pattern: `91....` génère 91000-91999 (préfixe "91" + 4 chiffres)
  - Pattern: `501...` génère 501000-501999 (préfixe "501" + 3 chiffres)

- **Mode "range"**: Plage numérique complète
  - Exemple: min=9000000, max=9999999

### 2. Interface utilisateur

#### a) Configuration des namespaces

`/admin/ght/{id}/namespaces/{ns_id}/edit`

Nouveaux champs disponibles:
- **Mode de génération**: fixed (pattern) ou range (plage)
- **Pattern de préfixe**: ex: "9...", "91....", "501..."
- **Plage min/max**: pour mode "range"

#### b) Exécution de scénarios

`/dossiers/{id}` → Section "Relire un scénario"

Nouveaux champs dans le formulaire (section dépliable "Configuration des identifiants de test"):
- **Préfixe IPP**: Override ponctuel (ex: "9...")
- **Préfixe NDA**: Override ponctuel (ex: "501...")
- **Utiliser namespace test**: Checkbox pour isolation complète

### 3. Traçabilité

Chaque exécution de scénario enregistre:
- `ScenarioBinding.generated_ipp`: Dernier IPP généré
- `ScenarioBinding.generated_nda`: Dernier NDA généré  
- `ScenarioBinding.generated_venue_id`: Dernier VENUE généré
- `ScenarioBinding.last_execution_at`: Date/heure de génération

Ces informations sont affichées dans le message de confirmation après exécution.

## Exemples d'utilisation

### Exemple 1: Configuration namespace IPP avec préfixe "9..."

```
Namespace: IPP Test
System: urn:oid:1.2.250.1.213.1.1.1
Type: IPP
Mode: fixed
Pattern: 9...
```

**Résultat**: IPP générés seront 9000, 9001, 9123, 9456, etc.

### Exemple 2: Configuration namespace NDA avec plage

```
Namespace: NDA Test
System: urn:oid:1.2.250.1.213.1.1.2
Type: NDA
Mode: range
Min: 501000
Max: 501999
```

**Résultat**: NDA générés seront 501234, 501789, 501456, etc.

### Exemple 3: Override ponctuel lors de l'exécution

Lors de l'exécution d'un scénario, spécifier:
- Préfixe IPP: `91....` (override temporaire)
- Préfixe NDA: `502...` (override temporaire)

**Résultat**: 
- IPP généré: 91234 (au lieu de 9123 du namespace par défaut)
- NDA généré: 502456 (au lieu de 501456 du namespace par défaut)

## Architecture technique

### Services créés

#### `app/services/identifier_generator.py`

Fonctions principales:
- `generate_identifier()`: Génère un identifiant selon configuration namespace
- `generate_identifier_set()`: Génère ensemble IPP/NDA/VENUE
- `count_available_identifiers()`: Estime nombre d'identifiants disponibles
- `_parse_prefix_pattern()`: Parse pattern type "9..."
- `_generate_with_prefix_pattern()`: Génère avec pattern
- `_generate_with_range()`: Génère dans plage numérique

#### `app/services/scenario_identifier_replacer.py`

Fonctions principales:
- `replace_identifiers_in_hl7_message()`: Remplace identifiants dans message HL7
- `preview_identifier_replacement()`: Aperçu avant remplacement
- Fonctions internes pour manipulation segments PID/PV1

### Modifications des modèles

#### `IdentifierNamespace` (app/models_structure_fhir.py)

Nouveaux champs:
```python
prefix_pattern: Optional[str]  # Ex: "9...", "91...."
prefix_mode: Optional[str]     # "fixed" ou "range"
prefix_min: Optional[int]      # Pour mode "range"
prefix_max: Optional[int]      # Pour mode "range"
```

#### `ScenarioBinding` (app/models_scenarios.py)

Nouveaux champs:
```python
use_test_namespace: bool
identifier_prefix_ipp: Optional[str]
identifier_prefix_nda: Optional[str]
generated_ipp: Optional[str]
generated_nda: Optional[str]
generated_venue_id: Optional[str]
last_execution_at: Optional[datetime]
```

### Intégration scenario_runner

`app/services/scenario_runner.py` modifié:
- Fonction `_send_hl7_step()` accepte paramètre `binding`
- Avant envoi, remplace identifiants si binding configuré
- Met à jour binding avec identifiants générés
- Propagation du paramètre dans `send_step()` et `send_scenario()`

## Évitement de collisions

Le service vérifie automatiquement la table `Identifier` avant de générer:

```python
existing = session.exec(
    select(Identifier).where(
        Identifier.value == candidate,
        Identifier.type == identifier_type,
        Identifier.system == namespace_system
    )
).first()

if existing:
    # Générer un autre candidat
```

Tentatives max: 100 (configurable)

## Tests unitaires

Fichier: `tests/test_identifier_generator.py`

Coverage:
- ✅ Parsing patterns de préfixe
- ✅ Génération avec pattern
- ✅ Génération avec plage
- ✅ Évitement de collisions
- ✅ Overrides de préfixe
- ✅ Fallback sans configuration
- ✅ Comptage identifiants disponibles

Lancer les tests:
```bash
pytest tests/test_identifier_generator.py -v
```

## Migration base de données

⚠️ **À faire**: Générer migration Alembic pour ajouter les nouveaux champs.

En attendant, utiliser:
```bash
python tools/reset_db.py --init-vocab
```

## Utilisation recommandée

### Pour tests locaux

Utiliser préfixes courts pour faciliter le debugging:
- IPP: `9...` (4 chiffres)
- NDA: `9...` (4 chiffres)

### Pour tests avec systèmes réels

Coordonner avec l'équipe du système récepteur pour obtenir:
- Plage IPP réservée (ex: 9000000-9999999)
- Plage NDA réservée (ex: 501000-501999)

Configurer les namespaces en conséquence.

### Pour isolation complète

Créer des namespaces dédiés "Test" avec leurs propres OID:
- IPP Test: `urn:oid:1.2.3.4.TEST.1`
- NDA Test: `urn:oid:1.2.3.4.TEST.2`

Activer checkbox "Utiliser namespace test" lors de l'exécution.

## Limitations actuelles

1. **Pas de gestion de pool d'identifiants**: Chaque génération est indépendante
2. **Pas de réservation**: Plusieurs exécutions simultanées peuvent générer le même identifiant (risque faible)
3. **Pas de nettoyage automatique**: Les identifiants générés restent en base
4. **HL7 uniquement**: Remplacement pas encore implémenté pour FHIR

## Évolutions futures

- [ ] Pool d'identifiants pré-générés
- [ ] Réservation avec lock pour concurrence
- [ ] Nettoyage automatique des identifiants de test
- [ ] Support FHIR (Patient.identifier, Encounter.identifier)
- [ ] Dashboard de saturation des plages
- [ ] Export des identifiants générés (CSV)
- [ ] API REST pour génération externe
