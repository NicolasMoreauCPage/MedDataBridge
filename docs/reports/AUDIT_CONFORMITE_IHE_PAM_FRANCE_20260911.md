# Audit de conformité IHE PAM France / CPage

**Date de l'audit initial :** 11 septembre 2026
**Mise à jour des correctifs :** 11 septembre 2026
**Révision initialement auditée :** `403ce0e` (`main`), avec les modifications locales présentes au moment de l'analyse
**Référentiels :** IHE France PAM National Extension 2.11.1, contraintes françaises sur les types de données 1.8.1, HL7 v2.5 et spécification d'interface CPage IHE PAM 2.11 (document 1.3 du 01/07/2025)

## Conclusion exécutive

**Verdict après correctifs : socle IHE PAM France/CPage techniquement réaligné et contrôlé par tests ciblés.**

Les écarts bloquants relevés dans l'audit initial ont été corrigés : structures MSH-9, ZBE, actions d'annulation, A44, jeu d'événements, encodage MLLP/ACK, identifiants et XTN, ainsi que le filtrage d'émission. Le validateur détecte désormais les erreurs normatives injectées et accepte les principales variantes nationales précédemment rejetées. L'IHM expose le contrôle entrant et sa politique `warn`/`reject` pour chaque endpoint.

Cette conclusion est une validation technique interne : elle **ne vaut pas certification IHE, Connectathon ni recette bilatérale CPage**. Les extensions françaises non consommées par le modèle métier restent tolérées et journalisées ; leur conservation exhaustive nécessite une qualification métier spécifique.

| Question | Réponse auditée |
|---|---|
| Intégrer/recevoir ITI-30 | **Oui, périmètre implémenté** : A28/A31/A40/A47, structures et segments requis contrôlés. |
| Intégrer/recevoir ITI-31 | **Oui, périmètre implémenté** : mouvements nationaux, annulations, A44 et Z99 contrôlés. |
| Générer ITI-30 | **Oui** : MSH-9, MSH-12/17/18, identifiants et MRG normalisés. |
| Générer ITI-31 | **Oui** : ZBE normalisé, annulations corrigées et émission bloquée en cas d'erreur. |
| Détecter les messages non conformes | **Oui pour la matrice contrôlée** : structures, champs interdits, actions, dates, PID-32 et segments inconnus. |
| Utiliser le rejet automatique en production | **Oui, après recette de l'endpoint** : mode `reject` disponible ; commencer en `warn` sur les flux historiques. |

### Correctifs appliqués après l'audit initial

- une matrice normative unique centralise les événements, structures, natures de venue et règles ZBE ;
- la génération et les générateurs secondaires normalisent MSH-9, MSH-12, MSH-17, MSH-18, ZBE-1 et ZBE-3 avant l'envoi ;
- le transport MLLP encode selon MSH-18 et les ACK reprennent le trigger, la structure, le pays et le jeu de caractères ;
- le traitement A44 réaffecte le dossier de l'identité `MRG-1` vers l'identité `PID-3`, sans rendre ZBE artificiellement obligatoire ;
- le validateur contrôle les structures, les actions, les dates calendaires, PID-19, PID-32, les segments inconnus et les valeurs nationales de ZBE-9 ;
- l'émission automatique est bloquée si la validation sortante échoue ;
- l'IHM de configuration d'endpoint permet d'activer le contrôle PAM France entrant et de choisir entre journalisation et ACK `AE`.

Les détails ci-dessous décrivent le constat **avant correction** et sont conservés comme traçabilité de l'audit.

Il ne faut donc pas présenter l'application comme « conforme IHE PAM France 2.11.1 » ni activer un rejet systématique des flux CPage sur la seule décision du validateur actuel.

## Périmètre et méthode

L'audit a croisé :

- la spécification nationale [IHE France PAM 2.11.1](../SpecIHEPAM/Publication-IHE_FRANCE_PAM_National_Extension_v2.11.1.pdf) et sa version texte ;
- les [contraintes françaises sur les types de données 1.8.1](../SpecIHEPAM/IHE_France_Constraints_on_HL7_data_types_for_ITI_V1.8.1.pdf) ;
- les chapitres HL7 v2.5 présents dans [`docs/HL7v2.5`](../HL7v2.5/) ;
- la [spécification CPage IHE PAM 2.11](../SpecIHEPAM_CPage/INT_CPAGE_FORMAT_IHE_PAM_2.11.pdf) ;
- le chemin réel d'émission, le chemin réel de réception, le routeur, les parseurs, le validateur stateless, le validateur de séquence et les ACK ;
- 55 tests unitaires PAM ciblés, 6 tests d'intégration ciblés, 200 messages de production anonymisés et 1 170 exemples de messages du dépôt ;
- une matrice négative ciblée injectant des erreurs normatives une à une.

