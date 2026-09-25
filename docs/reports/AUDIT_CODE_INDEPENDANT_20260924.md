# Audit indépendant du code — 24 septembre 2026

## 1. Mandat et méthode

Cet audit a été réalisé comme une première découverte du dépôt. Le précédent audit et ses conclusions n'ont pas été utilisés comme source : les constats ci-dessous proviennent exclusivement du code, de la configuration, des tests et des commandes exécutées sur la révision courante.

Périmètre examiné :

- architecture FastAPI, services métier et accès aux données ;
- interfaces Jinja2, JavaScript et accessibilité automatisée ;
- authentification et surfaces d'exposition visibles dans le code ;
- migrations, démarrage, Docker et intégration continue ;
- stratégie de tests, dépendances, documentation et hygiène du dépôt.

Ce document est un audit statique et dynamique du dépôt, pas un test d'intrusion ni une qualification réglementaire. Les données réelles, la charge de production, les systèmes partenaires et les pratiques d'exploitation n'ont pas été observés.

## 2. Verdict exécutif

MedData Bridge possède une couverture fonctionnelle et protocolaire très large, une vraie démarche de qualification d'interopérabilité et plusieurs garde-fous techniques déjà utiles. Le code courant compile, passe Ruff, expose un inventaire OpenAPI très riche et dispose d'une chaîne frontend automatisée convaincante.

En revanche, l'application ne devrait pas être considérée comme prête pour une exposition de production contenant des données de santé. Les trois blocages principaux sont :

1. le contrôle d'accès n'est pas appliqué à la majorité des routes métier et des API ;
2. le démarrage Docker n'est pas reproductible depuis une extraction Git propre ;
3. la composition applicative repose encore sur des objets globaux et peut démarrer partiellement lorsque des domaines ne se chargent pas.

Le principal risque de maintenance vient ensuite de la taille de certains modules et fonctions, du mélange entre traitements synchrones et routes asynchrones, et de plusieurs chemins concurrents pour le schéma, les dépendances et le déploiement.

### Niveau de maturité observé

| Domaine | Évaluation | Synthèse |
|---|---|---|
| Fonctionnel / interopérabilité | Bon | Couverture HL7, IHE PAM, HPRIM, FHIR, MFN, outbox et scénarios très étendue |
| Qualité statique | Bon | Ruff et compilation passent ; conventions frontend contrôlées |
| Architecture / maintenabilité | Fragile | Modules géants, responsabilités mélangées, nombreux objets globaux |
| Données / performance | À consolider | Chargements non bornés, comptages en mémoire et écritures lors de GET |
| Tests | Moyen à bon | Beaucoup de tests, mais suite coûteuse, fixture globale lourde et CI partielle |
| Frontend / UX technique | Moyen à bon | Assets externalisés et testés, mais modules volumineux et budget presque saturé |
| Déploiement / exploitation | Insuffisant | Compose propre non exécutable, sources de déploiement dupliquées, images non figées |
| Sécurité applicative | Bloquant | Authentification locale de démonstration et périmètre métier largement public |

## 3. Éléments vérifiés

État mesuré sur la révision auditée :

- 364 fichiers Python dans `app/`, environ 90 300 lignes ;
- 161 templates, environ 27 800 lignes ;
- 67 fichiers JavaScript produit, environ 10 800 lignes ;
- 599 opérations dans l'inventaire OpenAPI généré ;
- aucune route OpenAPI dupliquée détectée par l'inventaire/test dédié ;
- `ruff check app` : succès ;
- `python3 -m compileall -q app` : succès ;
- `npm run check-frontend` : succès, 72 tests frontend réussis ;
- 67 assets JavaScript sur 67 sont référencés par les templates ;
- bundle CSS : 162 224 / 204 800 octets ; CSS total : 226 586 / 245 760 octets ; JavaScript produit : 415 274 / 430 080 octets ;
- construction Compose depuis une archive Git propre : échec, car `.env` est obligatoire et absent de l'archive ;
- pack Git : environ 232,6 Mio.

