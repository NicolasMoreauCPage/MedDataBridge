# Audit des IHM MedData Bridge - V2 (ARCHIVÉ)

> ⚠️ **Document archivé** : le plan d'action unifié et à jour se trouve dans `docs/ihm_audit.md`.  
> Ce fichier conserve le détail textuel de l'audit du 9 janvier 2026 (état actuel, points forts, points d'amélioration) mais **la référence pour le suivi des travaux est désormais uniquement `ihm_audit.md`**.

---

## 1. Accueil et dashboard global

### État actuel
- **Route** : `GET /` → `home.html`  
- **Status** : ✅ **Fonctionnel et moderne** (dernière révision 9 janvier 2026)

### Points forts
- Mise en page hero + cartes d'accès rapide bien structurées (Interop, Infrastructure, Structure, Workflow).
- **✅ Nouveau (9 janvier)** : Sidebar informative avec contexte établissement hiérarchisé (EG > EJ > GHT) dans la carte "Contexte établissement".
- Monitoring et documentation accessibles depuis la home.
- Stats clés (patients, dossiers, venues) bien mises en avant.

### Points d'amélioration identifiés
1. **Contexte visuel** : Le badge de contexte EG dans le header existe mais pourrait être plus visible (taille, position, ou duplication dans le hero).
2. **Indicateurs d'alerte** : Ajouter mini-résumé d'erreurs/alertes système directement dans le hero (ACK en erreur des dernières 24h, taux de disponibilité MLLP).
3. **Cartes d'accès rapide** : Uniformiser les couleurs/icônes (actuellement bleu/vert/violet/amber, pourrait être plus sobre).

### Actions recommandées
- [ ] Ajouter un widget "État système" dans la home (carte compact : ACK erreurs, listeners actifs, dernière synchro structure).
- [ ] Tester la visibilité du contexte EG sur écrans 1080p et 4K.

---

## 2. Contexte GHT / EJ / EG

### État actuel
- **Routes principales** :
  - Sélection GHT : `GET /admin/ght` → `ght_contexts.html`
  - Détail GHT + EJ/EG : `GET /context/ght/{id}` → `ght_detail.html`
  - Sélection EG : `GET /context/eg/{id}` (redirection vers `/structure/eg/{id}`)
- **Status** : ✅ **Corrigé** (bugs de contexte EG/EJ résolus le 9 janvier 2026)

### Points forts
- **✅ Corrections récentes (9 janvier)** :
  - Bug 404 sur sélection EG corrigé : route `/structure/entites-geo/{id}` remplacée par `/structure/eg/{id}`.
  - Logique de contexte corrigée : sélection d'une EG aligne maintenant `eg_context_id`, `ej_context_id` ET `ght_context_id` en session.
  - Template `home.html` : affichage hiérarchique EG > EJ > GHT explicite dans sidebar.
- Page `ght_detail.html` : hiérarchie claire GHT → EJ → EG avec cartes modernes Tailwind.
- Breadcrumbs et headers gradient cohérents sur toutes les pages de sélection.

### Points d'amélioration identifiés
1. **Titre et breadcrumb de `ght_detail.html`** : Le titre principal indique "Entités juridiques" alors que la page contient aussi les EG → clarifier avec "Contexte GHT : EJ et EG" ou "Configuration du GHT".
2. **Explications utilisateur** : Ajouter un bloc informatif en haut de `ght_detail.html` pour expliquer la différence EJ (entité juridique, FINESS EJ, SIREN) vs EG (site/hôpital, FINESS EG).
3. **Navigation structure** : Depuis une EG sélectionnée, faciliter l'accès aux pages structure (pôles, services, lits) avec un menu latéral ou des liens rapides.

### Actions recommandées
- [ ] Clarifier titre `ght_detail.html` : "GHT {nom} - Gestion EJ et EG".
- [ ] Ajouter encadré explicatif en haut (différence EJ/EG, workflow de sélection).
- [ ] Créer sidebar navigation structure avec contexte EG actif.

