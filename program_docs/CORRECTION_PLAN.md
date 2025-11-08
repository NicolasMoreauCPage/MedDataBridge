# Plan de Correction Conformité IHE PAM FR / HL7 v2.5

Ce document décrit les corrections nécessaires pour amener MedDataBridge en conformité avec les spécifications IHE PAM France (CPage + extension nationale) tout en séparant clairement la documentation externe (`/Doc/`) de la documentation interne (nouveau répertoire `/program_docs/`).

## 1. Objectifs

- Couvrir entièrement le segment ZBE (champs 1..9) selon la norme FR.
- Implémenter logique UPDATE/CANCEL (ZBE-4 + ZBE-5 + ZBE-6) et codes nature (ZBE-9).
- Ajouter support UF médicale (ZBE-7) et UF soins (ZBE-8) en type XON conforme.
- Introduire provenance (PV1-6) pour mouvements A02 (transfert / mutation).
- Fournir matrice de conformité traçable + tests automatisés.

## 2. Portée

Inclut génération outbound, parsing inbound, validation, modèle de données, migrations, tests et documentation d’implémentation. Exclut pour l’instant toute intégration FHIR avancée supplémentaire (traitée séparément).

## 3. Références

- IHE PAM FR CPage v2.11 (PDF) -> `/Doc/SpecIHEPAM_CPage/...`
- IHE PAM Extension Nationale v2.11.1 -> `/Doc/SpecIHEPAM/...`
- HL7 v2.5 Normative Chapters (PID, PV1, data types XON, CX, XPN, etc.)

## 4. Écarts Actuels (Synthèse)

| Domaine | État | Détail |
|---------|------|--------|
| ZBE-1 Identifiants mouvement | Partiel | Un seul ID géré, pas de répétitions |
| ZBE-2 Date/heure mouvement | OK | Format TS valide |
| ZBE-3 ??? (non utilisé selon spec locale) | N/A | Confirmé absent/spec locale si non requis |
| ZBE-4 Action (INSERT/UPDATE/CANCEL) | Manquant | Toujours INSERT implicite |
| ZBE-5 Historique (Y/N) | Manquant | Non généré, non validé |
| ZBE-6 Trigger original | Partiel | Stocké mais non conditionnel ni sur CANCEL |
| ZBE-7 UF médicale (XON) | Partiel | Format simplifié, composants manquants (.10 code) |
| ZBE-8 UF soins (XON) | Manquant | Champ absent |
| ZBE-9 Nature (S,H,M,L,D,SM) | Partiel | Valeur legacy "HMS" hors norme |
| Validation globale ZBE | Partiel | Manque règles conditionnelles & énumérations |
| Parsing inbound ZBE | Partiel | 1,2,6,9 seulement |
| PV1-6 provenance | Manquant | Pas de capture transfert précédent |
| Modèle mouvement | Partiel | Champs nature, historic, uf_soins absents |
| Tests conformité | Manquant | Couverture minimale uniquement |

## 5. Champs ZBE – Spécification Résumée

- ZBE-1: Identifiant(s) mouvement (répétable). Conserver premier comme clé locale; stocker liste complète pour traçabilité.
- ZBE-2: Date/heure du mouvement (TS) obligatoire.
- ZBE-4: Action: INSERT | UPDATE | CANCEL.
- ZBE-5: Indicateur historique: 'Y' si reconstitution rétroactive, sinon 'N'.
- ZBE-6: Trigger original (ex: A01, A02...) requis pour UPDATE/CANCEL (référence du mouvement initial).
- ZBE-7: UF de responsabilité médicale (XON). Composant 1 nom, composant 10 code, autres composants vides si non fournis.
- ZBE-8: UF de responsabilité soins (XON) même structure.
- ZBE-9: Nature du mouvement: S (Sortie), H (Hospitalisation), M (Mutation), L (Libération administrative?), D (Décès), SM (Sous-mouvement / mouvement secondaire). (Adapter si la spec PDF diffère: confirmer avant implémentation finale.)

## 6. Mapping Interne Proposé

| Champ | Modèle `Mouvement` | Type | Notes |
|-------|--------------------|------|-------|
| ZBE-1 principal | id (existant) | str | Stocker liste complète séparée `movement_ids` (JSON) |
| ZBE-2 | movement_datetime | datetime | Existant |
| ZBE-4 | action | enum(Action) | Nouvel enum |
| ZBE-5 | is_historic | bool | true si 'Y' |
| ZBE-6 | original_trigger | str | Trigger HL7 initial (A01...) |
| ZBE-7 code | uf_medicale_code | str | Composant XON-10 |
| ZBE-7 nom | uf_medicale_label | str | Composant XON-1 |
| ZBE-8 code | uf_soins_code | str | Composant XON-10 |
| ZBE-8 nom | uf_soins_label | str | Composant XON-1 |
| ZBE-9 | nature | enum(Nature) | Enum conforme |
| movement_ids | movement_ids | list[str] | JSON array (nouvelle colonne) |

