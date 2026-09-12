# Vérification de compatibilité FHIR France / FR Core 2.2.0

Date : 12 septembre 2026
Périmètre : export, import et émission de la structure hospitalière

## Verdict

**Compatible sur le périmètre FHIR Structure effectivement utilisé par
MedData Bridge**, avec le guide français publié **FR Core 2.2.0**, fondé sur
FHIR R4 (4.0.1).

Cette conclusion porte sur la conversion des entités de structure, leur
import, leur émission vers les endpoints FHIR et le roundtrip entre deux bases
indépendantes. Elle ne vaut pas certification officielle de l'ensemble du guide
FR Core : celui-ci couvre davantage de profils et de cas d'usage que ceux mis
en oeuvre dans l'application.

## Références vérifiées

- Guide publié : <https://hl7.fr/ig/fhir/core/> ;
- profils et cartographie des entités :
  <https://hl7.fr/ig/fhir/core/structure_entites.html> ;
- relations structurelles `partOf` et extension multi-rattachement :
  <https://hl7.fr/ig/fhir/core/structure_relations.html> ;
- contraintes et types d'organisation :
  <https://hl7.fr/ig/fhir/core/structure_contraintes.html> ;
- profil établissement :
  <https://hl7.fr/ig/fhir/core/StructureDefinition-fr-core-organization-etablissement.html>.

## Mapping appliqué

| Donnée métier | Ressource et profil émis | Type FR Core |
|---|---|---|
| Entité juridique | `Organization` / `fr-core-organization-etablissement` | `LEGAL-ENTITY` |
| Entité géographique | `Organization` / `fr-core-organization-etablissement` | `GEOGRAPHICAL-ENTITY` |
| Pôle | `Organization` / `fr-core-organization` | `POLE` |
| Service | `Organization` / `fr-core-organization` | `SERVICE` |
| UF | `Organization` / `fr-core-organization-uf` | `UF` |
| UAC | `Organization` / `fr-core-organization-uac` | `UAC` |
| UH, chambre, lit | `Location` / `fr-core-location` | `UH`, `CHAMB`, `LIT` |

Les canonicals placés dans `meta.profile` sont explicitement versionnés
`|2.2.0`. L'import accepte aussi les canonicals non versionnés afin de rester
interopérable avec les producteurs qui omettent la version.

Les établissements utilisent maintenant le système
`https://hl7.fr/ig/fhir/core/CodeSystem/fr-core-cs-v2-3307`. Les anciens codes
internes `EJ` et `EG` restent admis uniquement à l'import pour assurer la
compatibilité ascendante ; ils ne sont plus générés.

## Contrôles exécutés

La campagne locale suivante est verte :

```text
14 passed
tests/unit/test_fhir_frcore_2_2_0_conformance.py
tests/integration/test_fhir_structure_roundtrip.py
tests/integration/test_fhir_interop.py
```

Elle vérifie notamment :

- le profil, le type et les identifiants des EJ/EG ;
- la hiérarchie `Organization.partOf` et `Location.partOf` ;
- les extensions FR Core applicables aux UAC, chambres et lits ;
- l'import de profils versionnés ;
- la réintégration sans doublon dans une seconde BDD ;
- renommage, désactivation, déplacement de service et parent inconnu avec
  diagnostic explicite.

## Limites connues et règle d'usage

Le routeur historique `/fhir/Location` sert encore à une recherche IHM
héritée. Il ne constitue pas l'interface d'échange FR Core à utiliser avec un
partenaire : l'échange de structure conforme est
`/api/fhir/export/structure/{ej_id}` et son émission temps réel associée,
qui reposent sur `StructureToFHIRConverter`.

Une qualification externe complète demanderait, en complément, de soumettre
des bundles réels à un validateur FHIR R4 enrichi du package FR Core 2.2.0 et
de tester les profils non mis en oeuvre (notamment les scénarios
multi-rattachement via `fr-core-organization-member`, les responsabilités
`PractitionerRole` et les autres domaines cliniques).
