# Audit des améliorations restantes — backend et frontend

Date : 14 septembre 2026  
Périmètre : application MedData Bridge, hors sécurité  
Nature : audit du code, de la configuration, de la documentation et des tests présents dans le dépôt

## Verdict

Le socle métier principal est déjà avancé : IHE PAM, HPRIM XML, MFN, FHIR/FR
Core, outbox et scénarios multi-destinations disposent de preuves ciblées. Il
n'est pas nécessaire de réécrire le produit ni de changer de framework.

Les travaux restants les plus importants concernent désormais la fiabilité de
démarrage et de déploiement, la remise en état de la suite de tests générale,
la réduction des très gros modules, la maîtrise des erreurs et de la
performance, puis la consolidation du frontend. Les améliorations purement
cosmétiques passent après ces chantiers.

Les trois priorités immédiates sont :

1. rendre le démarrage, l'installation et le conteneur reproductibles ;
2. rendre la suite de tests générale hermétique et exploitable en CI ;
3. supprimer les chemins frontend incomplets ou obsolètes et modulariser les
   principaux écrans.

## Hors périmètre

Cet audit ne propose volontairement aucune action sur l'authentification, les
autorisations, les secrets, CORS, le rate limiting, les en-têtes HTTP, la CSP,
le chiffrement ou l'analyse de vulnérabilités.

Le problème de démarrage observé autour de `.env` est retenu uniquement comme
un défaut d'ordre de chargement de la configuration, pas comme un chantier de
sécurité.

## État vérifié

### Points solides à préserver

- Les 27 tests ciblés FHIR FR Core, MFN, HPRIM XML et outbox exécutés pendant
  cet audit passent.
- Le workflow actif
  [`.github/workflows/interop-conformance.yml`](../../.github/workflows/interop-conformance.yml)
  couvre les contrats d'interopérabilité prioritaires, les migrations ciblées
  et le moteur de scénarios.
- Les rapports du 13 septembre attestent 137 scénarios de catalogue réussis,
  125 messages de roundtrip CPage et une préparation de 360 livraisons.
- L'interface possède déjà un design system, un mode sombre, des composants
  Jinja réutilisables et des tests Playwright ciblés.
- Le projet contient des métriques, une outbox persistante, des contrôles de
  santé et des migrations Alembic.

### Indicateurs de dette constatés

| Indicateur | Valeur constatée | Lecture |
|---|---:|---|
| Code Python applicatif | 312 fichiers, environ 86 600 lignes | surface importante pour un monolithe |
| Plus gros routeur | `app/routers/structure.py`, 2 494 lignes | responsabilités trop concentrées |
| Plus gros service | `app/services/emit_on_create.py`, 2 340 lignes | émission, retry et persistance trop couplés |
| Templates | 162 fichiers, environ 37 100 lignes | frontend étendu et hétérogène |
| Templates avec script embarqué | 65 | code peu réutilisable et difficile à tester |
| Gestionnaires HTML inline | environ 170 | comportement fortement couplé au markup |
| Appels `fetch` | 1, dans `static/js/http.js` | transport réseau centralisé |
| Anomalies Ruff sur `app/` | 137 | dette de qualité non bloquante en CI |
| `except Exception` | environ 547 | erreurs trop largement interceptées |
| Exceptions suivies de `pass` | environ 218 | diagnostics ou échecs potentiellement masqués |
| Appels `print` dans `app/` | environ 82 | journalisation non homogène |
| Routes enregistrées | 590, dont 588 opérations OpenAPI | surface à rationaliser et documenter |
| Suite large interrompue à environ 13 % | 129 réussis, 4 échecs, 6 ignorés, 11 xfail en 7 min 14 s | collecte et isolation à reprendre |

Les nombres ci-dessus sont des indicateurs de priorisation, pas des objectifs à
réduire mécaniquement à zéro. Certains imports signalés par Ruff servent par
exemple à enregistrer les modèles SQLModel.

## Avancement de mise en œuvre — 14 septembre 2026

Les premières tranches des lots BE-05, BE-06 et BE-07 ont été livrées après
l'audit :

- **BE-04 :** les échecs FHIR de l'émetteur historique ne déclenchent plus
  trois tentatives synchrones espacées de 60 secondes. Après une unique
  tentative, le payload et sa corrélation sont confiés à l'outbox durable,
  dont le worker applique le backoff et les reprises. Le réglage historique
  `base_url` est de nouveau reconnu comme cible FHIR. Une réémission
  idempotente conserve maintenant strictement le même Bundle entre le journal
  et l'outbox, y compris lorsque l'horodatage de génération varierait. Les
  émissions PAM sur MLLP suivent désormais la même règle : une tentative
  immédiate, puis mise en outbox durable avec le backoff du worker, sans attente
  synchrone entre plusieurs essais. La normalisation générale des exceptions
  demeure à faire.
- **BE-03 :** `emit_on_create.py` délègue désormais la génération FHIR à
  `fhir_emission.py` (Bundle, cibles et reprise durable) et la construction
  XML des actes de cotation à `hprim_emission.py` (abonnement, patient,
  professionnel et actes CCAM/NGAP/UCD/LPP). L'émetteur conserve
  l'orchestration, l'outbox et les points de monkeypatch de transport ; la
  branche PAM reste à extraire.
