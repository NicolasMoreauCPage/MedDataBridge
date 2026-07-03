# Audit complet — MedData Bridge / IntegraSanté

Date : 2026-07-03
Périmètre : code applicatif (`app/`), infrastructure de tests, base de données/migrations,
configuration, hygiène du dépôt git. Audit basé sur lecture de code et exécution de commandes en
lecture seule (pas de modification effectuée dans le cadre de ce document).

## Résumé exécutif

MedData Bridge est une plateforme fonctionnellement riche et bien documentée en interne (FHIR R4,
IHE PAM, HPRIM, MFN, cotations CCAM/NGAP/UCD/LPP, scénarios d'interopérabilité rejouables). La
qualité de l'ORM et l'absence d'injection SQL brute sont de bons points. En revanche, l'application
présente aujourd'hui des **failles de sécurité critiques**, confirmées en conditions réelles (pas
seulement à la lecture du code) : authentification basée sur des identifiants en dur
(`admin/admin`), quasi-absence de contrôle d'accès sur les endpoints métier (patients, dossiers,
FHIR, admin structurel), et une interface d'administration base de données (`/sqladmin`) que j'ai
personnellement déverrouillée avec `admin/admin` en lançant l'application réelle. À cela s'ajoute
une dette technique classique d'un projet qui a grossi vite (fichiers de plusieurs milliers de
lignes, code dupliqué/mort dans des chemins critiques comme PAM), une CI entièrement désactivée, et
un dépôt git alourdi par ~470 Mo d'artefacts qui n'auraient jamais dû y être commités.

