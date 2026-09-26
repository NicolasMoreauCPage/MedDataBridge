# Audit indépendant du code — 26 septembre 2026

## Mandat et méthode

Cet audit évalue la révision `47ca8c0` comme une découverte du dépôt. Les
audits, plans et statuts précédents n'ont pas été utilisés pour qualifier les
constats. Les preuves viennent de la lecture du code courant et de commandes
exécutées localement sur cette révision.

Périmètre : démarrage, architecture FastAPI, persistance, interfaces,
interopérabilité, sécurité, tests, livraison et documentation. Ce n'est ni un
test d'intrusion, ni une recette avec un partenaire réel, ni un test de charge.

## Verdict

Le produit est une plateforme d'interopérabilité substantielle, et non un POC :
il comporte migrations Alembic, CI, base de tests étendue, scénarios, outbox,
FHIR, IHE PAM, MFN et HPRIM. La configuration Compose est valide depuis un
checkout propre et les migrations fraîches vérifiées passent.

En revanche, **la branche courante n'est pas entièrement verte**. Trois
régressions immédiatement corrigeables empêchent de la qualifier de version
propre prête à livrer sans réserve :

1. le démarrage local normal échoue sans clé JWT alors que la sécurité est
   explicitement désactivée ;
2. une page analytics renvoie HTTP 500 à cause d'environnements Jinja2
   incohérents ;
3. la CI échouerait actuellement sur Ruff et sur le contrôle async/SQL.

Après ces corrections, les sujets restants sont principalement la maîtrise de
la dette de taille, la robustesse du packaging publié, le budget frontend et
la qualification auprès des logiciels partenaires.

## Mesures observées

| Indicateur | Valeur |
|---|---:|
| Fichiers Python dans `app/` | 397 |
| Lignes Python dans `app/` | 91 948 |
| Templates | 161 / 27 816 lignes |
| Assets JavaScript | 68 / 10 869 lignes |
| Fichiers de tests Python | 263 / 42 602 lignes |
| Migrations Alembic | 50 |
| Pack Git | 232,61 Mio |
| Environnements Jinja2 créés dans le code | 20 |

## Vérifications exécutées

| Commande | Résultat |
|---|---|
| `python3 -m compileall -q app tests scripts init_db.py` | Réussie |
| `python3 scripts/check_quality_budgets.py` | Réussie |
| `npm run check-frontend` | Réussie : 72 tests ; 68/68 assets référencés |
| `docker compose -f docker/docker-compose.yml config --quiet` | Réussie |
| Tests ciblés clonage GHT + migrations fraîches | Réussis : 8 tests |
| `ruff check app` | Échec : 1 import inutilisé |
| `ruff check app tests` | Échec : 504 écarts, majoritairement dans les tests historiques |
| `python3 scripts/check_async_db_boundaries.py` | Échec : 2 routes async avec accès SQL synchrone |
| `pytest -q tests/unit tests/integration --maxfail=2` | Échec : 2 échecs, 34 succès, 3 skips, 14 désélections |
| Construction d'une application avec la configuration LAN courante | Échec avant création de l'application |

La suite Python complète n'a pas été déclarée verte : son exécution a révélé
des échecs, puis a été relancée avec `--maxfail=2` pour obtenir les diagnostics
reproductibles ci-dessous.

## Constats

### AUD-01 — Critique — Le démarrage LAN documenté dépend encore d'une clé JWT

**Preuve.** La configuration locale chargée pendant l'audit indique
`SECURITY_ENABLED=false`, `DEBUG=false` et aucune `JWT_SECRET_KEY`. Malgré ce
mode LAN volontairement sans authentification, l'import de `app.app` échoue :

```text
RuntimeError: JWT_SECRET_KEY doit être défini avec une valeur forte en environnement non test
```

La cause est l'import inconditionnel de `app.auth` par `app.routers.auth`, qui
évalue `SECRET_KEY = _resolve_jwt_secret()` au niveau module, avant que
`create_app()` ne décide de ne pas monter les routes d'authentification.

**Impact.** La procédure README « copier `.env.example`, puis lancer uvicorn »
ne fonctionne pas avec la configuration LAN par défaut. Le comportement
contredit le choix produit de ne pas imposer de login sur un réseau local.