- **BE-05 :** la timeline patient/dossier ne fait plus une requête par dossier
  puis par venue. Les venues et mouvements sont chargés en masse ; un test
  vérifie le contenu produit et un budget de quatre requêtes SQL au maximum.
  L'export FHIR de structure précharge maintenant tous les niveaux (EG, pôle,
  service, UF, UAC, UH, chambre et lit), ainsi que les activités d'UF. Un test
  d'arborescence large borne le nombre de `SELECT` à dix. La pagination et les
  objectifs p95 restent à traiter. L'API d'arbre structure reçoit maintenant
  explicitement la requête FastAPI pour lire le contexte EJ, sans inspection
  coûteuse et implicite de la pile d'appel. Les listes structure (EG, pôle,
  service, UF, UH, chambre et lit) appliquent désormais le même contrat
  `skip`/`limit` borné et un tri stable, sans casser leur réponse historique.
  L'arbre ne parcourt plus les six tables structure entières avant son rendu :
  les mises à jour de statut programmé portent uniquement sur son graphe déjà
  préchargé. Les historiques HPRIM CCAM et NGAP calculent aussi leur total par
  `COUNT(*)`, sans matérialiser tous les actes d'un patient. Les recherches
  FHIR `Location` par parent ou identifiant bornent et trient désormais aussi
  leurs lectures avant de convertir les ressources.
- **BE-06 :** la migration `c7e1f2a4b603` tolère désormais l'absence des tables
  de cotations optionnelles sur les anciennes installations. Le test de base
  fraîche suit dynamiquement la tête Alembic et ces deux tests sont exécutés
  dans le workflow. La séparation complète de `create_all`, des seeds et des
  migrations reste à faire.
- **BE-07 :** les familles Ruff bloquantes `F821`, `F823`, `F601` et `F811`
  sont à zéro dans `app/` et sont imposées par la CI. Le nettoyage progressif
  des 137 alertes restantes (principalement imports et imports tardifs)
  variables inutilisées) demeure un chantier distinct ; aucun correctif global
  automatique n'a été appliqué. La CI impose aussi une baseline globale à 137
  anomalies : toute nouvelle alerte échoue désormais avant fusion. Les deux
  derniers lots ont supprimé 27 variables locales inutilisées et les 26 noms
  locaux ambigus, sans supprimer les validations hiérarchiques qui les
  produisaient. Les imports inutilisés clairement sans effet de bord ont aussi
  été retirés des schémas et services isolés, puis des adaptateurs FHIR/HPRIM
  et de polling. Les constructions de mappings restants sont maintenant
  justifiées par leur cascade ORM et couvertes par un test SQLite dédié.
  Un lot supplémentaire a retiré douze imports sans effet de bord des modèles
  et services isolés, avec les régressions PAM, PIX/PDQ, MFN et scénarios.
  Les réexports inutilisés de 24 routeurs ont également été supprimés du paquet
  `app.routers`, dont les consommateurs importent déjà les sous-modules
  explicitement.
  Treize imports inutilisés ont ensuite été retirés des services de scénarios,
  planification, émission de structure et vocabulaires, couverts par les tests
  disponibles du scheduler et du remplacement d'identifiants.
  Les imports redondants de la composition FastAPI ont été supprimés, sans
  modifier les imports locaux nécessaires aux routeurs optionnels.
  Un sous-lot de validateurs, transitions et tâches a retiré neuf imports
  inutilisés, avec les régressions dossier et HL7 exécutées.
  Le service d’arbre structure ne conserve maintenant que ses deux dépendances
  de types effectives, avec ses régressions de routeur exécutées.
  Les branches d’émission structure et PAM ainsi que le seed de structure ont
  aussi été allégés de six imports sans effet, avec les tests MFN et PAM.
  Le pipeline de réception HL7 ne conserve plus onze parseurs, transitions ou
  helpers non appelés, validé par ses 49 tests unitaires MLLP.
  Les modules de vocabulaires et la composition FastAPI ont enfin perdu sept
  imports inutilisés ou tardifs, avec les tests de cascade de mapping.
- **BE-08 :** les gestionnaires d'erreurs communs sont maintenant enregistrés
  dans l'application. Les erreurs HTTP, de validation et métier retournent la
  même enveloppe (`code`, `message`, `details`, `correlation_id`) et propagent
  `X-Correlation-ID`; les champs historiques `type` et `detail` sont conservés
  durant la transition. Les exceptions non gérées suivent le même contrat. La
  pagination et les schémas de sortie dédiés restent à étendre route par route.
- **DOC-01 :** `scripts/generate_openapi_inventory.py` produit désormais
  l'inventaire Markdown depuis le contrat OpenAPI réellement servi. Les
  documents ne doivent plus recopier un nombre de routes à la main.
- **BE-01 :** la configuration est chargée par `config.settings` pour tous les
  points d'entrée, avec conversion typée et diagnostic unique des valeurs
  invalides. Un import applicatif en mode test est vérifié sans création de
  base. `create_app(settings)` accepte maintenant une configuration validée et
  son cycle de vie en dépend, ce qui isole les applications de test sans
  mutation de l'environnement global.
- **BE-02 :** Docker n'utilise plus Poetry ; il installe le même manifeste
  `requirements.txt`, lance Alembic avant Uvicorn et le compose utilise le
  dialecte `psycopg`. Le compose conserve ses données applicatives dans un
  volume nommé, ne publie pas PostgreSQL et permet de choisir
  `MEDBRIDGE_PORT` sans modifier sa configuration. Son smoke test complet a
  construit l'image, migré PostgreSQL jusqu'à `c7e1f2a4b603`, confirmé le pool
  PostgreSQL compatible et l'accès Redis par le réseau Compose. Uvicorn démarre
  désormais avec un seul worker : les écouteurs MLLP et le planificateur ne
  sont ainsi pas dupliqués. Le workflow de conformité exécute désormais ce
  smoke test Compose (build, migrations, healthcheck HTTP et collecte des logs)
  sur chaque push et pull request.