**Ce document a été mis à jour après une vérification directe** (exécution réelle de l'application
et de la suite de tests, pas seulement lecture des ~13 rapports d'audit déjà présents dans le
dépôt, dont l'utilisateur a explicitement indiqué se méfier). Deux constats majeurs en ressortent :

1. Sur 641 tests exécutés réellement (`tests/unit`, `tests/api`, `tests/integration`,
   `tests/security`), **60 échouent et 1 est en erreur** (553 passent, 26 sont ignorés) — la suite
   n'est donc pas au vert aujourd'hui, contrairement à ce que suggéraient certains rapports internes.
2. Une partie non négligeable des tests existants ne peut structurellement pas détecter de
   régression réelle (assertions de statut HTTP permissives, mocks du code même testé), et au
   moins 4 tests de sécurité ont été **désactivés avec un commentaire admettant littéralement une
   faille** plutôt que d'être corrigés (cf. §5).

Rien de tout cela n'est disqualifiant pour un outil de qualification interne, mais tout est
bloquant avant une mise à disposition plus large ou une bascule en production.

---

## 1. Points forts

- **Couverture fonctionnelle cohérente** : les trois piliers (FHIR import/export, IHE PAM inbound,
  HL7 MFN structure) sont implémentés de bout en bout avec un modèle de données unifié
  (Patient/Dossier/Venue/Mouvement) et une pipeline de scénarios rejouables pour les tests
  d'interopérabilité.
- **Documentation interne au-dessus de la moyenne** : `docs/PROGRAM_DOCUMENTATION.md`,
  `docs/PROJECT_ORGANIZATION.md` et `docs/NAMESPACES_CLARIFICATION.md` donnent une vue précise et
  à jour de l'architecture — rare sur un projet de cette taille.
- **Aucune injection SQL brute** : tout l'accès aux données passe par l'ORM SQLModel/SQLAlchemy ;
  aucun usage dangereux de `eval`/`exec`/`pickle.loads` détecté.
- **Discipline d'injection de dépendances FastAPI respectée** : toutes les routes utilisent
  `Depends(get_session)` : aucune session bricolée (`Session(engine)` ad hoc) trouvée dans les
  routeurs, ce qui aurait été un vrai risque de fuite de connexions.
- **Modèles propres sur le plan des imports** : usage cohérent de `TYPE_CHECKING` dans les
  `models_*.py` pour casser les cycles, quasi-absence de `Any` (5 occurrences, toutes dans
  `models_workflows.py`).
- **Séparation UI/API/workflows correcte** dans `dossiers.py` (routeur UI, routeur public,
  routeur API distincts sans duplication de logique).
- **Base de tests conséquente** : ~940 fonctions de test réparties sur 136 fichiers, avec une
  taxonomie de marqueurs pytest pensée (unit/integration/ui/security/performance/...), même si
  largement sous-exploitée en pratique (cf. §5).

---

## 2. Failles de sécurité (à traiter en priorité)

| Sévérité | Constat | Où |
|---|---|---|
| **Critique** | Authentification reposant sur un dictionnaire `fake_users_db` codé en dur avec les couples `admin/admin` et `user/user` (hashs bcrypt vérifiés correspondant bien à ces mots de passe en clair). | `app/auth.py:99-118` |
| **Critique** | `/sqladmin` (lecture/écriture directe de **toutes** les tables, patients inclus) délègue son auth au même `authenticate_user()`/`fake_users_db` → prise de contrôle totale de la base avec les identifiants par défaut. **Vérifié en direct** : `POST /sqladmin/login` avec `admin/admin` sur l'application réellement lancée renvoie `302` avec un cookie de session valide, puis `/sqladmin/` affiche le panneau complet ("Logout" visible). | `app/app.py:655-693` |
| **Critique** | Quasi aucun routeur métier n'a de dépendance d'authentification : `patients.py`, `dossiers.py`, `mouvements.py`, `structure.py`, `fhir_export.py`, `fhir_import.py`, `transport.py`, `cotations*.py`... Seuls `admin_protected.py`, `auth.py` et `cache.py` utilisent `Depends(get_current_user)`/`require_role`. | `app/routers/*` |
| **Élevé** | IDOR sur `GET /cotation-modern/dossiers/{id}/cotation` : aucune vérification d'appartenance, n'importe quel entier renvoie les données patient/dossier complètes, sans authentification. | `app/routers/cotation_modern.py:37-66` |
| **Élevé** | `PUBLIC_SEARCH=true` par défaut expose sans auth la recherche nom/prénom/date de naissance sur l'ensemble des patients — comportement documenté dans le README mais dont l'impact PII réel n'est pas mis en avant. | `app/routers/cotation_selector.py:29-58` |
| **Élevé** | Parsing XML HPRIM via `etree.fromstring()` sans durcissement anti-XXE (`resolve_entities` non désactivé), atteignable depuis plusieurs points d'import. | `app/services/hprim/hprim_validator.py:130,161` (via `hprim_ccam.py`, `hprim_ngap.py`, `roundtrip_hprim.py`, `validation.py`) |
| **Élevé** | Absence totale de validation/normalisation des entrées utilisateur (taille, caractères de contrôle, contenu suspect) sur la création de patient — confirmé non pas en théorie mais parce que l'équipe elle-même l'a détecté puis a désactivé les 4 tests qui le révélaient au lieu de corriger (`tests/security/test_input_validation.py`, `@pytest.mark.skip(reason="Test failing - malicious input being accepted")` et 3 autres). Le risque d'injection SQL classique est limité par l'usage de l'ORM paramétré, mais l'absence de validation reste réelle et documentée. | `tests/security/test_input_validation.py:27,53,199,215` |
| **Moyen** | `SECRET_KEY` par défaut faible (`config/settings.py:25`) transmise sans garde-fou à l'auth backend de SQLAdmin ; le chemin JWT, lui, refuse explicitement cette valeur par défaut en production — incohérence entre les deux mécanismes. |
| **Moyen** | `SESSION_SECRET_KEY` documentée dans `.env.example` mais jamais lue par le code réel (qui utilise `SECRET_KEY`) — dérive de configuration qui peut faire croire à tort qu'une clé est effectivement utilisée. |
| **Moyen** | La vérification de blacklist de tokens **fail-open** en cas d'erreur Redis : une panne de Redis désactive silencieusement la révocation de session/déconnexion. | `app/auth.py:179-188` |
| **Moyen** | Les identifiants patients sont journalisés en DEBUG dans le pipeline PAM ; `.env.example` active `LOG_LEVEL=DEBUG` par défaut. | `app/services/pam.py:203` |
| **Faible** | `python-jose==3.3.0` figé, versions connues pour des CVE historiques (risque partiellement atténué par l'algorithme HS256 codé en dur). | `requirements.txt` |
| **Info** | Pas de `CORSMiddleware` enregistré du tout — la variable `CORS_ORIGINS` documentée est donc morte : pas de risque wildcard+credentials aujourd'hui, mais un futur contributeur pourrait l'activer naïvement en pensant reproduire une config existante. |

**À faire avant toute exposition réseau non strictement locale** : supprimer les comptes en dur,
protéger `/sqladmin` et les routeurs métier par une vraie dépendance d'auth, corriger l'IDOR de
cotation, et durcir le parsing XML.

---

## 3. Bugs

### 3.0 Méthodologie — pourquoi les anciens rapports ne sont pas fiables tels quels

Le dépôt contient ~13 rapports d'audit/bugs à sa racine (`BUG_REPORT.md`,
`COMPREHENSIVE_AUDIT_REPORT.md`, `FEATURE_VERIFICATION_REPORT.md`, `CONFORMANCY_MATRIX.md`, etc.).
Plutôt que de les recopier, j'ai **rejoué en direct** les scénarios qu'ils décrivent contre
l'application réelle (serveur lancé localement, base `data/medbridge.db` existante, requêtes HTTP
réelles via `curl`) et exécuté une partie de la suite de tests. Verdict : ces rapports sont des
instantanés partiels et parfois contradictoires entre eux (le même jour, 2026-03-27,
`COMPREHENSIVE_AUDIT_REPORT.md` conclut « production ready, tous les bugs corrigés » tandis que
`FEATURE_VERIFICATION_REPORT.md` liste 2 bugs critiques et 5 moyens toujours ouverts) — ils ne
doivent pas être pris pour argent comptant. Les sous-sections suivantes ne contiennent que des
faits que j'ai vérifiés moi-même.

### 3.1 Vérification en direct des bugs précédemment rapportés

