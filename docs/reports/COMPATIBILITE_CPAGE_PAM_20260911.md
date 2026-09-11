# Vérification de compatibilité CPage — IHE PAM France

**Date :** 11 septembre 2026  
**Corpus :** `data/pam/*.hl7`, 199 messages dont `MSH-3=CPAGE`.

## Verdict

Le validateur est compatible avec les messages CPage du corpus pour les écarts connus de `ZBE-9`, tout en les rendant visibles. Les messages restent contrôlés selon le profil IHE PAM France 2.11.1 ; la tolérance ne s'applique ni aux autres émetteurs ni à la génération sortante.

| Résultat après vérification | Nombre |
|---|---:|
| Messages acceptés avec avertissement | 199 |
| Messages rejetés | 0 |
| Avertissements `MSH-18=8859/1` CPage historique | 199 |
| Avertissements de compatibilité `ZBE9_CPAGE_SUFFIX_COMPAT` | 7 |
| Rejets `ZBE9_INVALID` | 0 |

## Bug CPage `ZBE-9`

La spécification nationale autorise `S`, `H`, `M`, `L`, `D`, `SM`, `SH`, `MH`, `LD`, `HMS` et, dans le seul cas de correction `Z99`, `C` ([publication nationale, §6.13.9](../SpecIHEPAM/Publication-IHE_FRANCE_PAM_National_Extension_v2.11.1.txt)).

Le corpus contient sept valeurs CPage non conformes : `MC`, `MHC` et `HMSC`. Elles correspondent à un suffixe `C` ajouté par CPage :

- pour `ADT^Z99`, elles sont interprétées comme `C` ;
- pour les mouvements, le suffixe parasite est retiré (`MHC` devient `MH`) ;
- un avertissement traçable conserve la valeur reçue et l'interprétation appliquée ;
- la même valeur émise par un autre système reste une erreur `ZBE9_INVALID`.

## Écarts CPage conservés comme avertissements

Trois messages (`1117925616.hl7`, `1117925626.hl7` et `1117925680.hl7`) ont `ZBE9=HMS` mais omettent `ZBE-8` (UF de soins).

Le profil attend cette information lorsqu'une responsabilité de soins est concernée. Pour l'interopérabilité CPage demandée, le validateur l'affiche désormais en avertissement `ZBE8_MISSING`, sans rejet technique. Pour tout autre émetteur, l'absence reste une erreur.

## Régression automatisée

`tests/unit/test_ihe_pam_fr_211_conformance.py` balaye désormais le corpus CPage : aucune erreur ne doit réapparaître, et les écarts ZBE-8/ZBE-9 restent explicitement comptés comme avertissements.