La suite Python complète ciblant `tests/unit` et `tests/integration` termine avec un code de sortie nul : 936 tests sont collectés, dont 922 sélectionnés par la configuration de marqueurs. Elle comporte des skips, xfail et xpass attendus. Les avertissements observés concernent principalement une combinaison système `requests`/`urllib3`/`chardet` et des API de chargement dépréciées.

## 4. Points forts constatés

### 4.1 Interopérabilité traitée comme un domaine de premier rang

Le dépôt ne se limite pas à quelques convertisseurs : il contient des validateurs, des imports/exports, des scénarios, des preuves de roundtrip et des tests dédiés à PAM, HPRIM, MFN et FHIR. L'outbox persistante et les mécanismes de reprise sont de bonnes bases pour les échanges fiables.

### 4.2 Contrats API et erreurs mieux structurés que dans un prototype classique

FastAPI produit un inventaire OpenAPI de 599 opérations. Le projet possède des schémas de lecture dédiés sur plusieurs API, des enveloppes d'erreur communes et des tests d'inventaire. Aucun doublon méthode/chemin n'a été relevé dans l'application générée.

### 4.3 Qualité frontend automatisée

Les scripts exécutables ont été sortis des templates, les gestionnaires inline sont interdits, les assets sont inventoriés et des budgets sont contrôlés. Les 72 tests Node couvrent notamment le client HTTP commun, les assistants de saisie, plusieurs workspaces, le clavier et l'accessibilité.

### 4.4 Socle de déploiement raisonnable

L'image Docker utilise un utilisateur non privilégié, possède un healthcheck et documente pourquoi un seul worker est lancé. Alembic dispose d'un bootstrap dédié aux bases neuves. Ces choix sont pertinents, même si leur industrialisation reste incomplète.

## 5. Constats prioritaires

### AUD-01 — Bloquant — Le périmètre métier n'est pas protégé par défaut

**Preuves**

- Les dépendances `get_current_user` et `require_role` ne sont utilisées que par les routes d'authentification, deux routes de cache et le petit routeur `admin_protected`.
- `require_ght_context` sélectionne un contexte fonctionnel ; ce n'est pas une authentification.
- Les API patients sont montées sans dépendance d'authentification dans [`app/api/patients.py`](../../app/api/patients.py).
- La recherche de dossiers renvoyant identité patient et numéro de dossier est publique par défaut avec `PUBLIC_SEARCH=true` dans [`app/routers/cotation_selector.py`](../../app/routers/cotation_selector.py).
- Des comptes intégrés `admin/admin` et `user/user` sont présents dans [`app/auth.py`](../../app/auth.py).

**Impact**

Une instance accessible sur le réseau expose en lecture et en écriture des données métier et des actions d'interopérabilité sans contrôle homogène. Le contexte GHT ne constitue pas une frontière de sécurité.

**Recommandation**

Appliquer une politique d'authentification globale, puis déclarer explicitement une courte liste de routes réellement publiques (`/health`, documentation si souhaitée, login). Ajouter une autorisation par rôle et par contexte GHT/EJ, supprimer les comptes codés en dur et rendre toute recherche patient privée par défaut.

**Critère de sortie**

Un test parcourt l'OpenAPI et prouve que toute opération non inscrite dans une allowlist retourne 401 sans identité et 403 hors périmètre métier.

### AUD-02 — Bloquant — Les secrets et la configuration de session ne suivent pas une politique unique

**Preuves**

- `Settings.secret_key` vaut par défaut `dev-secret-key-change-in-production` dans [`config/settings.py`](../../config/settings.py).
- Le middleware de session ne considère que `change-me-in-production` comme valeur interdite dans [`app/app.py`](../../app/app.py) ; la valeur par défaut reste donc utilisable et prévisible.
- La clé JWT refuse correctement cette valeur hors test, mais utilise une autre logique dans [`app/auth.py`](../../app/auth.py).
- La révocation JWT est « fail-open » lorsque le cache échoue : un token révoqué peut redevenir acceptable si Redis est indisponible.

**Impact**

