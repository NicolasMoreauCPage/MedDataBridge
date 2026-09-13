# Plan de refonte du front et de l'expérience utilisateur

Date : 13 septembre 2026
Périmètre : ensemble des interfaces Web de PAMélia, hors sécurité.

## Décision proposée

Le front est fonctionnel et riche, mais il a atteint le point où ajouter des
corrections écran par écran coûtera plus cher qu'une refonte progressive. La
priorité doit être de reconstruire un socle commun, puis de migrer les parcours
par domaine métier.

La recommandation est de conserver FastAPI et le rendu serveur Jinja, adaptés à
un outil LAN, et de moderniser l'interface avec :

- un shell applicatif unique et léger ;
- Tailwind et un seul système de composants sémantiques ;
- HTMX pour les mises à jour partielles et Alpine uniquement pour les états
  locaux simples ;
- des modules JavaScript sans gestionnaires inline ;
- CodeMirror pour l'édition HL7, XML et JSON ;
- une pagination et des filtres gérés côté serveur.

Une migration vers React/Vue n'est pas justifiée à ce stade : elle imposerait
de réécrire les 244 réponses HTML des routes sans résoudre à elle seule les
problèmes d'architecture de l'information, de cohérence ou d'accessibilité.

## Méthode de l'audit

L'analyse combine :

- l'inventaire des templates, styles, scripts et composants ;
- l'inspection du layout, de la navigation et des principaux parcours ;
- des rendus Playwright en 1 440 × 1 000 et 390 × 844 ;
- des contrôles sur l'overflow, la hauteur des pages et les erreurs de rendu ;
- la prise en compte de l'audit IHE PAM précédent.

Il ne s'agit pas d'un audit RGAA officiel ni d'un test utilisateur terrain.

## État des lieux mesuré

| Indicateur | Valeur observée |
|---|---:|
| Templates HTML | 162 |
| Volume front, CSS et JavaScript compris | environ 42 000 lignes |
| Layout `base.html` | 1 315 lignes |
| Bibliothèque `macros/ui.html` | 920 lignes |
| Templates contenant un script | 62 |
| Balises `<script>` dans les templates | 88 |
| Templates contenant du CSS inline | 20 |
| Gestionnaires `onclick` inline | 143 |
| Appels `alert()` | 40 |
| Appels `confirm()` | 38 |
| Affectations ou insertions `innerHTML` | 145 |
| Traces `console.log` hors bibliothèques | 48 |
| Marqueurs TODO/FIXME front | 21 |
| Tables HTML | 62 pour 49 conteneurs horizontaux identifiés |

Le système de composants est dupliqué : `status_badge`, `empty_state` et
`pagination` existent dans deux bibliothèques différentes. Deux macros
`modal` sont même définies dans le même fichier, la seconde masquant la
première. Tailwind, DaisyUI, des composants CSS maison et des classes locales
sont utilisés simultanément.

Le layout charge également des scripts métier sur toutes les pages, dont le
script de structure interactive. Il contient du CSS, la navigation, les
notifications, les loaders, les raccourcis, le thème et un correctif heuristique
qui parcourt tout le DOM pour masquer un élément supposé parasite.

## Résultats des rendus responsive

Les mesures suivantes correspondent à un viewport de 390 pixels :

| Page | Largeur réelle du contenu | Hauteur rendue | Verdict |
|---|---:|---:|---|
| Tableau de bord GHT | 472 px | 3 923 px | débordement |
| Structure | 622 px | 1 915 px | débordement |
| Endpoints | 827 px | 1 503 px | débordement important |
| Dossiers | 1 303 px | 1 546 px | inutilisable sans défilement latéral |
| Scénarios | 1 440 px | 20 853 px | inutilisable sur mobile |
| Messages | 1 051 px | 19 137 px | inutilisable sur mobile |
| Validation | 488 px | 1 620 px | débordement modéré |

La liste des scénarios affiche 289 lignes et la supervision 199 messages dans
une seule page. Le conteneur de table défilant ne suffit pas : des barres
d'outils et des en-têtes imposent aussi leur largeur au document entier.

Le rendu de `/scenarios/2` a par ailleurs répondu HTTP 500 avec une
`UndefinedError`. Ce défaut doit être corrigé avant toute refonte visuelle du
détail.

## Points forts à préserver

