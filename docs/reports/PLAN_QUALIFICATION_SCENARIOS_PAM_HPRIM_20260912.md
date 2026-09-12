# Plan de reprise et de qualification des scénarios PAM/HPRIM

Date : 12 septembre 2026

État d'implémentation au 12 septembre 2026 : le socle décrit ci-dessous est
livré. Il comprend les jeux immuables multi-endpoints, le catalogue canonique
PAM/HPRIM avec dédoublonnage et traçabilité des sources, les thèmes, le
commentaire fonctionnel, l'état par logiciel cible, le retry de livraison et
la création de campagnes. Les assertions historiques détaillées et les
contrôles BDD spécifiques au partenaire restent à enrichir scénario par
scénario : aucun import automatique ne peut inventer leur intention métier.
Le catalogue actif issu des sources disponibles contient 219 séquences
distinctes : 165 IHE PAM et 54 HPRIM. Les copies techniques sont conservées
comme traces inactives et ne sont pas affichées dans le catalogue opérationnel.

Périmètre : remplacer l'ancien outil `interfaces.integration` pour les
scénarios IHE PAM France, HPRIM XML et les parcours mixtes PAM + HPRIM. Les
domaines historiques IMBO/MBO, GEF, RH, EDI, B2/DRE/TG et Chorus ne font pas
partie de ce périmètre tant qu'ils ne sont pas explicitement demandés.

## Objectif produit

Le module de scénarios doit devenir un véritable tableau de qualification par
logiciel cible. Il doit permettre de savoir immédiatement :

- quels scénarios sont actifs pour une cible ;
- lesquels n'ont jamais été exécutés ;
- lesquels réussissent ou échouent, et depuis quand ;
- quelle étape, quel endpoint et quel diagnostic expliquent le dernier échec ;
- quelles exécutions peuvent être reprises avec les mêmes identifiants ;
- quels scénarios doivent être relancés comme un nouveau jeu.

Le remplacement de l'ancien outil ne sera considéré comme acquis qu'après
reprise des messages, des paramètres, des assertions et des contrôles BDD, et
pas uniquement après import des payloads.

## État des lieux de l'ancien corpus

L'analyse du dépôt historique montre :

- 322 classes de scénarios ou tests ;
- 1 189 méthodes annotées `@Test` ;
- 1 350 assertions ;
- 267 références à des utilitaires de contrôle BDD ;
- 155 temporisations explicites ;
- 166 interactions ou demandes de paramètres ;
- des transports MLLP, HTTP, IMBO/MBO, HPRIM XML, fichiers et pivots.

Le nouveau dépôt consolide 322 entrées PAM et 60 scénarios HPRIM disponibles
dans les sources du projet :

| Famille | Entrées exportées | Étapes |
|---|---:|---:|
| IHE PAM | 322 | corpus historique |
| HPRIM cotation | 60 | corpus `scenarios_hprim_seed` |
| Total | 382 | corpus importé |

Cet export n'est pas encore une reprise fonctionnelle complète :

- la base locale ne contient actuellement que 61 scénarios, dont 1 PAM et 60
  HPRIM ;
- aucune assertion historique n'est portée dans `assertions_json` ;
- aucun délai historique n'est conservé ;
- les liens vers les sources historiques ne sont pas structurés ;
- les 322 entrées PAM correspondent à 165 séquences de payloads distinctes,
  les autres provenant principalement de copies entre sources et classes
  compilées ;
- les formats HPRIM historiques utilisent encore `hprim` ou `hprimxml`, tandis
  que le moteur courant utilise le format canonique `xml` ;
- 118 payloads HPRIM comportent un préfixe historique `MSH|` devant le XML ;
- les variables CPage sont converties vers les tokens du nouveau moteur ou
  vers une valeur de démonstration explicite ; toute variable inconnue reste
  signalée par le contrôle préalable.

## 1. Tableau de bord par système cible

L'utilisateur commence par choisir un système cible logique, par exemple
`CPAGE_RECETTE` ou `DPI_PARTENAIRE_A`. Un même système peut regrouper plusieurs
endpoints : PAM MLLP, HPRIM fichier et FHIR HTTP.

### États fonctionnels

| État | Signification |
|---|---|
| Jamais exécuté | Aucun jeu n'a été lancé sur cette cible |
| En cours | Une exécution est active |
| Réussi depuis… | Toutes les livraisons obligatoires réussissent depuis cette date |
| En erreur depuis… | Au moins une livraison obligatoire échoue depuis cette date |
| Partiel | Une partie des flux réussit et une autre échoue |
| Désactivé | Le scénario est volontairement exclu pour cette cible |
| Incompatible | Un endpoint PAM ou HPRIM requis est absent ou désactivé |