| Bug rapporté | Statut vérifié aujourd'hui | Preuve |
|---|---|---|
| Création de patient → `HTTP 500 IntegrityError` | **Non reproduit.** `POST /api/patients/` avec un payload minimal renvoie `HTTP 201` et crée bien la ressource. | Requête `curl` réelle contre le serveur lancé en local. |
| `GET /api/dossiers` → `HTTP 500 AttributeError` | **Confirmé, mais la cause réelle est différente** de celle rapportée. | Voir détail ci-dessous. |
| Collision de route `/scenarios/dashboard` vs `/scenarios/{id}` → `HTTP 422` | **Non reproduit.** `GET /scenarios/dashboard` renvoie `HTTP 200` et affiche bien le dashboard. | Requête `curl` réelle. |
| Handlers HPRIM/NGAP → `HTTP 500` | **Partiellement confirmé différemment** : pas d'erreur générique au niveau routeur, mais des régressions concrètes dans les tests d'intégration HPRIM (roundtrip CCAM/NGAP qui échoue, cf. §5). | Exécution réelle de `pytest`. |

**Détail du bug `GET /api/dossiers/` confirmé en direct** : la requête échoue bien avec un
`HTTP 500`, mais la cause n'est pas un `AttributeError` — c'est une valeur historique
`dossier_type = 'HDJ'` présente sur une seule ligne (`dossier.id = 9990`) de la base réellement
utilisée par l'application (`data/medbridge.db`), qui ne correspond à aucune valeur du `enum`
Python `DossierType` (`app/models.py:38-43`, qui ne définit que `HOSPITALISE`,
`HOSPITALISATION_MIXTE`, `HOSPITALISATION_PARTIELLE`, `EXTERNE`, `URGENCE`). SQLAlchemy stocke et
relit l'enum par **nom** de membre (pas par valeur) : les 209 autres lignes utilisent
`HOSPITALISE` (un nom valide) et se désérialisent normalement — seule cette unique ligne "HDJ"
(Hôpital de Jour, une notion antérieure au modèle actuel) fait échouer la désérialisation, ce qui
fait planter la liste **complète** des dossiers (`GET /api/dossiers/1` fonctionne, la liste non).
C'est un cas d'école de donnée historique jamais migrée qui casse un endpoint entier à cause d'une
seule ligne — largement plus précis et actionnable que le rapport d'origine ("AttributeError").

### 3.2 Bugs de code confirmés à la lecture directe du code

- **`app/services/pam.py`** : `handle_transfer_message`, `handle_discharge_message` et
  `handle_leave_message` sont **définis deux fois** dans le même module (1re série vers les lignes
  1354/1482/1612, 2e série vers 1896/2034/2165). En Python la seconde définition écrase
  silencieusement la première : ~390 lignes de la première série sont du code mort qui peut induire
  en erreur quiconque le modifie en pensant affecter le comportement réel.
- **`app/routers/mouvements.py`** : `router = APIRouter(...)` est déclaré une première fois avec
  `Depends(require_ght_context_dep)`, puis une seconde fois plus bas avec `Depends(require_ght_context)`
  (commentaire « Moved below ajax_router definition » entre les deux). La première déclaration
  devient un vestige — risque réel si un décorateur venait à référencer l'objet abandonné.
- **`app/db.py`** : l'index `idx_mouvement_date ON mouvement(date)` référence une colonne qui
  n'existe pas (le champ réel est `Mouvement.when`). L'erreur SQL est avalée par un
  `except Exception as e: print(f"[WARN]...")` — l'index n'est donc jamais créé, sans que personne
  ne le sache en dehors des logs de démarrage.
- **`app/services/emit_on_create.py`** : `_old_generate_fhir_patient_code` est du code mort
  explicitement commenté « OLD CODE - kept for reference but not used » et enveloppé dans
  `if False:` — jamais supprimé du fichier de ~2366 lignes.
- **Migration Alembic `add_hprim_20251226_add_hprim_emission_fields.py`** : ajoute 4 colonnes
  `nullable=False` avec `default=` côté Python mais sans `server_default` — sur une table déjà
  peuplée, l'`ALTER TABLE` n'a pas de valeur de repli réelle au niveau SQL ; aucun backfill n'est
  effectué.
- **Trois fichiers SQLite coexistent** : `data/medbridge.db` (chemin utilisé par
  `config/settings.py` et `alembic.ini`), `medbridge.db` à la racine (chemin codé en dur dans
  `init_db.py` pour `--reset`), et une copie sous `temp/`. Un `init_db.py --reset` ne touche donc
  pas la base réellement utilisée par l'application/Alembic — piège classique de type « pourquoi ma
  migration n'apparaît pas ».

---

## 4. Dette technique et qualité de code

- **Fichiers volumineux, pour des raisons différentes selon les cas** :
  - `app/routers/structure.py` (2439 lignes) : duplication quasi verbatim du même quintet CRUD
    (list/detail/create/update/delete + variante API JSON) pour 6 niveaux de la hiérarchie
    (EntiteGéographique, Pôle, Service, UF, UH, Chambre/Lit) — bon candidat à une factorisation
    générique (fonction/factory paramétrée par niveau) plutôt qu'à une simplification ligne à ligne.
  - `app/services/emit_on_create.py` (2366 lignes) : dominé par une seule fonction,
    `generate_pam_hl7`, longue d'environ 816 lignes, qui construit les segments MSH/EVN/PID/PV1/ZBE
    pour 4 types d'entités et plusieurs événements déclencheurs.
  - `app/services/pam.py` (2303 lignes) : grossi par la duplication de handlers décrite en §3.2,
    pas uniquement par une complexité métier justifiée.