**Correction.** Retarder la résolution JWT au moment où
`SECURITY_ENABLED=true`, ou rendre les routes/authentification réellement
optionnelles à l'import. Ajouter un test de démarrage avec
`SECURITY_ENABLED=false` et des secrets JWT absents.

### AUD-02 — Critique — Des environnements Jinja2 indépendants cassent le rendu

**Preuve.** `tests/unit/test_analytics_dashboard.py` obtient HTTP 500 sur
`GET /structure/analytics?eg_id=<id>` avec :

```text
TemplateAssertionError: No filter named 'sanitize_icon_svg'
```

`app.app` déclare ce filtre sur son environnement Jinja2, mais
`app/routers/analytics.py` (et 19 autres emplacements) instancie son propre
`Jinja2Templates`. Le template commun utilise le filtre et l'environnement du
routeur ne le connaît pas.

**Impact.** Une page utilisateur existante est inutilisable ; d'autres routes
ayant leur propre environnement risquent le même défaut dès qu'elles utilisent
un filtre ou un global ajouté par l'application.

**Correction.** Créer une fabrique unique de templates (filtres, globals,
chargement, politiques HTML) et l'injecter dans `app.state` ou les routeurs.
Ajouter un test de rendu pour chaque route HTML critique.

### AUD-03 — Élevé — Les garde-fous qualité et la CI sont rouges sur `main`

**Preuves.**

- `ruff check app` échoue sur l'import `SECRET_KEY` inutilisé dans
  `app/routers/auth.py` ; le workflow actif exécute exactement cette commande.
- `scripts/check_async_db_boundaries.py` détecte `list_users` et
  `get_system_stats` dans `app/routers/admin_protected.py` : elles sont
  `async def` mais ouvrent et interrogent une session SQLModel synchrone.
- Le test unitaire du garde-fou échoue donc également.

**Impact.** La CI ne peut plus jouer son rôle de barrière de régression. Les
deux routes peuvent bloquer la boucle événementielle si la base est lente.

**Correction.** Retirer l'import inutilisé et rendre les deux routes
synchrones (ou adopter une vraie pile SQL async). Exiger la réussite des mêmes
commandes localement avant toute livraison.

### AUD-04 — Élevé sous condition — La pile Compose est ouverte et contient des secrets de démonstration

**Preuves.** `docker/docker-compose.yml` publie Redis sur `6379`, utilise
`POSTGRES_PASSWORD=password`, une URL de base PostgreSQL avec le même mot de
passe et ne définit pas `SECURITY_ENABLED`. Cette dernière valeur vaut donc
`false` par défaut.

**Impact.** Ce choix est acceptable uniquement sur un LAN réellement de
confiance et isolé. Une copie de Compose sur un réseau partagé, ou une
exposition involontaire des ports, rendrait l'application et Redis accessibles
sans la protection applicative optionnelle.

**Correction.** Conserver le mode LAN si c'est le besoin, mais ne plus publier
Redis par défaut, fournir les identifiants PostgreSQL via variables
obligatoires et ajouter un profil explicite `lan-insecure`. Le profil exposé
doit imposer `SECURITY_ENABLED=true`, des secrets forts et TLS via le proxy.

### AUD-05 — Élevé — L'artefact Python installable ne déclare aucune dépendance runtime

**Preuve.** Le projet Hatch construit le package `app`, mais
`pyproject.toml` contient `dependencies = []`. Docker installe correctement
`requirements-runtime.lock`, mais `pip install` de la wheel seule ne peut pas
installer FastAPI, SQLModel, Alembic ou les bibliothèques de protocoles.

**Impact.** Le conteneur est reproductible, pas nécessairement l'artefact
Python publié. Un utilisateur de la wheel obtient un package incomplet.

**Correction.** Déclarer les dépendances runtime dans les métadonnées du
package ou déclarer explicitement que seule l'image Docker est distribuée et
ne pas publier de wheel. Ajouter un test qui installe la wheel dans un
environnement vierge.

### AUD-06 — Moyen — Version et contrats de livraison ne sont pas uniques

**Preuve.** `pyproject.toml` annonce `2.0.2`, tandis que `package.json`
annonce `1.1.0`. Le README annonce le premier produit ; les contrôles frontend
affichent le second.

**Impact.** Les artefacts, tickets et diagnostics peuvent référencer des
versions différentes pour la même livraison.

