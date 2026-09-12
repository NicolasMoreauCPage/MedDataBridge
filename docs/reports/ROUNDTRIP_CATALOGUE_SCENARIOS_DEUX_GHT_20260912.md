# Roundtrip du catalogue de scénarios — deux GHT

Date : 12 septembre 2026

## Résultat de référence — catalogue exécutable

La campagne de référence a rejoué le **catalogue administré** dans deux GHT
SQLite isolés. Elle inclut les corrections d'identifiants de mouvement : un
Z99 ou une annulation cible strictement le mouvement porté par son `ZBE-1` ;
les prérequis ajoutés au scénario créent ce même identifiant sans substitution
heuristique.

| Indicateur | Résultat |
|---|---:|
| Scénarios actifs rejoués | **137** |
| Scénarios entièrement acceptés | **137** |
| Scénarios partiels | **0** |
| Scénarios en erreur | **0** |
| ACK PAM `AA` | **432** |
| Projections métier BDD GHT A = GHT B | **oui** |

Les **137 scénarios approuvés** constituent le catalogue exécutable. Les
**74 scénarios réparables** restent conservés et éditables dans
l'administration, mais sont désactivés jusqu'à leur correction métier ; les
doublons et scénarios non qualifiés le restent également. Ainsi, une émission
de masse ne sélectionne jamais un scénario ayant produit un ACK négatif.

La campagne fidèle au catalogue courant se lance ainsi :

```bash
PYTHONPATH=. .venv/bin/python scripts/roundtrip_scenario_catalog_two_ght.py \
  --catalog-source database \
  --workdir artifacts/roundtrip-scenarios-two-ght-current
```

Le résultat machine-readable de cette campagne est
`/tmp/medbridge-scenarios-final-ETCa2m/result.json` (répertoire temporaire de
qualification).

## Résultat final

La campagne a rejoué les **219 scénarios actifs** dans deux environnements
SQLite isolés et identiquement structurés. Chaque message est émis depuis le
GHT A, puis intégré indépendamment dans A et B ; les empreintes métier sont
enfin comparées.

| Indicateur | Avant corrections | Après corrections | Évolution |
|---|---:|---:|---:|
| Scénarios entièrement acceptés | 35 | **71** | **+36** |
| Scénarios partiels | 77 | 132 | +55 |
| Scénarios en erreur | 107 | **16** | **-91** |
| Étapes acceptées | 213 | **356** | **+143** |
| Étapes rejetées | 617 | **469** | **-148** |
| ACK PAM `AA` | 194 | **281** | **+87** |
| ACK PAM `AR` | 243 | **106** | **-137** |
| BDD GHT A = BDD B | oui | **oui** | conservé |

Les `AE` PAM passent de 310 à 360 : les messages auparavant rejetés très tôt
pour un en-tête incomplet atteignent maintenant le validateur de séquence PAM,
qui exprime donc davantage d'erreurs métier réelles. Ce n'est pas une
régression de transport : les ACK `AA` augmentent et les ACK structurels `AR`
diminuent fortement.

Les deux BDD finales sont identiques : **156 patients, 295 identifiants, 38
dossiers, 38 venues, 63 mouvements et 200 actes HPRIM**.

## Corrections réalisées

- Les profils de destination appliquent une UF et un médecin par rôle à chaque
  livraison (`PV1-3`, `ZBE-7`, HPRIM et FHIR).
- Le parseur HPRIM accepte les exports historiques non namespacés et les
  identifiants patient/venue portés uniquement côté `recepteur`.
- Les messages HPRIM sans identité de personne dans `acteur` sont complétés
  avec le médecin résolu pour la destination, sans créer de prescripteur ou
  d'exécutant absent dans le template.
- Un jeton historique générique est rendu conforme lorsqu'il représente une
  lettre-clé NGAP (`AMK`, plutôt que le code CCAM `TEST001`).
- Les messages HL7 historiques dont `MSH-3` ou `MSH-4` est vide reçoivent une
  valeur locale de secours, sans écraser les valeurs renseignées.
- Les erreurs XML HPRIM sont maintenant remontées telles quelles ; elles ne
  sont plus masquées par une erreur interne d'attribut.

## Ce qui reste volontairement contrôlé

Les **139 scénarios alors qualifiés** `corriger_sequence_pam` contiennent
des transitions effectivement refusées par la machine d'état (par exemple
`A01 → A01`, `A03 → A03`, `A05 → A02`). Le contrôle est maintenu : le relâcher
rendrait le validateur non conforme à son objectif. Ces scénarios doivent être
classés explicitement entre parcours positifs et tests PAM négatifs, puis les
parcours positifs doivent être réordonnés ou complétés avec leurs prérequis.

### Correctif de périmètre HL7 SIU

`SIU^Sxx` est un flux **HL7 v2 Scheduling** de rendez-vous, et non un flux
IHE PAM. La qualification et le catalogue les séparent désormais : dans la
dernière exécution, les 109 scénarios résiduels précédemment regroupés sous
`corriger_sequence_pam` correspondent à **100 scénarios PAM** et **9 scénarios
HL7 SIU** (5 SIU purs et 4 scénarios mixtes ADT/SIU). Les flux SIU purs sont
rangés dans le thème `HL7 v2 / Rendez-vous (SIU)` ; les scénarios mixtes dans
`HL7 v2 / Mouvements et rendez-vous`. Ils ne sont plus comptabilisés comme des
écarts PAM.

Neuf scénarios HPRIM nécessitent également une qualification métier : cinq
portent au moins un UCD sans code de produit, deux un acte CCAM de quantité
nulle, et deux sont des messages PAM présents dans le répertoire historique
HPRIM. Ils ne doivent pas être supprimés : les anomalies de données restent
des tests négatifs utiles au validateur.

## Reproduction

```bash
TESTING=1 PYTHONPATH=. .venv/bin/python \
  scripts/roundtrip_scenario_catalog_two_ght.py \
  --workdir artifacts/roundtrip-scenarios-two-ght-v12-final-corrections
```

Les preuves détaillées sont dans
`artifacts/roundtrip-scenarios-two-ght-v12-final-corrections/result.json` et
`report.md`. La campagne ne considère les deux GHT conformes que lorsque leurs
projections métier sont strictement identiques.