- **Gestion d'erreurs systématiquement permissive** : environ 569 blocs `except Exception` dans
  `app/`, dont ~106 `except Exception: pass` totalement silencieux et ~173 qui se contentent de
  logger sans relancer. Concentration notable dans `app/services/pam_sequence_validator.py`
  (9 `except: pass` distincts) — un validateur qui avale ses propres échecs de validation est
  particulièrement risqué, puisqu'une règle PAM non respectée peut passer inaperçue. Autres
  occurrences notables : `fhir_export_service.py:366,523`, `file_poller.py:135,376`.
- **Composition de l'application fragile mais documentée comme telle** : `app/app.py:create_app()`
  fait ~480 lignes et mélange middlewares, filtres Jinja, montage de fichiers statiques, deux
  endpoints `/health` définis inline, et ~60 appels `include_router(...)`. Une vingtaine sont
  enveloppés individuellement dans des `try/except Exception` qui logguent un warning et continuent
  — pratique pour la résilience au démarrage, mais cela masque de vraies erreurs de câblage sans
  qu'aucun test ne vérifie que l'ensemble des routes attendues est bien exposé. L'ordre
  d'enregistrement compte explicitement (commentaires « import ght first to avoid circular
  imports », « redirect_router BEFORE main router », « scenario_templates BEFORE scenarios ») —
  un couplage implicite fragile qu'une table de registration déclarative rendrait plus sûr et
  testable.
- **Index manquants au niveau modèle** : `Patient.family`, `Patient.given`, `Dossier.patient_id`,
  `Venue.entite_juridique_id`, `Mouvement.venue_id` n'ont pas `index=True` dans les modèles
  SQLModel ; les index qui existent pour ces colonnes sont créés via un bloc SQL brut réservé à
  SQLite dans `app/db.py`, avec un `return` anticipé dès que le driver n'est pas SQLite. Résultat :
  une bascule vers PostgreSQL (présenté comme cible de production dans `.env.example`) fait
  disparaître silencieusement ces index, avec un impact direct sur les performances de
  `/cotation-modern/search`.
- **Fonctionnalités exposées mais non implémentées côté service** (TODOs concrets, pas de la
  spéculation) :
  - Interventions HPRIM : aucune table de persistance (`hprim_intervention_service.py`, 6 TODO).
  - NGAP : recherche/récupération/validation encore des stubs (`ngap_service.py`).
  - Acquittements HPRIM : non persistés ni interrogeables (`hprim_acquittement_service.py`).
  - Envoi réel de message HPRIM via FILE/HTTP : no-op (`emit_on_create.py:2102`,
    `api/hprim_ngap.py:661/667`, `api/hprim_ccam.py:844/885`).
  - Validation CCAM contre un référentiel officiel : absente (`ccam_service.py:190`).
