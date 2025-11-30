# Intégration MFN (M05) — Documentation complète (FR)

Version: 2025-11-30

Objectif
-------
Ce document décrit de manière exhaustive l'intégration des messages MFN (généralement MFN^M05 dans nos jeux de données) au sein du projet MedData_Bridge. Il couvre :

- La gestion des identifiants et des namespaces (Identifier, IdentifierNamespace, usage pour ZBE/ZBX/ZAM/PID-3 etc.).
- Les relations entre entités (EntiteJuridique, EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit) et les règles pour remplir les clefs étrangères (FK).

Développeurs et ingénieurs d'intégration qui :
- doivent maintenir ou améliorer l'importateur MFN ;
- doivent implémenter ou valider la génération MFN/PAM/FHIR ;
- veulent comprendre comment les données HL7 sont traduites en entités SQL/ORM.

## Sommaire

1. Données lues depuis les messages MFN (segments et champs)
2. Gestion des identifiants et namespaces
3. Modèle relationnel et mapping
4. Algorithme d'import (multi-pass, parentage, fallback)
5. Règles de génération MFN
6. Exemples concrets
7. Cas d'erreur et diagnostics
8. Tests de régression et validation
9. Annexes et utilitaires

---

## 1. Données lues depuis les messages MFN (segments et champs)

- Tous les champs extraits depuis les segments MFN/LOC/Zxx/ZRL/LRL (et autres segments pertinents) et la façon dont ils sont mappés vers les modèles persistés.


---

## 3. Modèle relationnel et mapping
- Les relations sont résolues en multi-pass pour garantir l’import complet même si l’ordre des entités dans le message est non hiérarchique.

---

---


---

- `scripts/debug_mfn_generate.py` (génération MFN)
- `archives/tests/test_mfn_structure.py` (tests unitaires MFN)


- **Identifiant manquant** : erreur bloquante, log détaillé, tentative de récupération via ID_GLBL ou relations.
- **Parent manquant** : entité reportée à la pass suivante, création de parent virtuel si possible.
- **Import incomplet** : log d’avertissement, liste des entités non importées après 10 passes.

---
## 8. Tests de régression et validation
- Tester l’import/export roundtrip pour valider la conformité.
- Vérifier la cohérence des identifiants et des relations parent/enfant.
- Utiliser les jeux de données de test pour valider tous les cas d’erreur et de fallback.

---

## 9. Annexes et utilitaires

- Utiliser le répertoire `tmp/` pour stocker les MFN générés ou importés lors des tests ou roundtrips.
- Les utilitaires de parsing et de génération sont dans `app/services/mfn_structure.py` et `app/services/mfn_organization.py`.
- Les patterns d’écriture atomique sont recommandés pour éviter les corruptions lors de l’export MFN.

---

## 10. Gestion technique des relations entre entités

### Extraction des relations
- Les relations hiérarchiques sont extraites des segments LRL (champ 4 : type, champ 6 : cible).
- Chaque entité MFN peut avoir zéro ou plusieurs relations : parent (ex : Service → Pôle), rattachement (ex : UF → Service), ou lien virtuel.
- Les types de relation courants : LCLSTN (localisation), ETBLSMNT (établissement), rattachement parent/enfant.

### Mapping vers le modèle ORM
- Les relations sont mappées vers les clefs étrangères du modèle SQLModel :
  - Service.pole_id
  - UF.service_id
  - UH.unite_fonctionnelle_id
  - Chambre.unite_hebergement_id
  - Lit.chambre_id
  - EG.entite_juridique_id
- Lors de l’import, le parser résout le parent via l’identifiant cible (champ 6 du LRL), en cherchant d’abord l’identifiant exact, puis par suffixe si besoin.

### Logique de parentage et multi-pass
- L’import MFN utilise un algorithme multi-pass : chaque pass tente d’importer les entités dont les parents sont déjà présents.
- Si le parent n’existe pas, l’entité est reportée à la pass suivante ou un parent virtuel est créé (ex : VIRTUAL-POLE, VIRTUAL-SERVICE, VIRTUAL-UH).
- Les parents virtuels sont créés à la volée, avec un identifiant préfixé, et rattachés à l’entité pour garantir la cohérence de la hiérarchie.
- Les relations sont résolues en priorité par type (EJ/EG, Pôle, Service, UF, UH, Chambre, Lit).

### Cas d’erreur et diagnostics
- Si la résolution d’un parent échoue après 10 passes, l’entité est considérée comme non importable (erreur parent manquant).
- Les logs détaillent chaque étape de résolution, la création de parents virtuels, et les erreurs de rattachement.
- Les collisions ou incohérences de relations sont gérées par fallback ou création de liens virtuels.