- **QA-01 :** les démonstrations qui requièrent un serveur HTTP externe sont
  exclues de la campagne pytest standard, les tests de seed écrivent dans un
  répertoire temporaire et les tests de logging fixent explicitement leur
  niveau de capture. Les tests UI, E2E et performance sont maintenant marqués
  automatiquement selon leur dossier et sortent du job rapide; ils restent
  exécutables par marqueur. Les régressions mémorisées du lot historique sont
  maintenant vertes (32 réussites, 7 `xfail` documentés et 2 `xpass`) : le
  validateur PAM accepte le profil ZBE national, les tests suivent les
  contrats d'erreur rétrocompatibles, les doubles DB ciblent le bon module et
  le catalogue sépare correctement les préambules HL7 des XML HPRIM. La suite
  historique complète doit encore être stabilisée par familles de tests. Au
  23 septembre 2026, la campagne `tests/unit` en environnement isolé passe
  entièrement avec des marqueurs Pytest stricts : les scripts nécessitant une
  archive PAM ou une base locale sont classés `external`, et les deux tests
  asynchrones du routeur dossiers sont désormais effectivement exécutés. La
  campagne `tests/integration` isolée est également verte : les scripts de
  diagnostic qui nécessitent un listener MLLP, des chemins historiques ou une
  base locale sont explicitement classés `external`, et le workflow dossiers
  utilise l'API SQLModel actuelle. Une nouvelle exécution complète des deux
  campagnes, après les lots de qualité livrés le 23 septembre 2026, confirme
  cette isolation sans échec.
- **FE-01 :** la logique de recherche de cotation moderne est extraite dans
  `static/js/cotation-selector.js`; le template ne conserve que son markup et
  l'inclusion du module. Une première tranche de `structure_new.html` (filtre,
  navigation et traitement en lot) vit désormais dans
  `static/js/structure-new-actions.js`, avec un test d'intégration d'asset.
  La vue structure historique délègue aussi son arbre, ses filtres de lits et
  ses actions d'édition à `static/js/structure-legacy-workspace.js` : le
  template ne conserve plus de script métier ni de gestionnaire inline. Le
  module expose des états de chargement et d'erreur, et un test vérifie ce
  découplage. L'assistant de structure ignore désormais les réponses tardives
  lors d'un changement rapide de modèle et verrouille sa navigation pendant
  le chargement du modèle sélectionné. Une création vide ou un pôle sans nom
  sont refusés par le wizard puis par l'API, afin qu'une confirmation de succès
  corresponde toujours à une structure effectivement créée. Ce contrôle couvre
  également les services, UF et unités d'hébergement fournis par un modèle
  édité. Le wizard interrompt désormais la navigation dès l'étape contenant le
  nom manquant, au lieu de ne le signaler qu'à la génération. La liste
  historique de cotations délègue désormais ses filtres, sa sélection et ses
  actions à `static/js/cotations-list-workspace.js`; son script métier embarqué
  et ses gestionnaires inline ont été retirés. Dans la saisie rapide, la tranche
  historique (filtres, sélection, traitement en lot et édition) vit également
  dans `static/js/cotations-history-workspace.js`, avec une délégation
  d'événements au lieu de gestionnaires inline. La recherche avancée de
  structure délègue maintenant sa recherche FHIR, ses filtres, sa pagination,
  son historique et son export à `static/js/structure-search-workspace.js` ;
  le template ne conserve plus de script métier inline. Le tableau Analytics
  délègue à son tour ses KPI, graphiques, alertes et exports à
  `static/js/analytics-dashboard-workspace.js`, avec l'EG de contexte fournie
  par un attribut `data-*`. L'import de structure est également isolé dans
  `static/js/structure-import-workspace.js` et ses boutons de confirmation
  passent par des listeners JavaScript au lieu de gestionnaires inline. La
  configuration des alertes délègue aussi ses filtres, modales et actions de
  règles à `static/js/alert-config-workspace.js`, y compris les actions sur
  lignes générées dynamiquement. Le plan de lits isole désormais sa recherche
  patient, son affectation, ses transferts et son glisser-déposer dans
  `static/js/plan-lits-workspace.js` ; ses boutons utilisent des attributs de
  données et la délégation d'événements. Le tableau de cache isole ses
  métriques et son graphique dans `static/js/cache-dashboard-workspace.js` ;
  le bouton d'actualisation est désormais réellement raccordé à son identifiant.
  L'assistant de structure délègue maintenant toutes ses étapes, sa validation,
  ses modèles et sa génération à `static/js/structure-wizard-workspace.js`.
  Les actions générées de ses pôles, services, UF et UH y sont maintenant
  déléguées à deux listeners de workspace, sans attributs inline.
  Le tableau principal de structure délègue également son arbre, ses vues,
  recherches et détails à `static/js/structure-dashboard-workspace.js` ; son
  asset d'actions chargé ensuite est différé afin de préserver cet ordre. Les
  nœuds, actions, chemins et enfants générés par le tableau utilisent aussi
  une délégation d'événements au lieu de gestionnaires inline. Le
  shell applicatif délègue enfin navigation, raccourcis, thèmes, toasts et
  loaders à `static/js/base-behaviors.js`, chargé avant les workspaces de page.
  La fermeture des toasts générés est elle aussi déléguée à un unique listener,
  sans gestionnaire HTML inline.
  L'exécution groupée de scénarios isole enfin ses compteurs, sa sélection et
  son contrôle tout/aucun dans `static/js/scenarios-bulk-execute-workspace.js`.
  L'extraction des autres grands
  écrans cotation classique reste à poursuivre.
