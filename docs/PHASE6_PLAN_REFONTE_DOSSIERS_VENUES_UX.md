# 📂 Phase 6 - Refonte UX Dossiers & Venues (Admissions / Séjours)

**Status** : 🟡 EN PLANIFICATION  
**Date** : 8 janvier 2026  
**Portée** : Interfaces de gestion des dossiers (Dossier) et venues (Venue) pour les professionnels administratifs (admissions, bureaux des entrées, facturation)

---

## 1. 🎯 Objectifs UX & Métier

- Réduire l’effort cognitif et les erreurs de saisie pour les équipes administratives.
- Standardiser les écrans autour des workflows réels : admission, suivi de séjour, clôture dossier, facturation.
- Reprendre les fondations du Design System (Phase 5.2) pour garantir cohérence et efficacité visuelle.
- Offrir des raccourcis d’accès aux informations critiques : IPP, NDA, VN, UF, médecin, dates clés.
- Faciliter la navigation croisée Patient ↔ Dossier ↔ Venues ↔ Mouvements.

---

## 2. 👥 Personas Cibles

### 2.1. Agent Administratif Admissions
- Contexte : Bureaux des entrées / admissions programmées ou urgences.
- Besoins :
  - Créer rapidement un patient (si nécessaire) puis un dossier + 1ère venue.
  - Visualiser les dossiers en cours par patient (NDA) et par EJ.
  - Vérifier les informations d’identité et de rattachement (UF, médecin, service).

### 2.2. Gestionnaire de Séjours / Facturation
- Contexte : Service facturation / gestion PMSI.
- Besoins :
  - Accéder aux dossiers clos/en cours avec statut de complétude.
  - Voir les venues associées, dates de début/fin, UF, mouvements clés.
  - Identifier rapidement les anomalies (dossier sans venue, venue sans UF, dates incohérentes).

### 2.3. Secrétaire Médicale de Service
- Contexte : Secrétariat d’un service hospitalier.
- Besoins :
  - Voir la liste des patients présents/attendus dans le service (par UF ou service).
  - Accéder rapidement à un dossier/venue à partir du patient ou de l’UF.
  - Mettre à jour certaines informations administratives (UF responsable, médecin, motif).

---

## 3. 🔍 Analyse de l’Existant (Haute-Niveau)

### 3.1. Modèles Backend
- `Patient` : identité + champs adresse/contact (modèle déjà modernisé et RGPD).
- `Dossier` :
  - `dossier_seq` (NDA), `patient_id`, `admit_time`, `discharge_time`.
  - Métier : `dossier_type`, `uf_responsabilite`, `admission_type`, `admission_source`, `attending_provider`, `reason`, `current_state`, `has_cotations`, `cotations_count`.
  - Relations : `patient`, `venues`, `identifiers`, `contracts`, `ngap_acts`, etc.
- `Venue` :
  - `venue_seq` (VN), `dossier_id`, `code`, `label`, `assigned_location`, `start_time`, `uf_responsabilite`, `uf_soins_*`, `hospital_service`, `attending_provider`, `chambre_id`, `lit_id`.
  - Relation : `dossier`, `mouvements`.

### 3.2. Templates Clés
- `app/templates/dossier_detail.html` :
  - Vue détaillée dossier avec header visuel et section infos.
  - Liste des venues liées + identifiants via `components/identifier_table.html`.
  - Liens rapides vers patient, venues, mouvements, cotations.
- `app/templates/venue_detail.html` :
  - Vue détaillée d’une venue (VN) avec contexte patient/dossier.
  - Infos de base (dossier_id, UF, dates) + actions (modifier, workflow, mouvements, suppression).
- `app/templates/patient_form.html` :
  - Formulaire déjà très travaillé pour la saisie identité patient.
  - Bon candidat pour patterns de formulaires administratifs (sections, détails, feedbacks).

### 3.3. Routers & Workflows liés
- `app/routers/dossier_type.py` : changement de type de dossier.
- `app/routers/patients.py` : création/mise à jour patient (formulaire avancé).
- `app/routers/mouvements.py`, `app/routers/workflow.py` (deployment) : gestion mouvements/workflows liées aux venues.

---

## 4. 😣 Pain Points Pressentis (Administratif)

### 4.1. Problèmes de Navigation & Orientation
- **Dispersion des actions** : création/modification dossiers et venues non centralisée autour de workflows métier (Admission, Transfert, Sortie).
- **Manque de lisibilité hiérarchique** : Patient ↔ Dossier (NDA) ↔ Venues (VN) ↔ Mouvements pas mis en scène comme un parcours.
- **Retours arrière complexes** : difficile de revenir à un écran précédent dans le parcours de saisie.
- **Contexte perdu** : quand on navigue d'une fiche patient vers un dossier puis une venue, on perd le fil.

### 4.2. Problèmes de Saisie & Formulaires
- **Saisie redondante** : UF, médecin, type/admission renseignés à plusieurs endroits sans auto-pré-remplissage.
- **Champs requis peu visibles** : pas d'indication claire des champs obligatoires avant la soumission.
- **Validation tardive** : erreurs métier découvertes après soumission plutôt qu'en temps réel.
- **Pas de sauvegarde brouillon** : perte de données en cas de déconnexion ou erreur.

### 4.3. Problèmes de Visibilité & Feedback
- **Peu d'indicateurs d'état** : difficultés à voir rapidement si un dossier est « complet », « en attente d'infos », « à clôturer ».
- **Manque de contrôle d'erreurs métier** : dates incohérentes, UF manquante, type dossier incompatible avec venues.
- **Anomalies invisibles** : dossier sans venue, venue sans UF, dates illogiques non signalées.
- **Pas de tableau de bord** : aucune vue d'ensemble sur « mes dossiers en attente », « mes tâches du jour ».

### 4.4. Problèmes d'Efficacité
- **Trop de clics** : création dossier + venue nécessite 4-5 écrans distincts.
- **Pas de raccourcis clavier** : navigation lente pour les utilisateurs expérimentés.
- **Recherche limitée** : difficile de retrouver un dossier par critères métier (UF, médecin, période).
- **Actions groupées absentes** : impossible de clôturer plusieurs dossiers ou valider plusieurs venues d'un coup.

---

## 5. 🧭 Principes UX Directeurs

### 5.1. Principes Fondamentaux

1. **Workflow Centré Métier (Task-Oriented Design)**  
   - Organiser les écrans par scénarios métier réels : Admission complète, Suivi séjour, Clôture administrative, Correction anomalies.
   - Réduire le nombre d'écrans : combiner création patient + dossier + venue quand possible.

2. **Une page = une intention principale (Single Purpose)**  
   - Dossier : vue de synthèse administrative + suivi venues.
   - Venue : vue séjour + localisation + mouvements.
   - Liste : recherche/filtrage rapide multi-critères.

3. **Feedback Immédiat & Transparent (Progressive Disclosure)**  
   - Validation en temps réel (dates, UF obligatoire, cohérence métier).
   - Indicateurs visuels d'état (badges, couleurs, icônes).
   - Messages d'erreur contextuels et constructifs (pas juste "Erreur", mais "UF responsabilité obligatoire pour un dossier Hospitalisé").