### Exemples de relations
- LRL|^^^^^D^^^^0192|||LCLSTN^Relation de localisation^L||^^^^^P^^^^123 → Service 0192 rattaché au Pôle 123
- LRL|^^^^^UF^^^^456|||LCLSTN^Relation de localisation^L||^^^^^D^^^^0192 → UF 456 rattachée au Service 0192
- LRL|^^^^^CH^^^^789|||LCLSTN^Relation de localisation^L||^^^^^UH^^^^654 → Chambre 789 rattachée à l’UH 654
- LRL|^^^^^LIT^^^^321|||LCLSTN^Relation de localisation^L||^^^^^CH^^^^789 → Lit 321 rattaché à la Chambre 789

### Schéma hiérarchique

```text
EJ
└── EG
    └── Pôle
        └── Service
            └── UF
                └── UH
                    └── Chambre
                        └── Lit
```

---

Document rédigé le 30/11/2025. Relisez et inspirez-vous de cette doc pour toute règle de génération ou d’intégration MFN.

---

### Listes de valeurs possibles pour les champs HL7 MFN

#### MFE-1 (Record-Level Event Code)
- MAD : Add record to master file (Ajout)
- MUP : Update record (Mise à jour)
- MDL : Delete record (Suppression)
- MDC : Correction (Correction)
- MFD : Deactivate/Disable (Désactivation)

#### MFE-5 (Primary Key Value Type)

Conformément à la spécification AtelierStructure, le champ MFE-5 doit contenir la valeur constante "PL" pour
indiquer que la clé primaire fournie en MFE-4 est au format PL (Person Location). Le type d'entité (Service,
Chambre, Lit, etc.) ne doit pas être placé dans MFE-5 : il est précisé dans le sous-champ PL-6 (ou, pour les
segments LOC, dans LOC-3) du PL utilisé en MFE-4.

Résumé opérationnel :