- **FE-02 :** l'asset non référencé `cotationForm.js`, qui simulait une
  sauvegarde, ainsi que deux sauvegardes Python exécutables obsolètes ont été
  supprimés. La commande `npm run inventory-assets` contrôle désormais les
  références aux scripts statiques dans les templates. Elle a permis de retirer
  deux doublons historiques du workflow mouvements ; l'inventaire actuel ne
  signale plus aucun script JavaScript orphelin. Les boutons de validation,
  facturation et suppression de cette liste ne reposent plus sur un délai local
  : ils confirment l'action via le dialogue applicatif, appellent l'API groupée
  puis rechargent les données persistées. L'export télécharge effectivement un
  CSV des lignes filtrées.
- **FE-03 :** `static/js/http.js` centralise timeout, annulation, parsing et
  erreurs HTTP. Les parcours cotation, listes, scénarios, messages et tableau
  de bord l'utilisent désormais; la recherche de structure passe également par
  ce client, tout comme les listes dynamiques du formulaire de mouvement, et
  l'édition interactive de structure (modification, déplacement et duplication).
  La vue structure principale utilise désormais ce même client pour son arbre,
  ses détails et ses actions en lot.
  L'assistant de création de structure l'utilise aussi pour charger et
  appliquer ses modèles, ce qui aligne ses délais et erreurs sur le reste de
  l'interface.
  Les tableaux de bord analytics et métriques passent également par ce client
  pour leurs lectures de données.
  Les aides à l'admission, à la génération d'identité patient et à l'édition
  des règles de validation partagent désormais le même comportement réseau.
  La confirmation d'import de structure conserve son envoi multipart mais
  bénéficie elle aussi du timeout et des erreurs centralisées.
  La configuration des alertes migre enfin toutes ses lectures et mutations
  vers ce même point d'accès réseau.
  Le tableau de bord GHT centralise à son tour ses lectures de supervision.
  Le plan de lits partage désormais cette couche pour sa recherche patient et
  ses mouvements par glisser-déposer.
  Le changement de type de dossier, y compris son parcours de forçage, utilise
  à présent la même gestion réseau.
  Le lint interdit désormais tout nouvel `await fetch(...)` dans les scripts
  ou les 162 templates, hors implémentation interne de ce client partagé.
  La cartographie de localisation utilise elle aussi le client partagé pour
  ses sélecteurs hiérarchiques.
  Les compteurs de cotation dossier, le générateur de scénarios, la suppression
  de configuration EJ et de contacts sont également consolidés sur ce client.
  L'import de scénario et le basculement de conformité suivent le même contrat.
  La saisie rapide de cotations (recherches, modèles, créations, actions de
  masse et édition) est maintenant également migrée vers le client HTTP.
  Le gestionnaire générique de formulaires l'utilise enfin pour les soumissions
  AJAX et les téléchargements binaires, avec restitution des erreurs de champ.
  Le template structure historique ne conserve plus non plus de client réseau
  parallèle.
  La suppression AJAX d'un patient l'utilise aussi et rend enfin son erreur
  visible, de même que la matérialisation et l'exécution de modèles de
  scénarios et l'autocomplétion de localisation du workflow de mouvements.
  Le tableau de cache l'utilise également. Des tests frontend empêchent le
  retour à `fetch` direct : la seule occurrence restante est le transport
  interne de `static/js/http.js`. La liste historique de cotations utilise à
  son tour ce client pour ses mutations groupées.
- **FE-06 :** `npm run lint`, `npm test` et `npm run check-frontend` sont
  disponibles et exécutés dans un job CI frontend. Ils vérifient la syntaxe,
  le client HTTP et la génération CSS; l'extension graduelle des tests aux
  modules extraits reste à faire.
- **FE-04/FE-05 :** le gestionnaire partagé de formulaires associe désormais
  les erreurs au champ, annonce leur apparition et place le focus sur le
  premier champ invalide. La couverture axe/RGAA complète et les revues
  clavier des écrans prioritaires restent à planifier. Le wizard structure
  annonce à présent son étape active via une région live et marque celle-ci
  avec `aria-current`, afin de rendre sa progression intelligible au lecteur
  d'écran.
- **FE-07 :** les styles de la liste de cotations ont été transférés du
  template au design system sous des classes préfixées `cotations-list-*`.
  L'écran ne déclare donc plus de styles globaux locaux, et les styles de cet
  espace de travail ne peuvent pas modifier involontairement une autre vue.
  La saisie rapide de cotations suit désormais la même règle : ses styles sont
  centralisés et scopés sous `.rapid-shell`, et ses animations locales non
  utilisées ont été supprimées.

## Backlog priorisé

### P0 — Fiabilité immédiate

#### BE-01 — Corriger l'initialisation de la configuration

**Constat.** La commande documentée `uvicorn app.app:app` échoue dans l'état
local si `.env` n'a pas été préalablement exporté dans le shell. Dans
[`app/app.py`](../../app/app.py), un routeur est importé avant l'appel à
`load_dotenv()`. Des modules dépendants peuvent donc instancier
[`config/settings.py`](../../config/settings.py) avant le chargement du fichier
d'environnement. Les réglages sont en outre évalués comme attributs de classe
au moment de l'import.

**Amélioration.** Charger la configuration avant tout import applicatif, puis
adopter une vraie fabrique `create_app(settings)` sans effets de bord à
l'import. Centraliser toutes les variables dans un objet de configuration
validé ; le code contient encore davantage d'accès directs à `os.getenv` que
d'usages de `settings`.

**Critères d'acceptation.**

- `uvicorn app.app:app --port 8000` fonctionne après simple copie de
  `.env.example` vers `.env`, sans `source .env` ;
- importer `app.app` ne démarre ni Redis, ni MLLP, ni scheduler et ne modifie
  aucune base ;
- un test couvre le démarrage en développement, en test et en configuration de
  déploiement ;
- les variables inconnues ou mal typées produisent un diagnostic unique et
  lisible.

**Effort estimé : M.**

#### BE-02 — Rendre l'installation et le conteneur reproductibles

