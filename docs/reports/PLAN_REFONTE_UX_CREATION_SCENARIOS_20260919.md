# Plan de refonte UX — création de scénarios

**Date :** 19 septembre 2026  
**Périmètre :** création, configuration et première validation d'un scénario d'interopérabilité  
**Hors périmètre :** sécurité, refonte du moteur d'exécution, refonte complète du catalogue de scénarios existants

## État de mise en œuvre — 19 septembre 2026

Le socle de la refonte est livré :

- un assistant en cinq étapes remplace la création initiale vide ;
- les parcours types existants, la duplication et l'import convergent vers une revue de brouillon ;
- la clé technique est facultative et proposée automatiquement ;
- les scénarios créés par l'assistant sont inactifs jusqu'à validation explicite ;
- la revue affiche la chronologie, les destinations compatibles, les payloads repliés et les erreurs de préparation ;
- la chronologie permet maintenant d'ajouter, réordonner ou retirer des événements métier sans saisir de payload ;
- un routage commun peut être appliqué à tout le parcours, avec filtrage des endpoints incompatibles ;
- une exécution à blanc est accessible depuis la revue, y compris pour un brouillon, sans jamais autoriser d'émission réelle ;
- une identité de test commune est saisie une seule fois et injectée dans tous les messages compilés ;
- des contrôles attendus peuvent être générés par étape sans modifier les assertions JSON expertes ;
- l'usage du constructeur est maintenant mesuré par actions agrégées (création, validation, prévisualisation et revue), dans le tableau de bord interne et dans Prometheus, sans nom, clé, identifiant ni donnée patient ;
- le mode expert historique reste disponible pour les ajustements avancés ;
- une migration et une compatibilité de démarrage local accompagnent le nouvel état `draft` / `ready`.

Reste à réaliser dans les lots suivants : les optimisations issues des retours terrain.

## 1. Objectif produit

Permettre à un utilisateur métier ou fonctionnel de créer un scénario valide sans devoir connaître immédiatement :

- une clé technique ;
- les codes de messages HL7 ;
- la structure brute d'une ressource FHIR ;
- les règles de routage internes ;
- les identifiants techniques des endpoints.

Le parcours avancé doit rester disponible pour les intégrateurs qui souhaitent modifier les messages bruts, le routage, les temporisations ou les assertions.

### Résultat attendu

Le parcours par défaut doit permettre de passer de l'intention fonctionnelle à un scénario prêt à tester en cinq étapes au maximum :

1. définir le besoin ;
2. choisir ou composer le parcours ;
3. renseigner les données de test ;
4. sélectionner les destinations ;
5. vérifier et enregistrer.

## 2. Diagnostic du parcours actuel

La difficulté actuelle n'est pas seulement visuelle. Elle vient surtout de l'organisation du parcours.

### 2.1 Création trop technique dès le premier écran

L'écran `scenario_new.html` demande une clé immuable, un protocole et une catégorie libre avant de connaître le contenu du scénario. Il crée ensuite un scénario vide.

Conséquences :

- l'utilisateur doit comprendre le modèle interne avant de commencer ;
- une erreur de clé est traitée après soumission et fait perdre le contexte du formulaire ;
- la catégorie libre favorise les libellés incohérents ;
- le choix du protocole est prématuré pour un utilisateur qui raisonne en parcours de soins.

### 2.2 Rupture après la création

Après l'enregistrement initial, l'utilisateur arrive sur la page de détail et doit ajouter les étapes une par une. La création n'aboutit donc pas à un scénario utilisable, mais à un conteneur vide.

### 2.3 Une page de détail qui cumule trop de responsabilités

`scenario_detail.html` regroupe notamment :

- les informations générales ;
- les métadonnées de qualification ;
- les assertions ;
- les étapes et leur ordre ;
- le routage ;
- les payloads bruts ;
- les temporisations ;
- la publication et les versions ;
- le lancement d'une exécution.

Cette concentration augmente fortement la charge cognitive et masque l'action principale : construire le parcours.

### 2.4 Les notions fonctionnelles et techniques sont mélangées