- identité PAMélia déjà reconnaissable ;
- thème clair, sombre et automatique ;
- lien d'évitement vers le contenu principal ;
- contexte GHT/EJ/patient/dossier visible ;
- parcours fonctionnels très complets ;
- fil d'Ariane présent sur une majorité de pages ;
- premiers composants partagés et premiers tests Playwright ;
- informations métier riches sur les scénarios, messages et endpoints ;
- usage cohérent du rendu serveur, robuste dans un environnement LAN.

## Problèmes à traiter

### P0 — fonctionnement et utilisabilité

1. Corriger toutes les pages qui répondent 500, en commençant par le détail de
   scénario.
2. Supprimer tout overflow horizontal au niveau de la page. Seuls un éditeur de
   code ou une table explicitement défilante peuvent défiler horizontalement.
3. Ajouter une pagination serveur aux scénarios, messages, dossiers,
   exécutions et autres catalogues volumineux. La valeur par défaut recommandée
   est 25 ou 50 lignes.
4. Rendre les actions principales accessibles sur mobile et empêcher les
   barres d'outils de conserver une largeur desktop.
5. Retirer les boutons ou fonctions factices signalés par des TODO dans les
   écrans de cotation et de structure, ou les terminer avant de les présenter.
6. Remplacer les erreurs silencieuses, `alert()` et `confirm()` par le système
   partagé de notifications et de dialogues.

### P1 — architecture de l'information

La navigation actuelle expose trop de fonctions dans de grands menus et mélange
actions quotidiennes, documentation et administration. Le contexte actif
occupe jusqu'à quatre pastilles distinctes, ce qui réduit fortement l'espace
disponible.

L'architecture cible comportera cinq espaces :

| Espace | Contenu principal |
|---|---|
| Piloter | tableau de bord, santé des transports, activité récente, alertes |
| Valider | validation ponctuelle, supervision, rejets, qualification |
| Scénarios | catalogue, exécutions, campagnes, profils de destinations |
| Données de test | patients, dossiers, venues, mouvements, actes, structure |
| Configurer | GHT/EJ, endpoints, vocabulaires, imports et administration |

La documentation devient une aide globale, accessible depuis l'en-tête et
contextualisée par écran, au lieu d'occuper un méga-menu métier.

### P1 — cohérence visuelle et interaction

- trop de variantes de cartes, boutons, badges, champs et en-têtes ;
- mélange d'icônes SVG, d'emoji et de symboles texte ;
- dégradés et couleurs d'accent employés sur presque tous les blocs, ce qui
  affaiblit la hiérarchie ;
- textes et statuts encore mélangés entre français et anglais ;
- libellés à normaliser, notamment « interopération » vers
  « interopérabilité » ;
- actions destructives parfois placées au même niveau que les actions usuelles ;
- états vides, chargements et erreurs différents selon les pages ;
- plusieurs pages concurrentes pour la structure, les dashboards, les
  composants et la cotation ;
- raccourcis clavier non découvrables et potentiellement incompatibles avec le
  navigateur ou les technologies d'assistance.

### P1 — dette technique front

- JavaScript fortement couplé au DOM par des identifiants globaux ;
- logique applicative directement incluse dans les templates ;
- multiples macros portant le même nom ;
- chargement global de scripts uniquement utiles à certaines routes ;
- rendu par chaînes HTML et `innerHTML`, difficile à tester et à sécuriser
  fonctionnellement ;
- comportement responsive corrigé localement plutôt que garanti par le shell ;
- absence de catalogue officiel des composants réellement supportés ;
- absence de tests de régression visuelle multi-résolutions.

## Vision du nouveau shell applicatif

### Navigation desktop

- barre latérale repliable avec les cinq espaces ;
- en-tête compact contenant le fil de contexte, la recherche globale, l'aide,
  le thème et l'état du système ;
- entrée active clairement indiquée ;
- sous-navigation locale dans la page, pas dans un méga-menu global ;
- palette de commandes avec `Ctrl+K` pour rechercher un patient, un dossier,
  un scénario, un message ou une action.

### Navigation mobile

- en-tête réduit à l'identité, au contexte et au bouton de navigation ;
- tiroir plein écran regroupé par espace ;
- actions primaires dans une barre basse ou un bouton d'action local ;
- filtres dans un panneau latéral ;
- détail d'une ligne affiché en cartes, sans reproduire une table desktop de
  dix colonnes.

### Contexte métier

Le contexte devient un fil unique :

```text
GHT Démo > CHU Démo > Patient DUPONT Jean > Dossier 12345
```

Un clic ouvre un sélecteur permettant de remplacer ou d'effacer chaque niveau.
Les écrans qui ne nécessitent aucun contexte l'indiquent, tandis que les écrans
qui en exigent un proposent directement de le sélectionner.