**Correction.** Définir une source de version unique, la propager au package
frontend et la vérifier en CI.

### AUD-07 — Moyen — Frontend sain mais budget JavaScript presque épuisé

**Preuve.** Les 72 tests frontend passent et les 68 assets sont référencés,
mais le contrôle mesure 419 597 / 430 080 octets de JavaScript (97,6 %) et
226 586 / 245 760 octets de CSS (92,2 %).

**Impact.** Une fonctionnalité normale peut faire échouer la CI ou pousser à
relever artificiellement le plafond. Les workspaces lourds restent coûteux à
charger et à faire évoluer.

**Correction.** Mesurer les assets par écran, scinder les workspaces les plus
gros et retirer le code commun inemployé. Ne pas relever les budgets sans une
mesure d'usage réelle.

### AUD-08 — Moyen — Des modules centraux restent trop volumineux

**Preuves.** Exemples mesurés : `routers/scenarios.py` (1 577 lignes),
`services/transport_inbound.py` (1 368), `services/hprim/hprim_xml.py`
(1 336), `services/mfn_structure.py` (1 313) et `services/scenario_play_service.py`
(1 092). Le code compte aussi 484 `except Exception` ou `except:`.

**Impact.** Les changements de protocoles, persistance et rendu partagent des
unités difficiles à relire et à tester. Un traitement trop générique des
exceptions peut masquer des erreurs de configuration ou d'intégrité.

**Correction.** Continuer les extractions par cas d'usage : parsing,
validation, résolution de contexte, transaction, émission et présentation.
Remplacer les captures génériques sur les chemins critiques par des erreurs
attendues et journalisées avec contexte.

### AUD-09 — Moyen — Certains calculs d'exploitation chargent les données en mémoire

**Preuve.** Le dashboard analytics charge les lits puis les dossiers avec
`.all()` et calcule occupation, DMS et périodes en Python. L'analyse statique
trouve 484 occurrences de `.all()` dans routeurs et services ; toutes ne sont
pas problématiques, mais cette page a déjà un périmètre non borné.

**Impact.** Les tableaux de bord deviennent plus lents et plus consommateurs
de mémoire avec l'historique patient réel.

**Correction.** Déplacer agrégats, comptages et filtres de période vers SQL,
limiter les exports/listes et ajouter un test de budget de requêtes sur un jeu
de données représentatif.

### AUD-10 — Faible à moyen — Limites fonctionnelles explicites à arbitrer

**Preuves.**

- `HprimXmlGenerator.generate_etat_patient()` porte encore un TODO de contenu
  selon les spécifications ; il ne doit pas être présenté comme une couverture
  HPRIM exhaustive.
- La validation contre le référentiel CCAM officiel est marquée TODO.
- La génération ADT A08 est explicitement désactivée en mode PAM FR strict.

**Impact.** Ce ne sont pas des défauts si ces flux ne font pas partie du
périmètre contractuel, mais ils doivent être visibles dans la matrice de
compatibilité et dans les recettes partenaires.

**Correction.** Décider pour chaque capacité : supporter et qualifier, ou
masquer/documenter comme non supportée dans l'IHM et l'OpenAPI.

### AUD-11 — Faible — Dépôt et tests historiques encore lourds

**Preuves.** Le pack Git pèse 232,61 Mio ; le checkout contient de nombreux
artefacts de scénarios (bases SQLite de 12 à 18 Mio), et `ruff check app tests`
relève 504 écarts majoritairement dans des tests historiques/générés.

**Impact.** Clones, CI et lecture de la qualité sont plus coûteux. Le signal du
lint global est noyé, même si le lint applicatif est plus strict.

**Correction.** Publier les artefacts de qualification comme artefacts CI avec
checksum, conserver de petits échantillons déterministes dans Git et isoler
ou nettoyer progressivement les tests historiques.

## Points forts observés

- Fonction clone GHT testée : structure, configurations de scénarios et
  endpoints sont dupliqués ; les cibles FHIR sont remplacées par l'URL de la
  nouvelle version connectée.
- Migrations fraîches et tests ciblés associés : 8 succès.
- Compose se valide sans `.env` résiduel.
- Contrôles de syntaxe Python et de budget de taille réussis.
- Chaîne frontend structurée : lint, tests Node, inventaire d'assets et budgets.
- La sécurité peut être activée sans changer le code ; le mode ouvert reste un
  choix explicite pour le LAN.