Les sessions et JWT n'ont pas le même modèle de défaillance. Une configuration apparemment valide peut protéger les deux mécanismes de façon différente.

**Recommandation**

Créer un validateur unique de secrets au chargement de configuration, sans valeur de production par défaut. En production, échouer avant le montage des routes si une clé est absente/faible. Pour la révocation, choisir et documenter explicitement une stratégie fail-closed ou remplacer la blacklist par des sessions persistées/versionnées.

### AUD-03 — Élevé — La fabrique d'application n'isole pas réellement sa configuration

**Preuves**

- `create_app(runtime_settings)` accepte une configuration injectée.
- L'`engine`, `get_session`, `session_factory` et le `mllp_manager` sont cependant créés au niveau module depuis l'instance globale de settings avant l'appel à `create_app()`.
- Le lifespan migre `runtime_settings.database_url`, alors que les routes continuent à utiliser l'engine global dans [`app/db.py`](../../app/db.py).
- SQLAdmin est monté seulement sur l'objet global `app`, après `app = create_app()`, et non sur les autres instances créées par la fabrique.

**Impact**

Une application construite avec une URL de base spécifique peut migrer une base et en interroger une autre. Les tests de fabrique ne représentent pas fidèlement le runtime et plusieurs instances dans un même processus partagent leur manager MLLP.

**Recommandation**

Introduire un conteneur de runtime par application : engine, fabrique de sessions, cache, scheduler et manager MLLP dans `app.state`. Construire les dépendances FastAPI à partir de ce conteneur et déplacer aussi SQLAdmin dans `create_app()`.

### AUD-04 — Élevé — Le serveur peut démarrer en état fonctionnel partiel

**Preuves**

Dans [`app/app.py`](../../app/app.py), le montage des domaines CCAM, NGAP/UCD, LPP, cotations, API patients/dossiers, messages HPRIM, contexte et scénarios est entouré de nombreux `except Exception`. Une erreur d'import ou d'initialisation devient un avertissement et l'application continue.

Le lifespan adopte la même stratégie pour les vocabulaires et les serveurs MLLP.

**Impact**

Un déploiement peut être déclaré vivant tout en ayant perdu un domaine entier ou ses récepteurs de messages. Le healthcheck actuel ne vérifie ni l'inventaire attendu des routes, ni l'état métier des listeners.

**Recommandation**

Déclarer les fonctionnalités optionnelles dans une configuration explicite. Une fonctionnalité activée qui ne se charge pas doit faire échouer le démarrage. Ajouter un readiness check vérifiant migrations, cache selon politique, listeners attendus, scheduler et signature de l'inventaire OpenAPI.

### AUD-05 — Élevé — Le déploiement Docker n'est pas reproductible depuis Git

**Preuves**

- [`docker/docker-compose.yml`](../../docker/docker-compose.yml) exige `../.env` via `env_file`.
- `.env` est ignoré et n'existe pas dans une archive Git propre.
- L'exécution de `docker compose ... config --quiet` sur une archive de `HEAD` échoue avec « env file .../.env not found ».
- Le workflow actif lance Compose sans créer ce fichier.
- Compose fournit `ENVIRONMENT=production`, variable que `Settings` ne lit pas, mais ne fournit pas les clés requises.
- `prom/prometheus:latest`, `python:3.11-slim` et des dépendances Python par plages rendent la reconstruction variable dans le temps.

**Impact**

Le smoke test CI et l'installation opérateur peuvent fonctionner sur une machine ayant un `.env` résiduel et échouer sur une machine propre. Une reconstruction ultérieure peut produire une image différente.

**Recommandation**

Rendre `env_file` optionnel pour le développement ou générer explicitement un fichier d'environnement CI. Déclarer toutes les variables requises, valider le profil de runtime, figer les images par version/digest et produire un lock Python avec hashes pour l'image livrée.

### AUD-06 — Élevé — La complexité est concentrée dans des unités difficiles à tester

**Mesures**