## 7. Règles Validation (Résumé)

1. ZBE obligatoire pour mouvements cliniques (A01,A02,A03,A08, etc. selon spec locale).
2. ZBE-4 présent et dans {INSERT,UPDATE,CANCEL}.
3. ZBE-6 obligatoire si ZBE-4 in {UPDATE,CANCEL}; interdit si INSERT.
4. ZBE-5 ∈ {Y,N}; si Y alors mouvement créé hors temps réel → marquer historique.
5. ZBE-7 & ZBE-8: Composant 10 (code) obligatoire; composant 1 (libellé) recommandé; rejet si code absent.
6. ZBE-9 ∈ {S,H,M,L,D,SM}; log WARN si combinaison incohérente avec trigger (ex: A01 avec 'M').
7. PV1-6: Doit être rempli pour A02 (mutation) avec valeur précédente d'UF médicale.
8. Segment order reste MSH EVN PID PV1 [ZBE].

## 8. Logique Inbound

- INSERT: Créer nouvel enregistrement mouvement; stocker nature/action.
- UPDATE (Z99 utilisé): Retrouver mouvement via ZBE-1 principal / autre clé; appliquer modifications champs UF / nature; journaliser diff.
- CANCEL: Marquer mouvement annulé (champ status ou flag); conserver audit.
- Historique (ZBE-5='Y'): Accepter timestamps passés sans modification de cohérence temps réel; ne pas override mouvements plus récents.

## 9. Génération Outbound

Algorithme: déterminer action (nouvelle vs modification vs annulation) → construire ZBE avec XON format: `Nom^^^^^^^^^Code` (nom en composant 1, code en composant 10). Omettre composants non spécifiés.

## 10. Tests à Implémenter

- Happy path INSERT (A01) avec ZBE complet.
- UPDATE (Z99) valid: ZBE-4=UPDATE + ZBE-6 fourni.
- CANCEL (A13 ou profil local) avec ZBE-4=CANCEL + ZBE-6.
- Erreurs: manque ZBE-6 sur UPDATE, ZBE-9 inconnu, ZBE-7 code manquant.
- Historique: ZBE-5='Y' accepte timestamp passé.
- PV1-6 présent sur mutation A02.
- Backward: ancien message sans ZBE-8 → WARNING pas ERREUR.

## 11. Migration

Créer migration SQL ajoutant colonnes: `is_historic` (BOOLEAN DEFAULT FALSE), `original_trigger` (VARCHAR), `nature` (VARCHAR), `uf_medicale_code`, `uf_medicale_label`, `uf_soins_code`, `uf_soins_label`, `movement_ids` (JSON/Text). Index sur `nature`, `uf_medicale_code`, `uf_soins_code` et composite `(action,nature)` si requêtes fréquentes.

## 12. Performance

Parsing additionnel O(1) par message (quelques splits). Impact négligeable; surveiller augmentation de latence <5%. Ajouter micro-benchmark après implémentation.

## 13. Risques & Mitigation

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| Mauvaise interprétation des codes nature | Non conformité | Vérifier libellés exacts dans PDF avant commit final |
| Migration cassant données existantes | Downtime | Migration idempotente + backup pré-exécution |
| Messages legacy sans nouveaux champs rejetés | Perte données | Mode compat: warnings + valeurs par défaut |
| Enum dur trop tôt | Refactoring | Centraliser mapping dans module unique `models_vocabulary.py` |

## 14. Phasage

1. Phase 1: Documentation + enums + mapping (ce plan, répertoires).
2. Phase 2: Génération ZBE étendue + validation enrichie.
3. Phase 3: Parsing inbound + modèle + migration.
4. Phase 4: Logique UPDATE/CANCEL + PV1 provenance.
5. Phase 5: Jeux de tests + compliance matrix complète.
6. Phase 6: Benchmark & ajustements.

## 15. Rollback

- En cas de problème après migration: revert code + restaurer backup DB.
- Feature flags temporaires pour activation validation stricte.

## 16. Compliance Matrix (Skeleton)

```text
Champ | Règle | Implémenté | Statut | Commentaire
ZBE-1 | Répétable; >=1 | Non | Missing | Stocker liste
ZBE-2 | Obligatoire | Oui | Pass |  
ZBE-4 | Obligatoire | Non | Missing | Action enum
ZBE-5 | Obligatoire Y/N | Non | Missing | Historic flag
ZBE-6 | Cond UPDATE/CANCEL | Partiel | Partial | Condition manquante
ZBE-7 | Code obligatoire | Partiel | Partial | XON incomplet
ZBE-8 | Code obligatoire | Non | Missing | À ajouter
ZBE-9 | Enum valeurs | Partiel | Partial | Valeur legacy
PV1-6 | A02 seulement | Non | Missing | Ajout provenance
```

## 17. Prochaines Actions Immédiates

- Implémenter Phase 2: ajuster générateur ZBE + ajouter enum nature & action.
- Préparer fichier migration pour Phase 3.

---

Document généré automatiquement pour amorcer la correction conformité.