---

## 3. Structure hospitalière

### État actuel
- **Routes principales** : `/structure`, `/structure/wizard`, `/structure/import/hl7`, `/structure/interactive`, `/structure/map`
- **Templates** : `structure/*.html`, `structure_interactive.html`, `structure_map_placeholder.html`
- **Status** : ✅ **Modernisé** (base Tailwind + `base.html`)

### Points forts
- Wizard de structure et import MFN/FHIR bien identifiés.
- Présence de breadcrumbs et de titres explicites.
- Pages EG, pôles, services bien intégrées dans le design system.

### Points d'amélioration identifiés
1. **Navigation hiérarchique** : Unifier la navigation "Structure" avec barre latérale ou menu onglets pour EG → Pôles → Services → UF → UH → Lits.
2. **Statuts d'import** : Clarifier les statuts d'import/synchronisation (succès, partiel, erreurs) avec composants de status uniformes.
3. **Structure interactive** : Sur `structure_interactive.html`, alléger le CSS inline et harmoniser les interactions.

---

## 4. Patients, venues et dossiers

### État actuel
- **Routes principales** :
  - Liste patients : `/patients` → `list.html`
  - Détail patient : `/patients/{id}` → `patient_detail.html`
  - Formulaires : `/patients/new`, `/patients/{id}/edit` → `patient_form.html`
  - Venues : `/venues` → `list.html`, `venue_detail.html`
  - Dossiers : `/dossiers` → `list.html`, `dossier_detail.html`
- **Status** : ✅ **Moderne et cohérent**

### Points forts
- Toutes les listes passent par `list.html` moderne (macros, actions, filtres, raccourcis clavier).
- `patient_detail.html` et `dossier_detail.html` utilisent cartes, badges et mise en page responsive.
- Formulaires patients/dossiers déjà refondus (groupes logiques, légendes, aides RGPD).

### Points d'amélioration identifiés
1. **Densité formulaires** : Réduire la densité de texte dans les formulaires longs en regroupant certains champs dans des sections repliables.
2. **Boutons standardisés** : Standardiser les boutons principaux (couleur, icône, position) pour Créer / Enregistrer / Annuler.
3. **Actions rapides** : Sur les détails, mettre mieux en avant les actions clés (ajouter mouvement, timeline, cotations) via header d'actions homogène.

---

## 5. Mouvements et timeline

### État actuel
- **Routes principales** : `/plan-lits`, `/timeline`, routes `mouvements.py`
- **Templates** : `plan_lits.html`, `timeline.html`, `mouvement_detail.html`, `mouvement_workflow.html`
- **Status** : ✅ **Moderne** (exploite bien Tailwind)

### Points forts
- Timeline et plan de lits : vue synthétique avec filtres et légendes.
- Détails de mouvements en cartes/sections bien structurées.

### Points d'amélioration identifiés
1. **Code couleur timeline** : Clarifier visuellement l'axe temporel avec code couleur homogène admission/transfert/sortie.
2. **État des lits** : Sur `plan_lits.html`, améliorer la lisibilité des états (occupé, libre, réservé) avec badges et contraste fort.
3. **Actions visuelles** : Mieux lier les actions aux éléments visuels (icônes, menus contextuels).

---

## 6. Messages, interop et monitoring

### État actuel
- **Routes principales** :
  - Journal : `/messages`, `/messages/{id}` → `messages.html`, `message_detail.html`
  - Envoi : `/messages/send` → `send_message.html`, `send_message_result.html`
  - Métriques : `/metrics/dashboard` → `metrics_dashboard.html`
  - Cache : `/cache-dashboard` → `cache_dashboard.html`
- **Status** : ⚠️ **Partiellement moderne** (cache dashboard à revoir)

### Points forts
- Journal messages avec `list.html` moderne et légende d'état intégrée.
- Écrans d'envoi de message structurés (type, endpoint, payload).
- `metrics_dashboard.html` et `analytics_dashboard.html` déjà dans un style moderne.

