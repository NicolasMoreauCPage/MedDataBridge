# Audit IHM et UX — Validateur IHE PAM France

**Date :** 11 septembre 2026

**Périmètre :** validation unitaire et de scénario, journal des messages, détail d'un message et de son ACK, rejets, qualification partenaire, génération de données et formulaires métier produisant des messages PAM.

## Conclusion exécutive

**Réévaluation après corrections : le parcours de validation et de supervision IHE PAM France est désormais explicable de bout en bout.**

Le parcours principal permet de coller ou générer un message France 2.11, choisir sa direction, obtenir un verdict limité aux contrôles effectivement implémentés, atteindre le champ concerné depuis le diagnostic, parcourir segments/champs/répétitions/composants, retrouver le message et son ACK, et filtrer les rejets. Les scénarios de qualification sont également exportables en HL7, copiable et téléchargeable.

La note 10/10 ne peut pas être affirmée de manière responsable sans tests utilisateurs, audit RGAA et qualification auprès d'un partenaire. Le reste des écarts concerne surtout un éditeur exhaustif de toutes les extensions nationales, pas le parcours de validation.

| Domaine | Verdict | Appréciation |
|---|---|---:|
| Validation d'un message brut | Très bonne | 9/10 |
| Validation d'un scénario | Très bonne | 9/10 |
| Supervision et ACK | Très bonne | 9/10 |
| Rendu structuré des données PAM | Très bonne | 9/10 |
| Génération guidée ITI-30/ITI-31 | Bonne | 8/10 |
| Qualification partenaire | Très bonne | 9/10 |
| Accessibilité et cohérence | Bonne, à tester | 8/10 |
| **UX globale du validateur PAM** | **Prête à qualifier** | **9/10** |

## Corrections appliquées

| Écart initial | Correction vérifiable |
|---|---|
| Profil international affiché sans moteur associé | Retiré des deux formulaires : l'écran annonce exclusivement IHE PAM France 2.11. |
| Verdict et « HAPI » trompeurs | Terminologie remplacée par « structure HL7/PAM » et verdict borné aux contrôles implémentés. |
| Issue sans emplacement | Chaque `ValidationIssue` expose désormais couche et localisation HL7, y compris après traduction française et sérialisation. |
| Message brut difficile à lire | Vues structurées non destructives dans la validation et le détail : segment, champ, répétition, composant et sous-composant. |
| Diagnostic non navigable | Les diagnostics renvoient au champ décodé concerné. |
| Supervision incohérente | Correction des attributs obsolètes de la vue dossier, du filtre global `status=error`, de l'option HPRIM dupliquée et ajout de la copie de payload. |
| Exemples HL7 génériques | Exemples d'injection et de scénario complétés avec MSH-9.3, MSH-12 France, EVN, PID-32, PV1 et ZBE. |
| Générateur de qualification JSON-only | Sérialisation HL7 France, carte par message, copie et téléchargement `.hl7`. |
| PID-32 incomplet | Liste nationale complète, saisie des répétitions avec `~` et validation navigateur. |
| Édition patient partielle | La soumission persiste maintenant tous les champs de `PatientUpdateSchema`, y compris les données PAM démographiques. |
| Contacts liés par ID technique | Sélecteurs libellés patient/venue, association obligatoire selon le type et retour d'erreur accessible. |
| Onglets peu accessibles | Rôles ARIA, état sélectionné et navigation clavier par flèches. |

## Ce qui fonctionne bien

### Validation et diagnostic

- validation d'un message unique ou d'un scénario depuis un même écran ;
- distinction visuelle entre erreurs, avertissements et informations ;
- résumé du type, de l'événement, de la direction et du profil ;
- regroupement apparent des résultats entre profil PAM, structure, HL7 v2.5 et types de données ;
- conservation du message saisi après validation et défilement automatique vers le résultat ;
- contrôle entrant configurable par endpoint en mode avertissement ou rejet.