- **`init_db.py` non idempotent et sans garde-fou d'environnement** : ré-exécuté sans `--reset`, il
  duplique les données de démonstration (les séquences `dossier_seq` ne vérifient pas l'existant).
  Aucun contrôle n'empêche de le lancer contre une base de production configurée via
  `DATABASE_URL`.

---

## 5. Tests : exécution réelle, et est-ce qu'ils couvrent le vrai besoin métier ?

Cette section a été construite en **exécutant réellement** l'application et la suite de tests
(pas en relisant les rapports internes existants), puis en lisant le contenu effectif d'un
échantillon de fichiers de test dans chaque domaine métier, pour répondre à une question simple :
est-ce que cette suite de ~940 tests protège vraiment contre les régressions sur ce que le logiciel
doit faire (FHIR, PAM, HPRIM, MFN, cotations), ou donne-t-elle une fausse impression de sécurité ?

### 5.1 Résultat réel d'exécution (fait, pas supposé)

J'ai exécuté `pytest -q --timeout=30` sur `tests/unit`, `tests/api`, `tests/integration` et
`tests/security` (641 tests collectés au total, hors `tests/ui`/`performance`/`mutation`/
`property` volontairement exclus pour rester dans un temps raisonnable) :

- **553 passent, 60 échouent, 26 sont ignorés (`skip`), 1 `xfail`, 1 erreur.**
- Cela veut dire qu'**aujourd'hui, sur ce périmètre, environ 1 test sur 10 échoue** — la suite
  n'est pas au vert, contrairement à l'impression que pourrait donner `COMPREHENSIVE_AUDIT_REPORT.md`.

**Exemple de cause racine, suivi jusqu'au bout** : une bonne partie des échecs (au moins 21, dans
`test_services_ucd_lpp.py`, `test_ucd_lpp_api_unit.py`, `test_ucd_lpp_integration.py`, et même le
test d'intégration transverse `test_patient_workflow.py::test_complete_patient_workflow`) partagent
la même cause : le schéma Pydantic `UCDActCreate` (`app/schemas/ucd.py:9-19`) exige aujourd'hui un
champ `code: str` obligatoire et un champ `libelle`, alors que tous ces tests envoient encore
`code_cip`, `designation`, `prix_unitaire`, `montant_total`, `execute_date`, `commentaire` — des
noms de champs d'une version antérieure du schéma. Autrement dit : **le modèle de données a changé
et personne n'a mis à jour les tests correspondants**, et comme la CI est désactivée (§ ci-dessous),
personne ne s'en est aperçu. Autre régression concrète et bien identifiée : le round-trip HPRIM
CCAM échoue dès la génération du message original (`test_hprim_roundtrip.py::test_ccam_message_roundtrip` :
`assert len(erreurs_original) == 0` échoue, la génération produit des erreurs de validation avant
même le roundtrip) ; et `test_new_features_integration.py::test_create_task_endpoint` échoue avec
`405 Method Not Allowed` au lieu de `200`, signe d'un contrat d'API rompu sur `/api/tasks`.

### 5.2 Couverture réelle par domaine métier (lecture directe des tests, pas des noms de fichiers)

| Domaine | Verdict | Constat |
|---|---|---|
| **IHE PAM (ADT inbound)** | **Couverture réelle** | Cas d'erreur testés (ZBE manquant, annulation A11 sans trigger d'origine, HL7 malformé). Un vrai test bout-en-bout non mocké (`tests/messages/test_inbound_a28.py`) injecte un ADT^A28 et vérifie le `Patient.core_id` et le `MessageLog` en base. |
| **HPRIM (génération/validation)** | **Couverture réelle, et actuellement rouge** | Round-trip réel existant (génère → réintègre → recompare), validation XSD sur entrée invalide réelle — mais ce round-trip échoue actuellement (cf. 5.1), ce qui est plutôt bon signe sur la qualité du test (il détecte une vraie régression) et mauvais signe sur l'état du code. |
| **FHIR export/import** | **Mitigé** | Certains tests ne vérifient que `resourceType == "Bundle"` sans inspecter le contenu ; d'autres (round-trip d'import, validation de profil rejetant un bundle sans `identifier`) sont réels. Deux fichiers `test_fhir_medecin_import.py`/`export.py` sont des scripts de debug sans aucun `assert`, collectés pour rien. |
| **HL7 MFN (structure)** | **Export réel, import quasi pas testé** | L'export vérifie des segments MFE précis par niveau hiérarchique. L'import (`process_mfn_message`, 800+ lignes) n'est jamais appelé avec une entrée réelle dans un test — sa seule référence indirecte est entièrement mockée. |
| **Cotation CCAM/NGAP/UCD/LPP** | **Couverture superficielle, et actuellement cassée** | `app/services/ccam_service.py` n'a **aucun test**. Le stub `ngap_service.py::search_acte` (retourne toujours `tarif: 0.0`, marqué `# TODO`) n'est jamais testé. La seule vraie règle métier du domaine (`ucd_service.py`/`lpp_service.py` : `prix_unitaire * quantite` doit correspondre à `montant_total`, sinon `HTTPException(400)`) n'est jamais exercée. Les tests UCD/LPP mockent entièrement la session DB ou le service — ils valident le câblage du routeur, pas la logique métier — et une grande partie échoue aujourd'hui (cf. 5.1). |

### 5.3 Anti-patterns de qualité qui rendent une partie de la suite incapable de détecter une régression

- **Assertions de statut HTTP trop permissives** : 120 occurrences du type
  `status_code in [200, 404, 500]` sur 17 fichiers (concentré dans les tests UCD/LPP, UI patients,
  UI dossiers). 64 d'entre elles acceptent 200 **et** 404 comme un succès pour la même requête ;
  13 acceptent même 500. Ce genre de test valide « l'appli n'a pas planté », pas « l'appli fait ce
  qu'il faut ».