## Ateliers métier à reconstruire

### 1. Catalogue des scénarios

- pagination, recherche instantanée différée et filtres dans l'URL ;
- filtres par thème, protocole, état actif, statut de revue, dernier verdict et
  date de dernière exécution ;
- regroupement facultatif par thème/package ;
- vues enregistrées : « actifs », « à corriger », « en échec sur cette cible » ;
- actions de masse dans une barre contextuelle qui n'apparaît qu'après
  sélection ;
- noms, commentaires et dernière exécution visibles sans ouvrir le détail ;
- mode carte sur petit écran et table compacte sur desktop.

### 2. Éditeur de scénario

Créer un véritable atelier en trois zones :

```text
Étapes ordonnées | Éditeur du message | Paramètres et validation
```

- une étape par message, avec ajout, duplication, suppression et déplacement ;
- glisser-déposer accessible avec alternative par boutons ;
- éditeur CodeMirror HL7/XML/JSON, numéros de ligne et recherche ;
- rendu HL7 avec vrais retours de segment ;
- édition du délai, du caractère obligatoire, du routage et des assertions ;
- variables IPP, dossier, venue, mouvement, médecin, UF et dates affichées dans
  un inspecteur commun ;
- validation continue et clic sur une erreur pour atteindre le champ ;
- aperçu du payload compilé pour chaque destination ;
- historique des versions et comparaison avant/après ;
- sauvegarde explicite avec état « non enregistré » visible.

### 3. Lancement d'un scénario

Remplacer les formulaires dispersés par un assistant court :

1. scénario ou campagne ;
2. destinations et profil UF/médecins ;
3. variables du jeu, graine et options de dates ;
4. prévisualisation des messages compilés et de leur validation ;
5. confirmation puis suivi de l'exécution.

L'utilisateur doit savoir avant l'envoi combien de messages seront produits,
vers quels endpoints, avec quelles substitutions et quels avertissements.

### 4. Suivi d'exécution

- en-tête de verdict global toujours visible ;
- matrice étapes × destinations ;
- chronologie temps réel des états planifié, envoyé, ACK, erreur et rejeu ;
- détail d'une livraison dans un panneau latéral ;
- comparaison payload source, payload compilé et ACK ;
- filtre « erreurs uniquement » et rejeu au niveau livraison, cible ou jeu ;
- lien direct vers les données métier créées et les messages journalisés.

### 5. Validateur

- atelier en deux panneaux redimensionnables : éditeur à gauche, diagnostic à
  droite ;
- détection automatique HL7/HPRIM/FHIR, tout en permettant de forcer le profil ;
- dépôt de fichier, collage et exemples propres au standard ;
- vues brut, structuré et métier ;
- erreurs triables par couche et sévérité ;
- sélection d'une issue synchronisée avec le segment/champ XML ou HL7 ;
- affichage valeur reçue, valeur attendue, règle et référence documentaire ;
- correction puis nouvelle validation sans quitter l'écran ;
- export du rapport et du message corrigé.

### 6. Supervision des messages

- pagination serveur et actualisation optionnelle ;
- filtres compacts, repliables et conservés dans l'URL ;
- vues enregistrées par endpoint ou logiciel cible ;
- recherche MSH-10, IPP, dossier, trigger et code ACK ;
- colonnes configurables et en-tête de table fixe ;
- panneau de détail sans perdre la position dans la liste ;
- onglets payload, message décodé, validation, ACK et corrélation ;
- rejeu avec prévisualisation de la destination et retour non bloquant.

### 7. Structure et données de test

- fusionner les vues concurrentes de la structure en un seul master/detail ;
- arbre virtualisé ou chargé à la demande ;
- recherche globale des nœuds et chemin hiérarchique toujours visible ;
- éditeur dans un panneau latéral, avec validation et confirmation partagées ;
- formulaires patient/dossier/venue/mouvement découpés en sections métier ;
- résumé avant émission des messages induits par une opération ;
- autocomplétion pour les UF, médecins, patients et dossiers ;
- mode compact pour la consultation mobile, édition avancée réservée au grand
  écran si nécessaire.

### 8. Endpoints et profils de destination

- vue synthétique par logiciel cible regroupant MLLP, HPRIM, FHIR et fichiers ;
- état, dernier test, dernière erreur et volume récent visibles immédiatement ;
- assistant de configuration par protocole ;
- bouton de test avec progression et résultat détaillé ;
- éditeur dédié du profil UF/médecins avec recherche dans la structure ;
- aperçu des substitutions appliquées aux scénarios ;
- distinction nette entre configuration, supervision et actions destructives.