- 2 309 fonctions et 455 classes ;
- 102 fonctions de 100 lignes ou plus ; 27 de 200 lignes ou plus ;
- 487 gestionnaires larges `except Exception` ou équivalents ;
- `handle_admission_message` : 629 lignes ;
- `generate_pam_hl7` : 615 lignes ;
- `validate_pam` : 604 lignes ;
- `on_message_inbound_async` : 586 lignes ;
- `create_app` : 551 lignes ;
- [`app/routers/scenarios.py`](../../app/routers/scenarios.py) : 1 902 lignes ;
- [`app/services/hprim/hprim_xml.py`](../../app/services/hprim/hprim_xml.py) : 1 488 lignes ;
- [`app/services/transport_inbound.py`](../../app/services/transport_inbound.py) : 1 481 lignes.

**Impact**

Les changements de protocole, de persistance et d'IHM se croisent dans les mêmes unités. Les erreurs sont plus difficiles à localiser et les tests doivent préparer beaucoup de contexte.

**Recommandation**

Découper par cas d'usage et par phase : parseur pur, validation pure, résolution de contexte, mutation transactionnelle, émission et présentation. Fixer des limites progressives (par exemple aucune nouvelle fonction au-delà de 80 lignes et aucun routeur au-delà de 500 lignes) dans un contrôle de budget de complexité.

### AUD-07 — Élevé — Le modèle de concurrence mélange routes async et SQL synchrone

**Preuves**

L'analyse syntaxique relève 53 routes `async def` dépendant de la session SQLModel synchrone. Plusieurs effectuent des requêtes ou commits avant/après des attentes réseau. Les endpoints `/health` et `/health/db`, eux aussi async, appellent directement la base et le cache synchrones.

**Impact**

Sous latence PostgreSQL, Redis, fichier ou réseau, ces appels peuvent bloquer la boucle événementielle et dégrader toutes les requêtes du worker unique.

**Recommandation**

Choisir une règle uniforme : routes synchrones pour les cas d'usage synchrones, ou pile SQLAlchemy async de bout en bout. Pour les workflows mixtes, isoler le travail SQL synchrone dans un service exécuté hors boucle et interdire les appels DB directs dans les routes async par un test statique étendu à `app/app.py`.

### AUD-08 — Élevé — Plusieurs lectures chargent des tables complètes ou écrivent en GET

**Preuves**

- 486 appels `.all()` sont présents dans `app/` ; ils ne sont pas tous problématiques, mais plusieurs listes publiques n'ont ni limite ni pagination.
- La liste patients charge l'ensemble du périmètre sélectionné dans [`app/routers/patients.py`](../../app/routers/patients.py).
- La recherche de dossiers compte les résultats en chargeant toutes les lignes au lieu d'utiliser `COUNT(*)`.
- Des assertions de scénarios et vérifications de qualification chargent des tables avant filtrage Python.
- Des GET de structure appellent `apply_scheduled_status()` puis `session.commit()`, par exemple les chambres et la recherche de disponibilité.

**Impact**

Le temps et la mémoire augmentent avec le volume de données. Les GET ne sont plus sans effet de bord, ce qui complique cache HTTP, répétition, observabilité et gestion des contentions.

**Recommandation**

Imposer pagination, `COUNT(*)`, projections et filtres SQL sur les listes. Déplacer l'application des statuts planifiés vers un job idempotent ou calculer un statut effectif sans écriture. Ajouter des budgets de requêtes et des tests avec un volume représentatif.

### AUD-09 — Élevé — La CI active ne protège pas toute la suite de régression

**Preuves**

- Un seul workflow est actif : `.github/workflows/interop-conformance.yml` ; les workflows généralistes sont suffixés `.disabled`.
- Le job conformance exécute une sélection de fichiers, pas l'ensemble de `tests/unit` et `tests/integration`.
- Le smoke Compose dépend du `.env` absent d'un checkout propre.
- Trois configurations pytest coexistent : `pytest.ini`, `pyproject.toml` et `tests/pytest.ini`, avec des options différentes.

**Impact**

Une régression hors du sous-ensemble conformance peut être fusionnée. La commande réellement exécutée dépend du répertoire et de la manière dont pytest est lancé.