4. **Pré-remplissage Intelligent & Raccourcis (Efficiency)**  
   - Auto-complétion : reprendre patient, UF, médecin, EJ du contexte.
   - Valeurs par défaut métier (type dossier selon contexte d'admission).
   - Raccourcis clavier pour utilisateurs expérimentés (Ctrl+S sauvegarder, Ctrl+N nouveau, Tab/Shift+Tab navigation).

5. **Lisibilité Haute Densité (Information Density)**  
   - Informations critiques visibles sans scroll (header riche).
   - Hiérarchie visuelle forte (titres, espacements, couleurs).
   - Groupement logique des informations (identité, administrative, clinique, facturation).

6. **Cohérence Design System (Consistency)**  
   - Réutiliser Phase 5.2 : badges, cartes, alertes, notifications, barres d'état.
   - Harmonisation couleurs/icônes avec Phase 5 (structure hospitalière).

### 5.2. Principes Spécifiques Administratifs

7. **Contexte Préservé (Context Awareness)**  
   - Fil d'Ariane (breadcrumb) toujours visible : Patient > Dossier > Venue.
   - Navigation rapide entre entités liées (patient ↔ dossiers ↔ venues).

8. **Prévention & Correction Erreurs (Error Prevention)**  
   - Validation métier proactive (empêcher les dates incohérentes plutôt que les corriger après).
   - Confirmation pour actions destructives (suppression dossier/venue).
   - Auto-sauvegarde brouillon toutes les 30s.

9. **Accessibilité & Adaptabilité (Inclusive Design)**  
   - Contraste élevé pour lectures longues.
   - Taille de police adaptée (minimum 14px pour formulaires).
   - Support mobile/tablette pour consultations nomades.

10. **Performance Perçue (Perceived Performance)**  
    - Chargement progressif (skeleton screens).
    - Actions instantanées (feedback UI avant confirmation serveur).
    - Cache intelligent pour listes fréquentes (UF, médecins).

---

## 6. 🎛️ Écrans Cibles & Flots Fonctionnels

### 6.1. Écran « Vue Dossier Administratif » (refonte de `dossier_detail.html`)

**Rôle** : Hub administratif autour du NDA.

- Header dossier :
  - `#NDA` (dossier_seq) très visible, statut (en cours / clos / à compléter).
  - Patient (nom, prénom, IPP) + accès fiche patient.
  - Résumé venues : nombre total, dernière venue, UF principale.
- Section « Synthèse Dossier » :
  - Type de dossier (avec label du vocabulaire + éventuel bouton « Modifier »).
  - UF responsabilité, médecin responsable, motif, état courant.
  - Dates d’admission/discharge avec badge d’état (séjour ouvert/clos).
- Section « Identifiants » :
  - Utilisation de `identifier_table.html` avec mise en avant NDA, IPP, identifiants externes.
- Section « Venues du Dossier » :
  - Tableau/listing des venues (VN) avec :
    - VN, dates début/fin, UF soins, service, localisation (chambre/lit).
    - Badges d’état (en cours, clôturée, transférée, annulée).
    - Actions rapides : voir, éditer, accéder au workflow.
- Actions rapides (top ou latéral) :
  - « Nouvelle venue dans ce dossier ».
  - « Clôturer le dossier » (si conditions remplies).
  - « Voir les mouvements » (vue chronologique globale).

### 6.2. Écran « Vue Venue / Séjour » (refonte de `venue_detail.html`)

**Rôle** : Focus sur un séjour précis (VN) et son contexte.

- Header venue :
  - `#VN` très visible, lien vers dossier parent (NDA) et patient.
  - UF responsabilité, UF de soins, service hospitalier.
  - Localisation actuelle (chambre, lit) avec code couleur occupation.
- Section « Détails séjour » :
  - Dates début (obligatoire) et fin (facultative, si séjour ouvert).
  - Médecin responsable, nature du séjour, notes administratives.
- Section « Mouvements » :
  - Liste des mouvements (ordre chronologique) avec types (entrée, transfert, sortie).
  - Boutons : « Nouveau mouvement », « Voir tous les mouvements / timeline ».
- Actions :
  - Modifier venue.
  - Supprimer (avec garde-fous si mouvements existants).
  - Accéder au workflow détaillé (si existant, router workflow/venue).

### 6.3. Écran « Listing Dossiers/venues par Patient »

- Depuis `patient_detail` et `dossier_detail` :
  - Panneaux latéraux ou sections dédiées pour voir :
    - Tous les dossiers du patient.
    - Toutes les venues liées.
  - Tri par date, filtre par EJ, UF.

### 6.4. Maquettes UX Détaillées

#### Maquette 1 : Vue Dossier - Header Moderne & Synthèse
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🏠 > 👥 Patients > DUPONT Martin > 📂 Dossier #1234                 │
├─────────────────────────────────────────────────────────────────────┤
│ ╔═══════════════════════════════════════════════════════════════╗   │
│ ║  ⚡ DOSSIER #1234  [🟢 EN COURS] ← Gradient Animé Bleu-Indigo║   │
│ ║     + Effet Glassmorphism + Blur Background                   ║   │
│ ║                                                                ║   │
│ ║  [🎭] 👤 DUPONT Martin                     → [Voir fiche] 🔗  ║   │
│ ║      IPP: 123456789012 | Né: 01/01/1980                       ║   │
│ ║                                                                ║   │
│ ║  📊 Stats: [2 venues] [15j total] [Dernière UF: CARDIO]      ║   │
│ ║            ▓▓▓▓▓▓▓▓░░ 80% complet                            ║   │
│ ╚═══════════════════════════════════════════════════════════════╝   │
├─────────────────────────────────────────────────────────────────────┤
│ 📋 SYNTHÈSE ADMINISTRATIVE (Cards Glassmorphism)                    │
│ ┌──────────────────────────────┬──────────────────────────────────┐ │
│ │ 🏥 Type: Hospitalisé          │ 📅 Admission                     │ │
│ │    [Badge Gradient Bleu]      │    01/01/2026 14:30             │ │
│ │    [Modifier Type ⚙️] ←Hover │    Il y a 7 jours               │ │
│ │                                │                                  │ │
│ │ 🏢 UF resp: CARDIO             │ 📅 Sortie prévue                │ │
│ │    → [Fiche UF] 🔗 Hover     │    15/01/2026 (dans 8j)         │ │
│ │                                │    [Badge Orange Gradient]       │ │
│ │ 👨‍⚕️ Médecin: Dr. MARTIN       │                                  │ │
│ │    → [Fiche] 🔗              │ 📊 État: [Badge Vert Animé]     │ │
│ │                                │    Séjour actif ✓               │ │
│ │ 📍 Source: Programmée         │                                  │ │
│ │    [Badge Bleu]               │ ⚡ Actions (Hover Effects):     │ │
│ │                                │    [✏️ Modifier] [🔒 Clôturer] │ │
│ └──────────────────────────────┴──────────────────────────────────┘ │
│                                                                      │
│ Note Design: Cards avec backdrop-blur, shadows douces, hover        │
│              transform scale(1.02), transitions 300ms                │
└──────────────────────────────────────────────────────────────────────┘
```

#### Maquette 2 : Vue Dossier - Tableau Venues Moderne
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🏥 VENUES DU DOSSIER                                                │
│    [➕ Nouvelle Venue] ← Bouton Gradient Cyan avec Pulse Hover     │
├─────┬────────────┬─────────┬─────────┬──────────┬──────┬──────────┤
│ VN  │ Dates      │ UF Soins│ Service │ Location │ État │ Actions  │
│ (→) │ (Durée)    │ (Badge) │ (Link)  │ (Icon)   │(Grad)│ (Hover)  │
├─────┼────────────┼─────────┼─────────┼──────────┼──────┼──────────┤
│ → # │ 01/01-05/01│ [CARDIO]│ USC →   │ 🛏️Ch12-L2│ [✓]  │ 👁 ✏️ 🔄 │
│ 5678│ (4 jours)  │ Gradient│         │ Tooltip  │Green │ Appear   │
│     │            │ Bleu    │         │ Hover    │Pulse │ onHover  │
├─────┼────────────┼─────────┼─────────┼──────────┼──────┼──────────┤
│ → # │ 05/01-cours│ [CARDIO]│ Hospi →│ 🛏️Ch24-L1│ [⏸]  │ 👁 ✏️ 🔄 │
│ 5679│ (3j cours) │ Gradient│         │ Disponib │Blue  │ Appear   │
│ ⭐  │            │ Bleu    │         │ 🟢       │Anim  │ onHover  │
└─────┴────────────┴─────────┴─────────┴──────────┴──────┴──────────┘

Hover Effects:
- Row hover → Gradient background from-blue-50/50 to-purple-50/30
- VN hover → Apparition flèche →, scale(1.05), color blue-600
- Actions icons → Scale(1.2) + rotation subtile
- Badge état → Shadow intensifiée + subtle pulse

Legend: 
✓ Clôturée (Gradient Vert + Shadow) | ⏸ En cours (Gradient Bleu Animé)
⚠️ Anomalie (Gradient Orange Pulse) | ⭐ Venue active (Highlight)
👁 Voir | ✏️ Modifier | 🔄 Mouvements (avec hover tooltips)
```

#### Maquette 3 : Vue Venue - Header Moderne & Timeline
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🏠 > 📂 Dossier #1234 > 🏥 Venue #5678                              │
├─────────────────────────────────────────────────────────────────────┤
│ ╔══ CONTEXTE (Cards Glassmorphism) ════════════════════════════╗  │
│ ║ ┌─────────────────────────┬─────────────────────────────────┐║  │
│ ║ │ 👤 DUPONT Martin         │ 📂 Dossier #1234               │║  │
│ ║ │    IPP: 123456789012     │    Hospitalisé                 │║  │
│ ║ │    → [Voir fiche] 🔗    │    [Badge EN COURS Gradient]   │║  │
│ ║ │                          │    → [Voir dossier] 🔗        │║  │
│ ║ └─────────────────────────┴─────────────────────────────────┘║  │
│ ╚═══════════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────────┤
│ ╔═══════════════════════════════════════════════════════════════╗  │
│ ║  ⚡ VENUE #5678  [🟢 EN COURS] ← Gradient Animé Cyan-Teal    ║  │
│ ║     + Glassmorphism Effect + Soft Shadows                     ║  │
│ ║                                                                ║  │
│ ║  🏢 UF Resp: CARDIO | UF Soins: CARDIO [Badges Gradients]    ║  │
│ ║  🏛️ Service: Hospitalisation Cardiologie → [Fiche] 🔗        ║  │
│ ║  🛏️ Localisation: Chambre 12 - Lit 2                          ║  │
│ ║     [Disponibilité: 🟢 Badge Vert Gradient] Hover → Tooltip  ║  │
│ ╚═══════════════════════════════════════════════════════════════╝  │
├─────────────────────────────────────────────────────────────────────┤
│ 📊 DÉTAILS SÉJOUR (Grid Layout Moderne)                             │
│ ┌──────────────────────────┬────────────────────────────────────┐  │
│ │ 📅 Début                  │ ⏱️ Durée séjour                    │  │
│ │    01/01/26 14:30         │    7 jours (en cours)             │  │
│ │    Il y a 7 jours         │    [Progress Bar Gradient]        │  │
│ │                           │    ▓▓▓▓▓▓▓░░░ 70%                 │  │
│ │ 📅 Fin                    │                                    │  │
│ │    -- (séjour ouvert)     │ 📋 Nature                         │  │
│ │    [Badge Orange Anim]    │    H (Hospitalisation complète)   │  │
│ │                           │    [Badge Gradient Bleu]          │  │
│ │ 👨‍⚕️ Médecin               │                                    │  │
│ │    Dr. MARTIN Jean        │ 🏷️ Label                          │  │
│ │    → [Fiche] 🔗          │    Séjour USC post-intervention   │  │
│ └──────────────────────────┴────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│ 🔄 MOUVEMENTS CHRONOLOGIQUES (Timeline Verticale Moderne)           │
│    [➕ Nouveau Mouvement] ← Bouton Gradient avec Hover Effect      │
│ ┌─────────────────────────────────────────────────────────────┐    │
│ │ ┌────────────────────────────────────────────────────────┐  │    │
│ │ │ • 01/01 14:30 ⬇️  ENTRÉE                               │  │    │
│ │ │   │              → USC Chambre 12-Lit 2                │  │    │
│ │ │   │              [Badge Vert ✓ Validé]                 │  │    │
│ │ │   │              Dr. MARTIN                            │  │    │
│ │ │   ▼ Timeline connector (gradient vertical)            │  │    │
│ │ │                                                         │  │    │
│ │ │ • 03/01 10:00 ↔️  TRANSFERT                            │  │    │
│ │ │   │              → Hospi Ch 12-Lit 2                   │  │    │
│ │ │   │              [Badge Vert ✓ Validé]                 │  │    │
│ │ │   │              Transfert interne service             │  │    │
│ │ │   ▼ Timeline connector (gradient vertical)            │  │    │
│ │ │                                                         │  │    │
│ │ │ • [Prochain mouvement attendu]                         │  │    │
│ │ │   ⬆️  SORTIE (Badge Orange Pulse)                      │  │    │
│ │ │      À planifier...                                    │  │    │
│ │ └────────────────────────────────────────────────────────┘  │    │
│ │                                                              │    │
│ │  📋 [Voir timeline complète / Export PDF] 🔗 →             │    │
│ └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│ ⚡ ACTIONS (Buttons avec Hover Transform & Shadows):                │
│ [✏️ Modifier Venue] [🔒 Clôturer Venue] [📋 Workflow Détaillé]    │
│ [🗑️ Supprimer (⚠️)] ← Hover → Scale + Shadow Rouge                │
│                                                                      │
│ Note Design: Timeline avec connecteurs gradient, badges états       │
│              avec shadows, hover tooltips, micro-animations         │
└──────────────────────────────────────────────────────────────────────┘
```

#### Maquette 4 : Workflow Admission Complète (3 étapes)
```
┌─────────────────────────────────────────────────────────────────────┐
│ 🎯 NOUVELLE ADMISSION COMPLÈTE                                      │
├─────────────────────────────────────────────────────────────────────┤
│ Progress: [████████████░░░░░░░░░░░░] 1/3                           │
├─────────────────────────────────────────────────────────────────────┤
│ ÉTAPE 1/3 : IDENTITÉ PATIENT                                        │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 🔍 Rechercher patient existant:                                 │ │
│ │    [Nom, IPP ou Date naissance...                          ] 🔍 │ │
│ │                                                                  │ │
│ │ Ou créer nouveau patient:                                       │ │
│ │                                                                  │ │
│ │ Civilité: [M. ▼] Nom *: [DUPONT_______________]                │ │
│ │ Prénom: [Martin______________] Nom naissance: [____________]    │ │
│ │ Date naissance *: [01/01/1980] Sexe *: [Masculin ▼]            │ │
│ │ Adresse: [10 rue de la Paix__________________________]         │ │
│ │ Code postal: [75001] Ville: [PARIS_______________]             │ │
│ │                                                                  │ │
│ │ * Champs obligatoires                                           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ Actions: [Annuler] [💾 Sauvegarder brouillon] [Suivant →]          │
├─────────────────────────────────────────────────────────────────────┤
│ ÉTAPE 2/3 : DOSSIER ADMINISTRATIF (aperçu suivant)                 │
│ ÉTAPE 3/3 : VENUE INITIALE (aperçu après)                          │
└─────────────────────────────────────────────────────────────────────┘
```

#### Maquette 5 : Formulaire Dossier (Étape 2/3)
```
┌─────────────────────────────────────────────────────────────────────┐
│ Progress: [████████████████████░░░░] 2/3                           │
├─────────────────────────────────────────────────────────────────────┤
│ ÉTAPE 2/3 : DOSSIER ADMINISTRATIF                                   │
│ Patient: DUPONT Martin (IPP: 123456789012) ✓                       │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 📋 INFORMATIONS REQUISES                                        │ │
│ │                                                                  │ │
│ │ Type de dossier *: [🏥 Hospitalisé        ▼]                   │ │
│ │   💡 Type définit les contraintes métier (UF obligatoire...)    │ │
│ │                                                                  │ │
│ │ UF Responsabilité *: [CARDIO - Cardiologie         ] 🔍        │ │
│ │   ⚠️ Obligatoire pour type "Hospitalisé"                        │ │
│ │                                                                  │ │
│ │ Médecin responsable *: [Dr. MARTIN Jean           ] 🔍         │ │
│ │   💡 Commence à taper pour rechercher                           │ │
│ │                                                                  │ │
│ │ Date admission *: [01/01/2026] Heure *: [14:30]                │ │
│ │   ⚠️ Si date > 7j futur: vérification nécessaire                │ │
│ │                                                                  │ │
│ │ 📋 INFORMATIONS OPTIONNELLES                                    │ │
│ │                                                                  │ │
│ │ Type d'admission: [Programmée                 ▼]                │ │
│ │ Source admission: [Domicile                  ▼]                 │ │
│ │ Motif admission: [Angioplastie coronaire_______________]       │ │
│ │                  (200 caractères max)                           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ Actions: [← Retour] [💾 Sauvegarder brouillon] [Suivant →]         │
└─────────────────────────────────────────────────────────────────────┘
```

#### Maquette 6 : Badge & Indicateurs d'État
```
Badges Statut Dossier:
[🟢 EN COURS]  [🔵 CLOS]  [🟡 À COMPLÉTER]  [🔴 ANOMALIE]

Badges Statut Venue:
[🟢 EN COURS]  [🔵 CLÔTURÉE]  [🟡 ANOMALIE]  [⏸ SUSPENDUE]

Indicateurs Disponibilité Localisation:
[🟢 Disponible]  [🟠 Partiellement occupé]  [🔴 Occupé]  [-- Non assigné]

Icônes Actions:
👁 Voir | ✏️ Modifier | 🗑️ Supprimer | 🔄 Mouvements | 📋 Workflow
💰 Cotations | 📊 Timeline | ⚡ Actions rapides | ➕ Nouveau
```

---

## 7. ✏️ Stratégie de Saisie & Formulaires

### 7.1. Architecture Formulaire « Admission Complète »

**Nouveau workflow unifié** : créer Patient + Dossier + Venue initiale en un seul parcours.

#### Écran 1/3 : Identité Patient (étape obligatoire)
- Recherche patient existant (par nom, IPP, date naissance).
- Si existant : pré-remplir et permettre mise à jour.
- Si nouveau : formulaire identité (réutiliser `patient_form.html` optimisé).
- Validation : nom obligatoire, date naissance valide, IPP unique si fourni.

#### Écran 2/3 : Dossier Administratif (contexte séjour)
- **Auto-rempli** : patient_id, entite_juridique_id (contexte EJ), admit_time (maintenant par défaut).
- **Champs requis** :
  - Type de dossier (hospitalise/externe/urgence) - select avec icônes.
  - UF responsabilité - autocomplete avec liste UF actives de l'EJ.
  - Médecin responsable - autocomplete avec liste praticiens actifs.
- **Champs optionnels** :
  - Type d'admission (programmée/urgence/mutation...).
  - Source d'admission.
  - Motif d'admission (textarea 200 caractères max).
- **Validation temps réel** :
  - UF obligatoire si type = Hospitalisé.
  - Date admission < date du jour + 7j (prévenir si trop future).

#### Écran 3/3 : Venue Initiale (localisation séjour)
- **Auto-rempli** : dossier_id, start_time (= admit_time dossier), uf_responsabilite (du dossier).
- **Champs requis** :
  - UF de soins (pré-rempli = UF responsabilité, modifiable).
  - Service hospitalier - select lié à l'UF choisie.
- **Champs optionnels** :
  - Chambre/lit - sélecteur avec disponibilité en temps réel.
  - Nature venue (H/M/L/D/S/SM).
  - Label descriptif venue.
- **Actions finales** :
  - Bouton « Enregistrer et terminer » → crée tout + redirige vers dossier_detail.
  - Bouton « Enregistrer et ajouter mouvement » → crée tout + ouvre formulaire mouvement d'entrée.

### 7.2. Formulaire Édition Dossier (simplifié)

- Focus sur données administratives modifiables post-création :
  - Type dossier (avec validation compatibilité venues existantes).
  - UF responsabilité, médecin responsable.
  - Dates admission/sortie (avec contrôle cohérence venues).
  - Motif, état courant.
- Champs non modifiables :
  - Patient (lien visible mais non éditable).
  - Dossier_seq (NDA).
  - Entité juridique.
- Actions :
  - Sauvegarder modifications.
  - Annuler (retour sans enregistrer).
  - Clôturer dossier (si conditions OK : toutes venues closes, dates cohérentes).

### 7.3. Formulaire Venue (création/édition optimisée)

#### Création Venue (depuis dossier existant)
- **Pré-rempli automatiquement** :
  - dossier_id, patient (read-only).
  - UF responsabilité/soins (du dossier).
  - Médecin responsable (du dossier).
  - Start_time (maintenant ou discharge_time venue précédente + 1 minute).
- **Validation métier** :
  - Start_time > dernière venue du dossier.
  - Chambre/lit disponible à la date choisie.
  - UF de soins active et compatible.

#### Édition Venue
- Modification limitée aux champs « vivants » :
  - UF soins, service, chambre/lit.
  - Dates début/fin (avec garde-fous mouvements).
  - Label, nature venue.
- Champs verrouillés si mouvements existent :
  - Start_time (seul 1er mouvement peut le modifier).
- Actions :
  - Sauvegarder.
  - Annuler.
  - Clôturer venue (si séjour terminé).

### 7.4. Patterns UX Formulaires (réutilisables)

#### Pattern 1 : Champs requis visuels
```html
<label class="block text-sm font-bold text-slate-700 mb-1">
  UF Responsabilité <span class="text-red-600 text-lg">*</span>
</label>
<input required aria-required="true" 
       class="border-2 border-slate-300 focus:border-blue-500 rounded-lg px-4 py-2.5 w-full" />
<p class="text-xs text-slate-500 mt-1">Unité fonctionnelle responsable du dossier (obligatoire)</p>
```

#### Pattern 2 : Validation temps réel
```javascript
// Validation date admission
inputAdmitDate.addEventListener('blur', () => {
  const admitDate = new Date(inputAdmitDate.value);
  const today = new Date();
  const maxFutureDate = new Date(today.getTime() + 7*24*60*60*1000);
  
  if (admitDate > maxFutureDate) {
    showWarning('Date d\'admission très future, êtes-vous sûr ?');
  }
});
```

#### Pattern 3 : Autocomplete UF avec recherche
```javascript
class UFAutocomplete {
  constructor(inputEl, ejId) {
    this.input = inputEl;
    this.ejId = ejId;
    this.setupListeners();
  }
  
  async fetchUFs(query) {
    const res = await fetch(`/api/uf?ej_id=${this.ejId}&q=${query}&active=true`);
    return await res.json();
  }
  
  // Affichage liste déroulante, sélection, etc.
}
```

#### Pattern 4 : Sauvegarde brouillon automatique
```javascript
let draftTimeout;
formEl.addEventListener('input', () => {
  clearTimeout(draftTimeout);
  draftTimeout = setTimeout(() => {
    saveDraft(formEl);
  }, 30000); // 30s
});
```

### 7.5. Messages d'Erreur Constructifs

❌ **Mauvais** : "Erreur de validation"  
✅ **Bon** : "UF Responsabilité obligatoire pour un dossier de type 'Hospitalisé'"

❌ **Mauvais** : "Date invalide"  
✅ **Bon** : "La date d'admission (15/02/2026) ne peut pas être postérieure à la date de sortie (12/02/2026)"

❌ **Mauvais** : "Champ requis"  
✅ **Bon** : "Médecin responsable : sélectionnez un praticien dans la liste ou saisissez son nom"

---

## 8. 🎨 Style Visuel Moderne 2024-2026 (vs. "Année 2020")

### 8.1. Principes Esthétiques Modernes

**❌ À ÉVITER (style 2020 dépassé)** :
- Bordures épaisses et grises partout.
- Couleurs fades et peu contrastées.
- Formulaires plats sans hiérarchie.
- Boutons rectangulaires sans personnalité.
- Espaces blancs insuffisants (layout étouffant).
- Police system par défaut sans caractère.
- Pas d'animations ou transitions.

**✅ À ADOPTER (style moderne 2024-2026)** :
- **Glassmorphism subtil** : cartes avec backdrop-blur léger, ombres douces.
- **Gradients vivants mais élégants** : header et CTA avec dégradés colorés métier.
- **Micro-interactions** : hover states fluides, transitions 200-300ms, feedback tactile.
- **Espacements généreux** : respiration visuelle (padding 6-8, gap 4-6).
- **Typographie hiérarchisée** : Inter/Geist font-stack, échelle claire (text-xs → text-4xl).
- **Couleurs sémantiques saturées** : badges et états avec couleurs vives (pas de gris triste).
- **Icônes modernes** : Heroicons/Lucide avec stroke-width adapté, animations subtiles.
- **Dark mode ready** (optionnel Phase 6, mais architecture prête).

### 8.2. Composants UI Modernes à Utiliser

#### Cards (Cartes Modernes)
```html
<!-- Style 2020 (à éviter) -->
<div class="border border-gray-300 p-4 bg-white">
  <h3 class="font-bold">Titre</h3>
  <p>Contenu</p>
</div>

<!-- Style Moderne 2024-2026 -->
<div class="group relative overflow-hidden rounded-2xl border-2 border-slate-200/50 bg-white shadow-lg hover:shadow-2xl hover:border-blue-300/50 transition-all duration-300">
  <div class="absolute inset-0 bg-gradient-to-br from-blue-50/30 via-transparent to-purple-50/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
  <div class="relative p-6 space-y-3">
    <h3 class="text-xl font-bold text-slate-900 tracking-tight">Titre</h3>
    <p class="text-slate-600 leading-relaxed">Contenu</p>
  </div>
</div>
```

#### Headers (En-têtes Visuels)
```html
<!-- Style Moderne avec Gradient Animé -->
<div class="relative overflow-hidden rounded-2xl p-8 text-white shadow-2xl">
  <!-- Gradient animé selon type dossier -->
  <div class="absolute inset-0 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 animate-gradient-x"></div>
  
  <!-- Pattern overlay subtil -->
  <div class="absolute inset-0 opacity-10" style="background-image: url('data:image/svg+xml,...')"></div>
  
  <!-- Effet glassmorphism -->
  <div class="absolute -left-10 -bottom-10 w-60 h-60 bg-white/10 rounded-full blur-3xl"></div>
  
  <div class="relative z-10">
    <div class="flex items-center gap-4">
      <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center ring-2 ring-white/30">
        <svg class="w-8 h-8">...</svg>
      </div>
      <div>
        <h2 class="text-3xl font-bold tracking-tight">Dossier #1234</h2>
        <p class="text-white/80 text-sm mt-1 font-medium">ID interne: XYZ</p>
      </div>
    </div>
  </div>
</div>
```

#### Badges Modernes (États)
```html
<!-- Badges avec effets visuels -->
<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-lg shadow-green-500/30 ring-2 ring-white">
  <svg class="w-4 h-4 animate-pulse">...</svg>
  EN COURS
</span>

<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg shadow-blue-500/30">
  <svg class="w-4 h-4">...</svg>
  CLOS
</span>

<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-lg shadow-orange-500/30 animate-pulse">
  <svg class="w-4 h-4">⚠️</svg>
  À COMPLÉTER
</span>
```

#### Boutons CTA (Call-to-Action)
```html
<!-- Bouton primaire moderne -->
<button class="group relative overflow-hidden px-6 py-3 rounded-xl font-bold text-white shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-0.5 active:translate-y-0">
  <div class="absolute inset-0 bg-gradient-to-r from-blue-600 to-cyan-600 group-hover:from-blue-700 group-hover:to-cyan-700 transition-all duration-300"></div>
  <div class="absolute inset-0 opacity-0 group-hover:opacity-20 bg-white transition-opacity duration-300"></div>
  <span class="relative flex items-center gap-2">
    <svg class="w-5 h-5 transition-transform duration-300 group-hover:rotate-12">...</svg>
    Action Principale
  </span>
</button>

<!-- Bouton secondaire glassmorphism -->
<button class="relative px-6 py-3 rounded-xl font-semibold text-slate-700 bg-white/80 backdrop-blur-sm border-2 border-slate-200/50 shadow-lg hover:shadow-xl hover:bg-white hover:border-blue-300/50 transition-all duration-300">
  Action Secondaire
</button>
```

#### Inputs Modernes (Formulaires)
```html
<!-- Input avec micro-interactions -->
<div class="group relative">
  <label class="block text-sm font-bold text-slate-700 mb-2 transition-colors group-focus-within:text-blue-600">
    UF Responsabilité <span class="text-red-500">*</span>
  </label>
  <div class="relative">
    <input 
      type="text" 
      class="w-full px-4 py-3 rounded-xl border-2 border-slate-200 bg-white text-slate-900 placeholder-slate-400 transition-all duration-200 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20 focus:shadow-lg focus:shadow-blue-500/10" 
      placeholder="Rechercher UF..."
    />
    <div class="absolute inset-y-0 right-3 flex items-center pointer-events-none">
      <svg class="w-5 h-5 text-slate-400 transition-transform duration-200 group-focus-within:scale-110 group-focus-within:text-blue-500">...</svg>
    </div>
  </div>
  <p class="mt-1.5 text-xs text-slate-500 transition-opacity duration-200 opacity-0 group-focus-within:opacity-100">
    💡 Tapez pour rechercher dans les UF actives
  </p>
</div>
```

#### Tableaux Modernes (Listing)
```html
<!-- Tableau avec hover effects sophistiqués -->
<div class="overflow-hidden rounded-2xl border-2 border-slate-200/50 shadow-xl">
  <table class="min-w-full divide-y-2 divide-slate-200/50">
    <thead>
      <tr class="bg-gradient-to-r from-slate-50 to-slate-100">
        <th class="px-6 py-4 text-left text-xs font-bold text-slate-700 uppercase tracking-wider">VN</th>
        <th class="px-6 py-4 text-left text-xs font-bold text-slate-700 uppercase tracking-wider">Dates</th>
        ...
      </tr>
    </thead>
    <tbody class="bg-white divide-y divide-slate-100">
      <tr class="group hover:bg-gradient-to-r hover:from-blue-50/50 hover:to-purple-50/30 transition-all duration-300 cursor-pointer">
        <td class="px-6 py-4 whitespace-nowrap">
          <span class="inline-flex items-center gap-2 text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
            <svg class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity">→</svg>
            #5678
          </span>
        </td>
        <td class="px-6 py-4 text-sm text-slate-600 font-medium">01/01-05/01</td>
        ...
      </tr>
    </tbody>
  </table>
</div>
```

### 8.3. Animations & Micro-interactions

#### CSS Animations à Ajouter
```css
/* Gradient animé pour headers */
@keyframes gradient-x {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
.animate-gradient-x {
  background-size: 200% 200%;
  animation: gradient-x 15s ease infinite;
}

/* Pulse subtil pour badges d'alerte */
@keyframes pulse-subtle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}
.animate-pulse-subtle {
  animation: pulse-subtle 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Slide-in pour notifications */
@keyframes slide-in-right {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* Skeleton loading moderne */
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}
.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 1000px 100%;
  animation: shimmer 2s infinite;
}
```

### 8.4. Intégration avec Design System (Phase 5.2 Modernisé)

- **Réutiliser et moderniser** :
  - Badges d'état → version gradient avec shadow.
  - Notifications → slide-in animations + glassmorphism.
  - Cartes structure → hover effects + gradient overlays.
  
- **Harmoniser** :
  - Palette couleurs métier (MCO, SSR, PSY, HAD) avec gradients.
  - Icônes Heroicons stroke-2 avec animations hover.
  - Espacements généreux (scale 4px, 8px, 12px, 16px, 24px, 32px).

### 8.5. Checklist Style Moderne

- [ ] Tous les headers utilisent des gradients animés.
- [ ] Tous les boutons ont des hover effects avec transform.
- [ ] Tous les inputs ont focus:ring et transitions fluides.
- [ ] Tous les badges utilisent des gradients + shadows.
- [ ] Toutes les cards ont des border-radius généreuses (rounded-xl/2xl).
- [ ] Tous les tableaux ont des hover effects sur rows.
- [ ] Toutes les transitions sont ≥ 200ms (smooth).
- [ ] Aucune bordure grise fade (border-slate-200/50 minimum).
- [ ] Glassmorphism utilisé pour overlays et modals.
- [ ] Skeleton screens pour chargements (pas de spinners basiques).

---

## 9. 🚀 Plan de Livraison (Incrémental)

### Sprint 6.1 – Refonte Vue Dossier & Amélioration Navigation (3-4 jours)

**Objectif** : Moderniser `dossier_detail.html` pour offrir une vue administrative claire et navigable.

#### Livrables :
1. **Header Dossier enrichi** :
   - NDA très visible avec badge statut (ouvert/clos/à compléter).
   - Résumé patient avec lien rapide vers fiche patient.
   - Statistiques venues : nombre total, venue active, durée totale séjour.
   
2. **Section Synthèse Administrative** :
   - Refonte layout en 2 colonnes (infos clés + dates).
   - Type dossier avec label vocabulaire + bouton modification inline.
   - UF responsabilité, médecin (avec liens vers fiches si disponibles).
   - Indicateurs visuels : badges état, couleurs par type dossier.

3. **Section Venues améliorée** :
   - Tableau venues avec colonnes : VN, dates, UF soins, service, localisation, état, actions.
   - Badges d'état venue (en cours/clôturée/transférée) avec couleurs.
   - Action rapide : « Nouvelle venue » avec pré-remplissage intelligent.

4. **Navigation croisée optimisée** :
   - Fil d'Ariane persistant : Accueil > Patients > Patient X > Dossier #NDA.
   - Quick links latéraux : Patient, Venues, Mouvements, Cotations, Timeline.

#### Tests de validation :
- [ ] Header affiche correctement NDA + statut + statistiques venues.
- [ ] Clic sur patient redirige vers `patient_detail`.
- [ ] Tableau venues affiche toutes les venues avec badges état corrects.
- [ ] Bouton « Nouvelle venue » pré-remplit UF et médecin du dossier.
- [ ] Fil d'Ariane fonctionne sur tous les niveaux.

---

### Sprint 6.2 – Refonte Vue Venue & Timeline Mouvements (2-3 jours)

**Objectif** : Moderniser `venue_detail.html` pour clarifier séjour + localisation + mouvements.

#### Livrables :
1. **Header Venue enrichi** :
   - VN très visible avec lien vers dossier parent.
   - Contexte patient + dossier (breadcrumb + cards).
   - Localisation actuelle (UF soins, service, chambre/lit) avec indicateur disponibilité.

2. **Section Détails Séjour** :
   - Dates début/fin avec durée calculée automatiquement.
   - Nature venue, médecin, UF responsabilité/soins.
   - Badge état (séjour ouvert/clos) + alertes (dates incohérentes, UF manquante).

3. **Section Mouvements chronologique** :
   - Timeline visuelle (inspiration Phase 5 design system).
   - Chaque mouvement avec : type, date/heure, localisation, UF, badge état.
   - Actions : « Nouveau mouvement », « Voir timeline complète ».

4. **Actions rationalisées** :
   - Modifier venue (formulaire optimisé Sprint 6.3).
   - Clôturer venue (si conditions OK).
   - Accéder workflow détaillé (si router workflow disponible).
   - Supprimer (avec garde-fous).

#### Tests de validation :
- [ ] Header affiche VN + contexte dossier/patient.
- [ ] Localisation affiche UF soins + chambre/lit avec état occupation.
- [ ] Timeline mouvements affiche tous les mouvements en ordre chronologique.
- [ ] Bouton « Nouveau mouvement » ouvre formulaire pré-rempli.
- [ ] Clôture venue vérifie cohérence (mouvements, dates).

---

### Sprint 6.3 – Formulaires Optimisés Dossier/Venue (4-5 jours)

**Objectif** : Créer formulaires modernes alignés sur `patient_form.html` avec validation temps réel.

#### Livrables :
1. **Formulaire « Admission Complète »** (nouveau workflow 3 étapes) :
   - Étape 1/3 : Identité patient (recherche + création si nouveau).
   - Étape 2/3 : Dossier administratif (type, UF, médecin, dates, motif).
   - Étape 3/3 : Venue initiale (localisation, service, chambre/lit).
   - Validation progressive, sauvegarde brouillon auto, feedback immédiat.

2. **Formulaire Édition Dossier** :
   - Sections claires : Administratif, Dates, État.
   - Champs requis visuels, validation temps réel.
   - Actions : Sauvegarder, Annuler, Clôturer (si éligible).

3. **Formulaire Venue** (création + édition) :
   - Pré-remplissage intelligent depuis dossier parent.
   - Autocomplete UF avec recherche.
   - Sélecteur chambre/lit avec disponibilité temps réel.
   - Validation métier : dates cohérentes, UF active, localisation disponible.

4. **Composants JS réutilisables** :
   - `UFAutocomplete` : recherche UF avec cache.
   - `DateValidator` : validation dates métier (admission/sortie, début/fin venue).
   - `DraftSaver` : auto-sauvegarde formulaires toutes les 30s.
   - `FormWizard` : gestion workflow multi-étapes avec progression.

#### Tests de validation :
- [ ] Workflow admission complète crée Patient + Dossier + Venue en 3 étapes.
- [ ] Validation temps réel empêche soumission si erreurs métier.
- [ ] Autocomplete UF affiche suggestions pertinentes.
- [ ] Sélecteur chambre/lit affiche disponibilité.
- [ ] Sauvegarde brouillon fonctionne après 30s d'inactivité.
- [ ] Messages erreur sont constructifs et contextuels.

---

### Sprint 6.4 – Optimisations & Raccourcis Administratifs (2-3 jours)

**Objectif** : Ajouter fonctionnalités productivité pour utilisateurs expérimentés.

#### Livrables :
1. **Boutons de création rapide** :
   - Depuis `patient_detail` : « Nouveau dossier » → workflow admission pré-rempli.
   - Depuis `dossier_detail` : « Nouvelle venue » → formulaire pré-rempli.
   - Depuis listing venues : « Nouveau mouvement » → formulaire pré-rempli.

2. **Recherche & Filtres avancés** :
   - Listing dossiers : filtres par UF, médecin, type, période, état.
   - Listing venues : filtres par dossier, patient, UF, service, localisation, état.
   - Sauvegarde filtres favoris (localStorage).

3. **Raccourcis clavier** :
   - `Ctrl+S` : Sauvegarder formulaire.
   - `Ctrl+N` : Nouveau dossier/venue selon contexte.
   - `Ctrl+E` : Éditer entité courante.
   - `Esc` : Fermer modal/annuler.
   - `/` : Focus barre de recherche.

4. **Tableau de bord administratif** (optionnel si temps) :
   - Widget « Mes dossiers en attente » (à compléter, à clôturer).
   - Widget « Venues actives » (séjours ouverts).
   - Widget « Anomalies » (dates incohérentes, UF manquantes).

#### Tests de validation :
- [ ] Bouton « Nouveau dossier » depuis patient fonctionne.
- [ ] Filtres listing dossiers/venues persistent après navigation.
- [ ] Raccourcis clavier fonctionnent dans tous les formulaires.
- [ ] Recherche avancée renvoie résultats pertinents.
- [ ] Dashboard affiche widgets avec données temps réel (si implémenté).

---

### Sprint 6.5 – Tests E2E & Documentation (1-2 jours)

**Objectif** : Valider l'ensemble de la refonte avec tests automatisés et documenter pour utilisateurs.

#### Livrables :
1. **Tests E2E Playwright** :
   - Scénario « Admission complète » (patient + dossier + venue).
   - Scénario « Édition dossier » (modification type, UF, dates).
   - Scénario « Création venue supplémentaire ».
   - Scénario « Navigation croisée » (patient → dossier → venue → mouvements).
   - Scénario « Recherche & filtres ».

2. **Documentation utilisateur** :
   - Guide « Créer une admission complète » avec captures écran.
   - Guide « Gérer les venues d'un dossier ».
   - FAQ « Erreurs courantes et résolutions ».
   - Changelog Phase 6.

3. **Documentation technique** :
   - Architecture composants formulaires.
   - Patterns validation métier.
   - API endpoints utilisés (UF, médecins, disponibilité lits).

#### Tests de validation :
- [ ] Suite E2E passe à 100%.
- [ ] Documentation utilisateur complète et illustrée.
- [ ] Documentation technique à jour.
- [ ] Changelog Phase 6 détaillé.

---

## 📅 Timeline Globale Phase 6

| Sprint | Durée | Fin prévue | Priorité |
|--------|-------|------------|----------|
| 6.1 - Vue Dossier | 3-4j | J+4 | 🔴 Critique |
| 6.2 - Vue Venue | 2-3j | J+7 | 🔴 Critique |
| 6.3 - Formulaires | 4-5j | J+12 | 🔴 Critique |
| 6.4 - Optimisations | 2-3j | J+15 | 🟡 Important |
| 6.5 - Tests & Docs | 1-2j | J+17 | 🟢 Normal |

**Total estimé** : 12-17 jours (~2.5-3.5 semaines)

---

## 🎯 Critères d'Acceptation Globaux

### Fonctionnels
- ✅ Créer une admission complète (patient + dossier + venue) en < 3 minutes.
- ✅ Modifier un dossier existant sans perte de contexte.
- ✅ Naviguer patient → dossiers → venues → mouvements de façon fluide.
- ✅ Rechercher et filtrer dossiers/venues par critères métier.
- ✅ Identifier visuellement anomalies (dates, UF manquante, incohérences).

### Techniques
- ✅ Validation métier temps réel (pas d'erreurs post-soumission évitables).
- ✅ Auto-sauvegarde brouillon toutes les 30s.
- ✅ Composants JS réutilisables et documentés.
- ✅ Cohérence Design System Phase 5.2 (couleurs, badges, notifications).
- ✅ Tests E2E couvrant 80%+ des workflows critiques.

### UX
- ✅ Temps de saisie réduit de 30% vs. workflows actuels (mesuré en tests utilisateurs).
- ✅ Taux d'erreur de saisie réduit de 50% (dates incohérentes, UF manquantes).
- ✅ Feedback utilisateurs positif (>80% satisfaction sur 5 critères clés).
- ✅ Accessibilité : contraste WCAG AA, navigation clavier complète.

---

## 10. ✅ Indicateurs de Succès

- Diminution du temps moyen de création d’un dossier + venue (mesuré sur tests internes).
- Réduction du nombre d’erreurs métier relevées (dates incohérentes, UF manquante, type inadapté).
- Feedback qualitatif positif des utilisateurs administratifs (entretiens / démos).
- Cohérence visuelle avec les phases précédentes (Design System, recherche structure).

---

## 11. 🔧 Dépendances Techniques & Pré-requis

### 11.1. APIs FHIR Nécessaires

**Principe** : Utiliser exclusivement les interfaces FHIR R4 existantes ou les compléter. Pas de nouvelles APIs REST custom.

#### FHIR Endpoints Existants (à vérifier/adapter)

**Location API (UF, Services, Chambres, Lits)** :
- ✅ `GET /fhir/Location?type=uf&status=active&_text={query}` : Recherche UF pour autocomplete.
- ✅ `GET /fhir/Location?type=service&partof={uf_id}` : Services liés à une UF.
- ✅ `GET /fhir/Location?type=room&partof={service_id}&operationalStatus=active` : Chambres disponibles.
- ✅ `GET /fhir/Location?type=bed&partof={room_id}&operationalStatus=U` : Lits libres (U=Unoccupied).
- ✅ `GET /fhir/Location/{id}` : Détails localisation (chambre/lit) avec disponibilité temps réel.

**Practitioner API (Médecins)** :
- ✅ `GET /fhir/Practitioner?active=true&name={query}` : Recherche médecins pour autocomplete.
- ✅ `GET /fhir/Practitioner/{id}` : Détails praticien.
- ✅ `GET /fhir/PractitionerRole?practitioner={id}&active=true` : Rôles actifs du praticien.

**Patient API** :
- ✅ `GET /fhir/Patient?name={query}&birthdate={date}` : Recherche patient existant.
- ✅ `POST /fhir/Patient` : Création patient.
- ✅ `PUT /fhir/Patient/{id}` : Mise à jour patient.
- ✅ `GET /fhir/Patient/{id}` : Récupération patient avec identifiers.

**Encounter API (Venues)** :
- ✅ `GET /fhir/Encounter?patient={id}&status=in-progress` : Encounters actifs patient.
- ✅ `GET /fhir/Encounter/{id}` : Détails encounter (venue) avec locations.
- ✅ `POST /fhir/Encounter` : Création venue.
- ✅ `PUT /fhir/Encounter/{id}` : Mise à jour venue.

**EpisodeOfCare API (Dossiers)** :
- ✅ `GET /fhir/EpisodeOfCare?patient={id}&status=active` : Dossiers actifs patient.
- ✅ `GET /fhir/EpisodeOfCare/{id}` : Détails dossier (EpisodeOfCare).
- ✅ `POST /fhir/EpisodeOfCare` : Création dossier.
- ✅ `PUT /fhir/EpisodeOfCare/{id}` : Mise à jour dossier.

#### FHIR Extensions à Créer/Compléter (Sprint 6.3)

**Bundle Transaction pour Admission Complète** :
- 🆕 `POST /fhir` avec Bundle type=transaction :
  ```json
  {
    "resourceType": "Bundle",
    "type": "transaction",
    "entry": [
      { "resource": {"resourceType": "Patient", ...}, "request": {"method": "POST", "url": "Patient"} },
      { "resource": {"resourceType": "EpisodeOfCare", ...}, "request": {"method": "POST", "url": "EpisodeOfCare"} },
      { "resource": {"resourceType": "Encounter", ...}, "request": {"method": "POST", "url": "Encounter"} }
    ]
  }
  ```
  - Création atomique Patient + Dossier (EpisodeOfCare) + Venue initiale (Encounter).
  - Retour : Bundle type=transaction-response avec références créées.

**$validate Operation** :
- 🆕 `POST /fhir/EpisodeOfCare/{id}/$validate` : Validation métier dossier.
  - Body : Parameters avec règles métier françaises (UF obligatoire si hospitalisé, dates cohérentes, etc.).
  - Retour : OperationOutcome avec errors/warnings.
- 🆕 `POST /fhir/Encounter/{id}/$validate` : Validation métier venue.
  - Vérifie cohérence dates, UF soins, localisation, mouvements.

**Custom Operations pour Clôture** :
- 🆕 `POST /fhir/EpisodeOfCare/{id}/$close` : Clôture dossier avec vérifications.
  - Parameters : `{force: false}` pour forcer ou non.
  - Vérifie : toutes venues closes, dates cohérentes, cotations complètes.
  - Retour : OperationOutcome + EpisodeOfCare mis à jour (status=finished).
- 🆕 `POST /fhir/Encounter/{id}/$close` : Clôture venue avec vérifications.
  - Vérifie : dernier mouvement = sortie, end date renseignée.
  - Retour : OperationOutcome + Encounter mis à jour (status=finished).

**Search Parameters Spécifiques** :
- 🆕 `GET /fhir/EpisodeOfCare?patient={id}&type={code}&period=gt{date}` : Dossiers par type et période.
- 🆕 `GET /fhir/Encounter?episodeofcare={id}&location={location_id}` : Venues par dossier et localisation.
- 🆕 `GET /fhir/Encounter?subject={patient_id}&date=ge{start}&date=le{end}` : Venues par patient et dates.

**Extensions FHIR Françaises (IHE PAM FR)** :
- 🔧 Extension `uf-responsabilite` sur EpisodeOfCare et Encounter.
- 🔧 Extension `uf-soins` sur Encounter.
- 🔧 Extension `dossier-type` sur EpisodeOfCare (hospitalise/externe/urgence).
- 🔧 Extension `venue-nature` sur Encounter (H/M/L/D/S/SM).
- 🔧 Extension `identifiers` avec types NDA, VN, IPP (use=official/usual/temp).

#### Mapping Modèles Internes ↔ FHIR

| Modèle Interne | Ressource FHIR | Mapping Clés |
|----------------|----------------|--------------|
| `Patient` | `Patient` | identifier=IPP, name, birthDate, gender, address |
| `Dossier` | `EpisodeOfCare` | identifier=NDA, patient ref, period, type extension, managingOrganization |
| `Venue` | `Encounter` | identifier=VN, subject=patient, episodeOfCare ref, period, location, participant=médecin |
| `Mouvement` | `Encounter.location` | location ref, period, status |
| `UniteFonctionnelle` | `Location` type=uf | identifier, name, partOf, operationalStatus |
| `Chambre` | `Location` type=room | identifier, name, partOf=service, operationalStatus |
| `Lit` | `Location` type=bed | identifier, name, partOf=chambre, operationalStatus |
| `MedecinResponsable` | `Practitioner` | identifier, name, qualification |

### 11.2. Composants Frontend Réutilisables (Phase 5.2)

#### Déjà disponibles
- ✅ `NotificationSystem` : Notifications toast (succès, erreur, warning, info).
- ✅ `StructureCard` : Cartes entités structure (adaptable pour dossiers/venues).
- ✅ `OccupationColors` : Calcul couleurs selon taux occupation (adaptable pour disponibilité lits).
- ✅ `SearchComponent` : Barre de recherche avec debounce.
- ✅ `FilterComponent` : Filtres multi-critères.

#### À créer (Sprint 6.3)
- 🆕 `UFAutocomplete` : Autocomplete UF avec cache et recherche serveur.
- 🆕 `DateValidator` : Validation dates métier (admission/sortie, début/fin venue).
- 🆕 `DraftSaver` : Auto-sauvegarde formulaires toutes les 30s.
- 🆕 `FormWizard` : Gestion workflow multi-étapes avec progression.
- 🆕 `LocalisationSelector` : Sélecteur Chambre/Lit avec disponibilité.
- 🆕 `BadgeStatus` : Badges d'état standardisés (dossier, venue, mouvement).

### 11.3. Services Backend & FHIR Adapters

#### Services FHIR à Créer/Adapter

**FHIRPatientService** :
- 🔧 `search_patients(name, birthdate, identifier)` → appelle `GET /fhir/Patient?...`.
- 🔧 `create_patient(patient_data)` → `POST /fhir/Patient` + mapping modèle interne.
- 🔧 `update_patient(patient_id, patient_data)` → `PUT /fhir/Patient/{id}`.

**FHIREpisodeOfCareService** (Dossiers) :
- 🔧 `get_episode_with_encounters(episode_id)` → `GET /fhir/EpisodeOfCare/{id}?_include=EpisodeOfCare:encounter`.
- 🔧 `create_episode(patient_id, episode_data)` → `POST /fhir/EpisodeOfCare`.
- 🔧 `validate_episode(episode_id)` → `POST /fhir/EpisodeOfCare/{id}/$validate`.
- 🔧 `close_episode(episode_id, force=False)` → `POST /fhir/EpisodeOfCare/{id}/$close`.

**FHIREncounterService** (Venues) :
- 🔧 `get_encounter_with_locations(encounter_id)` → `GET /fhir/Encounter/{id}?_include=Encounter:location`.
- 🔧 `create_encounter(patient_id, episode_id, encounter_data)` → `POST /fhir/Encounter`.
- 🔧 `validate_encounter(encounter_id)` → `POST /fhir/Encounter/{id}/$validate`.
- 🔧 `close_encounter(encounter_id)` → `POST /fhir/Encounter/{id}/$close`.
- 🔧 `get_encounter_duration(encounter_id)` → calcul depuis period.start/end.

**FHIRLocationService** (UF/Services/Chambres/Lits) :
- 🔧 `search_locations(type, status, query)` → `GET /fhir/Location?type={type}&status={status}&_text={query}`.
- 🔧 `get_location_availability(location_id)` → `GET /fhir/Location/{id}` + analyse operationalStatus.
- 🔧 `get_child_locations(parent_id, type)` → `GET /fhir/Location?partof={parent_id}&type={type}`.

**FHIRBundleService** (Transactions) :
- 🆕 `create_admission_bundle(patient_data, episode_data, encounter_data)` :
  - Construit Bundle transaction avec 3 resources.
  - `POST /fhir` avec Bundle.
  - Parse transaction-response et extrait IDs créés.
  - Retour : `{patient_id, episode_id, encounter_id, fhir_ids}`.

#### Routers à Adapter (HTML + FHIR Backend)

- 🔧 `app/routers/dossiers.py` :
  - `show_dossier(dossier_id)` → appelle `FHIREpisodeOfCareService.get_episode_with_encounters()`.
  - `new_dossier_form()` → affiche wizard admission, soumission vers FHIR Bundle.
  - `validate_dossier(dossier_id)` → appelle `$validate` operation FHIR.
  - `close_dossier(dossier_id)` → appelle `$close` operation FHIR.

- 🔧 `app/routers/venues.py` :
  - `show_venue(venue_id)` → appelle `FHIREncounterService.get_encounter_with_locations()`.
  - `new_venue_form(dossier_id)` → formulaire avec pré-remplissage, soumission FHIR.
  - `close_venue(venue_id)` → appelle `$close` operation FHIR.

#### Nouveaux templates
- 🆕 `app/templates/admission_wizard.html` : Workflow 3 étapes admission.
- 🆕 `app/templates/dossier_form.html` : Formulaire édition dossier (à séparer du wizard).
- 🆕 `app/templates/venue_form.html` : Formulaire création/édition venue.
- 🆕 `app/templates/components/badge_status.html` : Macro badges d'état.
- 🆕 `app/templates/components/timeline_mouvements.html` : Timeline mouvements venue.

### 11.4. Tests Pré-requis

#### Données de test nécessaires (fixtures)
- ✅ 3-5 patients avec identités complètes.
- ✅ 5-10 dossiers couvrant tous types (Hospitalisé, Externe, Urgence).
- ✅ 10-15 venues avec états variés (en cours, clôturées, anomalies).
- ✅ 5-10 UF actives dans différentes EJ.
- ✅ 3-5 médecins responsables.
- ✅ 5-10 chambres avec lits (certains occupés, d'autres disponibles).
- ✅ 20-30 mouvements couvrant tous types (entrée, transfert, sortie, mutation).

#### Scénarios de test E2E à préparer
1. Admission complète patient nouveau.
2. Admission complète patient existant.
3. Édition dossier avec modification type (validation incompatibilité venues).
4. Création venue supplémentaire sur dossier existant.
5. Clôture venue avec vérifications.
6. Clôture dossier avec vérifications.
7. Navigation croisée patient → dossier → venue → mouvements → retour.
8. Recherche dossier par NDA, patient, UF, période.
9. Détection anomalie (dates incohérentes, UF manquante).
10. Sauvegarde brouillon et reprise formulaire.

### 11.5. Vocabulaires & Référentiels

#### À vérifier/compléter
- ✅ Vocabulaire `dossier-type` : Hospitalisé, Externe, Urgence, HAD, etc.
- ✅ Vocabulaire `admission-type` : Programmée, Urgence, Mutation, Transfert, etc.
- ✅ Vocabulaire `admission-source` : Domicile, Autre établissement, Urgences, etc.
- ✅ Vocabulaire `discharge-disposition` : Domicile, Décès, Transfert, etc.
- ✅ Vocabulaire `venue-nature` : H, M, L, D, S, SM (codes IHE PAM FR).
- ✅ Vocabulaire `mouvement-type` : Entrée, Sortie, Transfert, Mutation, etc.

---

## 12. 📚 Références & Inspirations UX

### 12.1. Benchmarks Hospitaliers
- **Hospiway** (France) : Workflow admission avec wizard, validation temps réel.
- **Easily** (France) : Interface administrative épurée, badges état, autocomplete performant.
- **Opale** (Agfa Healthcare) : Gestion dossiers/séjours avec timeline mouvements.
- **DxCare** (Dedalus) : Synthèse dossier dense mais lisible, navigation contextuelle.

### 12.2. Patterns UX Généraux
- **Multi-step forms** (Stripe Checkout, Typeform) : Progression visuelle, sauvegarde brouillon.
- **Admin dashboards** (Tailwind UI, Ant Design) : Layouts info-denses, cartes statistiques.
- **Autocomplete** (Google, Algolia) : Recherche instantanée avec cache, suggestions pertinentes.
- **Timeline** (GitHub, Jira) : Affichage chronologique événements avec icônes/couleurs.

### 12.3. Guidelines Accessibilité
- **WCAG 2.1 AA** : Contraste 4.5:1 minimum, navigation clavier, labels explicites.
- **RGAA 4** (France) : Formulaires accessibles, messages d'erreur contextuels.
- **Nielsen Norman Group** : Heuristiques UX (visibilité état, prévention erreurs, consistance).

---

## 13. 🚨 Risques & Mitigation

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| **Incompatibilité données existantes** | 🔴 Élevé | 🟡 Moyen | Migration progressive, tests sur copie base prod, rollback plan |
| **Performance autocomplete UF/médecins** | 🟠 Moyen | 🟡 Moyen | Cache côté client, index DB optimisés, pagination résultats |
| **Complexité workflow admission 3 étapes** | 🟠 Moyen | 🟢 Faible | UX tests utilisateurs, feedback itératif, tutoriel intégré |
| **Validation métier bloquante** | 🟠 Moyen | 🟡 Moyen | Messages constructifs, mode "forcer" avec confirmation admin |
| **Régression fonctionnelle** | 🔴 Élevé | 🟢 Faible | Tests E2E exhaustifs, revue code, déploiement progressif |
| **Adoption utilisateurs** | 🟠 Moyen | 🟡 Moyen | Formation ciblée, documentation illustrée, support dédié J+0 |