**Constat.** `requirements.txt` est la source réellement utilisée en local et
en CI, alors que [`docker/Dockerfile`](../../docker/Dockerfile) exécute Poetry.
Le fichier [`pyproject.toml`](../../pyproject.toml) mélange la table PEP 621
`[project]` avec une table `[project.dependencies]` au format Poetry ; il ne
décrit donc pas correctement les dépendances installables. Le compose annonce
PostgreSQL, mais le driver PostgreSQL n'est pas dans les dépendances racine et
aucune étape de migration n'est lancée avant Uvicorn.

**Amélioration.** Choisir une seule source de dépendances et un seul outil de
build. Corriger les métadonnées du paquet, verrouiller les versions, installer
le driver PostgreSQL dans le profil concerné et faire exécuter `alembic upgrade
head` par une étape dédiée avant le démarrage de l'application.

**Critères d'acceptation.**

- création d'un environnement neuf et installation du projet en une commande ;
- construction du Dockerfile depuis un clone propre ;
- démarrage du compose avec PostgreSQL, migration à la tête et healthcheck
  vert ;
- smoke test de ces opérations dans la CI.

**Effort estimé : M.**

#### QA-01 — Rendre la suite générale hermétique

**Constat.** La conformité ciblée est verte, mais le rapport
[`REVUE_CODE_ET_REGRESSION_20260913.md`](REVUE_CODE_ET_REGRESSION_20260913.md)
recensait encore 88 échecs dans la suite historique. Les causes documentées
sont des bases partagées ou incomplètes, des services externes non marqués et
des assertions anciennes. Le scénario E2E Phase 6 est également décrit comme
instable dans [`TESTS_STATUS.md`](../TESTS_STATUS.md).

La passe lancée pendant cet audit a été interrompue après 7 min 14 s, à environ
13 % de la collecte : 129 tests avaient réussi, mais 4 avaient déjà échoué, 6
étaient ignorés et 11 étaient en `xfail`. Un test dit d'intégration a attendu
300 secondes sur un serveur HTTP réel. Un autre test a modifié le timestamp du
fichier suivi `P3_IMPORT_CORRECTIONS_REPORT.md` ; cette modification parasite a
été annulée après la campagne. Deux tests Alembic étaient également en échec et
un test de journalisation ne recevait aucun record.

**Amélioration.** Séparer explicitement les tests `unit`, `integration`,
`browser`, `external`, `performance` et `manual`. Chaque test automatique doit
recevoir une base isolée et un état indépendant de l'ordre d'exécution. Les
tests externes doivent utiliser des doubles locaux ou sortir de la CI standard.

**Critères d'acceptation.**

- deux exécutions successives et une exécution aléatoire donnent le même
  résultat ;
- la suite unitaires + intégration locale est entièrement verte ;
- aucun port réel ni base du dépôt n'est utilisé par cette suite ;
- la CI active au moins un job rapide obligatoire et un job d'intégration
  obligatoire, sans `|| true` ;
- les tests Phase 6 ne sont plus marqués instables.

**Effort estimé : L.**

### P1 — Backend

#### BE-03 — Découper les modules géants par cas d'usage

**Constat.** Plusieurs fichiers cumulent orchestration, accès aux données,
validation, transformation, transport et rendu :

- `app/routers/structure.py` : 2 494 lignes ;
- `app/routers/mouvements.py` : 2 227 lignes ;
- `app/services/emit_on_create.py` : 2 340 lignes ;
- `app/services/pam.py` : 2 288 lignes ;
- `app/services/structure_seed.py` : 2 190 lignes ;
- `app/services/pam_validation.py` : 1 567 lignes.

**Amélioration.** Découper par cas d'usage et protocole, garder les routeurs
minces, déplacer les transactions dans une couche applicative explicite et
injecter les transports. Commencer par `emit_on_create`, `structure` et
`mouvements`, qui combinent taille élevée et chemin critique.

**Critères d'acceptation.**

- un endpoint ne contient que parsing d'entrée, appel du cas d'usage et
  construction de réponse ;
- les fonctions d'émission ne réalisent plus elles-mêmes transport, boucle de
  retry, écriture du journal et choix de protocole ;
- chaque module extrait possède des tests unitaires sans démarrer FastAPI.

**Effort estimé : L, à livrer par tranches.**

#### BE-04 — Fiabiliser la gestion des erreurs et des traitements différés

**Constat.** Le code contient environ 547 captures larges de `Exception`, 218
blocs qui ignorent une exception et 82 `print`. Dans
[`app/services/emit_on_create.py`](../../app/services/emit_on_create.py), des
retries FHIR attendent encore 60 secondes avec `time.sleep`, alors qu'une
outbox persistante existe déjà.

**Amélioration.** Définir des exceptions métier et infrastructure, n'ignorer
que des erreurs explicitement jugées facultatives, corréler tous les logs et
faire passer retries, backoff et reprise par l'outbox/scheduler. Unifier
`logging_config.py` et `utils/structured_logging.py` au lieu de conserver deux
styles concurrents.

**Critères d'acceptation.**

- aucune attente réseau longue dans le thread d'une requête ou d'un listener ;
- toute erreur ignorée possède une justification, une métrique et le niveau de
  log adapté ;
- un identifiant de corrélation relie requête, message, livraison et ACK ;
- les erreurs API ont une enveloppe stable : code, message, détails et
  corrélation.

**Effort estimé : M à L.**

#### BE-05 — Corriger les accès aux données coûteux