**Recommandation**

Activer un workflow obligatoire avec Ruff, compilation, frontend, migration neuve, suite unitaire complète et suite d'intégration complète. Garder la conformance dans un job séparé. Ramener la configuration pytest à une source unique.

### AUD-10 — Élevé — La fixture globale réduit la valeur et la vitesse des tests unitaires

**Preuves**

[`tests/conftest.py`](../../tests/conftest.py) recrée et initialise la base pour chaque test via une fixture `autouse`, charge les vocabulaires et sème plusieurs objets. Il remplace globalement `app.services.cache_service` dans `sys.modules` par un mock et ignore plusieurs erreurs de seed avec `except Exception: pass`. Deux fonctions `pytest_configure` sont définies ; la seconde remplace la première en Python.

**Impact**

Les tests dits unitaires dépendent d'un bootstrap d'intégration, sont plus lents et peuvent ne jamais exercer le vrai cache. Les erreurs de fixture peuvent être masquées jusqu'à un scénario indirect.

**Recommandation**

Séparer les fixtures `unit`, `db` et `integration`, sans base autouse pour les tests purs. Remplacer les modules via injection de dépendances, faire échouer les seeds obligatoires et supprimer les définitions/configurations dupliquées.

### AUD-11 — Élevé — Des constructions HTML contournent l'échappement

**Preuves**

- Des modules JavaScript injectent des valeurs d'API dans `innerHTML`, notamment noms de lits/chambres dans [`app/static/js/location-cartography.js`](../../app/static/js/location-cartography.js) et codes/libellés dans [`app/static/js/cotation-entry-workspace.js`](../../app/static/js/cotation-entry-workspace.js).
- Plusieurs macros génériques acceptent `message`, `content`, `actions` ou `attrs` avec `|safe`.
- Le tableau générique et le dashboard scénarios possèdent également des rendus `|safe`.

**Impact**

Une donnée persistée ou issue d'un référentiel peut devenir du balisage exécutable si elle atteint l'un de ces sinks. Même si certaines sources sont aujourd'hui maîtrisées, les composants génériques rendent la garantie difficile à conserver.

**Recommandation**

Utiliser `textContent`, `createElement` et des attributs typés pour les données. Réserver `|safe` à un type HTML explicitement assaini, jamais à une chaîne générique. Ajouter des tests avec des charges HTML dans les noms, libellés et messages.

### AUD-12 — Moyen — Le schéma possède encore plusieurs chemins de vérité

**Preuves**

- La production passe par Alembic et une baseline `head_schema` pour une base vide.
- `init_db()` conserve `create_all`, des créations d'index/DDL et des `ALTER TABLE` manuels pour l'auteur de scénarios.
- Lors de l'import sous pytest, [`app/db.py`](../../app/db.py) tente déjà un `metadata.create_all()`.

**Impact**

Un test ou un démarrage local peut obtenir un schéma différent de celui d'une base migrée en production. Toute évolution doit être maintenue dans la metadata, la baseline et parfois les corrections manuelles.

**Recommandation**

Faire d'Alembic l'unique chemin de création, y compris pour les tests d'intégration. Générer ou vérifier automatiquement la baseline contre `SQLModel.metadata` et supprimer progressivement les migrations ad hoc de `init_db()`.

### AUD-13 — Moyen — Le dépôt contient des copies concurrentes de l'application

**Preuves**

- `deployment/general/app` et `deployment/postgresql/app` contiennent chacun 332 fichiers suivis, soit deux copies d'environ 4 Mio du code applicatif.
- Ces copies diffèrent du répertoire canonique `app/`.
- [`app/api/zfd.py`](../../app/api/zfd.py) importe même un modèle depuis `deployment.postgresql.app.models`.
- `app/api/ccam.py`, `contracts.py`, `ngap.py` et `zfd.py` ne sont pas montés par la composition principale.

**Impact**

Une correction peut être appliquée à une copie et absente d'une autre. L'import croisé peut enregistrer des modèles différents dans le même processus. Les modules non montés entretiennent une ambiguïté sur l'API réellement supportée.

