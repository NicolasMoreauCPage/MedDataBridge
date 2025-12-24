# Menu Map — MedData Bridge

Ce fichier répertorie la carte des menus principaux affichés dans l'interface (source: `app/templates/base.html`). Il sert de référence pour la documentation et la navigation.

> Note: certaines entrées sont conditionnelles (ex. filtrées par contexte GHT / EJ / patient). Les routes indiquées correspondent aux href utilisés dans le template.

## Navigation principale (bureau)

- Structure (visible si `ght_context`):
  - Tableau structurel: `/structure`
  - Contexts GHT (admin): `/admin/ght`
  - Recherche avancée: `/structure/search`
  - Entités (grouped):
    - Entités géographiques: `/structure/eg`
    - Pôles: `/structure/poles`
    - Services: `/structure/services`
    - UF: `/structure/ufs`
    - UH: `/structure/uh`
    - Chambres: `/structure/chambres`
    - Lits: `/structure/lits`

- Activités (visible si `ght_context`):
  - Patients: `/patients`
  - Dossiers & Cotation: `/dossiers`
  - Venues: `/venues` (optionnel `?dossier_id=`)
  - Mouvements: `/mouvements` (optionnel `?venue_id=` ou `?dossier_id=`)

- Interopérabilité:
  - Tous les messages: `/messages`
  - Par dossier: `/messages/by-dossier`
  - Messages rejetés: `/messages/rejections`
  - Envoi de message: `/messages/send`
  - Validation HL7: `/validation`
  - Conformité IHE: `/conformity`
  - Fichiers de test HPRIM: `/hprim/test-files`
  - Roundtrip HPRIM: `/roundtrip-hprim`
  - Scénarios IHE PAM: `/scenarios`
  - Import HPRIM: `/hprim/import`
  - Cotation moderne: `/cotation-modern`
  - Endpoints (gestion): `/endpoints`

- Ressources / Documentation:
  - Guide utilisateur: `/guide`
  - Documentation API: `/api-docs`
  - FHIR (site externe): https://www.hl7.org/fhir/
  - Index Documentation: `/documentation`
  - Docs programme / architecture / API / utilisateur / modèles: `/docs/PROGRAM_DOCUMENTATION.md`, `/docs/architecture.md`, `/docs/api_guide.md`, `/docs/user_guide.md`, `/docs/models_reference.md`
  - FHIR API (markdown): `/docs/FHIR_API.md`

- Outils & Exemples:
  - Exemples HL7 v2: `/examples/hl7v2`
  - Exemples MFN: `/examples/mfn`
  - Bundles FHIR: `/examples/fhir-bundles`
  - Endpoints de test internes: `/tools/endpoints-test`
  - Guide MLLP: `/tools/mllp`

- Scénarios (section dédiée):
  - Scénarios d'interopérabilité: `/scenarios`
  - Templates de scénarios: `/scenarios/templates`
  - Dashboard des exécutions: `/scenarios/runs`
  - Configuration UF / Médecins par EJ: `/config/scenario-ej`
  - Documentation scénarios: `/docs/SCENARIOS_DOCUMENTATION.md`

- Administration:
  - Interface d'administration SQL: `/sqladmin` (ou `/admin` selon contexte)
  - Vocabularies (listes de valeurs): `/vocabularies`
  - Dashboard principal: `/dashboard`
  - Cache Redis: `/cache-dashboard`
  - Métriques opérations: `/metrics/dashboard`

- Footer quicklinks (select):
  - Documentation: `/documentation`
  - API: `/api/docs`
  - Signaler un problème (mailto): `mailto:nicolas.moreau@cpage.fr`


## Menu mobile

Le menu mobile contient des raccourcis similaires :
- Tableau de bord `/`
- Dossiers & Cotation `/dossiers`
- Messages `/messages` (si `ght_context`)
- Patients, Dossiers, Venues, Mouvements, Formulaires
- Structure (tableau / admin / recherche / entités spécifiques)
- Interopérabilité (Messages, Injecter HL7/FHIR `/messages/send`, Endpoints `/endpoints`, Scénarios `/scenarios`)
- Ressources (Guide `/guide`, API docs `/api-docs`, documentation technique)


## Références aux templates et routers
- Template principal contenant la navigation: `app/templates/base.html`
- Composants et macros: `app/templates/components.html` et `app/templates/components/` (macros)
- Routage d'exemples: voir `app/routers/` pour les routers exposant les pages listées ci-dessus (ex. `app/routers/scenarios.py`, `app/routers/messages.py`, `app/routers/endpoints.py`)


## Notes
- Certaines routes peuvent exister en plusieurs copies (déploiement vs. app) dans `deployment/*/app/routers` et `deployment/*/app/templates`.
- Quelques entrées nécessitent un contexte (GHT/EJ/Patient) et peuvent être masquées ou annotées d'un avertissement dans l'interface.


---
_Généré automatiquement à partir de `app/templates/base.html` le 24 décembre 2025._