### Indicateurs

Afficher au minimum :

- nombre de scénarios réussis, en erreur, partiels et jamais exécutés ;
- date du changement vers l'état courant ;
- dernière réussite et dernier échec ;
- nombre d'échecs consécutifs ;
- taux de réussite sur 7 et 30 jours ;
- dernière étape et dernier endpoint en erreur ;
- durée de la dernière exécution.

### Persistance

Ajouter un état agrégé par couple `scénario × système cible`, comportant :

- `current_status` ;
- `status_since` ;
- `last_run_at` ;
- `last_success_at` ;
- `last_failure_at` ;
- `consecutive_failures` ;
- `last_play_id` et `last_failed_delivery_id`.

L'état doit être recalculable depuis les jeux et livraisons persistés afin
d'éviter qu'une valeur agrégée obsolète devienne la seule source de vérité.

## 2. Rejeu des erreurs

Trois actions doivent être explicitement distinguées dans l'IHM.

### Réessayer une livraison

- reprend une seule livraison technique en erreur ;
- conserve strictement le payload compilé ;
- conserve IPP, NDA, venue, mouvements, actes et identifiants de messages ;
- sert notamment après une indisponibilité réseau ou partenaire.

### Rejouer le jeu en échec

- reprend toutes les livraisons en erreur du jeu ;
- ne renvoie pas les livraisons déjà réussies, sauf action explicite ;
- conserve tous les identifiants et payloads du jeu initial.

### Relancer comme nouveau jeu

- crée un nouveau `ScenarioPlay` ;
- génère une nouvelle identité et de nouveaux identifiants métier ;
- recompile toutes les étapes ;
- permet au système cible de créer un nouveau patient/dossier sans écraser le
  jeu précédent.

Depuis le tableau de bord, l'utilisateur doit pouvoir sélectionner tous les
scénarios en erreur, en exclure certains, lancer une prévisualisation puis
suivre une campagne de rejeu.

## 3. Activation et organisation

L'activation doit exister à deux niveaux :

- activation globale du scénario ;
- activation pour un système cible précis.

Le cycle de vie proposé est :

```text
brouillon → publié → désactivé → archivé
```

Une désactivation doit conserver sa date, sa raison et son auteur logique. Les
actions groupées doivent permettre d'activer, désactiver, catégoriser, affecter
à une campagne ou changer de cible plusieurs scénarios.

Les scénarios publiés sont versionnés. Une modification crée une nouvelle
version sans altérer les preuves attachées aux anciens jeux.

### Commentaire fonctionnel du scénario

Chaque scénario doit disposer d'un commentaire fonctionnel éditable expliquant
son utilité. Ce commentaire est distinct du nom technique, du chemin source et
des commentaires propres aux étapes.

Il doit permettre d'indiquer au minimum :

- le comportement ou parcours métier testé ;
- les préconditions importantes ;
- le résultat attendu ;
- le contexte dans lequel utiliser le scénario ;
- les limites ou particularités connues du logiciel cible.

Le modèle peut conserver `description` comme résumé court et ajouter un champ
`functional_comment` en texte long avec Markdown limité. Le commentaire est :

- affiché dans la fiche du scénario ;
- consultable depuis la liste sans ouvrir l'éditeur ;
- inclus dans la recherche plein texte ;
- repris dans les exports JSON et Markdown ;
- versionné avec le scénario ;
- affiché dans les rapports de campagne.

Pour les scénarios importés de l'ancien outil, le premier commentaire est
généré depuis le nom de la classe, son package, ses méthodes de test et leurs
commentaires Java. Il doit ensuite pouvoir être enrichi manuellement.

### Classement hiérarchique par thème

La simple colonne `category` ne suffit pas à reproduire l'organisation par
packages de l'ancien logiciel. Ajouter une arborescence de thèmes persistante :

```text
IHE PAM
├── Identité
│   ├── Création et modification
│   ├── INS et identité fédérée
│   └── Fusion et rapprochement
├── Mouvements
│   ├── Hospitalisation
│   ├── Urgences
│   ├── Séances
│   ├── Maternité
│   └── Annulations et corrections
HPRIM
├── CCAM
├── NGAP
├── UCD
├── LPP
├── Interventions
└── Cas négatifs
Parcours mixtes
└── PAM + HPRIM
```

Le modèle cible comprend :

- `ScenarioTheme` : clé stable, nom, commentaire, parent, ordre d'affichage,
  état actif et chemin historique éventuel ;
- `ScenarioThemeAssignment` : association entre un scénario et un thème, avec
  un indicateur de thème principal ;