**Constat.** Plusieurs parcours effectuent des requêtes imbriquées. L'export de
structure FHIR parcourt EJ → EG → pôle → service → UF → UAC/UH → chambre → lit
avec une requête par nœud dans
[`app/services/fhir_export_service.py`](../../app/services/fhir_export_service.py).
La timeline répète le même motif dossier → venue → mouvement dans
[`app/routers/timeline.py`](../../app/routers/timeline.py). Plusieurs listes
chargent tous les résultats pour calculer un total. Enfin, de nombreuses routes
`async def` utilisent directement la session SQLModel synchrone et peuvent
bloquer la boucle événementielle.

**Amélioration.** Précharger les relations ou charger chaque niveau en masse,
utiliser `COUNT()` pour les totaux, standardiser une pagination avec
métadonnées et choisir clairement entre routes synchrones avec SQLModel sync ou
pile SQLAlchemy asynchrone. Pour les exports volumineux, ajouter pagination,
streaming ou jobs asynchrones selon le format.

**Critères d'acceptation.**

- budgets de nombre de requêtes sur timeline et export FHIR ;
- temps et mémoire mesurés avec des volumes réalistes, sur SQLite et
  PostgreSQL ;
- aucune liste publique non bornée ;
- objectifs p50/p95 documentés pour les écrans et API principaux.

**Effort estimé : L.**

#### BE-06 — Faire d'Alembic la source unique du schéma

**Constat.** [`app/db.py`](../../app/db.py) combine `create_all`, création
d'index SQL en dur, initialisation FTS SQLite et seed de templates. Cela peut
faire diverger une base créée au démarrage d'une base créée par Alembic.
Pendant cet audit, le test d'installation fraîche attendait encore la révision
`b6d4e2f7a901` alors que la tête est devenue `c7e1f2a4b603`. Le test de mise à
niveau incrémentale échouait aussi parce que cette nouvelle migration tentait
de modifier une table `ccamact` absente de sa base minimale.

**Amélioration.** Réserver `create_all` aux tests unitaires, déplacer les index
et évolutions persistantes dans Alembic, et séparer clairement migrations,
seeds de démonstration et initialisation des données de référence.

**Critères d'acceptation.**

- une base vide est créée uniquement par `alembic upgrade head` hors tests ;
- le schéma obtenu est identique sur installation fraîche et mise à niveau ;
- les seeds sont idempotents, versionnés et lançables séparément ;
- un test de migration PostgreSQL complète le test SQLite.

**Effort estimé : M.**

#### BE-07 — Mettre la qualité statique sous contrôle progressif

**Constat.** `ruff check app` remonte 692 anomalies : 322 imports inutilisés,
133 imports tardifs, 47 variables inutilisées, 20 noms non définis, 7 clés de
dictionnaire dupliquées et plusieurs redéfinitions. Une partie est historique
ou liée aux relations SQLModel, mais les noms non définis et les clés
dupliquées peuvent masquer de vrais défauts.

**Amélioration.** Traiter d'abord `F821`, `F823`, `F601` et `F811`, puis les
erreurs de structure. Configurer Ruff dans `pyproject.toml`, figer une baseline
temporaire si nécessaire et interdire toute nouvelle anomalie. Ajouter ensuite
un typage progressif sur les schémas, services et adaptateurs de protocole.

**Critères d'acceptation.**

- zéro nom non défini, variable locale non définie et clé littérale dupliquée ;
- le lint des nouveaux fichiers est obligatoire en CI ;
- la dette restante diminue à chaque lot sans correctif automatique aveugle ;
- les modules critiques passent un contrôle de types.

**Effort estimé : M, puis continu.**

#### BE-08 — Stabiliser les contrats API

**Constat.** L'application enregistre 590 routes et expose 489 chemins OpenAPI.
Les styles de réponse, la pagination et la gestion des erreurs varient selon
les anciens et nouveaux modules. Certaines routes renvoient directement les
modèles de persistance, d'autres des schémas dédiés.

**Amélioration.** Inventorier les routes réellement supportées, déprécier les
doublons fonctionnels, séparer clairement UI et API, adopter des schémas
d'entrée/sortie dédiés, une pagination commune et une politique de version de
contrat. Générer des tests de contrat depuis OpenAPI pour les API partenaires.

**Critères d'acceptation.**

- catalogue des routes avec propriétaire, statut et consommateur ;
- format cohérent des listes et erreurs ;
- aucun modèle ORM exposé par défaut comme contrat externe ;
- changements incompatibles versionnés et couverts par tests.

**Effort estimé : L.**

#### BE-09 — Enrichir les assertions fonctionnelles du catalogue

**Constat.** Le moteur de scénarios est opérationnel, mais le plan
[`PLAN_QUALIFICATION_SCENARIOS_PAM_HPRIM_20260912.md`](PLAN_QUALIFICATION_SCENARIOS_PAM_HPRIM_20260912.md)
précise que les assertions historiques détaillées et les contrôles de base
spécifiques au partenaire restent à enrichir scénario par scénario.

**Amélioration.** Prioriser les scénarios réellement utilisés, formaliser leur
intention métier, leur résultat attendu, les assertions ACK et les contrôles de
projection. Ne pas tenter de convertir automatiquement une intention qui
n'existe que dans l'ancien code ou dans la connaissance d'un partenaire.

**Critères d'acceptation.**

- chaque scénario publié prioritaire possède préconditions, résultat attendu
  et assertions exécutables ;
- le rapport de campagne distingue transport réussi et résultat métier réussi ;
- les contrôles spécifiques sont identifiés par cible et versionnés.

**Effort estimé : continu, dépendant des contrats partenaires.**

### P1 — Frontend

#### FE-01 — Extraire le JavaScript des templates monolithiques

**Constat.** 65 templates contiennent des scripts embarqués. Les cas les plus
forts sont `structure_new.html` (environ 989 lignes de script),
`cotations/saisie_rapide.html` (environ 762), `structure_wizard.html` (environ
720), `structure_search.html` (environ 458) et `base.html` (environ 406). Cela
rend le code difficile à tester, mettre en cache et réutiliser.