### Supervision

- journal filtrable par endpoint, protocole, direction, période et statut négatif ;
- détail contenant le payload original, l'ACK, la corrélation et le verdict PAM ;
- vues par dossier et par groupe de rejets IPP/dossier ;
- export ZIP d'un dossier avec messages, ACK et rapport JSON ;
- possibilité de rejouer un message en erreur avec confirmation préalable.

### Parcours métier

- le formulaire patient couvre les informations PID courantes, les coordonnées, le NIR et un statut PID-32 ;
- des parcours dédiés existent pour la fusion A40 et la modification d'identifiant A47 ;
- la gestion des contacts couvre une partie utile de NK1 ;
- le workflow de mouvement propose des cartes d'événements, une date, une destination hiérarchique et des aides contextuelles ;
- certains retours dynamiques utilisent `aria-live`, les tables sont placées dans des conteneurs défilants et le thème sombre est largement pris en charge.

## Compatibilité de rendu des informations

| Contenu du message | Rendu actuel | Verdict |
|---|---|---|
| MSH, EVN, PID, PV1, ZBE et extensions | Payload brut monospace | Visible, mais non décodé |
| Type, trigger, direction, endpoint, corrélation | Cartes et badges | Bon |
| Verdict et nombre d'issues | Cartes et listes | Bon |
| ACK MSH/MSA/ERR | Payload brut | Bon pour un expert |
| Emplacement exact d'une erreur | Souvent inclus seulement dans le texte libre | Insuffisant |
| Segment, champ, répétition, composant et sous-composant | Pas de vue arborescente ou tabulaire | Absent |
| Valeur reçue comparée à la valeur attendue | Pas de comparaison dédiée | Absent |
| Données patient et venue interprétées | Réparties dans d'autres écrans métier | Partiel |
| Historique d'un scénario | Résumé et liste des messages | Bon |
| Preuve de qualification | Statut, ACK et extrait du payload | Partiel |

Le détail d'un message permet donc de lire l'intégralité des octets décodés, mais pas de comprendre rapidement `PID-3.4.2`, une répétition de PID-32 ou le contenu XON de ZBE-7. Pour un validateur, c'est le principal manque fonctionnel de l'IHM.

## Compatibilité de génération

### Événements accessibles depuis des parcours guidés

- identité : A28/A31 par création ou modification du patient ;
- rapprochement : A40 et A47 par formulaires dédiés ;
- mouvements courants : A01, A02, A03, A04, A05, A06, A07, A11, A12, A13, A21, A22 et A38 ;
- tous les autres messages peuvent être collés manuellement dans l'écran d'injection.

### Événements ou données sans parcours IHM complet

- A15/A26, A44, A52/A53, A54/A55 et Z99 ne sont pas proposés dans le workflow de mouvement ;
- les actions, références et natures ZBE ne sont pas éditables explicitement ;
- les extensions ZFA, ZFP, ZFV, ZFM, ZFD et ZFS n'ont pas de formulaire métier complet ;
- IN1/IN2/IN3, GT1, OBX et ACC restent essentiellement accessibles par le message brut ;
- le générateur de scénarios expose son résultat comme un bloc JSON, sans vue par message, copie ciblée, téléchargement `.hl7` ni envoi direct ;
- l'API de génération accepte la spécialité et des injections d'erreurs, mais l'IHM ne propose pas ces paramètres.

### Écarts de données dans les formulaires

1. Le sélecteur PID-32 du patient ne propose qu'une partie de la table nationale et ne permet qu'une valeur, alors que le validateur accepte la table complète et les répétitions.
2. Les modèles possèdent des champs ZFD, ZFA, ZFP et ZFV qui ne sont pas exposés dans le formulaire patient ou mouvement.
3. Le formulaire NK1 demande des identifiants numériques internes de patient ou de venue au lieu d'une recherche lisible ; il n'expose qu'une partie des champs que les modèles savent conserver.
4. Le formulaire A47 suggère encore l'ancien libellé d'autorité `ASIP-SANTE-INS-NIR`, alors que la génération corrigée utilise l'autorité INS nationale.