**Recommandation**

Construire tous les livrables depuis `app/` et supprimer les copies versionnées. Déclarer chaque module API comme actif, expérimental ou obsolète ; tester l'inventaire attendu et supprimer les imports depuis `deployment/`.

### AUD-14 — Moyen — Le dépôt Git sert aussi d'entrepôt d'artefacts lourds

**Preuves**

- `docs/` occupe environ 149 Mio, `tests/` 38 Mio et `data/` 44 Mio dans le checkout.
- `docs/reports/pam_import_report.json` pèse environ 63 Mio.
- Deux wheels Playwright suivies pèsent environ 44 Mio et 35 Mio.
- Un projet imbriqué sous `docs/interfaces.integration_src/interfaces.integration` contient son propre `.git` et des classes compilées.
- Le pack Git atteint environ 232,6 Mio.

**Impact**

Clone, cache CI, revue et sauvegarde sont inutilement coûteux. La provenance des binaires et des rapports générés devient difficile à gérer.

**Recommandation**

Conserver dans Git les sources et de petits échantillons déterministes. Publier roues, gros corpus et rapports dans des artefacts de release, un registry ou un stockage objet avec checksum. Nettoyer ensuite l'historique dans une opération dédiée et coordonnée.

### AUD-15 — Moyen — Les manifestes et la documentation décrivent plusieurs produits

**Preuves**

- `pyproject.toml` annonce la version 1.1.0 et la licence MIT ; `package.json` annonce 1.0.0 et ISC.
- Les URL de projet Python pointent vers `github.com/whatever/...`.
- `requirements.txt` est déclaré canonique, mais quatre fichiers `requirements*.txt` coexistent avec des contenus différents.
- Le manifeste principal mélange runtime, tests, navigateur et outils ; le Dockerfile les installe tous.
- Le README parle d'une « petite base SQLite », tandis que Compose cible PostgreSQL et que le produit comporte environ 90 000 lignes Python.
- Certaines commandes README utilisent `python`, non disponible dans l'environnement d'audit où `python3` est requis.

**Impact**

Les contributeurs et opérateurs ne savent pas toujours quelle version, licence, commande ou liste de dépendances fait foi. L'image de production embarque plus que nécessaire.

**Recommandation**

Définir une version et une licence uniques, corriger les métadonnées, séparer les groupes runtime/dev/e2e et produire un lock. Réécrire le démarrage rapide à partir d'un test effectué en environnement propre.

### AUD-16 — Moyen — Les budgets frontend sont proches de leur plafond

La chaîne frontend est saine, mais le JavaScript produit utilise environ 96,6 % de son budget et le CSS total environ 92,2 %. Les plus gros fichiers (`forms.js`, workspaces structure et cotation) concentrent encore beaucoup de responsabilités.

**Recommandation**

Ne pas relever les budgets automatiquement. Mesurer les assets réellement chargés par écran, supprimer le code commun inutilisé, découper les workspaces par fonctionnalité et charger les modules lourds uniquement sur les pages concernées.

## 6. Plan d'action proposé

### Lot 0 — Rendre l'exposition sûre et le démarrage déterministe

1. Protéger par défaut toutes les routes et définir l'allowlist publique.
2. Remplacer les comptes intégrés par un fournisseur d'identité ou un stockage utilisateur administré.
3. Unifier la validation des secrets et la politique de révocation.
4. Supprimer les injections HTML non assainies.
5. Corriger Compose pour fonctionner depuis un checkout propre et ajouter un test CI correspondant.

**Sortie attendue :** aucune donnée patient accessible anonymement ; démarrage propre reproductible ; test de sécurité du périmètre OpenAPI vert.

### Lot 1 — Fiabiliser la composition et les tests obligatoires

1. Rendre l'engine, les sessions, le cache, MLLP et le scheduler propres à chaque instance d'application.
2. Remplacer les imports optionnels silencieux par des capacités configurées et vérifiées.
3. Ajouter une readiness complète.
4. Activer la suite unit + intégration complète dans la CI.
5. Unifier pytest et alléger les fixtures unitaires.

