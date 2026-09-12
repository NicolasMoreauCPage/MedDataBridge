# Test de roundtrip MLLP — IHE PAM France / CPage

Date : 11 septembre 2026  
Corpus : 199 captures CPage de `data/pam/` (fichiers numériques uniquement)

> Statut documentaire : **preuve de qualification PAM/CPage conservée**. Les
> volumes et empreintes correspondent à la campagne du 11 septembre 2026 ; ils
> ne représentent pas un compteur permanent. Pour le périmètre courant et les
> limites ouvertes, voir [README_FOR_REPORTS.md](README_FOR_REPORTS.md).

## Verdict

**Succès : les deux environnements GHT aboutissent à des données métier strictement identiques.**

| Étape | Résultat |
|---|---:|
| Messages CPage injectés dans GHT-1 par MLLP | 199 |
| ACK GHT-1 `AA` | 172 |
| ACK GHT-1 `AE` | 20 |
| ACK GHT-1 `AR` | 7 |
| Messages IHE PAM générés par l’application | 125 |
| Messages reçus par GHT-2 par MLLP | 125 |
| ACK GHT-2 `AA` | 125 |
| ACK GHT-2 `AE` / `AR` | 0 / 0 |
| Empreintes BDD GHT-1 = GHT-2 | **oui** |

Les ACK négatifs du premier chargement sont conservés et traçables. Ils correspondent aux messages du corpus qui ne peuvent pas être intégrés sans leur historique ou leur contexte métier, et ne sont donc pas exportés comme état métier.

## Environnements testés

Deux processus isolés ont été démarrés, chacun avec sa BDD SQLite et la même structure : GHT, entité juridique, entité géographique, pôle, service, UF `7700`, espaces d’identifiants IPP/NDA/VN/MVT et endpoint MLLP.

```text
captures CPage ──MLLP:29101──> GHT-1 / BDD-1
                                  │
                   génération IHE PAM France
                                  │
                         MLLP:29102
                                  ▼
                              GHT-2 / BDD-2
```

L’émission est réalisée par le générateur et l’émetteur MLLP applicatifs ; aucun message n’est simulé ni recopié directement en base.

## Comparaison BDD

La comparaison porte sur les données métier persistées, avec des empreintes SHA-256 afin de ne pas mettre de données de santé dans ce rapport.

| Entité | GHT-1 | GHT-2 | Empreintes égales |
|---|---:|---:|---|
| Patients | 97 | 97 | oui |
| Dossiers | 17 | 17 | oui |
| Venues | 17 | 17 | oui |
| Mouvements | 28 | 28 | oui |

Les empreintes incluent les identifiants métier et les attributs pertinents : identité patient, nom de naissance, coordonnées, dossier, UF, dates, localisation, statut, trigger, nature et identifiants de venue/mouvement.

## Correctifs validés par ce test

- PID-5 conserve désormais le nom usuel et le nom de naissance dans deux répétitions XPN typées `D` et `L`, y compris lorsqu’ils ont la même valeur.
- MSH-10 est unique à chaque émission, sans modifier les identifiants métier de venue et de mouvement.
- PV1-19, PV1-44 et PV1-52 sont construits aux positions HL7 correctes ; les dates de séjour sont ainsi préservées.
- La date clinique du séjour provient de PV1-44, puis de ZBE-2 ; la date de naissance n’est plus utilisée comme date d’admission lorsqu’un horodatage de mouvement existe.
- Les natures de mouvement françaises composées, notamment `MH`, sont conservées au roundtrip.
- La vérification de transition ne mélange plus l’historique de deux dossiers distincts d’un même patient lorsqu’un PID-18 ou PV1-19 explicite est fourni.
- Un rejet conserve toujours le journal et l’ACK, tout en annulant les écritures métier partielles.

## Reproductibilité

La campagne est exécutable avec :

```bash
python3 scripts/true_roundtrip_cpage.py run
```

Les BDD d’évidence du dernier essai sont temporaires et isolées. Le résultat final est également disponible sous forme d’agrégats non nominatifs dans `result.json` du répertoire d’artefacts choisi via `ROUNDTRIP_ARTIFACT_DIR`.

## Tests automatisés complémentaires

Les suites ciblées de cette campagne ont été exécutées avec succès : **80 tests
passés**. Elles couvrent notamment le transport MLLP, la transaction/ACK en
erreur, les transitions PAM, la génération et la conformité IHE PAM France.
Le nombre de tests actuel est suivi par la CI et par
[`docs/TESTS_STATUS.md`](../TESTS_STATUS.md), et non par ce compte rendu daté.