Cet audit est une évaluation technique interne. Il ne remplace pas une qualification avec un outil de référence, une campagne Gazelle/IHE Connectathon ou une recette bilatérale CPage.

## Référentiel fonctionnel retenu

### ITI-30 — Patient Identity Management

Le profil national impose les événements suivants :

| Événement | Structure attendue | Objet |
|---|---|---|
| A28 | `ADT_A05` | création d'identité |
| A31 | `ADT_A05` | mise à jour d'identité |
| A47 | `ADT_A30` | modification d'identifiant |
| A40 | `ADT_A39` | fusion d'identités |

### ITI-31 — Patient Encounter Management

Le socle national obligatoire couvre notamment A01/A11, A04/A11, A03/A13, A05/A38, A06/A07, A07/A06, A02/A12, A54/A55, A21/A52, A22/A53, A44 et Z99. Les événements d'attente A15/A26 font partie des options selon le périmètre d'intégration. La mise à jour d'identité est portée par A31 et la correction d'un mouvement par Z99 ; A08 n'est pas l'événement de mise à jour PAM France attendu.

## Matrice de couverture observée

La colonne « Réception » signifie que le routeur possède un chemin applicatif. Elle ne garantit pas que tous les messages conformes sont acceptés ni que toutes leurs données sont conservées.

| Événement | Structure CPage/nationale | Réception | Génération réelle | Validation actuelle | Verdict |
|---|---|---:|---:|---:|---|
| A28 | `ADT_A05` | Oui | Oui | Déclaré | Partiel : EVN imposé et PV1 synthétique mal validé ; identifiants nationaux incomplets. |
| A31 | `ADT_A05` | Oui | Oui | Déclaré | Partiel pour les mêmes raisons qu'A28. |
| A47 | `ADT_A30` | Oui | Oui | Déclaré | Partiel : MRG géré, mais couverture des règles d'identifiants insuffisante. |
| A40 | `ADT_A39` | Oui | Oui | Déclaré | Partiel : chemin identité correct, mais une autre branche d'émission choisit `ADT_A38`. |
| A01 | `ADT_A01` | Oui | Oui | Déclaré | Partiel. |
| A04 | `ADT_A01` | Oui | Oui | Déclaré | Partiel. |
| A03 | `ADT_A03` | Oui | Oui | Déclaré | Partiel. |
| A05 | `ADT_A05` | Oui | Oui | Déclaré | **Écart** : le générateur actif choisit `ADT_A01`. |
| A38 | `ADT_A38` | Oui | Oui/partiel | **Non déclaré** | Un message valide est signalé `TRIGGER_UNSUPPORTED`. |
| A06/A07 | `ADT_A06` | Oui | Oui | Déclaré | Partiel. |
| A11 | `ADT_A09` | Oui | Oui/partiel | Déclaré | L'annulation automatique d'A01 produit à tort A12 au lieu d'A11. |
| A02 | `ADT_A02` | Oui | Oui | **Non déclaré** | Le programme rejette son propre message généré. |
| A12 | `ADT_A12` | Oui | Oui | Déclaré | Partiel. |
| A13 | `ADT_A01` | Oui | Oui | Déclaré | Partiel. |
| A21/A22 | `ADT_A21` | Oui | Oui | Déclaré | Partiel. |
| A52/A53 | `ADT_A52` | Oui | Oui | Déclaré | **Écart** : le générateur actif annonce `ADT_A21`. |
| A54 | `ADT_A54` | Oui | Oui/partiel | **Non déclaré** | Traitement présent, mais validation et qualification incomplètes. |
| A55 | structure de la famille A52 | Oui | Oui/partiel | **Non déclaré** | Structure générée par défaut non démontrée conforme. |
| A44 | `ADT_A43` | Oui | Incomplet | **Non déclaré** | **Non conforme** : routé comme mouvement et ZBE exigé, alors que le message CPage utilise MRG et peut ne pas contenir ZBE. |
| Z99 | `ADT_A01` | Oui | Oui | Déclaré | Partiel : règles de correction et de référence seulement partiellement contrôlées. |
| A15/A26 | familles HL7 correspondantes | Non | A15 partiel / A26 absent | Non | Option avancée non couverte. |
| A08 | hors mécanisme de mise à jour PAM France | Oui | Oui | Déclaré | **Faux support** : accepté alors que les mises à jour doivent utiliser A31 ou Z99 selon leur objet. |