## Nouveau design system

Conserver la marque PAMélia, mais réduire le nombre de variantes. Le système
doit être défini par des tokens et des composants documentés.

### Tokens

- couleurs de fond, surface, texte, bordure et accent ;
- états succès, avertissement, erreur, information et neutre ;
- échelle d'espacement unique ;
- rayons, ombres, hauteurs de contrôles et largeurs de contenu ;
- typographie interface et monospace ;
- thèmes clair, sombre et contraste renforcé.

### Composants obligatoires

- page header et barre d'actions ;
- bouton, menu d'actions et bouton icône ;
- champ, select, autocomplétion, date et groupe de champs ;
- alerte, toast et dialogue de confirmation ;
- badge et statut avec icône et libellé ;
- tabs, accordéon, panneau latéral et modal ;
- table de données, pagination, filtres et état vide ;
- skeleton de chargement et erreur récupérable ;
- éditeur de code et rapport de validation ;
- fil d'Ariane et sélecteur de contexte.

Il faut supprimer DaisyUI ou l'adopter intégralement. La recommandation est de
le retirer et de conserver Tailwind avec des composants Jinja maîtrisés, afin
d'éviter les collisions actuelles sur `.btn`, `.card`, les thèmes et les
couleurs.

## Architecture technique cible

```text
templates/
├── layouts/
│   ├── app.html
│   └── document.html
├── components/
│   ├── navigation/
│   ├── data_table/
│   ├── forms/
│   ├── feedback/
│   └── protocol/
├── pages/
│   ├── validation/
│   ├── messages/
│   ├── scenarios/
│   ├── structure/
│   └── configuration/
└── fragments/
```

Principes :

- layout limité à l'ossature et aux imports ;
- navigation produite depuis une configuration Python testable ;
- macros sans doublon et API documentée ;
- composants de page alimentés par des view-models explicites ;
- fragments HTMX réutilisant les mêmes routes et règles métier ;
- JavaScript organisé en modules chargés uniquement par les pages concernées ;
- aucun `onclick`, `onchange` ou `onsubmit` inline ;
- aucune chaîne HTML construite avec une donnée métier non maîtrisée ;
- état des filtres, tris et pages représenté dans l'URL ;
- scripts globaux limités au shell, au thème, au contexte et aux notifications.

## Accessibilité et RGAA

La refonte doit préparer un véritable audit RGAA :

- ordre des titres et landmarks cohérent ;
- menus, onglets, arbres, dialogues et listes respectant leurs modèles ARIA ;
- parcours complet au clavier et focus restauré après fermeture d'un panneau ;
- zones cliquables d'au moins 44 × 44 pixels sur écran tactile ;
- libellés et erreurs de formulaire reliés aux champs ;
- statut jamais communiqué par la couleur seule ;
- contraste AA, zoom 200 % et reflow à 320 pixels ;
- respect de `prefers-reduced-motion` ;
- notifications avec niveaux `aria-live` adaptés ;
- éditeur de code accompagné d'une alternative textarea accessible ;
- terminologie française unique et textes compréhensibles hors contexte visuel.

L'objectif automatisé est zéro erreur critique Axe. La conformité RGAA ne sera
déclarée qu'après une vérification manuelle des critères applicables.

## Plan de réalisation

### Lot 0 — stabilisation

- corriger les erreurs 500 de rendu ;
- ajouter les paginations critiques ;
- corriger `main` avec `width: 100%` et `min-width: 0` ;
- contenir les tables et barres d'actions ;
- retirer ou désactiver les actions factices ;
- ajouter un test automatique interdisant l'overflow du document.

Critère de sortie : scénarios, messages, dossiers, endpoints, structure et
validation répondent 200 et n'élargissent pas la page à 390 pixels.

### Lot 1 — fondations

- créer les tokens et le catalogue de composants ;
- remplacer les macros dupliquées ;
- créer le nouveau layout sous un nom temporaire ;
- extraire le CSS et le JavaScript de `base.html` ;
- mettre en place les modules JavaScript et HTMX ;
- ajouter les tests visuels clair/sombre et desktop/mobile.

### Lot 2 — navigation et contexte

- nouvelle barre latérale et en-tête ;
- fil de contexte unique ;
- navigation mobile ;
- recherche/palette de commandes ;
- aide contextuelle et état système.

### Lot 3 — primitives métier

- nouvelle table de données paginée ;
- système de filtres commun ;
- formulaires, erreurs et autocomplétions ;
- dialogues et notifications ;
- vues sauvegardées et états vides.