- `legacy_package` sur le scénario ou dans ses métadonnées d'import afin de
  conserver le classement Java original sans en faire une dépendance métier.

Un scénario peut appartenir à plusieurs thèmes, mais possède un thème
principal utilisé dans l'arborescence et les exports. Les tags restent
disponibles pour les propriétés transversales telles que `négatif`, `INS`,
`CPage`, `UCD` ou `annulation`.

### IHM des thèmes

La liste des scénarios propose :

- une arborescence repliable comparable à celle des packages historiques ;
- un fil d'Ariane indiquant le thème sélectionné ;
- le nombre total, réussi, en erreur et jamais exécuté pour chaque thème ;
- une recherche portant sur le nom, le commentaire, les tags et l'ancien nom
  de package ;
- un filtre « sans commentaire » et un filtre « sans thème » pour terminer la
  migration documentaire ;
- des actions groupées pour changer de thème, activer ou désactiver ;
- un gestionnaire de thèmes permettant d'ajouter, renommer, déplacer,
  désactiver ou fusionner un thème sans modifier les scénarios eux-mêmes.

La fiche d'un scénario expose son thème principal, ses thèmes secondaires, son
package historique et son commentaire fonctionnel dans une zone éditable.

## 4. Reprise du catalogue historique

### Périmètre à reprendre

- scénarios d'identité IHE PAM ;
- mouvements, changements de statut, corrections et annulations PAM ;
- scénarios HPRIM CCAM, NGAP, UCD et LPP ;
- cas HPRIM négatifs et limites métier ;
- scénarios mixtes qui créent le patient et le dossier par PAM avant l'acte
  HPRIM.

### Chaîne d'import canonique

1. Inventorier chaque classe historique et ses ressources.
2. Regrouper les fichiers identiques entre `src/main/resources` et
   `target/classes`.
3. Conserver un identifiant historique et tous les chemins d'origine comme
   alias traçables.
4. Extraire l'ordre des messages depuis les méthodes `@Test` plutôt que depuis
   le seul ordre lexical des fichiers.
5. Importer les temporisations significatives comme délais d'étapes.
6. Convertir `hprim` et `hprimxml` en `xml`.
7. Retirer le préfixe `MSH|` placé devant les documents XML.
8. Convertir les variables historiques vers les tokens du jeu.
9. Traduire les assertions Java et BDD vers les assertions du nouveau moteur.
10. Produire un manifeste de couverture : repris, fusionné, hors périmètre ou
    à traiter manuellement.
11. Convertir le package Java en chemin de thème et conserver le package
    original dans les métadonnées d'import.
12. Initialiser le commentaire fonctionnel depuis la documentation et les
    commentaires disponibles dans la classe historique.

### Correspondance des variables

| Variable historique | Token cible |
|---|---|
| `$NIP$`, `$IPP$` | `{{patient.ipp}}` |
| `$DOSSIER$` | `{{dossier.nda}}` |
| identifiant de venue | `{{venue.id}}` |
| identifiant de mouvement | `{{movement.id}}` |
| identifiant de message | `{{message.control_id}}` |
| `$DATE$`, `$HEURE$` | tokens temporels du jeu à ajouter |
| `$UF$` | unité fonctionnelle résolue depuis la cible |
| `$ADELI$`, RPPS | professionnel configuré pour la cible |

Les paramètres sans équivalent automatique doivent devenir des préconditions
ou des paramètres éditables au lancement.

## 5. Validation avant émission

La préparation d'un jeu doit exécuter un contrôle préalable bloquant :

- conformité HL7 v2.5 et IHE PAM France ;
- validité XML et conformité HPRIM ;
- cohérence des IPP, NDA et venues entre PAM et HPRIM ;
- présence et activation des endpoints requis ;
- absence de variable ou token non résolu ;
- unicité des identifiants techniques ;
- chronologie et ordre métier cohérents ;
- présence des étapes de création préalables requises ;
- compatibilité de chaque étape avec au moins un endpoint sélectionné.

L'IHM affiche les erreurs et avertissements avant le premier envoi et propose
un lien direct vers l'étape à corriger.

## 6. Résultats et diagnostic

La page d'un jeu présente :

- la timeline des étapes ;
- la matrice `étape × endpoint` ;
- le payload compilé réellement envoyé ;
- l'ACK ou la réponse complète ;
- la durée et le nombre de tentatives ;
- le verdict de validation normative ;
- les assertions fonctionnelles ;
- l'écart avec la dernière exécution réussie ;
- l'état observé dans la BDD cible lorsqu'un connecteur de lecture est
  configuré.

Un export Markdown et JSON permet de conserver un rapport anonymisé de
qualification.

## 7. Assertions et contrôles BDD