Pour ajouter une étape, l'utilisateur doit saisir simultanément un nom, un type de message comme `ADT^A01`, un format, un payload brut, un délai, un mode de routage, un système cible et éventuellement plusieurs endpoints.

Il manque un niveau fonctionnel intermédiaire, par exemple :

> Admission du patient → mouvement `A01` en HL7v2 → endpoints compatibles proposés automatiquement.

### 2.5 Plusieurs bons parcours existent déjà, mais restent séparés

Le logiciel possède déjà des fondations utiles :

- des modèles `ScenarioTemplate` et `ScenarioTemplateStep` ;
- un mécanisme de matérialisation d'un modèle ;
- un générateur de parcours de test ;
- l'import JSON ;
- des payloads de référence HL7/FHIR ;
- la détection des endpoints compatibles ;
- le mode d'exécution à blanc.

Ces fonctions sont dispersées dans plusieurs écrans. L'utilisateur doit connaître leur existence et choisir lui-même le bon point d'entrée.

## 3. Principes de conception proposés

### 3.1 Partir de l'intention, pas du protocole

Le premier choix doit être fonctionnel : admission, transfert, sortie, mise à jour d'identité, parcours personnalisé, etc. Le protocole devient une conséquence configurable du parcours et du système cible.

### 3.2 Divulgation progressive

Le parcours simple affiche uniquement les décisions nécessaires. Les options techniques sont regroupées dans des panneaux « Options avancées ».

### 3.3 Un seul point d'entrée

Le bouton « Nouveau scénario » doit ouvrir un lanceur unique donnant accès à toutes les méthodes de création :

- utiliser un modèle — choix recommandé ;
- dupliquer un scénario ;
- importer une définition ;
- partir d'une capture ou d'un dossier existant, lorsque disponible ;
- créer un scénario vide en mode expert.

### 3.4 Prévisualiser avant de publier

L'utilisateur doit voir la chronologie, les messages générés, les destinations et les erreurs avant que le scénario ne soit considéré comme prêt.

### 3.5 Conserver un mode expert complet

La simplification ne doit pas retirer les possibilités actuelles. Le payload brut, le routage explicite, les délais et les assertions restent accessibles par étape, mais ne dominent plus l'interface.

## 4. Parcours cible

### Étape 0 — Choisir une méthode de création

Présenter de grandes cartes explicites :

1. **À partir d'un parcours type** — recommandé ;
2. **Dupliquer un scénario existant** ;
3. **Importer un scénario** ;
4. **Créer manuellement** — mode expert.

Chaque carte précise le résultat, le niveau de connaissance attendu et le temps estimatif relatif : rapide, intermédiaire ou avancé.

### Étape 1 — Définir le scénario

Champs visibles :

- nom du scénario ;
- objectif ou courte description ;
- contexte GHT/EJ, si nécessaire ;
- tags ou domaine métier proposés dans une liste contrôlée.

Comportements :

- générer automatiquement la clé depuis le nom ;
- vérifier sa disponibilité sans quitter l'écran ;
- placer la modification manuelle de la clé dans les options avancées ;
- enregistrer le travail comme brouillon.

### Étape 2 — Construire le parcours

Afficher une chronologie fonctionnelle plutôt qu'un tableau technique.

Exemple :

```text
[1 Admission] ── 5 min ──> [2 Transfert] ── 2 h ──> [3 Sortie]
      A01                       A02                      A03
```

Actions principales :

- ajouter un événement depuis un catalogue ;
- rechercher par terme métier ;
- réordonner les événements ;
- dupliquer ou supprimer une étape ;
- choisir une variante proposée ;
- ouvrir les paramètres avancés de l'étape.

Une étape doit afficher en priorité :

- son libellé fonctionnel ;
- son format déduit ou sélectionné ;
- son état de validité ;
- son délai relatif ;
- sa destination résumée.

Les codes HL7/FHIR et le contenu brut restent secondaires.

### Étape 3 — Définir les données de test

Proposer un formulaire métier commun aux étapes :