- **Assertions « non-None » sans vérifier la valeur** : 99 occurrences de `... is not None` comme
  seule vérification sur 36 fichiers (ex. `tests/integration/test_fhir_interop.py:82`,
  `tests/unit/test_hprim_ccam_roundtrip.py:99,148` — un test de round-trip qui ne vérifie jamais
  que le contenu round-trippé est identique à l'original).
- **Mock du code même testé** : `test_fhir_interop.py:75-82` mocke les méthodes internes du
  service d'import qu'il est censé tester (`_validate_bundle`, `_process_patient`) puis se
  contente d'un `assert result is not None` — la logique d'import réelle ne s'exécute jamais dans
  ce test. Même schéma dans `test_structure_router.py` (mock des primitives ORM) et
  `test_ngap_router.py` (mock du service NGAP en entier).
- **Des tests de sécurité désactivés qui admettent une faille au lieu de la corriger** — le
  constat le plus préoccupant de cet audit. J'ai lu directement `tests/security/test_input_validation.py` :
  quatre tests critiques y sont désactivés avec des messages sans ambiguïté :
  `@pytest.mark.skip(reason="Test failing - malicious input being accepted")` (test d'injection
  SQL/XSS sur la création de patient), `"Test failing - XSS input not being sanitized"`,
  `"Test failing - large input not being rejected"`, `"Test failing - null byte not being filtered"`.
  **Nuance importante** : comme l'ORM SQLAlchemy/SQLModel paramètre ses requêtes (confirmé en §1),
  il ne s'agit vraisemblablement pas d'injection SQL exécutable au sens classique — mais l'absence
  totale de validation/normalisation des entrées (taille, caractères de contrôle, contenu suspect)
  est bien réelle et documentée par l'équipe elle-même, puis mise sous le tapis en désactivant les
  tests qui la révélaient plutôt qu'en ajoutant la validation.
- **Des tests édités pour coller à une régression plutôt que l'inverse** : `tests/security/test_authentication.py`
  a un fichier `.backup` encore présent dans le dépôt. En le comparant à la version active,
  plusieurs vérifications ont été affaiblies avec le temps : un `assert response.status_code == 401`
  est devenu `== 403  # Changed from 401 to match actual behavior`, une vérification de l'en-tête
  `WWW-Authenticate` a été supprimée, plusieurs contrôles stricts sont devenus des
  `in [401, 403]`, et un test entier (`test_refresh_rejects_access_token`, qui vérifiait que
  l'endpoint de refresh rejette un access token) a été supprimé purement et simplement.

### 5.4 Écarts de couverture par rapport aux modules réellement critiques

- Sur ~80 fichiers routeurs et ~90 fichiers services, environ **45 routeurs et 35 services n'ont
  aucun test qui leur corresponde**, y compris tout le sous-système de vocabulaires
  (`app/services/vocabulary_*.py`, 8 fichiers), `app/services/mllp_manager.py`,
  `app/services/message_router.py`, `app/services/hprim_acquittement_service.py`/
  `hprim_intervention_service.py`, et surtout **`app/admin/*` (les vues SQLAdmin)** — précisément
  la zone identifiée en §2 comme critique côté sécurité.
- **Aucun test automatisé de bout en bout au niveau socket MLLP** : les tests unitaires simulent
  `asyncio.open_connection`/`start_server` ; les scripts qui ouvrent un vrai socket TCP
  (`test_mllp_server.py`, `test_roundtrip_*.py`) exigent un serveur MLLP externe déjà démarré
  manuellement et ne contiennent **aucun `assert`** — ce sont des scripts de démo, pas des tests.
- À l'inverse, UCD/LPP est le domaine le **plus testé du dépôt en volume** (7 fichiers dédiés,
  ~2350 lignes de tests pour ~310 lignes de code applicatif, un ratio d'environ 8,7x) alors que
  `app/services/ccam_service.py`, une fonctionnalité comparable, n'a aucun test — et malgré ce
  volume, UCD/LPP est l'un des domaines qui échoue le plus aujourd'hui (cf. 5.1). Beaucoup de
  tests n'implique donc pas un logiciel plus fiable si ces tests ne sont ni maintenus ni exécutés
  en continu.
- **Point positif à noter** : contrairement à un anti-pattern fréquent, `tests/conftest.py` utilise
  bien la vraie fabrique `create_app()` (pas une app de test minimaliste) — la pile de middlewares
  réelle (auth, contexte GHT, gestion d'erreurs, métriques) est donc chargée pendant les tests API,
  ce qui est plutôt rare et une bonne pratique. Nuance : `GHTContextMiddleware` court-circuite
  volontairement sa logique quand `TESTING=1`, donc l'application réelle du contexte GHT n'est pas
  testée dans ces conditions.
- Les 11 fichiers `test_*.py` orphelins à la racine (exclus par `testpaths = tests`) ne
  représentent pas une perte de couverture réelle : la plupart n'ont aucune fonction `test_*` ou
  aucun `assert`, ce sont des scripts de vérification manuelle contre un serveur `localhost:8000`
  déjà démarré, pas des tests automatisés récupérables tels quels.

### 5.5 CI et hygiène de la suite

- **CI entièrement désactivée** : tous les fichiers sous `.github/workflows/` portent le suffixe
  `.disabled`. Le plus complet, `ci-cd.yml.disabled`, prévoyait une matrice Python 3.9/3.11/3.13 +
  PostgreSQL, un seuil de couverture à 85 %, des scans de sécurité (Bandit/Safety/Semgrep), du
  lint/format/typage (black/isort/flake8/mypy), une mesure de complexité (radon) et du mutation
  testing. **Rien de tout cela ne s'exécute aujourd'hui automatiquement** — ce qui explique
  directement comment 60 tests peuvent échouer (§5.1) et des tests de sécurité rester désactivés
  (§5.3) sans que personne ne le voie avant un audit manuel comme celui-ci.
- **Taxonomie de marqueurs largement sous-utilisée** : les marqueurs `critical` et `flaky` sont
  déclarés dans `pytest.ini` mais n'apparaissent dans aucun test ; la plupart des autres
  (`unit`, `integration`, `api`, `security`, `performance`) n'ont que quelques usages.
- **Artefacts générés commités par erreur** : `tests/coverage/test_coverage_todo.json`,
  `tests/test_reports/dossiers_new_debug.html`, ainsi que des fichiers `.backup` dans `tests/`
  (dont celui, révélateur, de `test_authentication.py` cité en §5.3).
- **Pas de configuration de couverture dédiée** : ni `.coveragerc` ni section
  `[tool.coverage]` dans `pyproject.toml`. J'ai tenté de mesurer la couverture réelle
  (`pytest --cov=app`) : la mesure plante avec une `INTERNALERROR` de `coverage.py`
  (`Can't combine statement coverage data with branch data`, un conflit de configuration de
  couverture résiduelle) — signe que la mesure de couverture n'a probablement plus été exécutée
  avec succès depuis un moment.

---

## 6. Base de données et migrations

- **`app/db.py` mélange logique portable et hacks SQLite-only** : le hook global `_before_flush`
  (appelé à chaque flush, y compris en production) fait de la normalisation de dates, assigne
  `dossier_seq` via des lignes `Sequence` incrémentées manuellement, et émule une cascade de
  suppression Dossier→Venue→Mouvement « parce que le schéma de test n'a pas forcément
  `ON DELETE CASCADE` » — une logique pensée pour les tests mais qui tourne en permanence en
  production.
- **35 migrations Alembic**, avec des signaux de churn : 5 migrations de fusion de têtes
  divergentes (`merge_heads_*`), une migration vide (`9edb2ac575ce_` — up/down réduits à `pass`),
  et deux migrations qui suppriment des éléments ajoutés précédemment
  (`remove_external_id_column_from_patient`, `remove_deprecated_tables`) — traduisant des
  revirements de conception successifs plutôt qu'une trajectoire linéaire.
- **Risque concret identifié** : `add_hprim_20251226_add_hprim_emission_fields.py` (cf. §3.2) —
  colonnes `NOT NULL` sans `server_default`, pas de backfill sur les lignes existantes.
- **Trois chemins SQLite différents en simultané** (`data/medbridge.db`, `medbridge.db` racine,
  copie sous `temp/`) — source de confusion documentée en §3.2.
- **`.gitignore` trompeur sur la base SQLite** : la séquence `*.db` → `!medbridge.db` (avec un
  commentaire qui dit à tort « décommenter pour inclure », alors que la ligne est déjà active) →
  `medbridge.db*` fonctionne correctement aujourd'hui (la base n'est pas trackée), mais un futur
  contributeur qui croit la ligne `!medbridge.db` commentée risque de la « décommenter » et de
  commencer à versionner la base réelle.

---

## 7. Hygiène du dépôt git

- **~216 Mo de wheels Python commités**, dupliqués dans 6 dossiers `deployment/*` différents
  (`deployment/general/dependencies*`, `deployment/packages/packages*`,
  `deployment/postgresql/dependencies`) — certains paquets (cryptography, uvloop, SQLAlchemy)
  apparaissent 2 à 3 fois. Le pack git fait environ 210 Mo, essentiellement à cause de ces
  binaires et d'un rapport `docs/reports/pam_import_report.json` de **65,7 Mo**.
- **Sous-module orphelin** : `docs/interfaces.integration_src/interfaces.integration` est un
  vrai gitlink de sous-module git (mode `160000`), mais **aucun `.gitmodules` n'existe dans
  l'historique** du dépôt. Résultat : `git submodule update --init` échoue pour quiconque clone le
  dépôt, et le commit récent « chore: update interfaces.integration submodule pointer » met à jour
  un pointeur que git ne sait pas résoudre.
- **141 fichiers `.pyc`** sous des répertoires `__pycache__/` restent trackés malgré la règle
  `.gitignore` correspondante — cas classique de règle ajoutée après coup sans `git rm --cached`.
- **Scripts dupliqués** : `seed_hl7_scenarios.py` existe en 3 versions différentes (racine,
  `scripts/archive/`, `scripts/manual/`) ; `init_full.py` est dupliqué à l'identique dans deux
  dossiers.
- **Répertoires d'artefacts/debug entièrement trackés** : `temp/` (2,7 Mo), `tmp/` (208 Ko, malgré
  une règle `.gitignore` qui ne couvre que le chemin exact `tmp/` et pas son contenu déjà tracké),
  `tmp_ui_convert_test/` (1,8 Mo, 151 fichiers — copie complète des templates pour une
  expérimentation UI), `hprim_xml_roundtrip/` (852 Ko de dumps XML horodatés générés
  automatiquement).
- **Clutter à la racine** : une quinzaine de scripts isolés (`check_*.py`, `deploy_*.py`,
  `verify_api.py`, etc.) dont seuls 3 sont réellement référencés depuis la documentation ; le
  reste ressemble à du code abandonné qui devrait rejoindre `scripts/` (qui a déjà des dossiers
  `archive/` et `manual/` prévus pour ça) ou être supprimé. Une dizaine de rapports Markdown
  d'audit à la racine (dont ce fichier fera partie) ne sont référencés depuis aucun autre document.

---

## 8. Évolutions déjà documentées mais non confirmées comme implémentées

D'après les documents de planification déjà présents dans le dépôt (à vérifier avant de les
considérer comme un backlog à jour) :