### Points d'amélioration identifiés
1. **`cache_dashboard.html`** : ❌ **Problème** - contenu très "full HTML custom" (grille CSS classique, cartes custom) → migrer vers composants Tailwind/macros de `analytics_dashboard.html`.
2. **Assistance saisie** : Sur `send_message.html`, améliorer l'assistance (templates de payloads, exemples, validation UI).
3. **Filtres rapides** : Ajouter des vues enregistrées pour les messages (ACK négatifs 24h, etc.).

---

## 7. Endpoints, MLLP et configuration technique

### État actuel
- **Routes principales** :
  - Hiérarchie : `/endpoints` → `endpoints_hierarchical.html`
  - Détail : `/endpoints/{id}` → `endpoint_detail.html`
  - MLLP : `tools_mllp.html`, `mllp_config_form.html`
- **Status** : ⚠️ **Partiellement moderne** (CSS custom legacy important)

### Points forts
- Header moderne et breadcrumbs cohérents.
- Vue hiérarchique GHT → EJ → Endpoints permet navigation par contexte.
- Détails endpoint bien structurés (config, transports, scénarios).

### Points d'amélioration identifiés (CRITIQUE)
1. **`endpoints_hierarchical.html`** :
   - ❌ **Problème majeur** : CSS inline très custom (`.ght-group`, `.ej-group`, `.no-ght-group`, tables custom) qui contraste fortement avec design Tailwind.
   - Styles de bordures, couleurs, padding définis en dur → difficile à maintenir.
   - À migrer vers composants Tailwind : cards, badges, tables avec utilities.
2. **`endpoint_detail.html`** :
   - Bloc `<style>` important encore présent.
   - Uniformiser les sections avec patterns de `dossier_detail.html` ou `patient_detail.html`.

### Actions recommandées (PRIORITÉ HAUTE)
- [ ] **Refonte `endpoints_hierarchical.html`** : remplacer CSS custom par grilles Tailwind + cards standards.
- [ ] Migrer styles inline de `endpoint_detail.html` vers classes utilitaires Tailwind.
- [ ] Ajouter légende visuelle pour statuts endpoints (ON/OFF, running/stopped) avec badges colorés uniformes.

---

## 8. Cotations et codage

### État actuel
- **Routes principales** :
  - Saisie rapide : `/cotations/dossiers/{id}/saisie-rapide` → `cotations/saisie_rapide.html`
  - Cotation moderne HPRIM : `/cotation-modern/dossiers/{id}/cotation` → `hprim_cotation_modern.html`
  - NGAP legacy : `ngap/*.html`
- **Status** : ⚠️ **En cours d'harmonisation**

### Points forts
- **`cotations/saisie_rapide.html`** : ✅ Excellent modèle de référence (sélecteurs type acte, formulaires dédiés CCAM/NGAP/UCD/LPP, cartes stats, Tailwind pur).
- Détails des actes bien structurés avec badges et statuts clairs.
- Terminologie business alignée ("prestations", "séjour").

### Points d'amélioration identifiés
1. **`hprim_cotation_modern.html`** :
   - ✅ **Progrès récent** : ancien formulaire legacy géant supprimé (nettoyage important).
   - ⚠️ **Reste à faire** :
     - Modal d'ajout d'intervention : harmoniser markup avec patterns de `saisie_rapide`.
     - Intégrer pleinement `cotationForm.js` : IDs/classes DOM doivent matcher.
     - CSS inline encore présent (styles modal, toasts, loaders, tooltips) → migrer vers Tailwind utilities.
2. **Pages NGAP** : ❌ Aspect "legacy app", pas de header moderne ni breadcrumbs cohérents.

