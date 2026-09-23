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
| Anomalies Ruff sur `app/` | 0 (23 septembre 2026) | qualité statique bloquante en CI |
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
  demeure à faire. Chaque tentative sortante FHIR, PAM/MLLP et HPRIM est
  maintenant journalisée avec sa corrélation et mesurée par protocole, résultat
  et type d'erreur (sans labels Prometheus à forte cardinalité). Les erreurs
  explicites de cible FHIR absente, réponse HTTP non réussie, ACK MLLP absent,
  échec de transport, validation PAM et contexte HPRIM manquant sont ainsi
  visibles dans le tableau de bord et les logs, tout en conservant l'outbox pour
  les reprises réseau. Les routes d'import et d'export FHIR ne contiennent plus
  de capture silencieuse autour des métriques : ce chemin facultatif est
  centralisé, explicitement averti s'il échoue et ne peut pas interrompre le
  traitement métier ; les erreurs d'import sont journalisées avec leur pile.
  Le worker d'outbox trace également chaque tentative réelle (transport,
  corrélation, durée, résultat et type d'erreur) après sa persistance, y compris
  lorsque celle-ci est planifiée pour une nouvelle tentative. Les vues de
  journaux ne masquent plus non plus une saisie de filtre invalide : leurs dates
  ISO et identifiants d'endpoint sont validés et retournent une erreur 422
  explicite avant toute recherche. Côté réception PAM, les parseurs de segments
  optionnels gardent leur tolérance mais expliquent leurs échecs au niveau debug;
  une indisponibilité du validateur est désormais loguée avec la corrélation et
  persistée comme avertissement avant la poursuite contrôlée du traitement. La
  compilation HL7 des jeux de scénarios ne tente plus non plus une transformation
  requérant un endpoint encore inconnu : cet appel incomplet était masqué par
  une capture large et ne pouvait produire aucun effet fiable. Les enrichissements
  FHIR facultatifs (contacts patient/venue et activités d'UF) restent tolérants
  aux données historiques incomplètes, mais leur omission est désormais
  explicitement signalée sans empêcher l'export de la ressource principale. Le
  transport FHIR signale enfin les corps HTTP non JSON tout en gardant leur
  code de statut exploitable pour la décision de reprise de l'outbox. Les
  formulaires d'endpoint valident également leurs références GHT, EJ et endpoint
  lié : une valeur incorrecte retourne désormais une erreur 422 explicite au
  lieu d'être ignorée ou de provoquer une erreur interne. Les diagnostics
  optionnels d'exploitation suivent la même règle : une archive de scénario IHE
  illisible et une socket MLLP momentanément indisponible sont signalées, sans
  empêcher l'exploration du catalogue ni le statut des autres serveurs. Les
  anciennes API AJAX du formulaire de mouvement n'interceptent plus toute
  exception : seules les références parentes absentes produisent une réponse
  404 métier, les autres erreurs suivant le gestionnaire commun. Les
  filtres de dates des venues sont également validés : une saisie invalide
  retourne une erreur 422 plutôt que d'élargir silencieusement la liste. Un
  `UPDATE`/`CANCEL` PAM sans ZBE-1 ne peut enfin plus devenir une création en
  cas d'indisponibilité de la vérification d'historique : l'incident est corrélé
  et le chemin strict retourne un rejet explicite. Les identifiants
  administratifs PID-18 et PV1-19 du traitement PAM historique sont désormais
  persistés sans capture silencieuse : les erreurs de base remontent à la
  transaction, tandis qu'un format HL7 invalide est explicitement averti sans
  bloquer l'admission. Les sorties `print` de ce parcours ont été remplacées par
  le logger applicatif.
- **BE-03 :** `emit_on_create.py` délègue désormais la génération FHIR à
  `fhir_emission.py` (Bundle, cibles et reprise durable) et la construction
  XML des actes de cotation à `hprim_emission.py` (abonnement, patient,
  professionnel et actes CCAM/NGAP/UCD/LPP). L'émetteur conserve
  l'orchestration et les points de monkeypatch de transport ; la branche PAM
  délègue sa persistance de payload MLLP pour
  diagnostic et la mise à jour du journal sortant MLLP sont isolées dans
  `pam_emission.py`, en conservant la déduplication par corrélation et la
  reprise d'un échec en attente. Les snapshots détachés, primitives PAM et la
  construction PID-3 ainsi que les champs HL7 XPN/XAD sont isolés et testables
  sans FastAPI. Les règles de mouvement (contexte ORM, choix d'événement et structure
  ADT, transitions A06/A07, PV1 et ZBE) sont désormais séparés de
  l'assembleur. Une campagne consolidée de 36 tests d'émission et Ruff couvre
  cette tranche de découpage. La validation sortante, le transport MLLP
  (résolution d'une coroutine, interprétation de l'ACK et métrique), la
  traçabilité des payloads et l'envoi durable à l'outbox y sont maintenant
  testables isolément. La génération complète des messages PAM vit désormais
  dans `pam_message_generation.py` et reste réexportée par compatibilité. Le
  service `emit_on_create.py` ne conserve plus que le choix du destinataire et
  l'orchestration des protocoles. La sélection des endpoints éligibles
  (global, EJ ou GHT) et son court retry de contention SQLite sont maintenant
  isolés dans `emission_endpoints.py`, sans transport ni attente de livraison dans
  l'orchestrateur. La livraison FHIR (cibles, transport unique, journal de
  corrélation et remise à l'outbox) est également réunie dans
  `fhir_emission.py`; les branches identité et structure ne dupliquent plus
  cette logique et l'ancien exécuteur asynchrone local a disparu. La branche
  HPRIM se limite désormais au routage : `hprim_emission.py` construit le XML,
  crée le journal et remet l'envoi à l'outbox, ce qui rend ces étapes testables
  sans l'orchestrateur multi-protocole. Les transports historiques `FILE` et
  `SFTP`, leur écriture atomique, leur déconnexion et leurs journaux de succès
  ou d'échec sont enfin isolés dans `file_endpoint_emission.py`. Le service
  `emit_on_create.py` est ainsi passé de 2 340 à 232 lignes. Les campagnes
  unitaires et d'intégration isolées passent après cette dernière extraction.
  Le chargement, la mise à jour des statuts programmés et la projection JSON de
  l'arbre hospitalier ont ensuite quitté `routers/structure.py` pour le service
  `structure_tree.py`. La route ne conserve que la lecture du contexte et des
  filtres ; le service est couvert directement sur une hiérarchie complète et
  sur le filtrage strict sans résultat. L'application des modèles du wizard est
  également transactionnelle dans `structure_template_application.py` : toute
  la hiérarchie est validée avant la première écriture, et les vrais champs de
  rattachement EG et code UM sont maintenant alimentés. La projection des
  fiches par type est réunie dans `structure_details.py`, avec des erreurs
  métier distinctes pour type inconnu et entité absente ; sa route synchrone ne
  bloque plus la boucle asynchrone avec la session SQLModel. Le routeur passe
  ainsi de 2 640 à 2 283 lignes.
  Le premier cas d'usage de `routers/mouvements.py` est également isolé dans
  `bed_assignment.py` : l'affectation au lit, son idempotence et la création du
  transfert A02 sont testables sans FastAPI. La lecture et la projection du
  plan complet vivent maintenant dans `bed_plan.py`. La liste filtrée et son
  contexte patient/dossier sont isolés dans `movement_listing.py`, avec des
  erreurs de contexte explicites. La préparation du formulaire de création est
  à son tour réunie dans `movement_form_context.py` : venues et patients sont
  préchargés, les UF d'une EJ sont obtenues par une jointure unique et le
  dernier mouvement n'est plus lu deux fois. Les valeurs réellement soumises
  sont maintenant cohérentes avec le contrat POST (`ADT^Axx` pour le type, ID
  numérique pour l'UF médicale et identifiant pour l'UF de soins), tandis que
  chambre et lit sont correctement préremplis au lieu d'assimiler le lit à la
  chambre. La soumission est elle aussi isolée dans `movement_creation.py` :
  chronologie, transitions et cohérence UH/chambre/lit sont validées avant la
  transaction, la localisation complète est conservée et la venue courante est
  actualisée. La projection de la fiche détail rejoint `movement_details.py` :
  UF médicale et de soins sont chargées ensemble, et UH, chambre et lit sont
  tous résolus depuis la localisation structurée. La modification délègue
  maintenant ses validations et sa transaction à `movement_update.py`, en
  partageant les règles de localisation avec la création ; le formulaire
  d'édition utilise enfin le vrai lit au lieu de l'ID de la chambre. Sa
  préparation a également rejoint `movement_form_context.py` : le graphe
  venue/dossier/patient est préchargé et les UF/UH sont obtenues par requêtes
  groupées plutôt que par boucles imbriquées. Les listes dépendantes historiques
  sont enfin isolées dans `movement_options.py`. La suppression est portée par
  `movement_deletion.py`, avec notification sortante injectée et contexte
  patient préchargé ; elle est testable sans FastAPI. La projection complète de
  la liste (lignes, badges, filtres, actions, onglets et fil d'Ariane) appartient
  maintenant à `movement_listing.py` et possède ses propres tests unitaires. Le
  moteur de recherche patient du plan de lits a également rejoint `bed_plan.py`,
  avec tri stable, limite SQL et projection testée. Le routeur mouvements ne
  conserve que l'appel des cas d'usage et le rendu, et passe de 2 215 à 534
  lignes.
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
  leurs lectures avant de convertir les ressources. Les exports FHIR des
  patients et des venues appliquent maintenant réellement leur contrat
  `limit`/`offset` côté SQL (borne de 500), retournent le total du jeu et
  isolent chaque page dans le cache. Les venues préchargent dossier, patient,
  contacts et identifiants, puis lisent mouvements et lieux physiques par lots;
  un test borne cette page à sept `SELECT`. Les objectifs p50/p95 sont
  désormais publiés avec leur protocole de qualification PostgreSQL dans
  `docs/PERFORMANCE_SLO.md`; l'outil d'export FHIR mesure p50 et p95 sur les
  routes effectives et une taille de page déclarée. Les cinq routes d'export
  FHIR utilisant SQLModel synchrone sont maintenant elles-mêmes synchrones :
  FastAPI les exécute donc hors de la boucle asynchrone. Les autres routes
  historiques `async` à session synchrone restent à inventorier et convertir
  progressivement par domaine. Les huit routes de cartographie de lieux ont
  été traitées de la même façon, sans changer leur contrat JSON; les deux
  lectures de détail de qualification d'interfaces sont également synchrones.
  La liste des templates de structure est maintenant triée, bornée à 500 et
  exécutée hors boucle async; son détail suit le même modèle synchrone. La vue
  d'historique HPRIM est désormais paginée (1–500), ses totaux et compteurs par
  direction sont calculés en SQL, et les liens de navigation conservent les
  filtres; elle et son détail sont synchrones. Les tableaux de bord UCD et LPP,
  composés d'agrégats SQL, suivent aussi ce modèle synchrone. Les listes et
  l'arbre de cartographie appliquent désormais `limit`/`offset` (1–500), un
  tri stable et l'en-tête `X-Total-Count`, sans changer leurs corps JSON.
  L'affectation d'un patient depuis le plan de lits charge maintenant les
  derniers mouvements de toutes les venues candidates en une seule requête,
  au lieu d'une lecture supplémentaire par venue. Le rendu du plan charge aussi
  occupants, dossiers, patients et derniers mouvements par lots ; son budget
  courant est borné à cinq `SELECT`, indépendamment du nombre de lits.
  La liste globale des mouvements d'une EJ utilise également une seule jointure
  mouvement → venue → dossier au lieu de matérialiser successivement les deux
  listes d'identifiants intermédiaires. Le formulaire de mouvement supprime
  aussi ses rafraîchissements patient/dossier par venue et les boucles
  EG → pôle → service → UF qui provoquaient un N+1.
- **BE-06 :** la migration `c7e1f2a4b603` tolère désormais l'absence des tables
  de cotations optionnelles sur les anciennes installations. Le test de base
  fraîche suit dynamiquement la tête Alembic et ces deux tests sont exécutés
  dans le workflow. Le cycle de vie applicatif hors tests appelle maintenant
  `alembic upgrade head` via `migrate_database()` : il ne crée donc plus son
  schéma à partir des modèles au démarrage. `create_all()` est explicitement
  conservé pour les fixtures SQLite jetables. Le catalogue de qualification
  n'est plus injecté ni par Alembic ni au bootstrap d'une base vide :
  `scripts/setup/seed_scenario_catalog.py` le charge explicitement et de façon
  idempotente après migration. Les scripts de seed général et de scénarios
  d'interopération, ainsi que les initialiseurs de démonstration, invoquent
  désormais `migrate_database()` plutôt que `create_all()`. Le bootstrap
  historique d'une base Alembic totalement vide s'appuie maintenant sur une
  baseline DDL figée et versionnée à la tête courante, déclinée pour SQLite et
  PostgreSQL; il ne dépend plus de `SQLModel.metadata.create_all()`.
- **BE-07 :** `ruff check app` est désormais à zéro anomalie et est imposé par
  la CI (baseline globale à zéro). Les imports liés au registre ORM restent
  explicitement annotés lorsqu'ils ont un effet de bord; les imports tardifs
  ont été replacés en tête de module, après correction des modules concaténés
  historiques et sans correctif global automatique. Les deux derniers lots ont
  supprimé 27 variables locales inutilisées et les 26 noms locaux ambigus,
  sans supprimer les validations hiérarchiques qui les produisaient. Les
  imports inutilisés clairement sans effet de bord ont aussi été retirés des
  schémas et services isolés, puis des adaptateurs FHIR/HPRIM
  et de polling. Les constructions de mappings restants sont maintenant
  justifiées par leur cascade ORM et couvertes par un test SQLite dédié.
  Les imports nécessaires au registre ORM de `app.db` sont maintenant annotés
  explicitement, ce qui évite de confondre leur effet de bord voulu avec une
  dette d'import inutilisé.
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
  durant la transition. Les exceptions non gérées suivent le même contrat. Les
  sept listes JSON historiques de structure ont désormais une pagination
  bornée homogène et exposent leur cardinalité totale dans `X-Total-Count`,
  sans rupture de leur corps tableau. Ces mêmes routes utilisent maintenant
  sept schémas de sortie dédiés, alignés par test sur les colonnes historiques,
  et n'exposent donc plus directement leurs modèles ORM. L'extension de cette
  séparation aux autres API historiques reste progressive. Les quatre routes
  AJAX historiques de mouvement conservent désormais explicitement leur
  enveloppe `{success, options}` via un service testé ; le filtrage des motifs
  reconnaît aussi correctement un code complet `ADT^Axx`.
- **BE-09 :** la publication manuelle d'une version de scénario exige désormais
  une intention métier, au moins une précondition, une assertion exécutable et
  un résultat attendu explicite. Les manques sont visibles dès le contrôle
  préalable et bloquent la publication. Le résultat attendu rejoint aussi
  l'instantané immuable de version, afin qu'un scénario négatif conserve son
  contrat de rejet exact dans les preuves ultérieures. L'enrichissement du
  contenu propre à chaque partenaire reste nécessaire à mesure que leurs
  contrats sont fournis.
- **DOC-01 :** `scripts/generate_openapi_inventory.py` produit désormais
  l'inventaire Markdown depuis le contrat OpenAPI réellement servi. Les
  documents ne doivent plus recopier un nombre de routes à la main. Chaque
  opération inventoriée indique désormais son domaine propriétaire, son statut
  (`Active` ou `Dépréciée`) et son consommateur (`API`, interface web ou à
  qualifier), avec possibilité de préciser ces valeurs par les extensions
  OpenAPI `x-owner`, `x-status` et `x-consumer`.
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
  cette isolation sans échec : `tests/unit` compte 685 réussites, 14 ignorés,
  5 désélectionnés et 10 `xfail` attendus ; `tests/integration` compte 108
  réussites, 3 ignorés, 9 désélectionnés, 8 `xfail` et 2 `xpass`.
  La configuration Alembic ne remplace plus les handlers de journalisation du
  processus hôte lorsqu'une migration est lancée depuis pytest. La campagne
  unitaire complète repasse ainsi dans son ordre réel, et les assertions UI
  historiques ciblent désormais les modules JavaScript externalisés plutôt
  que leur ancien contenu inline.
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
  Le dashboard des métriques délègue maintenant son rafraîchissement, ses
  compteurs et son tableau à `static/js/metrics-dashboard-workspace.js` ; le
  client HTTP partagé est chargé avant les workspaces de contenu.
  Le détail de cotations délègue ses onglets à
  `static/js/dossier-cotations-tabs.js` et fournit désormais les rôles ARIA,
  états et raccourcis fléchés, Accueil et Fin attendus pour cette navigation.
  La liste de configuration EJ des scénarios isole aussi sa suppression dans
  `static/js/scenario-ej-config-list.js`, avec délégation d'événement et nom
  d'EJ transporté par attribut de données plutôt que dans un gestionnaire HTML.
  Les filtres de statut des scénarios par EJ délèguent enfin leur soumission
  automatique à `static/js/ej-scenarios-status.js`.
  La copie du message brut de conformité est isolée dans
  `static/js/conformity-message-detail.js`, avec annonce de résultat et
  prévention du double clic pendant l'accès au presse-papier.
  Le détail de message standard suit ce même modèle dans
  `static/js/message-detail.js`, avec bootstrap JSON du payload plutôt qu'une
  fonction métier inline. Le formulaire patient délègue désormais ses sections
  animées et la génération d'identité exemple à
  `static/js/patient-form-workspace.js`; le template ne conserve plus ce
  comportement métier embarqué. L'éditeur des règles de validation délègue
  aussi sa sauvegarde, son rechargement et la protection des modifications non
  enregistrées à `static/js/validation-rules-workspace.js`. La liste des
  contacts utilise désormais `static/js/contacts-list-workspace.js` pour sa
  confirmation et sa suppression asynchrone. Le tableau de bord GHT délègue
  enfin le rafraîchissement de sa supervision à
  `static/js/ght-dashboard-workspace.js`. La bascule du mode strict PAM de la
  page de conformité est maintenant portée par
  `static/js/conformity-home-workspace.js`. Le formulaire générique charge
  maintenant `state_transitions.js` puis `forms.js` avec des scripts différés,
  sans bootstrap dynamique ni polling embarqué.
  L'assistant d'admission délègue aussi le chargement hiérarchique service, UF
  et lit à `static/js/admission-wizard-workspace.js`. L'asset ne s'initialise
  que sur l'étape concernée, annonce ses chargements et erreurs, et délègue la
  sélection des lits avec un état `aria-pressed` au lieu de recréer des
  listeners pour chaque résultat.
  Le détail dossier charge désormais son compteur de cotations depuis
  `static/js/dossier-detail-workspace.js`, avec l'identifiant transmis par un
  attribut `data-*` et des gardes explicites sur les éléments facultatifs.
  Le tableau de qualification isole également dans
  `static/js/qualification-dashboard-workspace.js` le choix à blanc/réel et la
  confirmation préalable à toute émission partenaire.
  Les sept listes de structure (EG, pôles, services, UF, UH, chambres et lits)
  partagent enfin `static/js/structure-list-filters.js` : les paramètres sont
  décrits dans le HTML, les filtres clavier et listes sont délégués, et les
  gestionnaires inline dupliqués ont disparu.
  La saisie rapide de cotations délègue maintenant ses 596 lignes de logique à
  `static/js/cotation-entry-workspace.js`. L'identifiant du dossier transite
  par un attribut `data-*`, les recherches et les quatre créations restent sur
  le client HTTP partagé, et les actions statiques comme dynamiques utilisent
  une délégation d'événements sans gestionnaire `onclick` embarqué. Le bouton
  Historique, auparavant relié à une fonction absente, amène désormais le
  clavier et la vue sur la liste des cotations.
  Le workflow de mouvements délègue à son tour ses 358 lignes de sélection,
  validation et recherche de localisation à `static/js/movement-workflow.js`.
  Le nettoyage différé de la bannière de succès rejoint le même asset et le
  catalogue métier reste transmis sous forme de données JSON non exécutables.
  Le sélecteur cartographique partagé charge lui aussi sa hiérarchie depuis
  `static/js/location-cartography.js`, sans logique réseau dans le composant
  Jinja. Le formulaire générique ne contient plus non plus ses scripts inline :
  la sélection d'une option unique, l'affichage des champs propres au protocole
  et le raccourci d'enregistrement sont initialisés par `static/js/forms.js`.
  Cette reprise supprime également un fragment JavaScript tronqué qui était
  rendu comme du texte après le formulaire. Les derniers scripts du shell, de
  la documentation, du catalogue des standards et de la démonstration du design
  system sont maintenant externalisés. Le préchargement du thème reste
  volontairement synchrone dans le `<head>` afin d'éviter un flash de thème,
  mais son code réside dans `static/js/theme-preflight.js`. L'inventaire ne
  conserve ainsi plus aucun template avec JavaScript exécutable embarqué ; les
  balises restantes sans `src` ne transportent que des données JSON. Les
  derniers gestionnaires HTML inline du styleguide, des modales partagées, des
  alertes et des liens désactivés ont également été remplacés par des actions
  `data-*` déléguées ; un test parcourt désormais tous les templates et bloque
  leur réintroduction.
- **FE-02 :** l'asset non référencé `cotationForm.js`, qui simulait une
  sauvegarde, ainsi que deux sauvegardes Python exécutables obsolètes ont été
  supprimés. La commande `npm run inventory-assets` contrôle désormais les
  références aux scripts statiques dans les templates. Elle a permis de retirer
  deux doublons historiques du workflow mouvements ; l'inventaire actuel ne
  signale plus aucun script JavaScript orphelin. Les boutons de validation,
  facturation et suppression de cette liste ne reposent plus sur un délai local
  : ils confirment l'action via le dialogue applicatif, appellent l'API groupée
  puis rechargent les données persistées. L'export télécharge effectivement un
  CSV des lignes filtrées. Le prototype historique
  `hprim_cotation_modern.html`, non routé et porteur d'actions locales simulées,
  a aussi été supprimé ; `/cotation-modern/...` redirige déjà vers l'unique
  workspace persistant et le guide d'intégration a été aligné sur ce parcours.
  Le composant non inclus `components/cotations_inline.html`, qui ne manipulait
  lui aussi que des données locales, a été supprimé avec son exemption de
  garde-fou. La saisie rapide convertit désormais les dates ISO des formulaires
  avant persistance ; un test crée puis relit un acte CCAM, NGAP, UCD et LPP,
  afin qu'un succès affiché corresponde obligatoirement à une sauvegarde réelle.
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
  Les recherches rapides de cotations, de patients du plan de lits et de
  localisations annulent désormais leur requête précédente. Elles affichent
  leur chargement, ne laissent pas une réponse obsolète remplacer la saisie
  courante et proposent une action explicite de réessai en cas d'indisponibilité.
  Le tableau de cache l'utilise également. Des tests frontend empêchent le
  retour à `fetch` direct : la seule occurrence restante est le transport
  interne de `static/js/http.js`. La liste historique de cotations utilise à
  son tour ce client pour ses mutations groupées.
- **FE-06 :** `npm run lint`, `npm test` et `npm run check-frontend` sont
  disponibles et exécutés dans un job CI frontend. Ils vérifient la syntaxe,
  le client HTTP, la génération CSS et les budgets de taille. Les assets
  applicatifs sont limités à 420 Ko au total et 64 Ko par fichier, le bundle CSS
  généré à 200 Ko et l'ensemble des feuilles produit à 240 Ko, tandis que les
  bibliothèques minifiées disposent d'un budget séparé. Le job navigateur
  échoue aussi si un parcours prioritaire produit une
  erreur console ou `pageerror`; les modules HTTP, builder, recherches et
  formulaires possèdent des tests frontend ciblés.
- **FE-04/FE-05 :** le gestionnaire partagé de formulaires associe désormais
  les erreurs au champ, annonce leur apparition et place le focus sur le
  premier champ invalide. Le wizard structure
  annonce à présent son étape active via une région live et marque celle-ci
  avec `aria-current`, afin de rendre sa progression intelligible au lecteur
  d'écran. La modale de suppression des contacts possède maintenant un rôle
  de dialogue, une étiquette, une fermeture Échap et une restitution du focus
  à son déclencheur. Le créateur de scénarios marque aussi ses prérequis
  invalides avec `aria-invalid` et déplace le focus vers le titre de chaque
  étape lors de la navigation. Les formulaires patient, contact, endpoint et
  mouvement signalent désormais les modifications non enregistrées, préviennent
  avant une sortie et affichent un résumé navigable des erreurs. Sur mobile,
  leur action principale reste collée au bas de l'écran sans masquer le contenu
  du formulaire. Axe contrôle maintenant dans Chromium les parcours de création
  de scénario, wizard de structure et validation selon WCAG 2.1 AA ; toute
  violation critique ou sérieuse échoue le job navigateur de CI. Une checklist
  de revue clavier et des annonces dynamiques complète ce contrôle automatisé.
  La campagne réelle du 23 septembre 2026 passe ses six contrôles. Elle a permis
  de corriger la sémantique ARIA des deux navigations principales, le contraste
  des identifiants de modèles de structure et de rendre l'indicateur de focus
  global prioritaire sur les anciennes classes supprimant l'outline.
  La suppression d'une UH ou d'une chambre partage maintenant une seule modale
  déléguée : fermeture Échap, restitution du focus et ciblage de l'action via
  attribut de données sont couverts par un test frontend.
  Les contrôles de changement d'identifiant et de fusion patient partagent
  désormais `static/js/patient-identity-actions.js`, qui expose aussi
  `aria-invalid`; l'association patient/venue du contact est isolée dans
  `static/js/contact-form-workspace.js` avec des gardes d'initialisation.
  Les deux formulaires de namespace partagent aussi
  `static/js/namespace-form-workspace.js` pour l'extraction d'OID et le choix du
  mode de préfixe, sans fonction globale ni gestionnaire HTML inline.
  Le détail d'endpoint et le détail GHT externalisent à leur tour le filtrage
  EJ/GHT et le clonage de structure. La modale de clonage restaure le focus et
  accepte Échap sans exposer de fonction globale.
  Le changement de type de dossier est maintenant entièrement porté par
  `static/js/dossier-type-change-workspace.js`; les avertissements sont rendus
  par nœuds DOM, le forçage réutilise le même chemin et les erreurs deviennent
  visibles via le système de toast.
  L'import de scénario quitte aussi le template pour
  `static/js/scenario-import-workspace.js`, tout en conservant l'envoi
  multipart, la redirection vers la revue et la remise en état après erreur.
  La configuration EJ des scénarios externalise également l'ouverture
  temporaire des listes d'UF dans `static/js/scenario-ej-config-form.js`.
  Le générateur de scénarios de test délègue enfin génération, copie et
  téléchargement à `static/js/test-scenario-generator-workspace.js`, sans
  callbacks affectés dynamiquement dans le template.
- **FE-07 :** les styles de la liste de cotations ont été transférés du
  template au design system sous des classes préfixées `cotations-list-*`.
  L'écran ne déclare donc plus de styles globaux locaux, et les styles de cet
  espace de travail ne peuvent pas modifier involontairement une autre vue.
  La saisie rapide de cotations suit désormais la même règle : ses styles sont
  centralisés et scopés sous `.rapid-shell`, et ses animations locales non
  utilisées ont été supprimées. Les styles des champs et accordéons du
  formulaire patient sont maintenant regroupés dans `forms.css` et strictement
  scopés sous `.patient-form`; le template ne contient plus de bloc de style.
  Les espaces analytics, configuration d'alertes, import de structure et HPRIM
  ont rejoint `design-system.css` avec des préfixes de domaine (`analytics-*`,
  `alert-config-*`, `structure-import-*`, `hprim-*`) : leurs variantes ne se
  propagent plus à d'autres écrans. Le catalogue
  `CATALOGUE_DESIGN_SYSTEM.md` fixe désormais l'implémentation recommandée des
  formulaires, tableaux, badges, toasts, modales et états vides. Les sept
  dernières exceptions (`base`, documentation, démonstration du design system,
  patient, exécution groupée de scénarios et deux vues structure) disposent
  désormais de feuilles dédiées chargées via les blocs de tête du layout. Un
  test frontend interdit maintenant tout nouveau bloc `<style>` local sans
  liste d'exemption. Les
  deux pages de démonstration (`/styleguide` et `/design-system`) sont
  documentées comme références internes et ne sont plus proposées dans la
  navigation métier. Les contrôles navigateur existants couvrent le reflow
  mobile, le thème sombre et les erreurs JS des ateliers prioritaires.

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

> Mise à jour du 23 septembre 2026 : cette campagne historique est remplacée
> par deux campagnes isolées vertes. `tests/unit` compte 684 réussites, 14
> ignorés, 5 désélectionnés et 10 `xfail`; `tests/integration` compte 108
> réussites, 3 ignorés, 9 désélectionnés, 8 `xfail` et 2 `xpass`. Trois
> avertissements de dépréciation `BaseModel.dict()` subsistent dans l'import
> legacy, sans échec associé.

La campagne historique avait été arrêtée après 7 min 14 s : **129 réussis, 4 échecs, 6
ignorés et 11 xfail**, à environ 13 % de la collecte. Les échecs observés
concernent deux migrations Alembic, la capture des logs/métriques et un test qui
contacte un serveur HTTP réel puis atteint le timeout de 300 secondes. Ce
résultat est à rapprocher de la section QA-01 et du rapport de régression daté ;
les tests dépendant de services réels ou d'un navigateur doivent rester dans
des jobs séparés.