**Amélioration.** Extraire des modules JavaScript par espace de travail,
initialisés par attributs `data-*`. Garder dans Jinja uniquement les données de
bootstrap sérialisées. Remplacer progressivement les gestionnaires `onclick`
et `onchange` par délégation d'événements.

**Critères d'acceptation.**

- aucun nouveau script métier de plus de quelques lignes dans un template ;
- les cinq templates prioritaires délèguent leur comportement à des modules ;
- les fonctions sont testables sans rendu complet de la page ;
- les composants partagés n'installent leurs listeners qu'une fois.

**Effort estimé : L.**

#### FE-02 — Supprimer les chemins frontend morts ou simulés

**Constat.** [`app/static/js/cotationForm.js`](../../app/static/js/cotationForm.js)
n'est référencé par aucun template. Il contient en plus deux définitions de
`saveActe`, une génération HPRIM marquée « à implémenter » et une sauvegarde qui
affiche un succès de simulation sans appel backend. Le dépôt contient aussi
des sauvegardes telles que `app/app.py.backup` et
`app/routers/dossiers.py.bak`.

**Amélioration.** Vérifier les écrans consommateurs, supprimer les assets et
backups réellement morts, ou raccorder les fonctions à l'unique parcours de
cotation supporté. Une action visible ne doit jamais annoncer une sauvegarde
si seule une simulation locale a eu lieu.

**Critères d'acceptation.**

- inventaire automatisé des assets référencés ;
- aucun doublon de fonction global et aucun succès simulé sur un parcours
  utilisateur actif ;
- suppression ou archivage hors code exécutable des fichiers de sauvegarde ;
- test E2E création → persistance → relecture d'une cotation de chaque type.

**Effort estimé : S à M.**

#### FE-03 — Uniformiser les états réseau et les erreurs

**Constat.** Les appels `fetch` sont répartis entre templates et fichiers JS.
La vérification de `response.ok`, l'affichage d'erreur, l'annulation d'une
recherche précédente, les loaders et les états vides ne sont pas homogènes.

**Amélioration.** Fournir un petit client HTTP commun avec parsing d'erreur,
timeout/annulation, corrélation, gestion du bouton occupé et helpers de toast.
Pour les recherches, utiliser debounce et `AbortController` afin d'éviter que
la réponse la plus ancienne remplace la plus récente.

**Critères d'acceptation.**

- chaque action distante expose chargement, succès, erreur et possibilité de
  réessai ;
- double clic et réponses hors ordre ne créent pas de doublon ni d'affichage
  incohérent ;
- les erreurs de champ sont reliées au champ et un résumé est disponible en
  tête de formulaire.

**Effort estimé : M.**

#### FE-04 — Terminer les améliorations UX déjà identifiées

**Constat.** L'audit UI existant
[`UI_UX_AUDIT_2025-12-26.md`](../UI_UX_AUDIT_2025-12-26.md) laisse ouverts :
microcopy et tooltips, validation inline, bouton de sauvegarde fixe sur mobile
et prévisualisation/navigation vers les erreurs.

**Amélioration.** Traiter ces points comme un lot cohérent de formulaires,
d'abord sur patients, dossiers/venues, mouvements, cotations, endpoints et
scénarios. Conserver les valeurs saisies après erreur et prévenir clairement
avant de quitter un formulaire modifié.

**Critères d'acceptation.**

- même verbe pour une même action dans toute l'application ;
- erreur affichée près du champ, annoncée aux technologies d'assistance et
  accessible depuis un résumé ;
- action principale toujours accessible sur mobile sans masquer le contenu ;
- état « modifications non enregistrées » visible et testé.

**Effort estimé : M.**

#### FE-05 — Renforcer l'accessibilité par des tests réels

**Constat.** Les tests actuels vérifient surtout la présence de labels, d'ARIA
ou la navigation au clavier sur quelques pages. Aucun outil de détection de
violations tel qu'axe n'est configuré. Dans les templates, les attributs de
retour d'erreur (`aria-invalid`, `aria-describedby`) restent rares par rapport
au nombre de champs.

**Amélioration.** Définir une cible RGAA/WCAG, lancer axe sur les parcours
critiques, compléter par des tests clavier manuels et vérifier contrastes,
focus, modales, tableaux, annonces dynamiques et graphiques.

**Critères d'acceptation.**

- zéro violation critique ou sérieuse sur les parcours prioritaires ;
- parcours complet réalisable au clavier avec focus visible ;
- messages dynamiques annoncés, erreurs correctement associées et graphiques
  dotés d'une alternative textuelle ;
- résultats intégrés au job navigateur de la CI.

**Effort estimé : M.**

#### FE-06 — Ajouter une vraie chaîne de qualité JavaScript

**Constat.** `package.json` ne fournit ni lint ni tests frontend ; `npm test`
est une commande factice qui échoue. Aucun fichier ESLint, Prettier, Vitest ou
Jest n'est présent. Les comportements ne sont donc vérifiés qu'à travers
Python/Playwright, ce qui rend les retours lents et les fonctions isolées
difficiles à tester.

**Amélioration.** Ajouter formatage, lint et tests unitaires légers pour les
helpers, calculs de cotation, filtres, transformations de formulaire et client
HTTP. Garder Playwright pour les parcours utilisateur, pas pour chaque branche
de fonction.

**Critères d'acceptation.**

- `npm run lint`, `npm test` et `npm run build-css-prod` sont reproductibles ;
- les modules extraits par FE-01 ont des tests unitaires ;
- le job frontend est obligatoire en CI ;
- budgets simples sur taille CSS/JS et erreurs console.