### Actions recommandées (PRIORITÉ MOYENNE)
- [ ] Aligner `hprim_cotation_modern.html` sur `saisie_rapide.html` : markup modal, boutons, badges uniformes.
- [ ] Vérifier intégration complète `cotationForm.js` : tests fonctionnels recherche actes, calcul tarif.
- [ ] Migrer CSS inline vers Tailwind (modal-bg, toast, loader, tooltip).

---

## 9. Vocabularies, conformité et documentation

### État actuel
- **Routes principales** :
  - Vocabularies : `/vocabularies` → `vocabularies/list.html`, `vocabulary_detail.html`
  - Conformité : `conformity_home.html`, `conformity_dashboard.html`, `conformity_messages.html`
  - Documentation : `documentation*.html`, `doc_wrapper.html`, `api_docs.html`, `user_guide.html`
- **Status** : ✅ **Bien intégré** (quelques styles inline résiduels)

### Points forts
- Pages de vocabulaire déjà bien intégrées (listes et détails avec cartes).
- Conformité : usage cohérent des cartes et tableaux.
- Documentation interne bien structurée, avec page de design system pour référence.

### Points d'amélioration identifiés
1. **Headers standardisés** : Uniformiser les headers (même type de hero/breadcrumbs) sur toutes les pages conformité/documentation.
2. **Styles inline** : Réduire les styles inline restants dans `documentation.html` et `doc_wrapper.html`.
3. **Liens croisés** : Ajouter liens entre documentation et écrans (ex: écran cotation → doc NGAP/CCAM).

---

## 10. Synthèse et plan d'action priorisé

### État global de la refonte IHM (9 janvier 2026)
- ✅ **Base design system** : Tailwind + `base.html` + macros UI bien établis.
- ✅ **Pages métier principales** : Patients, dossiers, venues, messages, vocabulaires → modernes et cohérents.
- ✅ **Contexte GHT/EJ/EG** : Bugs de sélection corrigés, affichage hiérarchique fonctionnel.
- ⚠️ **Pages techniques** : Endpoints et cache encore en CSS custom legacy, contraste fort avec le reste.
- ⚠️ **Cotations HPRIM moderne** : Formulaire legacy nettoyé, mais intégration JS et modal à finaliser.

---

### Plan d'action par priorité

#### 🔴 **PRIORITÉ 1 - Cohérence visuelle technique** (Impact UX fort pour administrateurs)
**Objectif** : Mettre les pages techniques au même niveau que les pages métier.

1. **Refonte `endpoints_hierarchical.html`** (2-3h)
   - Remplacer CSS custom (`.ght-group`, `.ej-group`, tables) par composants Tailwind.
   - Utiliser cards standards, badges pour statuts, grilles responsive.
   - Ajouter légende visuelle (ON/OFF, running/stopped) avec code couleur uniforme.
   - **Bénéfice** : 80% des admins système utilisent cette page quotidiennement.

2. **Refonte `cache_dashboard.html`** (2h)
   - Migrer vers composants `analytics_dashboard.html` (cartes métriques Tailwind).
   - Supprimer CSS custom (grille, cards inline).
   - Harmoniser widgets Redis avec reste monitoring.
   - **Bénéfice** : Page de diagnostic technique critique, doit inspirer confiance.

3. **Nettoyage `endpoint_detail.html`** (1h)
   - Migrer bloc `<style>` vers Tailwind utilities.
   - Uniformiser sections (même patterns que `patient_detail.html`).

---

#### 🟠 **PRIORITÉ 2 - Finalisation cotations modernes** (Impact UX métier)
**Objectif** : Terminer l'harmonisation du module cotation HPRIM.

4. **Alignement `hprim_cotation_modern.html`** (3-4h)
   - Modal ajout intervention : adapter markup sur patterns `saisie_rapide.html`.
   - Vérifier intégration `cotationForm.js` : tests recherche actes, calcul tarif.
   - Migrer CSS inline (modal-bg, toasts, loader) vers Tailwind.
   - **Bénéfice** : Module cotation utilisé intensément par les professionnels de santé.

