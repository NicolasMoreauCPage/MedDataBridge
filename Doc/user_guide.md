# Guide Utilisateur - Interface Web

## Accueil

L'interface MedData Bridge propose une navigation contextuelle basée sur les GHT, Établissements Juridiques, Patients et Dossiers.

### Sélection du Contexte

#### Contexte GHT

1. Accéder à **Administration** → **GHT & Établissements**

2. Cliquer sur un GHT pour l'activer

3. Badge bleu affiché en haut à gauche confirme le contexte actif

#### Contexte Établissement Juridique (EJ)

1. Dans la liste des EJ du GHT actif, cliquer sur un établissement

2. Badge cyan affiché en haut pour confirmation

3. Permet de filtrer patients/dossiers de cet établissement

#### Contexte Patient

1. Rechercher un patient dans **Patients** → **Recherche**

2. Cliquer sur le patient pour l'activer

3. Badge vert affiché avec nom + ID patient

#### Contexte Dossier

1. Dans la fiche patient, sélectionner un dossier

2. Badge indigo affiché avec numéro de dossier

3. Filtrage automatique des mouvements pour ce dossier

**Effacement**: Cliquer sur × dans le badge ou Menu → **Effacer Contexte**.

## Gestion des Patients

### Créer un Patient

1. **Patients** → **Nouveau Patient**

2. Remplir:

   - Nom de famille (obligatoire)

   - Prénom (obligatoire)

   - Date de naissance (obligatoire)

   - Sexe: male | female | other | unknown

3. Optionnel: Adresse, Téléphones, Identifiants

4. **Enregistrer**

### Modifier un Patient

1. Rechercher le patient

2. Cliquer sur **Modifier**

3. Mettre à jour les champs

4. **Enregistrer les modifications**

### Supprimer un Patient

1. Ouvrir la fiche patient

2. **Actions** → **Supprimer**

3. Confirmation requise

4. Suppression logique (archivage)

## Gestion des Dossiers

### Créer un Dossier

1. Activer contexte Patient

2. **Dossiers** → **Nouveau Dossier**

3. Renseigner:

   - Numéro de dossier (unique)

   - Type: HOSPITALISE | URGENCES | EXTERNE | AMBULATOIRE

   - UF responsable

   - Date/heure admission

4. **Créer**

### Associer une Venue (Séjour)

1. Dans le dossier, **Venues** → **Nouvelle Venue**

2. Indiquer:

   - Code venue (unique)

   - UF responsable

   - Date/heure début

   - Location initiale

3. **Enregistrer**

## Gestion des Mouvements

### Enregistrer un Mouvement

1. Activer contexte Dossier + Venue

2. **Mouvements** → **Nouveau Mouvement**

3. Remplir:

   - Numéro séquence (unique)

   - Date/heure

   - Location (format: `SERVICE/CHAMBRE/LIT`)

   - Trigger Event: A01 (admission) | A02 (transfert) | A03 (sortie)

   - Action: INSERT | UPDATE | CANCEL

   - UF médicale + UF soins (codes)

   - Nature: S (Somatique) | H (Hospitalisation) | M (Maternité) | L (Long séjour) | D (Domicile) | SM (Santé mentale)

4. **Enregistrer**

### Modifier un Mouvement

1. Rechercher le mouvement

2. **Modifier**

3. Changer champs nécessaires

4. **Action**: Mettre `UPDATE` + indiquer **Trigger Original** (ex: A01)

5. **Enregistrer**

### Annuler un Mouvement

1. Ouvrir le mouvement

2. **Action** → `CANCEL`

3. Indiquer **Trigger Original**

4. **Enregistrer**

## Structure Hiérarchique

### Consulter la Hiérarchie

**Structure** → **Hiérarchie Complète**

Arborescence affichée:

```text

GHT
└── Entité Juridique
    └── Pôle
        └── Service
            └── Unité Fonctionnelle (UF)
                └── Unité d'Hébergement (UH)
                    └── Chambre
                        └── Lit

```

### Créer une Location

1. Naviguer vers le niveau parent (ex: UF pour créer UH)

2. **Nouvelle [Type]**

3. Renseigner:

   - Nom

   - Identifiant unique

   - Statut opérationnel

4. **Créer**

## Configuration Endpoints

### Ajouter un Endpoint MLLP

1. **Administration** → **Endpoints**

2. **Nouveau Endpoint**

3. Type: **MLLP**

4. Paramètres:

   - Nom

   - Host (IP ou hostname)

   - Port (ex: 2575)

   - Direction: inbound | outbound

   - EJ émetteur (sélection)

5. **Enregistrer**

### Tester un Endpoint

1. Liste endpoints

2. Cliquer sur **Tester**

3. Résultat connexion affiché (succès/erreur)

### Ajouter un Endpoint File

1. Type: **File**

2. Paramètres:

   - Répertoire inbox (messages entrants)

   - Répertoire outbox (messages sortants)

   - Pattern fichiers (ex: `*.hl7`)