**Sortie attendue :** deux applications créées dans le même processus peuvent utiliser deux bases isolées ; une capacité activée manquante bloque le démarrage ; la CI couvre la suite complète.

### Lot 2 — Réduire le risque de changement

1. Découper en priorité admission PAM, génération PAM, validation PAM, transport entrant et routeur scénarios.
2. Séparer calcul pur, I/O, transaction et rendu.
3. Uniformiser sync/async.
4. Paginer les listes, pousser filtres et comptages en SQL.
5. Supprimer les écritures déclenchées par les GET.

**Sortie attendue :** budgets de complexité et de requêtes vérifiés automatiquement ; aucun accès SQL synchrone dans une route async ; aucune mutation métier sur GET.

### Lot 3 — Réduire les chemins concurrents

1. Alembic comme chemin unique de schéma.
2. Une seule source applicative pour tous les packages de déploiement.
3. Une seule définition des dépendances par usage et un lock reproductible.
4. Nettoyage des modules orphelins et des gros artefacts Git.
5. Alignement README, version, licence et procédures opérateur.

## 7. Ordre de traitement recommandé

| Ordre | Sujet | Pourquoi maintenant |
|---:|---|---|
| 1 | AUD-01 et AUD-02 | Risque direct sur les données et l'administration |
| 2 | AUD-05 | Empêche de faire confiance à une installation propre et à son smoke test |
| 3 | AUD-03 et AUD-04 | Conditionne la fiabilité de tous les environnements et tests |
| 4 | AUD-09 et AUD-10 | Rend les corrections suivantes vérifiables en continu |
| 5 | AUD-11 | Ferme les sinks HTML génériques avant d'étendre les IHM |
| 6 | AUD-07 et AUD-08 | Prépare la tenue en charge et clarifie les effets de bord |
| 7 | AUD-06 et AUD-12 | Réduit le coût et le risque des évolutions métier |
| 8 | AUD-13 à AUD-16 | Simplifie la livraison, le dépôt et les assets |

## 8. Résultats des vérifications exécutées

| Vérification | Résultat |
|---|---|
| `ruff check app` | Réussi |
| `python3 -m compileall -q app` | Réussi |
| `git diff --check` avant rédaction | Réussi |
| Génération de l'inventaire OpenAPI | Réussie, 599 opérations |
| `npm run check-frontend` | Réussi, 72/72 tests |
| Inventaire des assets | Réussi, 67/67 référencés |
| Budgets frontend | Réussis, marges faibles sur JS et CSS total |
| Compose sur archive Git propre | Échec : `.env` requis absent |
| `pytest -q tests/unit tests/integration` | Réussi ; 936 collectés, 922 sélectionnés, code de sortie 0 |

## 9. Conclusion

Le produit possède déjà beaucoup plus de substance qu'un simple POC et ses tests de protocoles constituent un actif important. Sa prochaine étape ne devrait toutefois pas être l'ajout de nouvelles surfaces fonctionnelles. La priorité est de rendre le périmètre fermé par défaut, le démarrage reproductible, la composition réellement injectable et la suite complète obligatoire en CI.

Une fois ces fondations posées, le découpage des cinq plus gros workflows métier et la normalisation des accès aux données donneront le meilleur retour sur investissement : moins de régressions, des tests plus rapides et une exploitation plus prévisible.

## 10. Suivi de mise en œuvre — 25 septembre 2026

Le demandeur a explicitement exclu le lot 0 de cette mise en œuvre. Les sujets
authentification, secrets, assainissement HTML et Compose n'ont donc pas été
modifiés dans ce lot.

### Lots 1 à 3 réalisés