## Plan recommandé

### Priorité 0 — Rétablir une branche livrable

1. Corriger le chargement JWT lorsque `SECURITY_ENABLED=false` et ajouter le
   test de démarrage LAN.
2. Centraliser la construction Jinja2 et réparer la page analytics.
3. Corriger Ruff et les deux routes async/SQL.
4. Relancer `pytest -q tests/unit tests/integration`, Ruff, les garde-fous et
   le contrôle frontend jusqu'à obtention d'une branche entièrement verte.

### Priorité 1 — Sécuriser les modes d'exploitation sans renier le LAN

1. Séparer clairement les profils Compose LAN et exposé.
2. Externaliser les mots de passe/ports de démonstration ; ne pas publier
   Redis par défaut.
3. Documenter et tester le passage du profil LAN au profil sécurisé.

### Priorité 2 — Livraison et pérennité

1. Unifier la version Python/npm.
2. Rendre la wheel réellement installable ou limiter officiellement la
   distribution à Docker.
3. Planifier les extractions des grands modules et les agrégats SQL.
4. Établir une matrice partenaire des fonctionnalités HPRIM/CCAM/A08.

## Conclusion

Le socle est celui d'un logiciel métier riche et industrialisé, pas celui d'un
prototype. Toutefois, les régressions AUD-01 à AUD-03 sont concrètes et
doivent être traitées avant de prétendre que la version est totalement propre.
Elles constituent un petit lot de stabilisation prioritaire ; les autres
constats peuvent ensuite être planifiés selon le volume, les partenaires et le
mode réel de déploiement.

## Suivi de mise en œuvre — 26 septembre 2026

Les corrections directement réalisables ont été appliquées après cet audit :

| Audit | Mise en œuvre |
|---|---|
| AUD-01 | La résolution JWT accepte désormais le mode LAN sans authentification. Un test vérifie l'import de l'application sans `JWT_SECRET_KEY`. |
| AUD-02 | `app.templates` fournit un environnement Jinja2 unique, adopté par tous les routeurs qui rendaient auparavant leurs propres templates. La page Analytics et son API KPI sont couvertes. |
| AUD-03 | Ruff repasse sur `app` et les deux routes d'administration SQLModel sont synchrones ; le garde-fou async/SQL repasse. |
| AUD-04 | Compose explicite le profil LAN, n'expose plus Redis et ajoute `docker-compose.exposed.yml`, qui impose les secrets et l'authentification hors LAN. |
| AUD-05 | Les dépendances runtime sont maintenant des métadonnées PEP 621 valides ; une wheel `2.0.2` est constructible et déclare notamment FastAPI, SQLModel, Alembic et Psycopg. |
| AUD-06 | La version npm/package-lock est alignée sur `2.0.2`. |
| AUD-09 | Les KPI et les exports Analytics comptent lits, séjours et DMS par requêtes SQL agrégées au lieu de charger les dossiers complets. |
| AUD-07 | Le contrôle frontend mesure désormais chaque template avec ses scripts partagés et bloque tout écran dépassant 128 Ko de JavaScript produit. Le maximum courant est de 117 096 octets. |
| AUD-08 | La revue du créateur de scénarios est extraite dans son propre routeur, distinct du catalogue et des campagnes. Les budgets de taille empêchent toute nouvelle dérive pendant les extractions suivantes. |
| AUD-10 | Une matrice de capacités explicite le périmètre partenaire. L'émission HPRIM « état patient » refuse désormais explicitement le traitement au lieu de produire un XML vide non qualifié. |
| AUD-11 | Les corrections sûres de Ruff ont été appliquées aux tests et les règles de style historiques restantes sont isolées aux tests. Les rapports binaires générés sont ignorés et celui qui était versionné est retiré au profit des artefacts CI. |

Le découpage des très gros modules reste un chantier d'amélioration continue :
les gros modules sont fonctionnels et couverts, mais l'extraction par domaines
doit progresser sans changer les contrats de protocoles. Le contrôle de taille
refuse d'ores et déjà toute nouvelle route de plus de 2 000 lignes ou fonction
de plus de 500 lignes.