**Conséquence :** l'IHM peut générer des cas courants conformes, mais elle ne constitue pas encore un constructeur exhaustif de messages IHE PAM France.

## Incompatibilités et incohérences observées

### P0 — confiance dans le verdict

1. Le sélecteur « IHE PAM International » transmet un nom de profil, mais le validateur applique toujours les règles France. Il faut soit implémenter ce profil, soit retirer l'option.
2. Les textes « parfaitement valide » et « aucune erreur sur les 4 couches » sont trop absolus : la couche HL7 v2.5 réalise des contrôles essentiels, pas une validation exhaustive du standard.
3. La couche présentée comme « HAPI » repose sur des tables Python internes ; aucune exécution d'un validateur HAPI strict n'a été trouvée. Le libellé doit indiquer « structure HL7/PAM interne ».
4. Une issue persistée contient seulement `code`, `message` et `severity`. Le composant d'affichage attend aussi `layer` et `location`, qui ne sont donc pas disponibles dans le détail du journal.

### P1 — diagnostic et supervision

1. Le détail du message ne permet pas de cliquer sur une erreur pour atteindre le segment et le champ concernés.
2. Les quatre listes de résultats sont rendues par du code dupliqué, ce qui augmente le risque d'écart entre la validation immédiate, le journal et l'espace « Conformité ».
3. La vue d'un dossier référence d'anciens attributs (`validation_status`, `pam_validation_errors`, `segment_validation_errors`, `ack_text`) absents du modèle `MessageLog`; certaines informations peuvent donc ne jamais s'afficher.
4. Le filtre protocole du journal contient deux options HPRIM identiques.
5. Le lien global `messages?status=error` n'est pas traité par la route de liste, qui attend `neg_ack_only`.
6. Le détail standard ne propose pas le bouton de copie présent dans le détail « Conformité ».

### P1 — génération

1. Les exemples des écrans « Injecter » et « Scénario » utilisent encore des messages génériques `2.5` ou un MSH-9 sans structure ; ils ne sont pas de bons points de départ pour PAM France.
2. Le workflow graphique ne couvre pas tout le catalogue que le moteur reçoit et valide.
3. Aucun aperçu « données métier → segments générés → validation avant envoi » n'est présenté avant une émission réelle.
4. Le générateur de scénarios montre le modèle JSON interne plutôt que le livrable HL7 attendu par l'utilisateur.

### P2 — UX et accessibilité

1. L'interface mélange français et anglais : `Inbound`, `Outbound`, `Warning`, `Fail`, `Event`, `Kind` et des messages de validation en anglais.
2. Les onglets du validateur sont des boutons visuels sans sémantique ARIA complète (`role=tab`, `aria-selected`, `aria-controls`) ni gestion clavier dédiée.
3. Plusieurs formulaires associent visuellement un libellé à un champ sans attribut `for`, notamment dans les formulaires patient et mouvement.
4. Les retours de copie et de rejeu utilisent encore `alert()`/`confirm()`, moins cohérents et moins accessibles que le système de notifications partagé.
5. Les pages de validation sont très longues et toutes les catégories sont développées ; des panneaux repliables, un filtre par sévérité et une recherche réduiraient la charge cognitive.
6. Le NIR et les payloads complets sont affichés et exportés sans masquage visible dans les templates. Une politique selon les rôles est souhaitable pour les démonstrations et captures d'écran.

## Évaluation des parcours