- patient existant, patient synthétique ou données manuelles ;
- identifiants IPP/NDA ;
- établissement et service ;
- spécialité ;
- dates de début et de fin ;
- nombre de patients pour les parcours multiples.

Le système génère ensuite les payloads des étapes à partir des données communes et des modèles de référence.

Le mode expert permet de remplacer le payload généré pour une étape précise. L'interface signale alors que cette étape n'est plus entièrement synchronisée avec les données communes.

### Étape 4 — Configurer les destinations

Principes :

- proposer par défaut « tous les endpoints compatibles » ;
- filtrer les endpoints selon le protocole et le type de message ;
- afficher le nom fonctionnel du système avant sa clé technique ;
- expliquer pourquoi une destination est incompatible ;
- permettre une surcharge par étape dans un panneau avancé ;
- mémoriser une sélection commune pour tout le scénario.

### Étape 5 — Vérifier et créer

Présenter une synthèse lisible :

- objectif et contexte ;
- chronologie des événements ;
- données principales ;
- destinations ;
- avertissements et erreurs ;
- aperçu des messages ;
- résultat d'une validation ou d'une exécution à blanc.

Actions :

- revenir directement à la section concernée ;
- enregistrer comme brouillon ;
- créer et ouvrir le scénario ;
- créer et lancer un test, si toutes les conditions sont réunies.