## Écarts bloquants

### 1. Le ZBE généré n'est pas conforme au profil français

Le segment ZBE est central pour la gestion des mouvements. Les défauts suivants sont bloquants :

- **ZBE-3 est interdit par le profil**, mais le générateur actif y écrit `ADMIT`, `TRANSFER`, `DISCHARGE`, `UPDATE`, etc. ;
- ZBE-1 est un type **EI répétable**. Le générateur construit une représentation de type CX (`identifiant^^^autorité^type`) au lieu de `identifiant^namespace^OID^ISO` ;
- ZBE-9 doit accepter `S`, `H`, `M`, `L`, `D`, `SM`, `SH`, `MH`, `LD`, `HMS` et `C` sous leurs conditions. Le code ne produit et n'accepte réellement que six valeurs, et remplace certaines valeurs valides par `H` ;
- ZBE-7 et ZBE-8 ne transportent pas tous les composants XON d'autorité et de type attendus ;
- la cohérence entre le trigger, ZBE-4 (`INSERT`, `UPDATE`, `CANCEL`) et ZBE-6 n'est pas contrôlée de manière exhaustive.

Exemple réellement généré pour A02 :

```text
MSH|...|ADT^A02^ADT_A02|...|2.5^FRA^2.11|...|FRA|8859/1
...
ZBE|400^^^CPAGE&1.2.250.1.1&ISO^MVT|...|TRANSFER|INSERT|N||...|...|M
```

Ce message échoue dans le propre validateur entrant (`TRIGGER_UNSUPPORTED`, `ZBE1_NAMESPACE_MISSING`) et renseigne malgré tout ZBE-3.

### 2. Les structures MSH-9 ne sont pas fiables

Le générateur réellement appelé en émission sélectionne notamment :

- A05 → `ADT_A01` au lieu de `ADT_A05` ;
- A52/A53 → `ADT_A21` au lieu de `ADT_A52` ;
- A40 dans la branche mouvement → `ADT_A38` au lieu de `ADT_A39` ;
- A55 → structure de repli `ADT_A55`, sans preuve de conformité à la famille attendue.

Le validateur vérifie la forme de MSH-9, mais ne vérifie pas que sa troisième composante correspond au trigger. Une structure incohérente comme `ADT^A01^ADT_A39` est donc acceptée.

### 3. A44 CPage est traité selon une sémantique erronée

Le routeur envoie A44 vers un gestionnaire de mouvement/compte reposant sur ZBE. Le message d'exemple CPage A44 contient MRG et ne contient pas ZBE. Le contrôle précoce de réception le refuse donc avant le traitement métier. L'association d'un dossier au bon patient n'est pas implémentée conformément à la transaction décrite.

### 4. L'émission continue malgré une validation en échec

Le résultat de `validate_pam(..., direction="out")` est enregistré, mais un niveau `fail` n'empêche pas l'envoi MLLP. Le contrôle de conformité de sortie est donc informatif et non une barrière de sécurité.

### 5. Le jeu d'événements du validateur est incomplet et contradictoire

Le validateur ne déclare pas A02, A15, A26, A38, A44, A54 et A55. Il émet ainsi `TRIGGER_UNSUPPORTED` pour plusieurs événements PAM valides. Inversement, il déclare A08 et A23 sans correctement borner leur usage par rapport au profil national.

### 6. Le codage déclaré ne correspond pas au codage réseau

MSH-18 annonce `8859/1`, tandis que le transport MLLP encode systématiquement en UTF-8. Les caractères accentués peuvent donc être interprétés différemment par CPage. Le codage déclaré et les octets transmis doivent être identiques.

## Intégration des données françaises

### Couverture présente

- PID, PD1, PV1, PV2 et ZBE sont lus sur les parcours principaux ;
- MRG est exploité pour A40/A47 ;
- ZFD, ZFA, ZFP et ZFV ainsi que certaines données ROL sont partiellement parsés et appliqués ;
- le validateur de séquence sait rechercher un mouvement d'origine pour certaines actions UPDATE/CANCEL et effectuer quelques contrôles d'occupation et de transition.

