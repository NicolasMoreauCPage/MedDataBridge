# Documentation Interne MedDataBridge

Ce répertoire `program_docs/` concentre la documentation d'implémentation. Les spécifications officielles (IHE PAM France, HL7 v2.5) restent dans `Doc/` et ne doivent pas être modifiées hors mise à jour normative.

## Table des matières
1. Structure des fichiers
2. Segment ZBE – sémantique complète
3. Cycle de vie d'un Mouvement & Actions
4. Logique inbound (UPDATE / CANCEL / historic)
5. Provenance PV1 (A02)
6. Nature (ZBE-9) – mapping
7. Validation & Codes (sévérité)
8. Backward compatibility & Fallbacks
9. Compliance Matrix & couverture
10. Performance & benchmark
11. Pistes futures / dette technique

---
## 1. Structure
| Fichier | Rôle |
|---------|------|
| `CORRECTION_PLAN.md` | Roadmap de conformité PAM FR |
| `generate_compliance_matrix.py` | Extraction automatique des codes de validation |
| `COMPLIANCE_MATRIX.md` | État généré de la couverture ZBE |
| `README.md` | Vue synthétique et approfondie |
| `legacy_behavior.md` | (Créé) Comportements d'arrière‑compatibilité |

## 2. Segment ZBE – sémantique complète
Champs implémentés (IHE PAM FR):
| Champ | Description | Source | Statut |
|-------|-------------|--------|--------|
| ZBE-1 | Identifiant mouvement principal (reps futures) | `Mouvement.mouvement_seq` | OK |
| ZBE-2 | Date/heure mouvement | `Mouvement.when` | OK |
| ZBE-3 | Réservé (vide) | constant | OK |
| ZBE-4 | Action (INSERT/UPDATE/CANCEL) | `Mouvement.action` + fallback | OK |
| ZBE-5 | Historique Y/N | `Mouvement.is_historic` | OK |
| ZBE-6 | Trigger original (UPDATE/CANCEL) | `Mouvement.original_trigger` ou fallback | OK |
| ZBE-7 | UF médicale XON (label comp1, code comp10) | Champs mouvement / fallback dossier/venue | OK |
| ZBE-8 | UF soins XON (optionnel) | Champs mouvement | OK (Warning si vide) |
| ZBE-9 | Nature (S,H,M,L,D,SM) | Mapping dérivé | OK |

## 3. Cycle de vie Mouvement & Actions
| Action | Usage | Effet | Conditions |
|--------|-------|-------|------------|
| INSERT | Création mouvement | Ajout ZBE complet | Mouvement neuf |
| UPDATE | Correction mouvement existant | Mise à jour champs; ZBE-6 référence trigger original | ZBE-6 requis ou fallback `trigger_event` |
| CANCEL | Annulation mouvement | Marque mouvement annulé (internal flag) | ZBE-6 nécessaire (trigger original) |

Historic (ZBE-5=Y) marque un enregistrement rétro‑actif ou régularisation sans logique temporelle bloquante.

## 4. Logique inbound (UPDATE / CANCEL / historic)
Parsing ZBE → struct interne → application sur mouvement ciblé (lookup via ZBE-1). Absence de ZBE-6 pour UPDATE/CANCEL : fallback sur `trigger_event` mais validation signale sévérité (Warning vs Error selon contexte strict). Historic ne change pas la résolution; le flag est stocké.

## 5. Provenance PV1 (A02)
PV1-6 contient l'UF précédente (dernier mouvement avant transfert). Recalcul dynamique lors de génération A02.

## 6. Nature (ZBE-9) – mapping
Mapping central dans `services/nature_mapping.py` dérive nature selon trigger (ex: A01→S). Override par `Mouvement.nature` si valide; sinon ignoré.

## 7. Validation & Codes
`pam_validation` expose codes (ex: `ZBE4_ACTION_INVALID`, `ZBE6_MISSING_FOR_UPDATE`). Classification à venir: Error vs Warning. Absence UF soins -> Warning pour compat. La Compliance Matrix reconstruit couverture depuis ces codes.

## 8. Backward compatibility & Fallbacks
| Cas | Fallback | Sévérité |
|-----|----------|----------|
| ZBE-8 manquant | Champ vide, pas d'erreur | Warning |
| Action inconnue | Fallback INSERT | Warning |
| UPDATE/CANCEL sans ZBE-6 | Utilise `trigger_event` | Warning (strict: Error) |
| Nature invalide | Recalcul mapping trigger | Warning |

## 9. Compliance Matrix & couverture
`COMPLIANCE_MATRIX.md` généré: classification prévue (Full / Partial / Missing). Partial inclura champs où seules règles basiques sont présentes (ex: répétitions ZBE-1 non encore gérées). Script mise à jour prochainement.

## 10. Performance & benchmark
Script à créer `benchmark_zbe_performance.py` : génère N (1000) messages, mesure temps génération + parsing + validation; fixe baseline pour régressions (<100 ms / 1000 messages sur env dev cible – valeur indicative, ajustable).

## 11. Pistes futures / dette technique
| Item | Justification |
|------|---------------|
| Répétitions ZBE-1 | Multi-identifiants PAM FR futurs |
| Segments MRG (A40/A47) | Support fusion / changement d'identifiants |
| Migration Pydantic ConfigDict | Supprimer warnings dépréciation |
| Test charge multi-thread | Garantir scalabilité inbound |

---
Dernière mise à jour automatique.