**Effort estimé : M.**

#### FE-07 — Consolider le design system et les pages de démonstration

**Constat.** Le frontend charge Tailwind compilé, `forms.css`,
`design-system.css` et `animations.css`, tandis que 19 templates conservent un
bloc `<style>`. `base.html` et `macros/ui.html` sont eux-mêmes très volumineux.
Des pages de styleguide et de démonstration restent enregistrées dans
l'application principale.

**Amélioration.** Définir un catalogue unique de composants et tokens, déplacer
les styles locaux réutilisables, documenter les variantes et décider si les
pages de démonstration appartiennent au produit ou seulement à l'environnement
de développement. Éviter une migration vers une SPA : Jinja + modules JS est
suffisant pour le besoin actuel.

**Critères d'acceptation.**

- composants formulaire, tableau, modal, badge, toast et état vide possèdent
  une seule implémentation recommandée ;
- les nouveaux templates n'ajoutent pas de styles globaux locaux ;
- les pages de démonstration sont exclues de la navigation utilisateur si elles
  ne sont pas fonctionnelles ;
- une revue visuelle couvre clair/sombre et mobile/desktop.

**Effort estimé : M.**

### P2 — Exploitation, documentation et décisions produit

#### OPS-01 — Définir des objectifs de performance et de capacité

Les tests actuels donnent quelques seuils locaux, mais pas une mesure de charge
HTTP réaliste avec base PostgreSQL et transports concurrents. Définir des SLO
par parcours, un jeu de données de référence et une campagne reproductible :
recherche patient, timeline, export FHIR, import structure, campagne de
scénarios et traitement outbox. Publier p50, p95, débit, mémoire et nombre de
requêtes SQL.

**Effort estimé : M.**

#### DOC-01 — Réduire les contradictions documentaires

Le dépôt conserve de nombreux plans et TODO datés dont certains annoncent
encore comme manquantes des fonctions depuis livrées. Garder
[`docs/README.md`](../README.md) comme index faisant foi, déplacer les plans
clos vers les archives et ajouter à chaque document actif un statut, un
propriétaire et une date de dernière vérification. Générer automatiquement
l'inventaire OpenAPI et les commandes de test plutôt que recopier des chiffres.

**Effort estimé : S à M.**

#### PROD-01 — Arbitrer les extensions métier, sans les présumer obligatoires

Les documents historiques évoquent des modes Médical/DIM, des modèles EHPAD et
HAD, des webhooks, des notifications temps réel et une synchronisation SIH.
Ces éléments ne sont pas classés comme défauts dans cet audit : ils nécessitent
un besoin utilisateur, un sponsor et des critères métier. Les développer sans
validation augmenterait la surface déjà très importante du produit.

## Ordre de réalisation recommandé

### Lot 1 — Remettre la livraison sous contrôle

BE-01, BE-02 et QA-01. Le résultat attendu est un clone propre qui s'installe,
migre, démarre et passe une suite locale fiable comme en CI.

### Lot 2 — Stabiliser le backend critique

BE-04, BE-06, BE-07 puis première tranche de BE-03 sur
`emit_on_create`. Traiter en premier les erreurs Ruff susceptibles d'être de
vrais défauts, sans lancer un `--fix` global non relu.

### Lot 3 — Consolider les parcours frontend

FE-02, FE-03, FE-04 et FE-06, puis extraire progressivement les scripts avec
FE-01. Commencer par cotations et structure, qui concentrent le plus de code et
d'interactions.

### Lot 4 — Scalabilité et contrats

BE-05, BE-08, OPS-01, puis enrichissement continu BE-09 avec les partenaires.

### Lot 5 — Finition

FE-05, FE-07 et DOC-01, avec audit visuel et documentaire final.

## Définition globale de « terminé »

Le plan pourra être considéré comme achevé lorsque :

- l'installation locale et Docker partent d'un clone propre ;
- SQLite et PostgreSQL sont migrés et testés par la même chaîne Alembic ;
- la suite automatique non externe est verte, déterministe et obligatoire ;
- les chemins critiques n'ont plus d'erreurs statiques graves ni d'attentes
  bloquantes ;
- timeline et exports respectent des budgets SQL, temps et mémoire mesurés ;
- les grands écrans n'embarquent plus leur logique métier principale ;
- chaque formulaire critique gère chargement, erreurs, mobile et clavier de
  manière cohérente ;
- les scénarios prioritaires valident un résultat métier, pas seulement un
  transport réussi ;
- la documentation active reflète le code et distingue clairement acquis,
  dette technique et idées produit.

## Commandes de preuve utilisées

```bash
TESTING=1 PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_fhir_frcore_2_2_0_conformance.py \
  tests/integration/test_fhir_structure_roundtrip.py \
  tests/integration/test_fhir_interop.py \
  tests/unit/test_outbox_service.py \
  tests/unit/test_mfn_export.py \
  tests/integration/test_mfn_structure_roundtrip.py \
  tests/unit/test_hprim_acquittement_xsd.py \
  tests/integration/test_hprim_xml_roundtrip.py

ruff check app --statistics

TESTING=1 PYTHONPATH=. .venv/bin/pytest -c pytest.ini -q \
  --ignore=tests/e2e --ignore=tests/performance
```

La suite large a été arrêtée après 7 min 14 s : **129 réussis, 4 échecs, 6
ignorés et 11 xfail**, à environ 13 % de la collecte. Les échecs observés
concernent deux migrations Alembic, la capture des logs/métriques et un test qui
contacte un serveur HTTP réel puis atteint le timeout de 300 secondes. Ce
résultat est à rapprocher de la section QA-01 et du rapport de régression daté ;
les tests dépendant de services réels ou d'un navigateur doivent rester dans
des jobs séparés.