5. **Tests fonctionnels cotations** (2h)
   - Scénario complet : sélection intervention → ajout actes CCAM/NGAP/UCD/LPP → calcul tarif → validation.
   - Vérifier comportements JS (suggestions, modificateurs, coefficients).

---

#### 🟡 **PRIORITÉ 3 - Améliorations ergonomiques** (Impact confort utilisateur)
**Objectif** : Réduire charge cognitive sur formulaires longs et améliorer navigation.

6. **Formulaires patients/dossiers : sections repliables** (2h)
   - Grouper champs optionnels dans accordéons (adresses secondaires, RGPD, métadonnées).
   - Par défaut : afficher uniquement champs essentiels (identité, dates clés, statut).
   - Utiliser `<details>` HTML5 ou composant Tailwind accordion.

7. **Navigation structure hiérarchique** (3h)
   - Ajouter sidebar ou menu onglets sur pages structure : EG → Pôles → Services → UF → UH → Lits.
   - Breadcrumbs enrichis avec contexte actif (ex: "CHU Nord > Pôle Médecine > Service Cardio").
   - Liens rapides depuis contexte EG vers plan de lits, timeline, patients du site.

8. **Widget état système sur home** (1h)
   - Carte compacte : ACK erreurs 24h, listeners MLLP actifs, dernière synchro structure.
   - Indicateurs visuels (vert/orange/rouge) pour orienter l'utilisateur dès l'accueil.

---

#### 🟢 **PRIORITÉ 4 - Refonte pages legacy** (Impact faible court terme)
**Objectif** : Mettre à niveau les dernières pages anciennes (NGAP, anciennes docs).

9. **Refonte NGAP legacy** (`ngap/*.html`) (4-5h)
   - Header moderne, breadcrumbs, cards Tailwind.
   - Aligner sur patterns `saisie_rapide.html`.
   - **Note** : Basse priorité car usage NGAP en décroissance (majorité CCAM maintenant).

10. **Documentation interne** (2h)
    - Harmoniser headers `documentation.html`, `doc_wrapper.html`.
    - Réduire styles inline restants.
    - Ajouter liens croisés vers pages concernées (ex: doc CCAM → page cotations).

---

### Estimation globale et ROI
- **Priorité 1** (endpoints + cache) : ~5-6h → **Impact immédiat perception qualité** (pages utilisées quotidiennement par admins).
- **Priorité 2** (cotations) : ~5-6h → **Impact utilisateurs métier quotidiens** (soignants, secrétaires médicales).
- **Priorité 3** (ergonomie) : ~6h → **Amélioration confort usage** (réduction charge cognitive).
- **Priorité 4** (legacy) : ~6-7h → **Complétion refonte** (faible urgence, pages peu utilisées).

**Total refonte complète** : ~22-25h de développement.

**ROI recommandé** : Prioriser P1 et P2 (80% des bénéfices pour 50% de l'effort).

---

### Prochaines étapes recommandées

1. **Issues GitHub par priorité** :
   - `[P1] Refonte endpoints_hierarchical.html - CSS custom → Tailwind`
   - `[P1] Refonte cache_dashboard.html - Migration vers analytics pattern`
   - `[P2] Finalisation hprim_cotation_modern.html - Alignement saisie_rapide`

2. **Sprints proposés** :
   - **Sprint 1** (P1) : endpoints + cache → livraison cohérence technique
   - **Sprint 2** (P2) : cotations → livraison module métier complet
   - **Sprint 3** (P3+P4) : ergonomie + legacy → finitions

3. **Métriques de succès** :
   - Temps de chargement pages techniques < 2s
   - Réduction des tickets support "interface confuse" de 50%
   - Satisfaction utilisateur (enquête) > 8/10 pour modules cotation et endpoints

Ce document sert de référentiel pour la **v2 de la refonte IHM professionnelle**. Chaque section peut être convertie en issue/PR avec checklist détaillée et critères d'acceptation précis.