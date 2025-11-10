# Vocabulaire des relations de contacts (HL7 NK1 / FHIR)

Ce document répertorie les codes de relation utilisés pour les segments HL7 v2 NK1 (Table 0063) et leur correspondance conceptuelle avec FHIR (Patient.contact.relationship, RelatedPerson.relationship).

## Référence HL7 v2 – Table 0063 (extraits pertinents IHE PAM FR)

La spécification IHE PAM FR s'appuie sur HL7 v2.5; la table 0063 fournit les codes de relation. Le profil PAM FR autorise généralement les codes familiaux usuels et contacts d'urgence. Ci‑dessous une sélection prioritaire :

| Code HL7 (0063) | Libellé (FR)        | Usage interne | Rôle (NK1-7) suggéré | Mapping FHIR contact.relationship |
|-----------------|--------------------|---------------|----------------------|-----------------------------------|
| SPO             | Conjoint(e)        | PatientContact / VenueContact | EMERGENCY si prioritaire | `partner` / `spouse` |
| PAR             | Parent             | PatientContact / VenueContact | NEXT_OF_KIN | `parent` |
| MTH             | Mère               | PatientContact | NEXT_OF_KIN | `mother` |
| FTH             | Père               | PatientContact | NEXT_OF_KIN | `father` |
| DAU             | Fille              | PatientContact | NEXT_OF_KIN | `child` (female) |
| SON             | Fils               | PatientContact | NEXT_OF_KIN | `child` (male) |
| BRO             | Frère              | PatientContact | NEXT_OF_KIN | `sibling` |
| SIS             | Soeur              | PatientContact | NEXT_OF_KIN | `sibling` |
| FAM             | Famille (autre)    | PatientContact / VenueContact | NEXT_OF_KIN | `family` |
| EMR             | Contact urgence    | PatientContact / VenueContact | EMERGENCY | `emergency` |
| GUAR            | Garant financier   | PatientContact | GUARANTOR | `guarantor` |
| CARE            | Aidant / soignant  | PatientContact | CAREGIVER | `caregiver` |
| FRD             | Ami                | VenueContact   | VISITOR    | `friend` |
| OTH             | Autre              | PatientContact / VenueContact | OTHER | `other` |

Notes :
- Certains codes (GUAR, CARE) peuvent ne pas figurer dans 0063 de base selon la version; ils sont traités comme extensions locales si absents.
- Le champ NK1-7 (Contact Role) est interne ici et peut refléter une catégorisation (EMERGENCY, NEXT_OF_KIN, ACCOMPANYING, VISITOR, GUARANTOR).

## Stratégie de mapping

1. Système source HL7: `HL7-0063` (relationship_system dans les modèles)
2. Système cible interne (local): `contact-role` (à créer si nécessaire) pour normaliser les rôles fonctionnels.
3. Système FHIR: utilisation directe des codes standard FHIR quand disponibles. FHIR autorise des CodeableConcept multiples; ici on met un code principal.

## Règles d'utilisation

- `is_emergency_contact=True` renforce le code EMR ou rôle EMERGENCY; lors de génération FHIR, ajouter `use=emergency` si supporté.
- `priority` ou `sequence` détermine l'ordre des NK1 segments et l'ordre des `Patient.contact` en FHIR.
- Si plusieurs contacts partagent EMERGENCY, garder le plus prioritaire (`priority=1`) en tête de liste.

## Champs HL7 / FHIR

| HL7 NK1 | Interne modèle          | FHIR Patient.contact / RelatedPerson |
|---------|-------------------------|--------------------------------------|
| NK1-1   | sequence                | (ordering only)                      |
| NK1-2   | family_name + given...  | name                                 |
| NK1-3   | relationship_code       | relationship.code                    |
| NK1-5/6 | phone_number / business | telecom (system=phone; use=home/work)|
| NK1-7   | contact_role            | relationship.category (extension)    |
| NK1-8/9 | start_date / end_date   | period.start / period.end            |
| NK1-15  | gender                  | RelatedPerson.gender                 |
| NK1-16  | birth_date              | RelatedPerson.birthDate              |
| NK1-20  | primary_language        | communication.language               |
| NK1-29  | contact_reason          | extension (reason)                   |

## Validation IHE PAM FR

Le profil IHE PAM FR n'impose pas une liste restreinte additionnelle pour Table 0063 mais recommande les codes standards HL7 v2.5. Les implémentations locales peuvent ajouter des codes OTH ou FRD pour faciliter l'usage; ces ajouts doivent être documentés (ce fichier) et marqués `is_user_defined=True` dans le système `contact-role`.

## Prochaines étapes

- Initialiser le système de vocabulaire `contact-role` (LOCAL) et insérer les valeurs (EMERGENCY, NEXT_OF_KIN, ACCOMPANYING, VISITOR, GUARANTOR, CAREGIVER, OTHER).
- Créer mappings bidirectionnels HL7 0063 <-> contact-role quand pertinent.
- Exposer un service de traduction via `map_code()` / `reverse_map_code()`.
- Tests de roundtrip: modèle -> HL7 NK1 -> parsing -> modèle -> FHIR Patient.contact.

---
Version: 2025-11-10
Auteur: Auto‑généré (Contacts NK1)