### Couverture absente ou insuffisante

- ZFM, ZFS et plusieurs contenus détaillés des extensions françaises ne sont pas complètement mappés ;
- IN1/IN2/IN3, GT1, OBX et ACC ne sont pas intégrés ; certains sont même déclarés à tort interdits ;
- les répétitions, cardinalités, longueurs, tables, caractères d'échappement et contraintes conditionnelles ne sont pas contrôlés de façon systématique ;
- PID-32 n'est pas validé avec la table nationale complète et les répétitions comme `PROV~ANOM` ou `PROV~CACH` sont rejetées ;
- PID-19, interdit dans le profil examiné, n'est pas détecté ;
- le NIR/INS généré utilise `INS-NIR` et `NH`, sans l'autorité/OID et le type `INS` attendus par le profil national ;
- le téléphone est produit et relu dans des composants XTN incohérents. Un aller-retour peut perdre le numéro ;
- la règle locale interdisant deux mouvements à moins d'une minute est plus stricte que la règle nationale portant sur un doublon de même nature, patient, responsabilité médicale et horodatage exact.

## Capacité de détection des erreurs

### Erreurs correctement détectées lors de l'essai ciblé

- PID absent ;
- ZBE-4 inconnu ;
- MRG absent sur A40 ;
- plusieurs champs obligatoires simples absents ;
- certaines références UPDATE/CANCEL inconnues dans l'historique chargé ;
- quelques incohérences de chronologie, de statut et d'occupation.

### Messages invalides acceptés à tort

Chaque cas suivant a été injecté séparément dans un message minimal autrement valide et a obtenu un résultat `ok` :

| Erreur injectée | Résultat actuel | Résultat attendu |
|---|---|---|
| MSH-12 = `2.3` | Accepté | Rejet : version/profil incompatible |
| A01 avec structure MSH-9 `ADT_A39` | Accepté | Rejet : structure incohérente |
| ZBE-3 renseigné | Accepté | Rejet : champ interdit |
| A01 avec ZBE-4 = `UPDATE` | Accepté | Rejet : action incohérente |
| Z99 avec ZBE-4 = `INSERT` | Accepté | Rejet : Z99 corrige un mouvement existant |
| Date `20260231` | Acceptée | Rejet : date calendrier impossible |
| PID-19 renseigné | Accepté | Rejet : champ interdit |
| Segment inconnu `ZZZ` | Accepté | Rejet ou erreur de profil |
| A08 | Accepté | Rejet ou signalement hors périmètre PAM France |

### Messages conformes ou prévus par le profil rejetés à tort

| Cas | Résultat actuel | Cause |
|---|---|---|
| ZBE-9 = `MH` | Échec | table nationale incomplète |
| Segment OBX prévu par le profil | Échec | OBX déclaré globalement interdit |
| A02, A38, A44, A54 ou A55 | Échec | trigger absent de `SEGMENT_RULES` |
| A28 CPage minimal sans EVN | Échec | EVN imposé globalement |
| A28/A31 avec PV1 minimal de classe `N` | Échec entrant | PV1-3 imposé dès que PV1 existe |
| PID-32 répété `PROV~ANOM`/`PROV~CACH` | Échec | validation sans gestion correcte des répétitions et table incomplète |

**Conclusion sur le détecteur :** il détecte certaines erreurs élémentaires, mais ne peut pas servir de preuve de conformité. Ses faux négatifs laissent passer des violations importantes ; ses faux positifs peuvent interrompre des flux CPage valides.

## Revalidation après correctifs

| Campagne | Résultat |
|---|---|
| Unitaire PAM, génération, parseurs et matrice normative | **62 réussis, 1 xfail attendu, 0 échec** |
| Intégration entrante, MLLP et IHM | **21 réussis, 1 xfail attendu, 0 échec** |
| Compilation Python et contrôle des espaces Git | **Réussis** |

La matrice négative automatisée vérifie notamment une structure MSH-9 incohérente, ZBE-3 renseigné, une action ZBE incompatible, PID-19, une date impossible, un segment inconnu et les contraintes Z99. Elle inclut également le transport UTF-8, l'ACK et le traitement A44.

## Résultats des tests exécutés avant correctifs

### Tests unitaires PAM ciblés

| Résultat | Valeur |
|---|---:|
| Tests collectés | 55 |
| Réussis | 54 |
| XFail attendu | 1 |
| Échecs | 0 |
| Durée | 23,07 s |