- MFE-4 : clé primaire encodée en PL (PL-6 = type d'entité, PL-10 = EI identifiant dans le domaine)
- MFE-5 : valeur constante "PL"

Ne mettez pas le code d'entité (ex. "D", "UF") dans MFE-5 — mettez "PL" et utilisez PL-6/LOC-3 pour le type
d'entité.

#### LOC-3/LOC-4 (Type d’entité)
Les types d'entité transmis dans LOC-3 (et les types apparentés dans LOC-4/PL-6) sont alignés sur le jeu de
valeurs officiel décrit dans la spécification AtelierStructure. Les valeurs possibles (PL-6 / Location Type)
incluent (liste extraite de la spécification) :

- M : Entité juridique (Legal Entity)
- ETBL_GRPQ : Etablissement géographique
- D : Service (Department)
- H : Unité fonctionnelle responsabilité médicale (Medical Care Unit)
- N : Unité fonctionnelle hébergement (Nursing Unit / Housing Unit)
- B : Emplacement lit (Bed)
- PL : Pôle
- STRCTR_INTR : Structure interne
- UNT_MDCL : Unité médicale
- UAC : UAC
- BTMNT : Bâtiment
- L : Lieu
- ETG : Etage
- AL : Aile
- CLR : Couloir
- R : Chambre
- BX : Box
- PNT_CLCT : Point de collecte
- PNT_LVRSN : Point de livraison
- SL_ATNT : Salle d’attente
- SL_RVL : Salle réveil
- Other location / Room (autres valeurs libres selon contexte)

#### LRL-4 (Type de relation)
- LCLSTN : Relation de localisation (Location relationship)
- ETBLSMNT : Lien vers l'établissement
- RATTACH : Rattachement hiérarchique (le cas échéant)
- VIRTUAL : Indicateur interne pour parents virtuels (implémentation spécifique)

#### ORG-1 (Organization ID)
- FINESS : Identifiant FINESS
- SIREN : Identifiant SIREN
- SIRET : Identifiant SIRET

#### PRA-3 (Practitioner Category)
- ORG : Organisation
- GHT : Groupement Hospitalier de Territoire

#### AFF-3 (Affiliation)
- GHT : Groupement Hospitalier de Territoire

---

> Notes importantes tirées de la spécification officielle :
> - Le couple (PL-6, PL-10) doit être unique dans l'ensemble du catalogue de la structure : PL-6 identifie le
>   type d'entité et PL-10 contient la clé primaire (type EI) au sein du domaine défini par MSH-4.
> - Le champ PL-10 est de type EI (Entity Identifier) et son premier sous-champ (EI-1) contient l'identifiant
>   unique de l'entrée. Conformément à l'Annexe N du cadre ITI (IHE France), EI-1 est limité à 16 caractères.
> - Le récepteur doit utiliser PL-10 (EI) pour rechercher/rattacher l'entité plutôt que les codes ou libellés
>   susceptibles de changer entre mises à jour.

> Validation recommandée pour PL-10/EI :
>
> - PL-10 est de type EI (Entity Identifier) ; le premier sous-champ EI-1 contient l'identifiant unique de
>   l'entité dans le domaine (souvent l'émetteur, égal aux 3 sous-champs MSH-4-1..3).
> - Contrainte opérationnelle : EI-1 doit contenir au maximum 16 caractères (Annexe N IHE France). Si le
>   récepteur reçoit un EI-1 > 16 caractères il doit :
>   1) logguer l'événement et rejeter la clé (recommandé) ou
>   2) appliquer une règle locale de normalisation/tronquage (à documenter et à valider avec le correspondant
>      d'intégration) — éviter la troncation silencieuse sans accord.

> Pour chaque champ, la valeur doit respecter la liste ci-dessus. Toute valeur non reconnue doit être logguée et
> traitée comme une erreur ou ignorée selon le contexte métier.

---

### Exemple complet de message MFN (structure)

```hl7
MSH|^~\&|MEDBRIDGE|CPAGE|HOSPITAL|CPAGE|202511301200||MFN^M05^MFN_M05|123456|P|2.5
MFI|LOC|ST|UPD|202511301200|NE
MFE|MAD|||^^^^^D^^^^0192|PL
LOC|^^^^^D^^^^0192&CPAGE&700004591&FINEJ||D|Service de médecine
LCH|^^^^^D^^^^0192|||ID_GLBL^Identifiant unique global^L|^700004591
LRL|^^^^^D^^^^0192|||LCLSTN^Relation de localisation^L||^^^^^P^^^^123
ORG|FINESS|CHU Paris|||EJ
STF|FINESS
PRA|||ORG
AFF|||GHT
```

**Annotations :**

- `MSH-9` : MFN^M05^MFN_M05 (type de message)

- `MFI-1` : LOC (type d’entité)

- `MFE-1` : MAD (événement : Ajout)

- `MFE-4` : ^^^^^D^^^^0192 (identifiant entité, encodé en PL)

- `MFE-5` : PL (Primary Key Value Type = PL ; la vraie nature de l'entité est dans PL-6/LOC-3)

- `LOC-1` : ^^^^^D^^^^0192&CPAGE&700004591&FINEJ (identifiant, namespace, global id, type)

- `LCH-4/5` : ID_GLBL, 700004591 (identifiant global)

- `LRL-4/6` : LCLSTN, ^^^^^P^^^^123 (relation de localisation, parent)

- `ORG-1/2/4` : FINESS, CHU Paris, EJ (organisation)

- `STF-1` : FINESS (identifiant organisation)

- `PRA-3` : ORG (catégorie praticien)

- `AFF-3` : GHT (affiliation)

---

### Rappel - correspondance Entité -> LOC-3 / PL-6

| Entité (nom) | Code LOC-3 / PL-6 |
|---|---:|
| Entité juridique | M |
| Etablissement géographique | ETBL_GRPQ |
| Pôle | PL |
| Service | D |
| Unité fonctionnelle responsabilité médicale | H |
| Unité fonctionnelle hébergement | N |
| Unité médicale | UNT_MDCL |
| Structure interne | STRCTR_INTR |
| Bâtiment | BTMNT |
| Lieu | L |
| Etage | ETG |
| Aile | AL |
| Couloir | CLR |
| Chambre | R |
| Box | BX |
| Emplacement lit | B |
| Point de collecte | PNT_CLCT |
| Point de livraison | PNT_LVRSN |
| Salle d'attente | SL_ATNT |
| Salle réveil | SL_RVL |


### Exemple MFN avec mise à jour et parent virtuel

```hl7
MSH|^~\&|MEDBRIDGE|CPAGE|HOSPITAL|CPAGE|202511301210||MFN^M05^MFN_M05|123457|P|2.5
MFI|LOC|ST|UPD|202511301210|NE
MFE|MUP|||^^^^^UF^^^^456|PL
LOC|^^^^^UF^^^^456&CPAGE&700004592&FINEJ||UF|Unité de soins intensifs
LCH|^^^^^UF^^^^456|||ID_GLBL^Identifiant unique global^L|^700004592
LRL|^^^^^UF^^^^456|||LCLSTN^Relation de localisation^L||^^^^^D^^^^0192
```

**Annotations :**

- `MFE-1` : MUP (mise à jour)

- `MFE-5` : PL (Primary Key Value Type = PL)

- `LRL-6` : ^^^^^D^^^^0192 (parent Service, peut être virtuel si absent)

---