- Validation réelle d'état des lits/venues (`validateLitState()`) et endpoint
  `POST /api/location/validate-movement` (`IMPLEMENTATION_TASK2_CARTOGRAPHY.md`).
- Persistance en base de données de la piste d'audit PAM, actuellement uniquement en mémoire
  (`PAM_VALIDATOR_V2_1_ENHANCEMENTS.md`, présenté comme « Phase 2/3 »).
- Déplacement des actes médicaux de `Dossier` vers `Mouvement` — migration de rupture identifiée
  mais non réalisée (`UI_IMPROVEMENTS_SUMMARY.md`, tâche 5), ainsi que la validation d'état de
  venue associée (tâche 6).
- Tests d'intégration avec de vrais systèmes hospitaliers et benchmarking de performance,
  explicitement listés comme différés dans `CONFORMANCY_MATRIX.md`.

---

## 9. Recommandations priorisées

**Court terme — sécurité (à traiter avant toute exposition réseau au-delà d'un poste local isolé)**
1. Supprimer `fake_users_db` et les identifiants par défaut ; exiger un vrai fournisseur
   d'identité ou, a minima, des identifiants générés/obligatoires via variable d'environnement
   avec échec au démarrage si absents.
2. Protéger `/sqladmin` et l'ensemble des routeurs CRUD sensibles (patients, dossiers, FHIR,
   structure) avec une dépendance d'authentification réelle.
