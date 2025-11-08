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
Guide utilisateur v0.2.0