| Audit | Correction appliquée |
|---|---|
| AUD-03 | Chaque `create_app()` possède désormais son engine, ses dépendances de session, son cache, son scheduler, son manager MLLP et son SQLAdmin. Le test de fabrique construit deux bases SQLite distinctes dans le même processus. |
| AUD-04 | Les capacités métier requises font désormais échouer le démarrage si elles ne se chargent pas. `/ready` vérifie la base, le scheduler et les listeners MLLP. |
| AUD-07 | Les routes SQLModel sont synchrones et s'exécutent dans le pool FastAPI. Les traitements réseau des scénarios, qualifications et rejouages sont résolus depuis ce worker ; les rares lectures HTTP nécessaires restent des dépendances async dédiées. Le contrôle statique ne comporte plus aucune exception. |
| AUD-08 | Les listes patients/dossiers sont paginées et comptées en SQL ; les détails de dossier évitent les requêtes répétées ; les statuts planifiés de structure et PDQm ne persistent plus d'écriture lors d'un GET. |
| AUD-09 | La CI exécute Ruff, compilation, budgets de qualité et la totalité de `tests/unit` et `tests/integration`. La configuration pytest est unique. |
| AUD-10 | Les fixtures ont été dédoublonnées : une seule initialisation SQL reste active, le faux module cache global a été supprimé et les seeds indispensables ne masquent plus leurs erreurs. |
| AUD-12 | Alembic est le chemin de schéma hors tests en mémoire ; les `ALTER TABLE`, indexes et DDL manuels de démarrage ont été retirés. |
| AUD-13 | Les deux copies versionnées de `deployment/*/app` et le module API `zfd` obsolète ont été supprimés. Le bundle de déploiement est construit depuis `app/` canonique. |
| AUD-14 | Les wheels versionnées et le rapport PAM généré de 63 Mio ont été retirés du checkout et ignorés ; ils restent récupérables dans l'historique Git jusqu'à une opération de purge dédiée. |
| AUD-15 | Les dépendances runtime/dev sont séparées. `requirements-runtime.lock` est généré avec hashes ; Docker et le bundle installent/téléchargent ce lock. Métadonnées Python/npm, README et procédure RHEL sont alignés. |
| AUD-16 | Les dépendances npm sont ramenées aux dépendances directes, tout en conservant les budgets et les contrôles d'assets existants. |

### Réduction progressive de la dette (AUD-06 et AUD-07)

- La branche patient de `generate_pam_hl7` a été extraite dans
  `app/services/pam_patient_message.py`. Le point d'entrée conserve le contrat
  public mais passe de 615 à 419 lignes et n'est plus une exception au budget
  de qualité.
- Le validateur PAM délègue maintenant les règles PV1 détaillées et la
  construction du résultat/audit à des helpers dédiés. `validate_pam` repasse
  sous le plafond de 500 lignes et sort lui aussi des exceptions.
- `scripts/check_quality_budgets.py`, exécuté en CI, interdit toute nouvelle
  fonction de plus de 500 lignes et tout routeur de plus de 2 000 lignes. Le
  routeur historique `scenarios.py` reste temporairement plafonné à 2 500 lignes
  pendant son extraction ; les cinq grands workflows restent aussi des
  exceptions de longueur explicitement suivies.
- Les dépendances `read_form_data`, `read_body` et `read_optional_json_upload`
  effectuent les lectures HTTP dans la boucle événementielle. Toutes les routes
  SQLModel sont ensuite synchrones, donc exécutées dans le pool de threads
  FastAPI. Les 52 routes mixtes relevées au départ ont été ramenées à zéro ;
  `scripts/check_async_db_boundaries.py` interdit toute nouvelle exception.

### Vérifications après mise en œuvre

- `ruff check app tests/conftest.py tests/unit/test_ihe_pix_pdq.py` : réussi ;
- `python3 -m compileall -q app tests scripts init_db.py` : réussi ;
- `python3 -m pip install --dry-run --require-hashes -r requirements-runtime.lock` : réussi ;
- `npm ci && npm run check-frontend` : réussi, 72 tests frontend ;
- `pytest -q tests/unit tests/integration` : réussi après mise à jour du test
  PDQm pour vérifier l'absence volontaire d'écriture en GET.
- `python3 scripts/check_async_db_boundaries.py` : réussi, aucune exception
  suivie ; `pytest -q` sur les parcours scénario et qualification : 39 réussis.