| Parcours utilisateur | Nombre d'étapes perçu | Résultat |
|---|---:|---|
| Coller et valider un message | 1 formulaire | Simple |
| Comprendre pourquoi il est refusé | Liste d'issues puis lecture manuelle du brut | Laborieux |
| Retrouver un rejet partenaire | Filtres puis détail | Correct |
| Comparer message et ACK | Même page | Bon |
| Corriger puis revalider | Copier, revenir au validateur, modifier, relancer | Trop fragmenté |
| Construire un mouvement courant | Workflow guidé | Bon |
| Construire un cas PAM avancé | Message brut ou scénario technique | Difficile |
| Prouver une qualification | Tableau et extraits | Utilisable, preuve incomplète |

## Recommandations

### P0 — rendre le verdict explicable

1. Enrichir chaque issue avec `layer`, `segment`, `field`, `repetition`, `component`, `line`, `actual` et `expected`.
2. Ajouter une vue structurée du message, synchronisée avec le brut, et surligner la zone concernée lorsqu'une issue est sélectionnée.
3. Remplacer les libellés « parfaitement valide » et « HAPI » par des formulations correspondant exactement aux contrôles exécutés.
4. Retirer le profil international tant qu'il ne dispose pas de règles distinctes.

### P1 — aligner les formulaires sur le profil France

1. Utiliser la même matrice centrale pour alimenter le catalogue d'événements du validateur, du workflow et du générateur.
2. Compléter PID-32, y compris les répétitions, et exposer les données nationales réellement conservées.
3. Ajouter des assistants pour A44, Z99, A52/A53 et A54/A55, avec choix contrôlés de l'événement d'origine et du mouvement visé.
4. Afficher un aperçu HL7 validé avant envoi, avec téléchargement, copie et injection en un clic.
5. Transformer le JSON du générateur de scénarios en cartes par étape contenant le trigger, le message, son verdict et ses actions.

### P2 — fluidifier l'usage quotidien

1. Unifier les vues « Validation », « Messages » et « Conformité » autour d'un seul composant de rapport.
2. Ajouter recherche, tri et filtres par trigger, code d'erreur, statut PAM et identifiant de contrôle MSH-10.
3. Uniformiser la terminologie française et les statuts.
4. Remplacer les identifiants techniques des formulaires par des champs de recherche patient, dossier et venue.
5. Ajouter des tests clavier, lecteur d'écran, contraste et affichage mobile aux tests de rendu existants.

## Tests et méthode

L'audit est fondé sur l'inspection des routes, modèles, services de génération et templates, puis sur deux campagnes de rendu :

| Campagne | Résultat |
|---|---|
| Routes PAM ciblées : validation, messages, dossiers, rejets, contacts et qualification | **7 réussies, 0 échec** |
| Suite UI sélectionnée : rendu, smoke tests et scripts de templates | **23 réussies, 4 échecs** |

Les quatre échecs généraux concernent un test Swagger trop strict, l'ancien nom « MedData Bridge », l'ancien favicon et une attente de redirection devenue obsolète. Ils n'empêchent pas le rendu PAM, mais indiquent que les tests d'acceptation UI ne suivent plus complètement l'interface actuelle.

Cet audit est une revue statique et fonctionnelle interne. Il ne remplace pas des tests utilisateurs avec des profils d'intégrateur, de référent identité et de support production, ni une campagne d'accessibilité RGAA.

## Fichiers principaux examinés

- [`app/templates/validation.html`](../../app/templates/validation.html)
- [`app/templates/messages.html`](../../app/templates/messages.html)
- [`app/templates/message_detail.html`](../../app/templates/message_detail.html)
- [`app/templates/messages_dossier_detail.html`](../../app/templates/messages_dossier_detail.html)
- [`app/templates/qualification_dashboard.html`](../../app/templates/qualification_dashboard.html)
- [`app/templates/test_scenario_generator.html`](../../app/templates/test_scenario_generator.html)
- [`app/templates/patient_form.html`](../../app/templates/patient_form.html)
- [`app/templates/mouvement_workflow.html`](../../app/templates/mouvement_workflow.html)
- [`app/services/pam_validation.py`](../../app/services/pam_validation.py)
- [`app/services/emit_on_create.py`](../../app/services/emit_on_create.py)
