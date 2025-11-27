# Audit de Navigation - MedData Bridge

Date: 9 novembre 2025

## Routes importantes NON accessibles via les menus

### 1. **Scénarios** (`/scenarios`)
- Route existante: `/scenarios` et `/scenarios/{id}`
- Utilité: Gestion des scénarios de tests IHE PAM
- **RECOMMANDATION**: Ajouter dans menu "Interopérabilité"

### 2. **Conformité IHE PAM** (`/conformity`)
- Routes: `/conformity` (liste des EJ), `/conformity/ej/{ej_id}` (dashboard de conformité)
- Utilité: Dashboard de conformité aux normes IHE PAM
- **RECOMMANDATION**: Ajouter dans menu "Interopérabilité" ou "Activités"

### 3. **Timeline** (visualisation temporelle)
- Routes: `/patient/{id}`, `/dossier/{id}`, `/venue/{id}` (avec prefix timeline implicite)
- Utilité: Visualisation chronologique des événements
- **RECOMMANDATION**: Accessible via les pages de détail (Patient, Dossier, Venue)

### 4. **Messages par dossier** (`/messages/by-dossier`)
- Route: `/messages/by-dossier`
- Utilité: Vue groupée des messages par numéro de dossier
- **RECOMMANDATION**: Ajouter dans menu "Interopérabilité" sous-menu Messages

### 5. **Messages rejetés** (`/messages/rejections`)
- Route: `/messages/rejections`
- Utilité: Liste des messages avec erreurs de traitement
- **RECOMMANDATION**: Ajouter dans menu "Interopérabilité" sous-menu Messages

### 6. **Validation de dossier** (`/messages/validate-dossier`)
- Route: `/messages/validate-dossier`
- Utilité: Validation complète d'un dossier selon règles IHE PAM
- **RECOMMANDATION**: Ajouter dans menu "Activités" sous Formulaires & validations

### 7. **Forms** (`/forms`)
- Route: `/forms` (liste des formulaires dynamiques)
- Utilité: Gestion des formulaires de saisie
- **PRÉSENT** dans le menu mais **aucun router n'existe** !
- **RECOMMANDATION**: Supprimer du menu OU créer le router

### 8. **Documentation standards** (`/documentation`)
- Routes: `/documentation/`, `/documentation/guide/{file}`, `/documentation/{category}/{file}`
- Utilité: Documentation complète avec recherche
- **RECOMMANDATION**: Lien déjà présent via `/guide` mais accès incomplet

### 9. **Export structure HL7** (`/structure/export/hl7`)
- Route: `/structure/export/hl7`
- Utilité: Export MFN de toute la structure
- **RECOMMANDATION**: Bouton dans page `/structure` (tableau structurel)

### 10. **Workflow (état des venues)** (`/workflow/venue/{id}/view`)
- Route: `/workflow/venue/{id}/view`
- Utilité: Visualisation du workflow d'une venue
- **RECOMMANDATION**: Lien depuis page détail venue

## Routes accessibles dans les menus

### Menu "Tableau de bord"
- ✅ `/` - Page d'accueil

### Menu "Interopérabilité"
- ✅ `/messages` - Liste des messages
- ✅ `/messages/send` - Envoi de message
- ✅ `/validation` - Validation HL7
- ✅ `/endpoints` - Gestion des endpoints
- ❌ `/scenarios` - **MANQUANT**
- ❌ `/messages/rejections` - **MANQUANT**
- ❌ `/messages/by-dossier` - **MANQUANT**
- ❌ `/conformity` - **MANQUANT**

### Menu "Ressources"
- ✅ `/guide` - Guide utilisateur
- ✅ `/api-docs` - Documentation API
- ✅ `/admin` - Admin SQL (gateway)

### Menu "Activités" (si GHT sélectionné)
- ✅ `/patients` - Liste patients
- ✅ `/dossiers` - Liste dossiers
- ✅ `/venues` - Venues (si dossier sélectionné)
- ✅ `/mouvements` - Mouvements (si dossier sélectionné)
- ❌ `/forms` - **ERREUR: route n'existe pas!**
- ✅ `/vocabularies` - Listes de valeurs
- ❌ `/messages/validate-dossier` - **MANQUANT**

### Menu "Structure" (si GHT sélectionné)
- ✅ `/structure` - Tableau structurel (si EJ sélectionné)
- ✅ `/admin/ght` - Contextes GHT
- ✅ `/structure/search` - Recherche avancée (si EJ sélectionné)
- ✅ `/structure/eg` - Entités géographiques (si EJ)
- ✅ `/structure/poles` - Pôles (si EJ)
- ✅ `/structure/services` - Services (si EJ)
- ✅ `/structure/ufs` - UF (si EJ)
- ✅ `/structure/uh` - UH (si EJ)
- ✅ `/structure/chambres` - Chambres (si EJ)
- ✅ `/structure/lits` - Lits (si EJ)

## Recommandations prioritaires

### 1. **URGENT: Corriger le lien `/forms`**
Le menu pointe vers `/forms` mais **aucun router n'existe**!
- Option A: Créer le router forms
- Option B: Supprimer le lien du menu

### 2. **Ajouter sous-menu Messages avancé**
Dans "Interopérabilité" > Messages:
- Messages (liste globale)
- Messages par dossier
- Messages rejetés
- Validation de dossier

### 3. **Ajouter lien Scénarios**
Dans "Interopérabilité":
- Scénarios IHE PAM

### 4. **Ajouter lien Conformité**
Dans "Interopérabilité" ou créer un menu "Qualité":
- Dashboard de conformité

### 5. **Améliorer liens contextuels**
Dans pages de détail:
- Patient → Ajouter lien Timeline
- Dossier → Ajouter lien Timeline + Messages
- Venue → Ajouter lien Workflow + Timeline

### 6. **Export structure**
Dans page `/structure`:
- Ajouter bouton "Export HL7/MFN"

## Pages fonctionnelles mais sans navigation

Ces pages fonctionnent mais ne sont accessibles que via liens directs ou formulaires:
- Pages de création (`/new`)
- Pages d'édition (`/edit`)
- Pages de détail avec ID
- API endpoints (`/api/*`)
- FHIR endpoints (`/fhir/*`)
- Debug endpoints (`/debug/*`)
- Health checks (`/health`, `/api/version`)

Ces routes sont **normales** et ne nécessitent pas de lien dans les menus.