3. **Enregistrer**

## Consultation des Messages

### Logs Messages

**Messages** → **Historique**

Filtres disponibles:

- Statut: ✓ Succès | ✗ Erreur | ⏳ En cours

- Trigger Event: A01, A02, A03, etc.

- Direction: ⬇ Entrant | ⬆ Sortant

- Période (date début/fin)

### Détails d'un Message

1. Cliquer sur le message

2. Affichage:

   - Contenu HL7 brut

   - Segments parsés

   - Erreurs de validation

   - Timestamp émission/réception

   - Endpoint source/destination

### Regénérer un Message

1. Ouvrir le message

2. **Actions** → **Regénérer**

3. Nouveau message créé avec timestamp actuel

## Documentation

### Accéder à la Documentation

**Menu** → **Documentation** ou `/documentation`

Sections disponibles:

- Architecture système

- Guide API

- Guide utilisateur (ce document)

- Conformité IHE PAM France

- Matrice de conformité ZBE

- Comportements legacy

### Rechercher dans la Documentation

1. Barre de recherche en haut à droite

2. Saisir mots-clés (min 3 caractères)

3. Résultats affichés avec contexte

## Notifications & Alertes

### Messages Flash

Affichés en haut de page après actions:

- ✓ Vert: Succès

- ✗ Rouge: Erreur

- ℹ Bleu: Information

- ⚠ Jaune: Avertissement

### Compteur Messages en Erreur

Badge rouge dans l'en-tête indique nombre de messages en erreur pour le contexte actif. Cliquer pour accéder aux logs filtrés.

## Raccourcis Clavier

- `Alt+H`: Accueil

- `Alt+P`: Patients

- `Alt+D`: Dossiers

- `Alt+M`: Messages

- `Alt+S`: Structure

- `Alt+A`: Administration

- `/`: Focus recherche

- `Esc`: Fermer modales/overlay

## Scénarios d'Interopération

Les scénarios permettent de capturer, reproduire et tester des séquences de messages HL7/FHIR complètes.

### Concepts Clés

**Scénario**: Séquence ordonnée de messages avec délais entre chaque étape
**Step**: Un message dans le scénario (ADT^A01, ORU^R01, etc.)
**Capture**: Créer un scénario automatiquement depuis un dossier existant
**Replay**: Rejouer un scénario vers un endpoint configuré

### Créer un Scénario par Capture

**Méthode Automatique** (recommandée):

1. Ouvrir un dossier avec mouvements
2. **Actions** → **Capturer comme Scénario**
3. Renseigner:
   - Nom du scénario
   - Clé unique (ex: `admission-simple-a01`)
   - Catégorie (optionnel)
   - Tags (ex: `urgences,admission`)
4. **Capturer**

Le système analyse les mouvements et génère automatiquement:
- Séquence de messages HL7 (A01, A02, A03...)
- Délais réels entre chaque événement
- Payloads HL7 complets

**Messages Z** (Legacy): Les messages Z01-Z99 (sauf Z99) sont marqués comme dépréciés IHE PAM ≥2.8 et ne seront pas émis lors du replay.

### Configuration Temporelle Avancée

Permet d'adapter les dates lors du replay:

**Mode Ancre** (`anchor_mode`):
- `sliding`: Dates décalées de N jours depuis aujourd'hui
- `fixed`: Date de départ fixe (ISO 8601)
- `none`: Utiliser dates originales (peut être obsolète)

**Décalage** (`anchor_days_offset`):
- `-7`: Scénario commence il y a 7 jours
- `0`: Aujourd'hui
- `+1`: Demain

**Préserver Intervalles** (`preserve_intervals`):
- `true`: Garder délais exacts entre messages (ex: 2h entre A01 et A08)
- `false`: Grouper messages (tous envoyés immédiatement)

**Jitter** (`jitter_min/max_minutes`):
- Variation aléatoire des timestamps (±N minutes)
- Simule envois non-parfaitement synchrones
- Appliqué sur événements spécifiques (`jitter_events`)

**Exemple Configuration**:
```json
{
  "anchor_mode": "sliding",
  "anchor_days_offset": -3,
  "preserve_intervals": true,
  "jitter_min": 1,
  "jitter_max": 5,
  "jitter_events": true
}
```
→ Scénario commence il y a 3 jours, délais préservés, ±1-5 min de variation

### Rejouer un Scénario

1. **Scénarios** → Sélectionner un scénario
2. Choisir **Endpoint cible** (système configuré en mode sender)
3. Options:
   - **Scénario complet**: Tous les messages en séquence
   - **Étape unique**: Un seul message spécifique
4. **Envoyer**

Le système:
- Applique la configuration temporelle
- Met à jour les dates HL7 (MSH-7, EVN-2, PV1-44...)
- Respecte les délais configurés
- Enregistre l'exécution dans Dashboard

### Dashboard d'Exécution

**Scénarios** → **Runs** affiche:

**Statistiques Globales**:
- Nombre total d'exécutions
- Taux de succès
- Messages en erreur
- Temps moyen d'exécution

**Vue Temporelle**:
- Graphique d'exécutions par jour (30 derniers jours)
- Filtrable par scénario ou endpoint

**Distribution ACK**:
- AA (Application Accept): Succès
- AE (Application Error): Erreur applicative
- AR (Application Reject): Rejet
- CA/CE/CR: Variantes conditionnelles

**Liste des Runs**:
- ID, Date, Scénario, Endpoint
- Statut (success, partial, error)
- Steps réussis/échoués/ignorés
- Détails erreurs (cliquer sur run)

**Comparaison Scénarios**:
- Performance relative entre scénarios
- Taux succès, temps moyen, fréquence d'usage

### Export / Import de Scénarios

**Exporter un Scénario**:

1. Ouvrir détail du scénario
2. Cliquer **Exporter JSON**
3. Fichier JSON téléchargé contient:
   - Métadonnées (nom, clé, protocole, tags)
   - Configuration temporelle complète
   - Tous les steps avec payloads

**Format JSON Exporté**:
```json
{
  "id": 42,
  "key": "admission-urgences-a01",
  "name": "Admission Urgences Standard",
  "description": "Patient arrivé aux urgences puis hospitalisé",
  "protocol": "HL7v2",
  "tags": "urgences,admission",
  "time_config": {
    "anchor_mode": "sliding",
    "anchor_days_offset": -1,
    "preserve_intervals": true,
    "jitter_min": 1,
    "jitter_max": 3
  },
  "steps": [
    {
      "order_index": 0,
      "message_type": "ADT^A01",
      "format": "HL7v2",
      "delay_seconds": 0,
      "payload": "MSH|^~\\&|SENDING|..."
    },
    {
      "order_index": 1,
      "message_type": "ADT^A02",
      "format": "HL7v2",
      "delay_seconds": 7200,
      "payload": "MSH|^~\\&|SENDING|..."
    }
  ]
}
```

**Importer un Scénario**:

1. **Scénarios** → **Importer**
2. Sélectionner **Contexte GHT** cible
3. **Méthode 1**: Upload fichier JSON
4. **Méthode 2**: Coller JSON directement
5. Options avancées (optionnel):
   - **Nouvelle clé**: Évite collision avec scénario existant
   - **Nouveau nom**: Renomme lors de l'import
6. **Importer**

**Cas d'Usage Import/Export**:
- 📦 Partager scénarios entre environnements (dev → prod)
- 📚 Créer bibliothèques de tests réutilisables
- 🔄 Modifier payloads manuellement (éditer JSON)
- 💾 Archiver scénarios pour documentation
- 🧪 Générer variantes d'un scénario (changer délais, dates)

**Modification Manuelle JSON**:
```bash
# Exporter scénario
curl http://localhost:8000/scenarios/42/export > scenario.json

# Éditer (changer délais, payloads, time_config...)
vim scenario.json

# Réimporter avec nouvelle clé
# Via UI: Importer avec override_key="scenario-modified"
```

### Namespaces et Identifiants

Scénarios utilisent les identifiants du patient/dossier d'origine. Lors du replay:
- IPP/NDA mappés selon namespaces du contexte cible
- MSH-3/MSH-4 adaptés au système émetteur
- PID-3/PV1-19 mis à jour automatiquement

**Configuration**: **Admin** → **Namespaces** pour gérer mappings.

### Bonnes Pratiques

**Nommage**:
- Clés descriptives: `admission-urg-a01-a02-a03`
- Noms explicites: "Admission Urgences puis Hospitalisation"
- Tags cohérents: `urgences`, `admission`, `transfert`

**Organisation**:
- Catégories par service: `Urgences`, `MCO`, `SSR`
- Bibliothèque de cas types (admission simple, complexe, avec transferts...)
- Versionner scénarios importants (export JSON en Git)

**Testing**:
- Tester scénarios sur environnement dev avant prod
- Vérifier Dashboard pour détecter régressions
- Comparer performances entre versions

**Maintenance**:
- Archiver scénarios obsolètes (tags `deprecated`)
- Mettre à jour scénarios après changements structurels (nouveaux champs obligatoires)
- Exporter régulièrement pour backup

## Astuces

### Navigation Rapide

Utiliser les badges contexte en haut pour passer rapidement d'un patient/dossier à l'autre sans repasser par les listes.

### Filtrage Intelligent

L'interface filtre automatiquement selon le contexte actif. Exemple: avec contexte Patient, seuls les dossiers de ce patient sont affichés.

### Identifiants Multiples

Un patient/dossier peut avoir plusieurs identifiants (IPP, NDA, etc.) selon les namespaces configurés. Gérer dans **Identifiants** de la fiche.

### Export Messages

Possible via **Messages** → **Exporter** (formats: JSON, HL7 brut, CSV logs).

---
Guide utilisateur v0.3.0