Les tests réussis confirment des comportements internes, pas la conformité au référentiel. En particulier, le test sur l'échantillon réel utilise une assertion diagnostique : il vérifie seulement qu'un résultat a été produit pour chaque fichier, pas que chaque message conforme reçoit `AA`.

### Tests d'intégration ciblés

| Résultat | Valeur |
|---|---:|
| Tests collectés | 6 |
| Réussis | 5 |
| XFail attendu | 1 |
| Échecs | 0 |

### Échantillon de 200 messages réels

| ACK | Nombre | Part |
|---|---:|---:|
| AA | 172 | 86,0 % |
| AE | 19 | 9,5 % |
| AR | 9 | 4,5 % |

Les 28 rejets incluent notamment A44 sans ZBE, des transitions refusées par une table locale plus stricte, des mouvements rapprochés et des Z99 dont le mouvement d'origine n'était pas chargé dans le sous-ensemble. Ce taux n'est pas un taux de conformité des données : il mesure la compatibilité du moteur actuel avec cet échantillon.

### Passage du validateur sur les exemples du dépôt

| Corpus | Messages | `ok` | `fail` |
|---|---:|---:|---:|
| `tests/exemples/pam_archive` | 298 | 2 | 296 |
| `tests/exemples/pam_errors` | 872 | 264 | 608 |
| **Total** | **1 170** | **266** | **904** |

Les noms de dossiers ne constituent pas un oracle de conformité. Le résultat — 22,7 % classés `ok` — met surtout en évidence le décalage entre le validateur et les messages présents dans le projet. Les causes dominantes sont PV1-3 imposé aux messages d'identité, la table ZBE-9 incomplète, les triggers non déclarés et l'interdiction abusive de GT1/OBX.

## Architecture : trois générateurs qui divergent

Trois implémentations de génération coexistent :

1. `app/services/emit_on_create.py::generate_pam_hl7`, utilisé par l'émission automatique réelle ;
2. `adapters/hl7_pam_fr.py`, utilisé par certains services et de nombreux tests de conformité ;
3. `app/services/hl7_generator.py`, annoncé dans son propre en-tête comme non utilisé par le flux automatique, mais encore accessible à des usages manuels.

Les tests valident principalement l'adaptateur, alors que plusieurs défauts bloquants se trouvent dans le premier chemin. Le troisième omet EVN, ne gère pas A40/A47 et n'est pas aligné sur le profil. Cette duplication crée une impression de couverture supérieure à la couverture effective.

## ACK et comportement de réception

- La validation PAM est désactivée par défaut sur un endpoint (`pam_validate_enabled = false`) et son mode par défaut est `warn` ; les erreurs n'empêchent donc généralement pas le traitement.
- En mode `reject`, les faux positifs décrits ci-dessus peuvent renvoyer AE à un message valide.
- Une exception interne du validateur est convertie en avertissement et ne bloque jamais le message.
- L'ACK construit ne reprend pas complètement la structure et les champs attendus dans les exemples CPage ; MSH-9 est limité à `ACK^trigger` et les paramètres de langue/codage ne sont pas alignés.

Le système est donc capable de journaliser un diagnostic, mais la configuration par défaut ne constitue pas un contrôle de conformité et le mode strict n'est pas encore sûr.

## Priorités de correction

### P0 — nécessaires avant toute revendication de conformité

1. Définir une table normative unique `trigger → structure → segments → cardinalités → champs → actions ZBE`, couvrant ITI-30 et le périmètre ITI-31 retenu.
2. Corriger ZBE : EI répétable en ZBE-1, ZBE-3 vide/interdit, ZBE-4/5/6 cohérents, XON conformes en ZBE-7/8 et table complète en ZBE-9.
3. Corriger les structures MSH-9 A05, A40, A52, A53 et A55, puis vérifier systématiquement la cohérence trigger/structure en entrée et sortie.
4. Implémenter A44 avec sa sémantique PID/MRG et sans exigence artificielle de ZBE.
5. Ajouter A02, A38, A44, A54 et A55 au validateur ; borner A08/A23 ; décider explicitement si les options A15/A26 sont revendiquées.
6. Bloquer l'émission lorsqu'une validation de sortie de sévérité erreur échoue.
7. Aligner MSH-18 et le codec MLLP, y compris les tests avec caractères français.

### P1 — données françaises et robustesse