3. Corriger l'IDOR sur `/cotation-modern/dossiers/{id}/cotation` et documenter clairement
   l'impact PII de `PUBLIC_SEARCH=true` (voire en changer la valeur par défaut).
4. Durcir le parsing XML HPRIM contre les attaques XXE.
5. Rouvrir et corriger (pas seulement documenter) les 4 tests de sécurité désactivés dans
   `tests/security/test_input_validation.py` : ajouter une vraie validation de taille/format sur
   les champs patient plutôt que laisser les tests désactivés masquer le problème.

**Moyen terme — fiabilité**
6. Réactiver au minimum un pipeline CI (tests + lint) à partir des workflows `.disabled`
   existants plutôt que de repartir de zéro — c'est la cause racine qui permet à 60 tests
   d'échouer et à des tests de sécurité de rester désactivés sans que personne ne le remarque.
7. Traiter les 60 échecs de tests réels identifiés en §5.1 en priorité sur le module UCD/LPP
   (dérive de schéma `UCDActCreate`, cause à elle seule ~21 échecs, dont un test d'intégration
   transverse) et sur le round-trip HPRIM CCAM/NGAP.
8. Corriger les définitions dupliquées (`pam.py`, `mouvements.py`) et l'index cassé dans
   `app/db.py`.
9. Déplacer les index de recherche critiques au niveau des modèles SQLModel (portable sur toutes
   les bases) plutôt que dans le bloc SQL réservé à SQLite.
10. Nettoyer les artefacts commités par erreur (wheels, JSON de 65 Mo, `__pycache__`, `tmp*/`) et
    réparer ou retirer le gitlink de sous-module orphelin.
11. Ajouter un vrai test bout-en-bout (socket MLLP réel, avec assertions) et un test de la
    logique d'import MFN (`process_mfn_message`) — les deux n'ont aujourd'hui aucune couverture
    automatisée exploitable.

**Long terme — dette produit**
12. Écrire les tests manquants sur `ccam_service.py` et `app/admin/*` (zéro couverture
    aujourd'hui sur ce dernier, alors que c'est la zone la plus critique côté sécurité), et
    rééquilibrer l'effort de test UCD/LPP (le plus testé du dépôt en volume, ~8,7x code/tests)
    vers des domaines non couverts.
13. Implémenter réellement les fonctionnalités déjà exposées côté routes/API mais encore des stubs
    côté service (interventions HPRIM, NGAP, acquittements, envoi effectif de messages).
14. Consolider les rapports d'audit existants (celui-ci compris) sous `docs/reports/` avec un
    unique statut vivant, plutôt que d'accumuler des instantanés contradictoires à la racine.

**Fait le 2026-07-03** : les 11 rapports d'audit historiques listés au §3.0 ont été déplacés
(`git mv`) vers `docs/reports/` (`BUG_REPORT.md`, `COMPREHENSIVE_AUDIT_REPORT.md`,
`CONFORMANCE_AUDIT_PAM_20260328.md`, `CONFORMANCY_MATRIX.md`,
`CORRECTION_PAM_CX_FORMAT_20260328.md`, `FEATURE_VERIFICATION_REPORT.md`,
`IMPLEMENTATION_TASK2_CARTOGRAPHY.md`, `IMPLEMENTATION_TASK3_COTATIONS.md`,
`PAM_VALIDATOR_V2_1_ENHANCEMENTS.md`, `PLAN_EVOLUTIONS_HPRIM_COTATIONS.md`,
`UI_IMPROVEMENTS_SUMMARY.md`). `P3_IMPORT_CORRECTIONS_REPORT.md` est resté à la racine
intentionnellement : c'est un chemin en dur utilisé par `tests/integration/test_phase3_seed_integration.py`
et `scripts/manual/seed_hl7_scenarios.py` (le déplacer casserait ces scripts) ; le déplacer
proprement nécessiterait de mettre à jour ces chemins en dur, ce qui n'a pas été fait dans le
cadre de ce nettoyage. `README.md`, `CLAUDE.md` et `AUDIT.md` restent à la racine (documents
vivants du dépôt).