### Lot 4 — cœur interopérabilité

- validateur ;
- supervision et détail d'un message ;
- catalogue, éditeur et lancement des scénarios ;
- suivi des exécutions et campagnes ;
- qualification partenaire.

### Lot 5 — données et structure

- structure unifiée ;
- patients, dossiers, venues et mouvements ;
- HPRIM, CCAM, NGAP, UCD et LPP ;
- endpoints et profils UF/médecins.

### Lot 6 — administration et convergence

- vocabulaires, imports et configuration GHT/EJ ;
- dashboards d'exploitation ;
- suppression des pages et composants hérités devenus inutiles ;
- nettoyage de la documentation et des liens internes.

### Lot 7 — qualification finale

- tests avec un intégrateur, un référent identité et un exploitant ;
- audit clavier, lecteur d'écran, contraste et zoom ;
- test sur jeux volumineux et exécutions longues ;
- correction des régressions visuelles ;
- audit RGAA séparé si une déclaration de conformité est recherchée.

## Stratégie de migration

La refonte ne doit pas être un basculement unique. Le nouveau layout peut être
introduit en parallèle, puis activé domaine par domaine :

1. shell et composants ;
2. validation et messages ;
3. scénarios ;
4. structure et données ;
5. administration ;
6. suppression de l'ancien shell.

Les routes, formulaires POST et services métier restent stables autant que
possible. Chaque page migrée doit remplacer complètement son ancienne version
pour éviter de maintenir deux interfaces actives.

## Tests à ajouter

### Tests de rendu

- 390 × 844, 768 × 1 024 et 1 440 × 1 000 ;
- thèmes clair et sombre ;
- aucune barre de défilement horizontale sur `body` ;
- captures de référence des écrans critiques ;
- états vide, chargé, erreur, partiel et volumineux.

### Parcours Playwright

- choisir un contexte et retrouver le fil complet ;
- valider un message puis atteindre son erreur ;
- filtrer un message, ouvrir son détail et revenir sans perdre les filtres ;
- éditer, prévisualiser et exécuter un scénario ;
- suivre une exécution partielle puis rejouer une livraison ;
- créer un patient/dossier/mouvement et vérifier les messages générés ;
- configurer un profil UF/médecin et vérifier son aperçu ;
- réaliser tous ces parcours principaux au clavier.

### Budgets de qualité

- zéro erreur JavaScript dans la console sur les parcours couverts ;
- zéro erreur Axe critique ;
- aucun template actif supérieur à 500 lignes hors documentation générée ;
- layout principal inférieur à 200 lignes ;
- aucun gestionnaire d'événement inline ;
- aucun `alert()` ou `confirm()` natif ;
- page initiale sans script métier inutile ;
- listes paginées et temps de rendu stable avec 10 000 enregistrements.

## Indicateurs de réussite UX

| Indicateur | Cible |
|---|---:|
| Accès à un scénario par nom ou thème | moins de 10 secondes |
| Identification de l'étape en erreur | moins de 15 secondes |
| Retrouver un message par MSH-10 ou dossier | moins de 10 secondes |
| Lancer un jeu vers plusieurs destinations | au plus 5 écrans courts |
| Largeur du document à 390 px | 390 px maximum |
| Lignes chargées par défaut dans une liste | 25 à 50 |
| Actions principales visibles sans défilement | 1 par écran |
| Erreurs critiques Axe | 0 |

## Définition de terminé

La refonte sera réellement terminée lorsque :

- tous les templates actifs auront été inventoriés, migrés ou supprimés ;
- il n'existera plus qu'un layout applicatif et une bibliothèque de composants ;
- les pages principales fonctionneront à 320/390 pixels sans overflow global ;
- les listes volumineuses seront paginées côté serveur ;
- validation, supervision et scénarios partageront le même rendu des payloads,
  diagnostics, ACK et statuts ;
- les actions factices et les TODO visibles auront disparu ;
- les parcours critiques seront couverts en desktop, mobile, clair et sombre ;
- trois profils utilisateurs auront validé les tâches principales ;
- la documentation utilisateur correspondra exactement au nouveau front.

## Ordre recommandé

Le meilleur rapport valeur/risque est : stabilisation responsive, composants,
navigation, puis refonte conjointe des scénarios et des messages. Ces deux
domaines concentrent les volumes, les statuts, les filtres, les payloads et les
actions asynchrones ; leurs composants pourront ensuite être réutilisés dans le
validateur, les endpoints, HPRIM et les écrans métier.