1. Implémenter la table PID-32 complète et ses répétitions.
2. Corriger INS/NIR, autorités d'affectation et types d'identifiants.
3. Corriger XTN pour téléphone et courriel et ajouter des tests d'aller-retour sans perte.
4. Aligner les segments autorisés et conditionnels : ROL, NK1, PV2, ACC, OBX, ZFA, ZFP, ZFV, ZFM, ZFD, ZFS, IN1/IN2/IN3 et GT1 selon les événements.
5. Vérifier les champs interdits, dont ZBE-3 et PID-19, les cardinalités et la validité calendrier réelle des TS.
6. Remplacer la règle « moins d'une minute » par la règle exacte d'unicité du mouvement du référentiel.
7. Compléter les ACK et ERR conformément à la convention CPage.

### P2 — industrialisation de la preuve

1. Conserver un seul générateur PAM en production et faire pointer les tests dessus.
2. Transformer chaque exemple normatif CPage autorisé en test positif, et chaque contre-exemple en test négatif à code d'erreur précis.
3. Ajouter une matrice de tests pour tous les couples événement/action et les structures MSH-9.
4. Exécuter les mêmes messages en entrée puis en sortie et vérifier la conservation des identifiants, téléphones, extensions et répétitions.
5. Qualifier avec un validateur HL7 v2.5/profil PAM indépendant, puis réaliser une recette bilatérale avec CPage.

## Critères de sortie proposés

La conformité ne devrait être annoncée qu'après obtention simultanée des résultats suivants :

- 100 % des exemples positifs nationaux et CPage du périmètre acceptés ;
- 100 % des erreurs normatives ciblées rejetées avec un emplacement ERR exploitable ;
- chaque message généré accepté par le validateur interne **et** un validateur indépendant ;
- aucune structure MSH-9 incohérente et aucun champ interdit généré ;
- aller-retour sans perte des identifiants, INS, téléphones, mouvements et extensions françaises revendiquées ;
- résultats documentés pour chaque événement obligatoire ITI-30/ITI-31 ;
- encodage vérifié octet par octet sur le transport MLLP ;
- campagne de non-régression exécutée sur l'intégralité des échantillons, sans assertion « souple » masquant les AE/AR.

## Traçabilité dans le code

| Sujet | Fichier principal |
|---|---|
| Générateur réellement utilisé | [`app/services/emit_on_create.py`](../../app/services/emit_on_create.py) |
| Validation PAM | [`app/services/pam_validation.py`](../../app/services/pam_validation.py) |
| Validation de séquence | [`app/services/pam_sequence_validator.py`](../../app/services/pam_sequence_validator.py) |
| Réception et politique warn/reject | [`app/services/transport_inbound.py`](../../app/services/transport_inbound.py) |
| Routage des événements | [`app/services/message_router.py`](../../app/services/message_router.py) |
| Traitements PAM | [`app/services/pam.py`](../../app/services/pam.py) |
| Parseurs des extensions françaises | [`app/infrastructure/hl7/parsing/french_extension_parser.py`](../../app/infrastructure/hl7/parsing/french_extension_parser.py) |
| Transport et ACK | [`app/services/mllp.py`](../../app/services/mllp.py) |
| Adaptateur couvert par plusieurs tests | [`adapters/hl7_pam_fr.py`](../../adapters/hl7_pam_fr.py) |
| Générateur secondaire/non automatique | [`app/services/hl7_generator.py`](../../app/services/hl7_generator.py) |

## Note sur les rapports antérieurs

Le dépôt contient des documents antérieurs affirmant une conformité complète, notamment `CONFORMANCE_AUDIT_PAM_20260328.md` et `IHE_PAM_INTEGRATION_COMPLETE_FR.md`. Le présent audit invalide cette conclusion : ces documents ne couvrent pas correctement le chemin d'émission réel, les valeurs nationales complètes, les champs interdits, les faux positifs/faux négatifs ni les exemples CPage. Ils doivent être considérés comme historiques jusqu'à une nouvelle qualification après correction.

## Décision finale — après correctifs

**Les défauts bloquants identifiés par cet audit ont été corrigés et sont couverts par des tests de conformité ciblés.** Le programme peut intégrer, générer et contrôler le périmètre IHE PAM France / CPage implémenté ; l'activation du rejet doit toutefois suivre une recette sur les messages réels de chaque partenaire. Une qualification indépendante reste nécessaire avant toute revendication de certification formelle.