L'ancien outil ne se limitait pas à vérifier les ACK. Il interrogeait également
la BDD CPage pour contrôler le résultat métier. Le nouveau moteur doit proposer
des assertions configurables, indépendantes de CPage lorsque cela est possible :

- ACK attendu (`AA`, `AE`, `AR`) ;
- présence ou absence d'un patient/dossier ;
- valeurs d'identité attendues ;
- statut du dossier ;
- ordre et type des mouvements ;
- UF de responsabilité ou de localisation ;
- présence, modification ou suppression d'un acte ;
- absence de doublon après un retry ;
- coexistence de deux jeux lancés successivement.

Les contrôles propres à une BDD partenaire passent par un adaptateur de lecture
explicitement configuré. Une absence de connecteur produit l'état « non
évalué », jamais une réussite implicite.

## 8. Campagnes de qualification

Une campagne regroupe des scénarios ordonnés et versionnés, par exemple :

- socle PAM identité ;
- mouvements hospitaliers ;
- annulations et corrections ;
- HPRIM CCAM ;
- HPRIM NGAP, UCD et LPP ;
- parcours mixtes PAM + HPRIM ;
- non-régression complète d'un logiciel cible.

Les actions disponibles sont :

- exécuter toute la campagne ;
- prévisualiser sans émettre ;
- rejouer uniquement les erreurs ;
- rejouer uniquement les scénarios modifiés depuis la dernière réussite ;
- comparer deux campagnes ;
- exporter le bilan.

## 9. UX proposée

### Écran de synthèse

- sélecteur de système cible ;
- compteurs par statut ;
- filtres protocole, catégorie, statut, période et texte ;
- cases à cocher pour les actions groupées ;
- colonne « statut depuis » ;
- accès direct au dernier jeu et au dernier échec.
- navigation par arborescence de thèmes et package historique ;
- aperçu du commentaire fonctionnel dans la liste ;
- filtres « sans thème » et « sans commentaire ».

### Détail d'un scénario

- timeline éditable des étapes ;
- badge PAM, HPRIM ou mixte ;
- liste des endpoints requis et compatibles ;
- historique par système cible ;
- prévisualisation côte à côte source/compilé ;
- actions clairement séparées : retry, rejouer le jeu, nouveau jeu.
- édition du commentaire fonctionnel ;
- sélection d'un thème principal et de thèmes secondaires ;
- affichage du package historique importé.

### Détail d'une campagne

- progression globale ;
- nombre de scénarios réussis, partiels et en erreur ;
- mise à jour progressive de la matrice ;
- filtre « erreurs seulement » ;
- arrêt contrôlé et reprise ultérieure.

## 10. Ordre de réalisation

### P0 — Exploitation quotidienne

1. État `scénario × système cible` et date « depuis quand ».
2. Activation globale et activation par cible.
3. Écran des scénarios en erreur et rejeu groupé.
4. Rejeu des seules livraisons en échec avec payload inchangé.
5. Commentaire fonctionnel éditable et classement hiérarchique par thème.

### P1 — Reprise fiable de l'ancien outil

1. Import et dédoublonnage complet du catalogue PAM/HPRIM.
2. Normalisation des formats et payloads HPRIM.
3. Conversion des variables historiques.
4. Manifeste de couverture entre classes historiques et scénarios importés.
5. Traduction des assertions ACK et BDD prioritaires.

### P2 — Qualification industrielle

1. Contrôle préalable complet PAM/HPRIM.
2. Campagnes versionnées.
3. Comparaison avec la dernière exécution réussie.
4. Rapports Markdown/JSON.
5. Tests E2E avec deux environnements et vérification des BDD.

## Critères de remplacement de l'ancien outil

L'ancien outil peut être retiré lorsque :

- chaque scénario PAM/HPRIM historique possède une décision documentée :
  repris, fusionné, hors périmètre ou abandonné ;
- chaque scénario repris possède un commentaire fonctionnel et un thème
  principal ;
- le classement par thèmes permet de retrouver l'organisation utile des
  packages historiques ;
- aucun doublon technique n'est présenté comme un scénario supplémentaire ;
- les variables nécessaires sont résolues sans modification manuelle du
  payload ;
- les assertions métier essentielles sont exécutées et tracées ;
- les 61 scénarios présents localement ont été remplacés par le catalogue
  canonique attendu ;
- un échec technique peut être repris sans modifier les identifiants ;
- un nouveau jeu produit systématiquement de nouveaux identifiants ;
- les campagnes PAM, HPRIM et mixtes sont exécutées automatiquement en CI et
  sur deux environnements de qualification ;
- l'IHM permet de diagnostiquer un échec sans consulter directement la BDD ou
  les fichiers de logs.