## 5. Maquette fonctionnelle simplifiée

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Nouveau scénario                         Brouillon enregistré à 14:32│
│ 1 Besoin  ─  2 Parcours  ─  3 Données  ─  4 Destinations  ─  5 Revue│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Construisez votre parcours                                         │
│                                                                     │
│  ┌ Admission du patient ─────────────────────────────── ✓ valide ┐  │
│  │ HL7v2 · ADT A01 · 2 destinations                 [Configurer] │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                         ↓ 5 minutes                                 │
│  ┌ Transfert du patient ───────────────────────────── ⚠ à vérifier┐ │
│  │ HL7v2 · ADT A02 · destination non définie          [Corriger] │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  [+ Ajouter un événement]                         [Options avancées] │
├─────────────────────────────────────────────────────────────────────┤
│ [Quitter et reprendre plus tard]                 [Continuer →]       │
└─────────────────────────────────────────────────────────────────────┘
```

Sur mobile, les actions « Précédent » et « Continuer » restent visibles dans une barre basse. La chronologie devient verticale.

## 6. Nouvelle organisation de l'espace scénario

Après la création, la page actuelle doit être allégée et répartie en quatre espaces :

1. **Conception** : identité et chronologie des étapes ;
2. **Données et routage** : jeu de données, destinations et temporisations ;
3. **Validation** : aperçu, assertions, erreurs et exécution à blanc ;
4. **Exécutions** : lancement, résultats, historique et versions.

La qualification et les fonctions d'administration ne doivent plus interrompre le flux de conception. Elles peuvent rester accessibles par des actions secondaires ou des écrans dédiés.

## 7. Améliorations front-end

### Priorité P0

- remplacer le formulaire initial par le lanceur et l'assistant guidé ;
- créer un stepper accessible avec navigation libre entre les étapes déjà complétées ;
- créer la chronologie fonctionnelle des événements ;
- ajouter un catalogue recherchable d'événements et de modèles ;
- masquer les champs techniques derrière « Options avancées » ;
- fournir des valeurs par défaut cohérentes ;
- afficher les erreurs à proximité des champs, avec un résumé en haut de l'étape ;
- conserver les données saisies lorsqu'une validation serveur échoue ;
- ajouter une page de revue avec liens de correction directs ;
- prendre en charge le brouillon et l'avertissement de modifications non enregistrées.

### Priorité P1

- édition et réorganisation des étapes par glisser-déposer, avec équivalent clavier ;
- aperçu formaté des messages avec recherche et comparaison ;
- duplication d'un scénario depuis le lanceur ;
- intégration de l'import dans le même parcours ;
- génération de données synthétiques depuis l'assistant ;
- barre de progression de préparation du scénario ;
- raccourcis « Ajouter après », « Dupliquer » et « Tester cette étape ».

### Priorité P2

- suggestions contextuelles fondées sur les choix précédents ;
- comparaison visuelle entre le payload généré et une surcharge manuelle ;
- bibliothèque de favoris et modèles récents ;
- visite guidée facultative pour une première création ;
- personnalisation des valeurs par défaut par équipe ou établissement.

## 8. Améliorations back-end

### 8.1 Introduire un cycle de vie de brouillon

Le scénario doit pouvoir être sauvegardé avant d'être complet, sans apparaître comme exécutable.

États fonctionnels proposés :

- `draft` : incomplet ou en cours d'édition ;
- `ready` : validation de préparation réussie ;
- `published` : version publiée ;
- `archived` : conservé mais non proposé à l'exécution.

Une première version peut porter cet état dans les métadonnées existantes si une migration immédiate est jugée trop coûteuse. La cible reste un champ explicite et indexé.

### 8.2 Créer un service d'orchestration de l'auteur de scénario

Ce service doit centraliser :

- la création depuis un modèle ;
- la duplication ;
- la génération de clé ;
- la génération des étapes et payloads ;
- la résolution des endpoints compatibles ;
- la validation de préparation ;
- la prévisualisation ;
- la création transactionnelle du scénario et de ses étapes.

Il doit réutiliser le mécanisme actuel de matérialisation des `ScenarioTemplate`, et non créer un second moteur de génération.

### 8.3 Exposer des contrats dédiés à l'assistant

Contrats indicatifs :

```text
GET    /api/scenario-authoring/options
GET    /api/scenario-authoring/templates
POST   /api/scenario-drafts
PATCH  /api/scenario-drafts/{id}
POST   /api/scenario-drafts/{id}/validate
POST   /api/scenario-drafts/{id}/preview
POST   /api/scenario-drafts/{id}/materialize
```

Le nom exact peut rester cohérent avec les conventions existantes. L'important est de séparer le contrat de construction guidée des routes historiques d'édition d'une étape.

### 8.4 Fournir une validation structurée

La réponse de validation doit fournir :

- un niveau : erreur, avertissement ou information ;
- un code stable ;
- un message utilisateur ;
- le chemin du champ ou l'identifiant de l'étape ;
- une action de correction éventuelle.

Cela permet au front de placer les erreurs au bon endroit et d'ouvrir directement l'étape concernée.

### 8.5 Éviter les scénarios vides orphelins

Deux options sont possibles :

- sauvegarder dans une entité de brouillon séparée puis matérialiser à la fin ;
- autoriser les `InteropScenario` incomplets mais les distinguer explicitement et les exclure des écrans d'exécution.

**Recommandation :** commencer par la seconde option pour livrer rapidement, puis évaluer une entité de brouillon séparée si les besoins de collaboration ou d'historisation le justifient.

## 9. Accessibilité et responsive

Les points suivants font partie des critères d'acceptation, et non d'une phase facultative :

- stepper utilisable au clavier et correctement annoncé ;
- focus placé sur le premier champ erroné après validation ;
- résumé des erreurs avec liens vers les champs ;
- états non transmis uniquement par la couleur ;
- boutons et zones cliquables adaptés au tactile ;
- alternative clavier aux réordonnancements par glisser-déposer ;
- conservation du contexte après ouverture d'un panneau avancé ;
- chronologie et aperçu utilisables sur petit écran ;
- messages dynamiques annoncés avec `aria-live` lorsque nécessaire.

## 10. Décisions produit proposées

| Sujet | Recommandation |
|---|---|
| Parcours par défaut | Création depuis un modèle fonctionnel |
| Clé technique | Générée automatiquement, modifiable en mode avancé |
| Protocole | Déduit du modèle et des destinations, modifiable ensuite |
| Routage initial | Tous les endpoints compatibles |
| Payload brut | Masqué par défaut, accessible par étape |
| Enregistrement | Brouillon automatique ou sauvegarde silencieuse à chaque changement d'étape |
| Visibilité d'un brouillon | Visible dans « Mes brouillons », absent des sélecteurs d'exécution |
| Scénario sans étape | Autorisé uniquement à l'état brouillon |
| Mode mixte HL7/FHIR | Conservé, mais présenté comme option avancée |
| Écran historique actuel | Maintenu temporairement comme mode expert pendant la transition |

## 11. Plan de réalisation

### Lot 1 — Socle du nouveau parcours — P0

Objectif : rendre la création initiale compréhensible sans modifier le moteur d'exécution.

- remplacer `/scenarios/new` par le lanceur unifié ;
- ajouter le parcours guidé en cinq étapes ;
- générer et vérifier la clé automatiquement ;
- introduire l'état brouillon ;
- utiliser les modèles existants pour créer les premières étapes ;
- conserver un lien explicite vers le mode expert actuel ;
- ajouter les tests de navigation, de validation et de persistance.

Critères d'acceptation :

- un utilisateur peut créer un scénario type sans saisir de clé technique ni de payload brut ;
- une erreur serveur ne supprime aucune saisie ;
- un brouillon incomplet ne peut pas être exécuté ;
- le parcours fonctionne au clavier et sur mobile ;
- les scénarios existants restent compatibles.

### Lot 2 — Constructeur visuel d'étapes — P0

Objectif : remplacer l'édition simultanée de tous les champs techniques par une chronologie métier.

- catalogue d'événements ;
- ajout, duplication, suppression et déplacement ;
- paramètres simples et avancés ;
- délais relatifs ;
- badge de validité par étape ;
- génération des payloads depuis les données communes ;
- édition brute conservée dans un panneau avancé.

Critères d'acceptation :

- l'ordre complet des étapes est compréhensible sans ouvrir les payloads ;
- toute action de réorganisation est accessible au clavier ;
- les surcharges manuelles sont identifiées visuellement ;
- une étape invalide indique la cause et l'action de correction.

### Lot 3 — Données, routage et revue — P0

Objectif : produire un scénario réellement prêt à tester à la fin de l'assistant.

- données patient communes ;
- choix d'un patient synthétique ou existant ;
- filtrage des destinations compatibles ;
- destination commune et surcharges par étape ;
- validation structurée ;
- aperçu des messages ;
- exécution à blanc depuis la revue.

Critères d'acceptation :

- aucun endpoint incompatible ne peut être sélectionné sans explication explicite ;
- les erreurs de préparation renvoient à la bonne étape ;
- la revue montre exactement ce qui sera enregistré ;
- la validation du brouillon et l'enregistrement final utilisent les mêmes règles serveur.

### Lot 4 — Unification des méthodes de création — P1

Objectif : faire du lanceur le point d'entrée de tous les nouveaux scénarios.

- duplication d'un scénario existant ;
- import JSON intégré ;
- intégration du générateur de parcours de test ;
- intégration de la création depuis un dossier ou une capture lorsque disponible ;
- harmonisation des écrans de résultat et d'erreur.

Critères d'acceptation :

- chaque méthode aboutit au même écran de revue ;
- un contenu importé peut être corrigé avant matérialisation ;
- la provenance du scénario est conservée dans ses métadonnées.

### Lot 5 — Refonte de l'espace de travail — P1

Objectif : prolonger la simplicité après la création.

- répartir la page de détail entre Conception, Données et routage, Validation, Exécutions ;
- retirer la qualification et l'administration du flux principal ;
- ajouter les indicateurs de préparation ;
- maintenir des liens directs vers les fonctions avancées ;
- réduire progressivement les formulaires imbriqués de la page historique.

### Lot 6 — Mesure et optimisation — P2

Objectif : valider que la refonte réduit réellement la complexité.

- instrumentation des étapes du parcours ;
- mesure des abandons et erreurs ;
- tests utilisateurs courts avec profils métier et intégrateur ;
- amélioration des libellés et valeurs par défaut ;
- optimisation des gros scénarios et du rendu des aperçus.

## 12. Stratégie technique de transition

Il n'est pas nécessaire de réécrire le logiciel pour obtenir le principal gain UX.

### À réutiliser

- `InteropScenario` et `InteropScenarioStep` ;
- `ScenarioTemplate` et `ScenarioTemplateStep` ;
- le service de matérialisation des modèles ;
- les contrôles de compatibilité des endpoints ;
- l'import et l'export ;
- le moteur d'exécution et le mode à blanc ;
- les payloads de référence.

### À ajouter ou isoler

- un service d'orchestration de création ;
- des schémas de brouillon et de validation ;
- un écran `scenario_builder` ;
- un module JavaScript dédié au constructeur ;
- des composants partagés pour la chronologie, les erreurs et l'aperçu ;
- des tests de parcours complets.

### Compatibilité

- aucun scénario existant ne doit nécessiter de migration fonctionnelle pour le premier lot ;
- l'ancienne page reste disponible comme mode expert durant la transition ;
- les routes actuelles d'édition des étapes restent utilisables jusqu'à stabilisation du nouveau constructeur ;
- le nouveau parcours matérialise les mêmes modèles persistants que l'existant.

## 13. Mesures de réussite proposées

Établir une mesure de référence avant mise en production, puis suivre :

- durée médiane entre « Nouveau scénario » et « Prêt à tester » ;
- taux de création terminée ;
- taux d'abandon par étape ;
- nombre moyen d'erreurs de validation ;
- part des scénarios créés sans édition de payload brut ;
- part des créations issues d'un modèle ;
- nombre de retours entre l'écran de détail et les écrans techniques ;
- satisfaction déclarée après la première création.

Objectifs initiaux à valider après la mesure de référence :

- réduire d'au moins 50 % le temps de création d'un scénario standard ;
- permettre à au moins 80 % des scénarios standards d'être créés sans édition brute ;
- diminuer d'au moins 40 % les erreurs bloquantes avant le premier test ;
- atteindre un taux de complétion supérieur à 85 % pour le parcours depuis un modèle.

## 14. Risques et réponses

| Risque | Réponse proposée |
|---|---|
| Le parcours guidé limite les experts | Conserver un mode avancé complet et l'accès à la page historique |
| Deux éditeurs divergent | Centraliser la persistance et la validation côté serveur |
| Les modèles ne couvrent pas tous les cas | Autoriser un parcours personnalisé et les surcharges par étape |
| Les brouillons polluent le catalogue | Les isoler dans « Mes brouillons » et les exclure de l'exécution |
| Une modification commune écrase un payload manuel | Marquer les surcharges et demander confirmation avant régénération |
| Le wizard devient lui-même trop long | Valeurs par défaut, étapes courtes, sauvegarde et navigation libre |
| Gros payloads ou longues chronologies | Chargement à la demande, virtualisation si nécessaire et aperçu repliable |

## 15. Ordre recommandé

L'ordre recommandé est :

1. lanceur unifié et assistant minimal ;
2. état brouillon et validation de préparation ;
3. création depuis les modèles existants ;
4. chronologie visuelle des étapes ;
5. données communes et routage assisté ;
6. revue, aperçu et exécution à blanc ;
7. duplication, import et génération regroupés ;
8. réorganisation de la page de détail ;
9. instrumentation et optimisation.

Cette séquence livre rapidement une amélioration visible, limite les changements du modèle de données et permet de tester le nouveau parcours avant de remplacer l'espace de travail historique.

## 16. Définition de fini globale

La refonte peut être considérée comme aboutie lorsque :

- un utilisateur non expert crée un scénario standard depuis une intention métier ;
- aucune donnée technique n'est obligatoire tant qu'elle peut être déduite ;
- chaque erreur indique où et comment la corriger ;
- un brouillon peut être quitté et repris sans perte ;
- les payloads et routes restent modifiables par un expert ;
- l'assistant, l'import, la duplication et les modèles convergent vers la même revue ;
- le scénario créé est compatible avec le moteur d'exécution actuel ;
- les parcours critiques sont couverts par des tests automatisés front et back ;
- l'accessibilité clavier et le comportement mobile sont validés ;
- les indicateurs confirment une baisse mesurable du temps et des erreurs de création.
